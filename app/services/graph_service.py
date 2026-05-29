"""Edge extraction service per knowledge-graph chunk-chunk (D1 piano v2).

L'edge-table `regulation_chunk_edges` (migrazione 005) materializza relazioni
normative dirette fra chunks per supportare:
  - 1-hop graph traversal in retrieval (`retrieval_v2.retrieve_for_module`
    quando `v2_kg_traversal_enabled=True` — F2.8): recuperi i chunk citati,
    modificati o gerarchicamente collegati ai top-30 reranked.
  - Audit di provenienza in UI (endpoint
    `GET /api/admin/regulations/{id}/edges-summary` — F2.7).
  - Future analisi statiche (es. "art. 36 c. 4 quale chunk lo cita?").

Tre tipi di estrazione (D1):
  1) DETERMINISTIC (regex su body, weight=1.0): cita/modifica/attua di
     "art./comma/allegato/D.Lgs/Reg CE" + struttura gerarchica.
  2) HIERARCHICAL (parsing del campo `hierarchy_path`, weight=1.0): parent
     e sibling automatici da Titolo→Capo→Sezione→Articolo→Comma.
  3) LLM-VERIFIED (gate VAA-b, weight=0.7): l'LLM propone `e_definito_da` ma
     l'edge viene accettato SOLO se i due chunk condividono (a) un riferimento
     normativo verificabile **oppure** (b) overlap lessicale Jaccard >= 0.15 su
     entita' normative estratte. Senza il gate il rumore di L1/L2 LLM scolla
     l'analisi semantica (storica patologia "medico-biologico" su Preposti).

Vincoli VAA:
  - (b) colonna `source` obbligatoria, mai dedurre da `weight` o da `kind`.
  - (c) edge LLM con gate NON solo loggato — l'`extraction_context` JSONB
    contiene `{"gate_method": "ref_overlap"|"jaccard", "gate_value": 0.21}`
    cosi' chi audita sa PERCHE' l'edge e' stato accettato.
  - (e) tutta la pipeline edge-extract gira solo se
    `v2_features.kg_traversal_enabled` e' on (F2.6: hook ingestion).
    Disabilitato di default → schema esiste vuoto, zero cost.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import asyncpg
import structlog

from app.config import settings
from app.services.ingestion_service import call_llm

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Dataclass per edge proposti (pre-persist)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProposedEdge:
    """Edge proposto dall'estrazione, pre-insert in DB."""

    src_chunk_id: str
    dst_chunk_id: str
    kind: str  # vedi CHECK constraint migrazione 005
    weight: float
    source: str  # 'deterministic' | 'llm_verified'
    extraction_context: dict[str, object]


# ---------------------------------------------------------------------------
# Helper regex per estrazione deterministica
# ---------------------------------------------------------------------------

# "art. 36" / "articolo 36" / "art. 36-bis" / "Articoli 36 e 37"
_ART_REF = re.compile(
    r"\b(?:art(?:icolo|t\.?)|articol[oi])\s*\.?\s*(\d+(?:[-\s]?(?:bis|ter|quater|quinquies))?)",
    re.IGNORECASE,
)
# "comma 4" / "co. 4" / "c. 4"
_COMMA_REF = re.compile(r"\b(?:comma|co\.?|c\.)\s*(\d+)\b", re.IGNORECASE)
# "allegato XX" / "allegato 4" / "all. III"
_ALLEGATO_REF = re.compile(
    r"\b(?:allegat[oi]|all\.?)\s+([IVX]+|\d+)\b", re.IGNORECASE
)
# "D.Lgs 81/08" / "D.Lgs. 81/2008" / "Decreto Legislativo 81/2008"
_DLGS_REF = re.compile(
    r"\b(?:d\.?\s*lgs\.?|decreto\s+legislativo)\s*\.?\s*(\d+)[/\\](\d{2,4})\b",
    re.IGNORECASE,
)
# "Reg. CE 852/2004" / "Regolamento UE 1272/2008"
_REG_REF = re.compile(
    r"\b(?:reg(?:olamento)?\.?\s+)(?:CE|UE)\s+n?\.?\s*(\d+)[/\\](\d{4})\b",
    re.IGNORECASE,
)

# Pattern intent: distingue "cita" (riferimento neutro) da "modifica" (riforma).
# Per ora pattern semplice; raffinabile post-F2.7 backfill se serve precision.
_MODIFICA_HINT = re.compile(
    r"\b(?:modifica\w*|sostitu(?:isce|ito|iti)|abrog\w*|integr(?:a|ato)"
    r"|aggiunge|aggiunto|sostituendo|nov[ae]ll(?:a|ato))\b",
    re.IGNORECASE,
)
_ATTUA_HINT = re.compile(
    r"\b(?:in\s+attuazione|attua\w*|recepimento|recepisce|in\s+conformit[àa])\b",
    re.IGNORECASE,
)


def _classify_intent(body: str, match_start: int, window: int = 80) -> str:
    """Classifica `cita` vs `modifica` vs `attua` guardando 80 char prima del match.

    Conservativo: di default 'cita'. Modifica/attua richiedono un trigger lessicale
    specifico nel contesto immediatamente precedente — sennò il rumore semantico
    del corpus 81/08 (frasi tipo "si modifica il proprio comportamento") produrrebbe
    falsi positivi in massa.
    """
    pre = body[max(0, match_start - window) : match_start]
    if _MODIFICA_HINT.search(pre):
        return "modifica"
    if _ATTUA_HINT.search(pre):
        return "attua"
    return "cita"


# ---------------------------------------------------------------------------
# 1) DETERMINISTIC: regex su body + struttura
# ---------------------------------------------------------------------------


class _ChunkResolver:
    """In-memory resolver (article, paragraph) -> chunk_id per UNA regulation.

    Carica una volta tutti i chunk della regulation e costruisce due mappe:
      - by_article_para: (lower_article, paragraph) -> chunk_id [primo match]
      - by_article: lower_article -> chunk_id [primo chunk dell'articolo]
    Pattern N+1 evitato: la versione DB-per-match si rompe quando il pool TCP
    proxy ricicla connessioni durante il backfill (osservato su 1819 chunk D.Lgs
    81/08). 1 fetch iniziale rende il path puro CPU, scalabile.
    """

    def __init__(self) -> None:
        self.by_article_para: dict[tuple[str, str], str] = {}
        self.by_article: dict[str, str] = {}

    @classmethod
    async def load(cls, pool: asyncpg.Pool, regulation_id: str) -> "_ChunkResolver":
        inst = cls()
        rows = await pool.fetch(
            "SELECT id::text AS id, article, paragraph FROM regulation_chunks "
            "WHERE regulation_id = $1::uuid AND is_current = true",
            regulation_id,
        )
        for r in rows:
            art = r["article"]
            if not art:
                continue
            key = art.strip().lower()
            # primo chunk dell'articolo
            inst.by_article.setdefault(key, r["id"])
            # se ha paragraph, indice esatto
            if r["paragraph"]:
                inst.by_article_para.setdefault((key, r["paragraph"]), r["id"])
        return inst

    def resolve(
        self,
        *,
        article: str | None,
        paragraph: str | None,
        allegato: str | None,
    ) -> str | None:
        if allegato:
            # Allegati: l'articolo del chunk e' tipicamente "Allegato XX" /
            # "allegato xx" — cerco entrambe le forme
            key = f"allegato {allegato.strip().lower()}"
            if key in self.by_article:
                return self.by_article[key]
            return None
        if article:
            key = f"art. {article.strip().lower()}"
            if paragraph and (key, paragraph) in self.by_article_para:
                return self.by_article_para[(key, paragraph)]
            return self.by_article.get(key)
        return None


async def extract_deterministic_edges(
    chunk_id: str,
    body: str,
    regulation_id: str,
    pool: asyncpg.Pool,
    *,
    resolver: "_ChunkResolver | None" = None,
) -> list[ProposedEdge]:
    """Estrai edge deterministici dal body di un chunk via regex.

    Pattern coperti:
      - art. N → cita (default) | modifica | attua (in base al contesto pre-match)
      - allegato N → cita
      - art. N comma M → cita ad articolo specifico (paragraph filter)
    Cross-regulation NON gestito qui (richiederebbe slug-map per D.Lgs/Reg CE
    citati): risolviamo solo intra-regulation. Se in F2.7 backfill emerge
    necessita' cross-reg, aggiungere _resolve_target_chunk_cross_reg.

    Output: lista di ProposedEdge con `source='deterministic'`, `weight=1.0`.
    """
    # Caricamento on-demand del resolver per call site singoli (test). Per
    # batch operations (ingest pipeline, backfill) il caller passa il resolver
    # pre-caricato cosi' la N+1 query e' evitata.
    if resolver is None:
        resolver = await _ChunkResolver.load(pool, regulation_id)

    edges: list[ProposedEdge] = []
    seen_pairs: set[tuple[str, str]] = set()  # dedup intra-chunk

    for art_match in _ART_REF.finditer(body):
        article_num = art_match.group(1).strip()
        intent = _classify_intent(body, art_match.start())

        # Cerca un comma adiacente al match (es. "art. 36, comma 4"):
        # finestra di 30 char dopo il match.
        post = body[art_match.end() : art_match.end() + 30]
        paragraph: str | None = None
        comma_m = _COMMA_REF.search(post)
        if comma_m:
            paragraph = comma_m.group(1)

        target = resolver.resolve(
            article=article_num,
            paragraph=paragraph,
            allegato=None,
        )
        if target is None or target == chunk_id:
            continue  # self-edge / unresolved skip
        pair = (target, intent)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        edges.append(
            ProposedEdge(
                src_chunk_id=chunk_id,
                dst_chunk_id=target,
                kind=intent,
                weight=1.0,
                source="deterministic",
                extraction_context={
                    "rule": "art_ref_regex",
                    "matched": art_match.group(0),
                    "paragraph": paragraph,
                },
            )
        )

    for all_match in _ALLEGATO_REF.finditer(body):
        allegato = all_match.group(1).strip()
        target = resolver.resolve(
            article=None,
            paragraph=None,
            allegato=allegato,
        )
        if target is None or target == chunk_id:
            continue
        pair = (target, "cita")
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        edges.append(
            ProposedEdge(
                src_chunk_id=chunk_id,
                dst_chunk_id=target,
                kind="cita",
                weight=1.0,
                source="deterministic",
                extraction_context={
                    "rule": "allegato_ref_regex",
                    "matched": all_match.group(0),
                },
            )
        )

    return edges


# ---------------------------------------------------------------------------
# 2) HIERARCHICAL: parent + sibling da `hierarchy_path` (regulation-wide)
# ---------------------------------------------------------------------------


async def extract_hierarchical_edges(
    regulation_id: str,
    pool: asyncpg.Pool,
) -> list[ProposedEdge]:
    """Estrai edge gerarchici parent + sibling per TUTTI i chunk di una regulation.

    Pattern strutturale:
      - `gerarchico_parent`: chunk → chunk il cui `hierarchy_path` e' un prefisso
        del proprio (es. "Titolo I > Capo II > Art. 36 > comma 4" ha come parent
        "Titolo I > Capo II > Art. 36").
      - `gerarchico_sibling`: chunk ↔ chunk con lo stesso parent gerarchico
        immediato. Bidirezionale (inseriamo entrambe le direzioni).

    Pensata per essere chiamata UNA volta per regulation post-ingestion
    (F2.6) o in backfill (F2.7). Costo: O(N^2) sul numero di chunk dentro la
    stessa sezione, accettabile perche' le sezioni sono piccole (~20-50 chunk).
    """
    rows = await pool.fetch(
        "SELECT id::text AS chunk_id, hierarchy_path "
        "FROM regulation_chunks "
        "WHERE regulation_id = $1 AND is_current = true "
        "ORDER BY hierarchy_path",
        regulation_id,
    )
    if not rows:
        return []

    # Map path -> [chunk_id, ...] per identificare sibling.
    by_path: dict[str, list[str]] = {}
    for r in rows:
        by_path.setdefault(r["hierarchy_path"], []).append(r["chunk_id"])

    edges: list[ProposedEdge] = []

    # Parent: per ogni chunk, trova il path piu' lungo che sia prefisso stretto del suo.
    # Es path "A > B > C > D" -> cerca "A > B > C" (poi "A > B", "A") e prendi il primo
    # che esiste come path di un altro chunk.
    all_paths = sorted(by_path.keys())
    path_set = set(all_paths)
    for path, chunk_ids in by_path.items():
        # Genera ancestor paths: tronca dall'ultimo ">" iterativamente.
        candidates: list[str] = []
        parts = path.split(" > ")
        for i in range(len(parts) - 1, 0, -1):
            ancestor = " > ".join(parts[:i])
            if ancestor in path_set:
                candidates.append(ancestor)
                break  # primo (= parent immediato), stop
        if not candidates:
            continue
        parent_path = candidates[0]
        parent_ids = by_path[parent_path]
        for cid in chunk_ids:
            for pid in parent_ids:
                if pid == cid:
                    continue
                edges.append(
                    ProposedEdge(
                        src_chunk_id=cid,
                        dst_chunk_id=pid,
                        kind="gerarchico_parent",
                        weight=1.0,
                        source="deterministic",
                        extraction_context={
                            "rule": "hierarchy_path_prefix",
                            "child_path": path,
                            "parent_path": parent_path,
                        },
                    )
                )

    # Sibling: chunk con lo stesso path sono sibling (atomico). Insertiamo
    # solo coppie (a < b) per dedup, poi il caller puo' decidere se materializzare
    # bidirezionalmente (per ora unidir: il 1-hop traversal seguira' anche src->dst
    # quindi una direzione e' sufficiente per la traversal logica).
    for path, chunk_ids in by_path.items():
        if len(chunk_ids) < 2:
            continue
        sorted_ids = sorted(chunk_ids)
        for i, a in enumerate(sorted_ids):
            for b in sorted_ids[i + 1 :]:
                edges.append(
                    ProposedEdge(
                        src_chunk_id=a,
                        dst_chunk_id=b,
                        kind="gerarchico_sibling",
                        weight=1.0,
                        source="deterministic",
                        extraction_context={
                            "rule": "hierarchy_path_match",
                            "shared_path": path,
                        },
                    )
                )

    return edges


# ---------------------------------------------------------------------------
# 3) LLM-VERIFIED: e_definito_da, con gate VAA
# ---------------------------------------------------------------------------


_LLM_EDGE_SYSTEM = (
    "Sei un analista di normative italiane sulla sicurezza sul lavoro. "
    "Dato un chunk di testo normativo, identifichi fino a 3 ALTRI chunk "
    "candidati (forniti nel prompt) che potrebbero `definire` un concetto "
    "centrale del chunk principale. NON inventare riferimenti: scegli SOLO "
    "fra i candidati elencati. Rispondi SOLO con JSON valido."
)


async def _extract_normative_entities(text: str) -> set[str]:
    """Estrai entita' normative (art., D.Lgs, Reg, allegato) per il gate Jaccard.

    Pattern semplici: ritorna un set di stringhe normalizzate lowercase,
    es. {"art. 36", "art. 36 c. 4", "d.lgs 81/08", "allegato xx"}.
    """
    out: set[str] = set()
    for m in _ART_REF.finditer(text):
        art = m.group(1).strip()
        # comma adiacente?
        post = text[m.end() : m.end() + 30]
        cm = _COMMA_REF.search(post)
        if cm:
            out.add(f"art. {art.lower()} c. {cm.group(1)}")
        out.add(f"art. {art.lower()}")
    for m in _ALLEGATO_REF.finditer(text):
        out.add(f"allegato {m.group(1).lower()}")
    for m in _DLGS_REF.finditer(text):
        out.add(f"d.lgs {m.group(1)}/{m.group(2)}")
    for m in _REG_REF.finditer(text):
        out.add(f"reg {m.group(1)}/{m.group(2)}")
    return out


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


async def extract_llm_edges(
    chunk_id: str,
    body: str,
    regulation_id: str,
    pool: asyncpg.Pool,
    *,
    candidates_top_k: int = 10,
    jaccard_threshold: float = 0.15,
) -> list[ProposedEdge]:
    """Proposta LLM di edge `e_definito_da` + gate VAA programmatico.

    Flow:
      1. Carica candidati: top_k chunk dello STESSO regulation diversi dal chunk
         corrente (ordine alfabetico per stabilita').
      2. 1 LLM call: scegli fino a 3 candidate_id che `definiscono` il chunk
         corrente.
      3. Per ogni proposta, verifica gate:
           (a) overlap di entita' normative fra src e dst (Jaccard >= 0.15) OPPURE
           (b) almeno 1 riferimento normativo condiviso (D.Lgs/Reg).
         Se PASS → ProposedEdge con `source='llm_verified'`, `weight=0.7`.
         Se FAIL → log + skip (l'edge NON entra nel grafo).

    Nota: `candidates_top_k=10` e' deliberatamente basso: l'LLM deve scegliere
    fra pochi candidati ben selezionati, non navigare un corpus. Per la
    selezione iniziale: ordinare per overlap regex con il body (TODO F2.6
    raffinamento, per ora primi 10 alfabetici).
    """
    rows = await pool.fetch(
        "SELECT id::text AS chunk_id, body, hierarchy_path FROM regulation_chunks "
        "WHERE regulation_id = $1 AND id != $2 AND is_current = true "
        "ORDER BY hierarchy_path LIMIT $3",
        regulation_id,
        chunk_id,
        candidates_top_k,
    )
    if not rows:
        return []

    candidates = [
        {
            "id": r["chunk_id"],
            "path": r["hierarchy_path"],
            "body_preview": (r["body"] or "")[:400],
        }
        for r in rows
    ]

    user_prompt = (
        "CHUNK PRINCIPALE:\n"
        f"{body[:1200]}\n\n"
        "CANDIDATI (scegli da qui SOLO):\n"
        + "\n".join(
            f"[{i + 1}] id={c['id']} path={c['path']}\n    {c['body_preview']}"
            for i, c in enumerate(candidates)
        )
        + "\n\nRispondi con JSON: "
        '{"edges": [{"candidate_index": <1-based int>, "reason": "<breve>"}], '
        '"_meta": "max 3 elementi"}\n'
        "Se nessun candidato e' veramente definitorio, restituisci edges: []."
    )

    try:
        raw = await call_llm(
            messages=[{"role": "user", "content": user_prompt}],
            system=_LLM_EDGE_SYSTEM,
            task="classify",
        )
    except Exception as exc:
        logger.warning(
            "llm_edge_call_failed",
            chunk_id=chunk_id,
            error_class=type(exc).__name__,
            error_msg=str(exc)[:200],
        )
        return []

    try:
        data = json.loads(raw or "{}")
        proposals = data.get("edges", []) if isinstance(data, dict) else []
    except json.JSONDecodeError:
        logger.warning("llm_edge_invalid_json", chunk_id=chunk_id, raw_preview=(raw or "")[:120])
        return []

    src_entities = await _extract_normative_entities(body)

    accepted: list[ProposedEdge] = []
    for prop in proposals[:3]:
        if not isinstance(prop, dict):
            continue
        idx_raw = prop.get("candidate_index")
        if not isinstance(idx_raw, int) or idx_raw < 1 or idx_raw > len(candidates):
            continue
        cand = candidates[idx_raw - 1]
        # Carica il body completo del candidato per il gate Jaccard (preview
        # potrebbe non bastare per overlap normativo).
        full_row = await pool.fetchrow(
            "SELECT body FROM regulation_chunks WHERE id = $1::uuid", cand["id"]
        )
        if full_row is None:
            continue
        dst_body = full_row["body"] or ""
        dst_entities = await _extract_normative_entities(dst_body)

        # Gate: ref overlap O Jaccard >= threshold
        shared_refs = src_entities & dst_entities
        jaccard = _jaccard(src_entities, dst_entities)
        gate_method: str
        gate_value: float
        if shared_refs:
            gate_method = "ref_overlap"
            gate_value = float(len(shared_refs))
        elif jaccard >= jaccard_threshold:
            gate_method = "jaccard"
            gate_value = round(jaccard, 4)
        else:
            logger.info(
                "llm_edge_rejected_by_gate",
                src=chunk_id,
                dst=cand["id"],
                jaccard=round(jaccard, 4),
                shared_refs=list(shared_refs),
                threshold=jaccard_threshold,
            )
            continue

        accepted.append(
            ProposedEdge(
                src_chunk_id=chunk_id,
                dst_chunk_id=cand["id"],
                kind="e_definito_da",
                weight=0.7,
                source="llm_verified",
                extraction_context={
                    "rule": "llm_proposal_gated",
                    "gate_method": gate_method,
                    "gate_value": gate_value,
                    "shared_refs": list(shared_refs),
                    "llm_reason": prop.get("reason", "")[:200],
                },
            )
        )

    return accepted


# ---------------------------------------------------------------------------
# 4) Persist
# ---------------------------------------------------------------------------


async def persist_edges(edges: list[ProposedEdge], pool: asyncpg.Pool) -> int:
    """INSERT batch idempotente (UNIQUE (src,dst,kind) → ON CONFLICT DO NOTHING).

    Implementazione: `executemany` su una singola connection del pool. Era
    `execute()` per ogni edge in versione precedente: su 1819 chunk del D.Lgs
    81/08 il proxy TCP Railway ha chiuso la connection a meta' (~12k execute
    consecutivi). `executemany` raggruppa in una sola sequenza protocol-level
    e mantiene la connection attiva.

    Ritorna una STIMA del numero di edge inseriti: `executemany` non
    restituisce il count per riga, quindi calcoliamo "edge totali proposti
    meno quelli che gia' esistevano nel DB". E' sufficiente per logging/audit;
    il count esatto per audit fine puo' essere ottenuto con un GROUP BY post-batch.
    """
    if not edges:
        return 0
    sql = """
        INSERT INTO regulation_chunk_edges
            (src_chunk_id, dst_chunk_id, kind, weight, source, extraction_context)
        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb)
        ON CONFLICT (src_chunk_id, dst_chunk_id, kind) DO NOTHING
    """
    args = [
        (
            e.src_chunk_id,
            e.dst_chunk_id,
            e.kind,
            e.weight,
            e.source,
            json.dumps(e.extraction_context),
        )
        for e in edges
    ]
    # Pre-count via UNNEST a 3 colonne (sintassi PG compatibile con asyncpg).
    src_ids = [e.src_chunk_id for e in edges]
    dst_ids = [e.dst_chunk_id for e in edges]
    kinds = [e.kind for e in edges]
    existing = await pool.fetchval(
        "SELECT count(*) FROM regulation_chunk_edges e "
        "WHERE EXISTS ( "
        "  SELECT 1 FROM UNNEST($1::uuid[], $2::uuid[], $3::text[]) AS t(s, d, k) "
        "  WHERE t.s = e.src_chunk_id AND t.d = e.dst_chunk_id AND t.k = e.kind "
        ")",
        src_ids,
        dst_ids,
        kinds,
    )
    async with pool.acquire() as conn:
        await conn.executemany(sql, args)
    return len(edges) - int(existing or 0)


# ---------------------------------------------------------------------------
# 5) Orchestratore per ingestion (chiamato in F2.6 da ingestion_service)
# ---------------------------------------------------------------------------


async def extract_and_index_edges(
    regulation_id: str,
    pool: asyncpg.Pool,
    *,
    enable_llm: bool | None = None,
) -> dict[str, int]:
    """Estrai TUTTI gli edge per una regulation appena ingestita e persisti.

    Ordine:
      1. hierarchical (regulation-wide, una sola query)
      2. deterministic (per ogni chunk, regex su body)
      3. llm-verified (opzionale: solo se enable_llm=True ed e' configurato il
         provider — costoso, non ne abbiamo bisogno al primo backfill).

    Ritorna dict di counts per source per logging/audit:
      {"hierarchical": 1240, "deterministic": 387, "llm_verified": 14}
    """
    if enable_llm is None:
        enable_llm = bool(settings.v2_features.get("kg_traversal_enabled"))

    counts: dict[str, int] = {
        "hierarchical": 0,
        "deterministic": 0,
        "llm_verified": 0,
    }

    # 1) Hierarchical (parent + sibling)
    h_edges = await extract_hierarchical_edges(regulation_id, pool)
    counts["hierarchical"] = await persist_edges(h_edges, pool)
    logger.info(
        "edges_hierarchical_done",
        regulation_id=regulation_id,
        proposed=len(h_edges),
        inserted=counts["hierarchical"],
    )

    # 2) Deterministic per chunk
    chunk_rows = await pool.fetch(
        "SELECT id::text AS chunk_id, body FROM regulation_chunks "
        "WHERE regulation_id = $1::uuid AND is_current = true",
        regulation_id,
    )
    # Carica il resolver UNA volta per la regulation (evita N+1 query DB ad
    # ogni match regex — la versione N+1 droppava la connessione TCP proxy
    # Railway sul D.Lgs 81/08 da 1819 chunk).
    resolver = await _ChunkResolver.load(pool, regulation_id)
    # Accumula tutti gli edge prima del persist: una sola executemany invece
    # di N execute() per chunk.
    all_det_edges: list[ProposedEdge] = []
    for r in chunk_rows:
        d_edges = await extract_deterministic_edges(
            chunk_id=r["chunk_id"],
            body=r["body"] or "",
            regulation_id=regulation_id,
            pool=pool,
            resolver=resolver,
        )
        all_det_edges.extend(d_edges)
    det_total = await persist_edges(all_det_edges, pool)
    counts["deterministic"] = det_total
    logger.info(
        "edges_deterministic_done",
        regulation_id=regulation_id,
        chunks_scanned=len(chunk_rows),
        inserted=det_total,
    )

    # 3) LLM-verified (opzionale)
    if enable_llm:
        llm_total = 0
        for r in chunk_rows:
            l_edges = await extract_llm_edges(
                chunk_id=r["chunk_id"],
                body=r["body"] or "",
                regulation_id=regulation_id,
                pool=pool,
            )
            llm_total += await persist_edges(l_edges, pool)
        counts["llm_verified"] = llm_total
        logger.info(
            "edges_llm_verified_done",
            regulation_id=regulation_id,
            chunks_scanned=len(chunk_rows),
            inserted=llm_total,
        )

    return counts
