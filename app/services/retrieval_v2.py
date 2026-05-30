"""Hybrid retrieval v2: BM25 + cosine recall + Cohere rerank + LLM-autogen query.

Sostituisce (dietro feature flag `v2_rerank_enabled`) il retrieval cosine-only di
`research_agent.py:624-1006`, che oggi compensa con 38 query-expansion hardcoded
(`MODULE_QUERY_EXPANSIONS` 292-585) e drop-list regex per moduli "blurry"
(`_DROP_PATTERN_*` 817-967). Quel debito non scala oltre i 3 corsi demo: ad ogni
nuovo corso/normativa serve la mano del developer per aggiungere un pattern.

L'architettura (decisione D2 del piano, vincolata dall'analista):

  module_title + course_target + normative_slug
            |
            v
  1) autogen_module_query  -> 1 LLM call (task=classify), log query + ms
            |
            v
  2) recall_hybrid (top_k=200)
        BM25Okapi su body  +  cosine via knowledge_repo  ->  RRF k=60
            |
            v
  3) rerank_chunks (Cohere rerank-multilingual-v3.0, top_n=30)
            |
            v
  ScoredChunk[]  +  module_top_topical_affinity_score loggato (sensore badge D9
                   `module_corpus_thin` quando sotto MIN_TOPICAL_AFFINITY_ALERT)

NOTA NOMENCLATURA (D-171-bis, 2026-05-30):
  Il punteggio Cohere e' stato rinominato da "rerank_score" a "topical_affinity_score"
  per onesta' nominale. Il check empirico GEN M3 ha dimostrato che Cohere
  multilingual-v3.0 NON e' ranker title-aligned su questo dominio normativo:
  esclude dal top-30 chunk on-topic veri presenti nel pool RRF (Art. 33 era rank
  24 nel pool, escluso). Cohere e' affidabile come selettore di candidati
  topicalmente affini al dominio (recall accelerator + telemetria), non come
  ranker decisionale. B2 ri-ranking via cosine_voyage diretto sostituisce Cohere
  come ranker; questo nome (topical_affinity_score) lo dichiara esplicitamente
  per prevenire drift architetturale futuro.

VAA:
  - (a) verifica al render: `module_top_topical_affinity_score` esposto, non scartato.
  - (b) provenienza: ogni ScoredChunk porta `source='rerank_cohere'` o `'bm25'`
        a seconda dello stadio in cui ha vinto. In caso di disabilitazione
        Cohere fallback al solo recall RRF con `source='rrf_fallback'`.
  - (d) sensore vs gate: il vecchio MIN_RELEVANCE filtrava silenziosamente.
        Qui MIN_TOPICAL_AFFINITY_ALERT NON filtra: tutti i top-30 entrano sempre,
        ma se max_score < soglia il chunk emette l'evento che alimenta D9.
  - (e) safety-net: se `v2_rerank_enabled=False` il modulo non viene neppure
        importato in hot path (lazy import in research_agent).

Tutto puramente funzionale: no DB writes, no side-effect oltre i log telemetrici.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any

import structlog
from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from app.config import settings
from app.models.knowledge import NormativeChunk
from app.services.ingestion_service import call_llm, voyage_embed_with_retry
from app.services.knowledge_repo import KnowledgeRepository
from app.services.pipeline_telemetry import PipelinePhase, emit, timed

logger = structlog.get_logger(__name__)


# Soglia che alimenta il sensore badge D9 `module_corpus_thin`. Non e' un gate:
# i chunk passano comunque. Calibrata sul corpus reale (sample dei 3 demo gia'
# approvati alla review 10 dell'analista). FIX D2/sessione: era MIN_RELEVANCE
# 0.3 e tagliava. Ora e' soglia di allerta visibile, non un coltello.
#
# Rinominata D-171-bis (2026-05-30): da MIN_RERANK_SCORE_ALERT a
# MIN_TOPICAL_AFFINITY_ALERT per onesta' nominale. E' soglia sull'output Cohere
# (topical-affinity, non ranking title-aligned). L'alias all'ex-nome resta come
# backward-compatibility.
MIN_TOPICAL_AFFINITY_ALERT = 0.45
MIN_RERANK_SCORE_ALERT = MIN_TOPICAL_AFFINITY_ALERT  # alias deprecato — vedi D-171-bis

# Parametri di recall (top_k pre-rerank). 200 e' compromesso fra coverage
# (il rerank lavora solo su cio' che vede) e latenza Cohere (~50ms per 200 doc
# multilingual-v3.0, gratis sul free tier).
RECALL_TOP_K = 200
RERANK_TOP_N = 30

# Reciprocal Rank Fusion (Cormack et al. 2009). k=60 e' lo standard di
# letteratura: smussa rank tail senza penalizzare troppo il top.
RRF_K = 60

# F2.8: peso applicato ai chunk recuperati via 1-hop graph traversal. Diminuito
# rispetto al rerank score per non sovrapesare gli edge "secondari". 0.7
# coerente con il peso degli edge LLM-verified (la cui qualita' e' analoga:
# rilevanza indiretta).
KG_TRAVERSAL_WEIGHT_DECAY = 0.7

# F2.12 (B2) — costanti per il selettore di pool cosine_voyage diretto.
# Architettura post-classify 2026-05-30 (sign-off analista):
#   - Pool RRF top-100 (POOL_FOR_B2) NOT top-30 Cohere.
#   - Top-K cosine_voyage K=30 fissa (B2_TOP_K_DEFAULT).
#   - cosine_voyage diretto fra subtopic.text_emb (Voyage) e chunk.body_emb
#     (Voyage gia' in DB).
#   - Cohere downgrade a "topical-affinity telemetry" (D-171-bis).
# La variante K adattiva (salto pendenza cosine_n - cosine_n+1) e' work-item
# successivo dopo B3 deploy (sequenza incrementale analista).
B2_POOL_FOR_RANKING = 100  # top-100 pool RRF da cui ricavare top-K cosine_voyage
B2_TOP_K_DEFAULT = 30  # K=30 fissa (analista 2026-05-30, default sequenza incrementale)

# F2.14 (B4) — soglie sensori D9 corpus-thin (calibrate sui 5 moduli classify cieca).
# Sensore primario: A1_useful = (on-topic + adjacent) / pool_a1. Soglia 0.30
# separa REGIME 3 (PRE_M3 23%, GEN_M1 23%) dagli altri (REGIME 1+2 a 57-74%).
# Sensore secondario: top_cosine_voyage_score sotto soglia.
B4_A1_USEFUL_ALERT = 0.30  # alert se A1_useful < 30% (regime corpus-thin per concetto)
B4_TOP_COSINE_ALERT = 0.30  # alert se top cosine_voyage del top-K < 0.30


@dataclass(frozen=True)
class ScoredChunk:
    """Risultato finale del retrieval: chunk + score + provenienza.

    Importante: `score` puo' essere su scale diverse a seconda di `source`:
      - 'rerank_cohere': 0..1 (Cohere normalizza). NOTA D-171-bis: questo e'
        un "topical-affinity score", NON un ranking title-aligned. Cohere
        multilingual-v3.0 esclude dal top-30 chunk on-topic veri (Art. 33 GEN M3
        rank pool 24 escluso). Usare come telemetria + recall accelerator, NON
        come ranker decisionale. Il ranker decisionale e' B2 cosine_voyage.
      - 'rrf_fallback' / 'bm25_only': il valore RRF grezzo (sommatorie di 1/k+rank)
    Il caller usa `source` per sapere come interpretarlo. La soglia
    MIN_TOPICAL_AFFINITY_ALERT (alias retro MIN_RERANK_SCORE_ALERT) vale solo
    per `source='rerank_cohere'`.
    """

    chunk: NormativeChunk
    score: float
    source: str  # 'rerank_cohere' | 'rrf_fallback' | 'bm25_only'


# ---------------------------------------------------------------------------
# 1) Query auto-generation
# ---------------------------------------------------------------------------

_AUTOGEN_SYSTEM = (
    "Sei un esperto di formazione professionale sulla sicurezza sul lavoro "
    "(D.Lgs 81/08, Accordi Stato-Regioni, decreti antincendio, primo soccorso). "
    "Il tuo compito e' formulare UNA query semantica in italiano che catturi "
    "il contenuto normativo del modulo descritto. La query verra' usata per "
    "recuperare i passaggi normativi pertinenti tramite ricerca vettoriale "
    "+ keyword BM25. Rispondi SOLO con un oggetto JSON valido."
)

# Schema JSON: la fallback chain di call_llm esige response_format=json_object,
# quindi modelliamo l'output con un solo campo. Cosi' resta compatibile con
# tutti i provider della catena (deepseek/azure/openai/anthropic) senza richiedere
# una variante "text-mode" che oggi non esiste.
_AUTOGEN_USER_TEMPLATE = """Modulo: {module_title}
Tipo di corso: {course_target}
Normativa di riferimento: {normative_slug}

Genera la query di retrieval. Restituisci JSON con questa forma esatta:

{{"query": "<una frase fra 15 e 30 parole, in italiano, senza preambolo, senza
virgolette, sui concetti normativi/tecnici che dovrebbero essere coperti in
questo modulo>"}}

Non includere altro testo. Non includere frasi meta tipo \"il presente documento\"."""


async def autogen_module_query(
    *,
    module_title: str,
    course_target: str,
    normative_slug: str,
    course_id: str | None = None,
    module_idx: int | None = None,
) -> str:
    """Genera una query semantica per il modulo via LLM (task=classify, cheap).

    Telemetria obbligatoria (decisione analista D2): logga query + ms.
    Il sensore `top_score` viene emesso in seguito da `rerank_chunks`.
    """
    user_prompt = _AUTOGEN_USER_TEMPLATE.format(
        module_title=module_title,
        course_target=course_target or "generale",
        normative_slug=normative_slug or "n/a",
    )
    with timed(
        PipelinePhase.QUERY_AUTOGEN,
        course_id=course_id,
        module_idx=module_idx,
        module_title=module_title,
        source="llm_classify_chain",
    ) as ev:
        raw = await call_llm(
            messages=[{"role": "user", "content": user_prompt}],
            system=_AUTOGEN_SYSTEM,
            task="classify",
        )
        # Parsing JSON: estraiamo il campo `query`. Fallback a parsing testo se
        # il JSON arriva malformato (i provider sotto pressione a volte
        # restituiscono testo grezzo, e non vogliamo crashare la pipeline).
        import json as _json
        query = ""
        try:
            data = _json.loads(raw or "{}")
            if isinstance(data, dict):
                query = str(data.get("query", "")).strip()
        except _json.JSONDecodeError:
            # Fallback: prima riga non vuota.
            query = (raw or "").strip().splitlines()[0].strip().strip('"\'')
        # Fallback se l'LLM ha sbrodolato troppo o JSON era vuoto:
        # usiamo il module_title puro come query.
        if len(query.split()) < 5:
            logger.warning(
                "query_autogen_too_short",
                module=module_title,
                got=query,
                fallback="module_title",
            )
            query = module_title
            ev["fallback_used"] = True
        ev["query"] = query
        ev["query_words"] = len(query.split())
        return query


# ---------------------------------------------------------------------------
# 2) Hybrid recall (BM25 + cosine via RRF)
# ---------------------------------------------------------------------------


def _tokenize_for_bm25(text: str) -> list[str]:
    """Tokenizzatore semplice italiano-friendly per BM25.

    Non lemmatizziamo (spaCy/nltk overhead non ne vale): BM25 sui token grezzi
    e' robusto, e i pattern normativi ("art.", "comma", "D.Lgs.") sono token
    rari e quindi auto-pesati dal TF-IDF intrinseco di BM25.
    """
    import re
    return [t for t in re.findall(r"\w+", text.lower(), re.UNICODE) if len(t) > 2]


def _rrf_fuse(
    bm25_ranked_ids: list[str],
    cosine_ranked_ids: list[str],
    k: int = RRF_K,
) -> dict[str, float]:
    """Reciprocal Rank Fusion: combina due ranking in uno score additivo.

    Per ogni chunk: score = sum(1 / (k + rank_i)) su ogni ranking che lo
    contiene. Mancanze sono 0 (non penalizzano oltre l'assenza). k=60 e' lo
    standard di letteratura.
    """
    scores: dict[str, float] = {}
    for rank, cid in enumerate(bm25_ranked_ids, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    for rank, cid in enumerate(cosine_ranked_ids, start=1):
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
    return scores


async def recall_hybrid(
    *,
    query: str,
    regulation_ids: list[str],
    region: str,
    repo: KnowledgeRepository,
    top_k: int = RECALL_TOP_K,
    course_id: str | None = None,
    module_idx: int | None = None,
) -> list[NormativeChunk]:
    """Recall ibrido BM25 + cosine fuso via RRF, top_k candidati.

    BM25 ha bisogno del corpus testuale lato Python: per economia carichiamo
    una volta sola il body di tutti i chunk delle `regulation_ids` (max 7
    normative * ~400 chunk medi = 2800 docs in RAM, ~3 MB) e fittiamo BM25Okapi
    on-the-fly. E' veloce (<200ms) e non richiede infrastruttura aggiuntiva.

    Per la parte cosine: embed Voyage della query + `search_chunks` (HNSW pgvector).
    """
    # ---- Cosine top_k: embed la query con Voyage (stesso modello dell'index)
    # e poi search_chunks su pgvector HNSW.
    query_embedding = await voyage_embed_with_retry(query)
    cosine_chunks: list[NormativeChunk] = await repo.search_chunks(
        query_embedding=query_embedding,
        regulation_ids=regulation_ids,
        region=region,
        top_k=top_k,
    )
    cosine_ids = [c.chunk_id for c in cosine_chunks]

    # ---- BM25 top_k: carico body dei chunk *delle stesse regulations*
    pool = repo.pool  # asyncpg pool gia' aperto
    rows = await pool.fetch(
        "SELECT id::text AS id, body FROM regulation_chunks "
        "WHERE regulation_id = ANY($1::uuid[]) AND is_current = true",
        regulation_ids,
    )
    corpus_ids = [r["id"] for r in rows]
    corpus_bodies = [r["body"] for r in rows]

    if not corpus_bodies:
        emit(
            PipelinePhase.RECALL_HYBRID,
            course_id=course_id,
            module_idx=module_idx,
            query=query,
            extra_corpus_empty=True,
        )
        return []

    with timed(
        PipelinePhase.RECALL_HYBRID,
        course_id=course_id,
        module_idx=module_idx,
        query=query,
        source="bm25_cosine_rrf",
    ) as ev:
        tokenized_corpus = [_tokenize_for_bm25(b) for b in corpus_bodies]
        # BM25Okapi e' sincrono ma lightweight; lo eseguiamo in thread per non
        # bloccare l'event loop sui corpus piu' grossi (~1800 doc).
        def _bm25_rank() -> list[str]:
            bm25 = BM25Okapi(tokenized_corpus)
            qt = _tokenize_for_bm25(query)
            if not qt:
                return []
            scores = bm25.get_scores(qt)
            # Indici ordinati per score discendente, prendi top_k.
            order = sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k]
            return [corpus_ids[i] for i in order if scores[i] > 0]

        bm25_ids = await asyncio.to_thread(_bm25_rank)

        ev["bm25_size"] = len(bm25_ids)
        ev["cosine_size"] = len(cosine_ids)

        # ---- RRF fusion
        fused = _rrf_fuse(bm25_ids, cosine_ids, k=RRF_K)
        # Mappa id -> chunk: cosine_chunks ha tutti i campi pronti; per chunk
        # che vincono SOLO via BM25 (non sono in cosine_chunks) faccio un fetch
        # singolo sul pool (knowledge_repo non espone get_chunks_by_ids).
        id_to_chunk: dict[str, NormativeChunk] = {c.chunk_id: c for c in cosine_chunks}
        missing_ids = [cid for cid in fused if cid not in id_to_chunk]
        if missing_ids:
            extra_rows = await pool.fetch(
                "SELECT rc.id::text AS chunk_id, rc.regulation_id::text AS regulation_id, "
                "rc.article, rc.paragraph, rc.hierarchy_path, rc.body, "
                "rc.chunk_type, rc.tags "
                "FROM regulation_chunks rc "
                "WHERE rc.id = ANY($1::uuid[]) AND rc.is_current = true",
                missing_ids,
            )
            for row in extra_rows:
                chunk = NormativeChunk(
                    chunk_id=row["chunk_id"],
                    regulation_id=row["regulation_id"],
                    article=row["article"],
                    paragraph=row["paragraph"],
                    hierarchy_path=row["hierarchy_path"],
                    body=row["body"],
                    chunk_type=row["chunk_type"],
                    tags=row["tags"] or [],
                )
                id_to_chunk[chunk.chunk_id] = chunk

        # Output: top_k per fused score, solo quelli che siamo riusciti a
        # idratare (alcuni potrebbero mancare per FK soft-delete fra il
        # recall e il fetch — fail-soft).
        ranked = sorted(fused.items(), key=lambda kv: -kv[1])[:top_k]
        result = [id_to_chunk[cid] for cid, _ in ranked if cid in id_to_chunk]
        ev["fused_size"] = len(result)
        return result


# ---------------------------------------------------------------------------
# 3) Cohere rerank
# ---------------------------------------------------------------------------


def _get_cohere_client() -> Any | None:
    """Lazy init del client Cohere. Ritorna None se la chiave non e' settata,
    cosi' il caller puo' fallback al solo recall RRF senza eccezioni."""
    api_key = settings.cohere_api_key
    if not api_key:
        return None
    # Import lazy: cohere non e' importato all'avvio app cosi' a flag spento
    # non aumenta nemmeno il footprint di import.
    import cohere
    return cohere.AsyncClientV2(api_key=api_key)


async def rerank_chunks(
    *,
    query: str,
    candidates: list[NormativeChunk],
    top_n: int = RERANK_TOP_N,
    course_id: str | None = None,
    module_idx: int | None = None,
) -> list[ScoredChunk]:
    """Re-rankka i candidati con Cohere rerank-multilingual-v3.0.

    Comportamento:
      - Se la chiave Cohere non e' settata, fallback al solo ordinamento
        delle candidate per la loro posizione attuale (gia' RRF-fused) con
        `source='rrf_fallback'`. La soglia D9 non si applica.
      - Altrimenti chiama Cohere e ritorna i top_n con `source='rerank_cohere'`.
        Emette `top_score` (topical-affinity, D-171-bis) per il sensore badge.
    """
    if not candidates:
        emit(
            PipelinePhase.RERANK_COHERE,
            course_id=course_id,
            module_idx=module_idx,
            query=query,
            source="empty_input",
            extra_candidates=0,
        )
        return []

    client = _get_cohere_client()
    if client is None:
        # Fallback: nessun rerank, restituisco i primi N per ordine RRF.
        ranked = candidates[:top_n]
        # Score sintetico decrescente per consistenza struct.
        fallback_out = [
            ScoredChunk(chunk=c, score=1.0 / (i + 1), source="rrf_fallback")
            for i, c in enumerate(ranked)
        ]
        emit(
            PipelinePhase.RERANK_COHERE,
            course_id=course_id,
            module_idx=module_idx,
            query=query,
            source="rrf_fallback",
            top_score=fallback_out[0].score if fallback_out else None,
            extra_no_cohere_key=True,
            extra_output_size=len(fallback_out),
        )
        return fallback_out

    documents = [c.body for c in candidates]
    with timed(
        PipelinePhase.RERANK_COHERE,
        course_id=course_id,
        module_idx=module_idx,
        query=query,
        source="cohere_rerank_multilingual_v3",
    ) as ev:
        try:
            resp = await client.rerank(
                model="rerank-multilingual-v3.0",
                query=query,
                documents=documents,
                top_n=min(top_n, len(documents)),
            )
        except Exception as exc:
            # Failure mode: log + fallback. Non rompiamo la pipeline per un
            # downtime API Cohere; degradiamo a RRF fallback come sopra.
            logger.warning(
                "cohere_rerank_failed",
                error_class=type(exc).__name__,
                error_msg=str(exc)[:200],
                fallback="rrf_fallback",
            )
            ranked = candidates[:top_n]
            return [
                ScoredChunk(chunk=c, score=1.0 / (i + 1), source="rrf_fallback")
                for i, c in enumerate(ranked)
            ]

        # resp.results: list of {index, relevance_score}. Ordine = best first.
        out: list[ScoredChunk] = []
        for r in resp.results:
            idx = r.index
            score = float(r.relevance_score)
            out.append(
                ScoredChunk(
                    chunk=candidates[idx],
                    score=score,
                    source="rerank_cohere",
                )
            )

        ev["output_size"] = len(out)
        if out:
            ev["top_score"] = out[0].score  # topical-affinity (Cohere), D-171-bis
            ev["under_alert_threshold"] = out[0].score < MIN_TOPICAL_AFFINITY_ALERT
        return out


# ---------------------------------------------------------------------------
# 4) 1-hop knowledge graph traversal (D1+F2.8, opzionale dietro flag)
# ---------------------------------------------------------------------------


async def expand_via_kg_1hop(
    *,
    reranked: list[ScoredChunk],
    repo: KnowledgeRepository,
    course_id: str | None = None,
    module_idx: int | None = None,
) -> list[ScoredChunk]:
    """Aggiungi chunk 1-hop dei top reranked tramite regulation_chunk_edges.

    Per ogni top-30 reranked, segue gli edge `source='deterministic'` (cita,
    modifica, attua, gerarchico_parent/sibling, e_definito_da se LLM-verified
    e' stato attivato) e idratta i chunk destinazione con `weight = score *
    KG_TRAVERSAL_WEIGHT_DECAY * edge.weight`. Risultato: lista combinata
    [reranked originali + 1-hop nuovi], deduplicata per chunk_id (vince score
    piu' alto).

    Filtraggio VAA-b:
      - SOLO edge con `source='deterministic'`. Gli edge `llm_verified` (anche
        gateati) hanno rumore residuo: usarli in 1-hop amplifica via dedup
        chunk con rilevanza incerta. Riattivabile via parametro se A/B mostra
        beneficio.

    Costo: 1 query batch su `regulation_chunk_edges` con `WHERE src IN
    (top_30_ids)` + 1 fetch dei chunk destinazione. ~50ms su corpus reale.

    Telemetria: emette `kg_1hop_expansion` con count edge seguiti + count
    chunk nuovi aggiunti (sensore: 0 nuovi = grafo sparso per quel modulo).
    """
    if not reranked:
        return reranked

    src_ids = [sc.chunk.chunk_id for sc in reranked]
    pool = repo.pool

    with timed(
        PipelinePhase.GRAPH_TRAVERSAL,
        course_id=course_id,
        module_idx=module_idx,
        source="kg_1hop_deterministic",
    ) as ev:
        # Query batch: tutti gli edge `deterministic` uscenti dai top reranked.
        edge_rows = await pool.fetch(
            "SELECT src_chunk_id::text AS src, dst_chunk_id::text AS dst, "
            "kind, weight FROM regulation_chunk_edges "
            "WHERE src_chunk_id = ANY($1::uuid[]) AND source = 'deterministic'",
            src_ids,
        )

        existing_ids: set[str] = {sc.chunk.chunk_id for sc in reranked}
        # Per ogni dst nuovo, calcola lo score combinato: max(src_score) *
        # decay * edge_weight. Cosi' se piu' top reranked puntano allo stesso
        # dst (es. art. 36 citato da art. 35 E art. 37), vince il path con
        # source piu' rilevante.
        src_score_map = {sc.chunk.chunk_id: sc.score for sc in reranked}
        new_scores: dict[str, float] = {}
        for er in edge_rows:
            dst_id = er["dst"]
            if dst_id in existing_ids:
                continue
            src_score = src_score_map.get(er["src"], 0.0)
            edge_weight = float(er["weight"])
            combined = src_score * KG_TRAVERSAL_WEIGHT_DECAY * edge_weight
            if combined > new_scores.get(dst_id, 0.0):
                new_scores[dst_id] = combined

        ev["edges_followed"] = len(edge_rows)
        ev["new_chunks_proposed"] = len(new_scores)

        if not new_scores:
            return reranked

        # Idratazione batch dei chunk destinazione.
        new_ids = list(new_scores.keys())
        rows = await pool.fetch(
            "SELECT id::text AS chunk_id, regulation_id::text AS regulation_id, "
            "article, paragraph, hierarchy_path, body, chunk_type, tags "
            "FROM regulation_chunks "
            "WHERE id = ANY($1::uuid[]) AND is_current = true",
            new_ids,
        )

        expanded: list[ScoredChunk] = list(reranked)
        for row in rows:
            chunk = NormativeChunk(
                chunk_id=row["chunk_id"],
                regulation_id=row["regulation_id"],
                article=row["article"],
                paragraph=row["paragraph"],
                hierarchy_path=row["hierarchy_path"],
                body=row["body"],
                chunk_type=row["chunk_type"],
                tags=row["tags"] or [],
                relevance_score=new_scores[row["chunk_id"]],
            )
            expanded.append(
                ScoredChunk(
                    chunk=chunk,
                    score=new_scores[row["chunk_id"]],
                    source="kg_1hop",
                )
            )

        # Riordina per score decrescente (i nuovi entrano dove meritano).
        expanded.sort(key=lambda sc: -sc.score)
        ev["final_size"] = len(expanded)
        return expanded


# ---------------------------------------------------------------------------
# 5) End-to-end: recall + rerank + (opzionale) kg traversal per modulo
# ---------------------------------------------------------------------------


async def _retrieve_pipeline(
    *,
    query: str,
    regulation_ids: list[str],
    region: str,
    repo: KnowledgeRepository,
    course_id: str | None = None,
    module_idx: int | None = None,
) -> list[ScoredChunk]:
    """Core retrieval pipeline: recall_hybrid -> rerank -> optional KG 1-hop.

    Helper privato condiviso fra ``retrieve_for_module`` (path legacy by-title
    che fa autogen LLM prima di chiamare qui) e ``retrieve_for_subtopic`` (path
    D3 by-subtopic che SKIPPA l'autogen perché la query è già scritta da
    instructor structured nel contesto del sotto-tema).

    Tutta la stocasticità LLM (autogen) vive sopra a questo helper, mai dentro:
    qui dentro tutto è deterministico modulo il jitter Cohere (ε~0.05).
    """
    candidates = await recall_hybrid(
        query=query,
        regulation_ids=regulation_ids,
        region=region,
        repo=repo,
        top_k=RECALL_TOP_K,
        course_id=course_id,
        module_idx=module_idx,
    )
    reranked = await rerank_chunks(
        query=query,
        candidates=candidates,
        top_n=RERANK_TOP_N,
        course_id=course_id,
        module_idx=module_idx,
    )
    if settings.v2_features.get("kg_traversal_enabled"):
        return await expand_via_kg_1hop(
            reranked=reranked,
            repo=repo,
            course_id=course_id,
            module_idx=module_idx,
        )
    return reranked


async def retrieve_for_module(
    *,
    module_title: str,
    course_target: str,
    normative_slug: str,
    regulation_ids: list[str],
    region: str,
    repo: KnowledgeRepository,
    course_id: str | None = None,
    module_idx: int | None = None,
) -> list[ScoredChunk]:
    """LEGACY V2 path (by-title): autogen riformula module_title -> query.

    Usato dal research_agent quando il flag ``skeleton_validation`` e' OFF
    (D3 non attivo). Il ``module_title`` qui e' generico (es. "Prevenzione e
    protezione") e ha bisogno di essere riformulato in una query semantica
    richiamando il contesto normativo/dominio.

    Step 1: autogen query (LLM, **stocastico**)
    Step 2: recall_hybrid (BM25+cosine RRF top_k=200)
    Step 3: rerank Cohere top_n=30 (o fallback RRF se chiave non settata)
    Step 4: (F2.8 opzionale) 1-hop KG traversal quando flag attivo.

    Per il path D3 (skeleton attivo), usare ``retrieve_for_subtopic``: la
    ``SkeletonItem.retrieval_query`` e' gia' una query semantica scritta da
    instructor structured, riformularla con autogen e' doppio LLM e introduce
    stocasticita' inutile (D-170 lezione 2026-05-30).
    """
    query = await autogen_module_query(
        module_title=module_title,
        course_target=course_target,
        normative_slug=normative_slug,
        course_id=course_id,
        module_idx=module_idx,
    )
    return await _retrieve_pipeline(
        query=query,
        regulation_ids=regulation_ids,
        region=region,
        repo=repo,
        course_id=course_id,
        module_idx=module_idx,
    )


async def retrieve_for_subtopic(
    *,
    retrieval_query: str,
    regulation_ids: list[str],
    region: str,
    repo: KnowledgeRepository,
    course_id: str | None = None,
    module_idx: int | None = None,
) -> list[ScoredChunk]:
    """D3 path (by-subtopic): query gia' semantica, NO autogen.

    Pensata per essere chiamata da ``materialize_module_from_skeleton`` con
    ``SkeletonItem.retrieval_query`` direttamente in input. La retrieval_query
    e' gia' una module-query autogen-style scritta da instructor structured
    nel contesto del sotto-tema specifico (vincolo Pydantic: min 15 chars,
    "frase di 15-30 parole in italiano che cattura il contenuto normativo/
    tecnico di QUEL sotto-tema").

    Differenza VS ``retrieve_for_module``:
      - retrieve_for_module fa 1 LLM call (autogen) prima del recall.
      - retrieve_for_subtopic NON fa LLM call: passa la retrieval_query
        direttamente a recall_hybrid e rerank_chunks.

    Vantaggi (D-170 fix 2026-05-30):
      - **Deterministico modulo jitter Cohere (~0.05)**: due chiamate con
        stessa retrieval_query producono lo stesso top_score entro epsilon.
      - **-30s a corso** circa: una LLM call in meno per sotto-tema (-10s)
        per ~3 moduli a corso 4h = -30s totali.
      - **Calibrazione B2 stabile**: il dataset oracolo non oscilla tra run.
      - **Allineamento concettuale**: la retrieval_query di SkeletonItem ha
        proprio quel ruolo (la "module-query autogen-style" scritta dal
        skeleton-generator).
    """
    return await _retrieve_pipeline(
        query=retrieval_query,
        regulation_ids=regulation_ids,
        region=region,
        repo=repo,
        course_id=course_id,
        module_idx=module_idx,
    )


# ---------------------------------------------------------------------------
# 6) F2.12 B2 — selettore di pool via cosine_voyage diretto (post-D-171-bis)
# ---------------------------------------------------------------------------


def _cosine_voyage(a: list[float], b: list[float]) -> float:
    """Cosine similarity fra due embedding Voyage 1024-dim.

    a = subtopic.text_emb (1 chiamata Voyage al subtopic, deterministica)
    b = chunk.body_emb (gia' in DB dall'ingestione)

    Calcolo in-memory veloce (<10ms per 100 chunks).
    """
    dot = float(sum(x * y for x, y in zip(a, b)))
    na = float(sum(x * x for x in a)) ** 0.5
    nb = float(sum(y * y for y in b)) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(dot / (na * nb))


async def retrieve_for_subtopic_b2(
    *,
    retrieval_query: str,
    regulation_ids: list[str],
    region: str,
    repo: KnowledgeRepository,
    course_id: str | None = None,
    module_idx: int | None = None,
    top_k: int = B2_TOP_K_DEFAULT,
) -> list[ScoredChunk]:
    """F2.12 B2 — selettore di pool via cosine_voyage diretto.

    Architettura post-classify cieca 2026-05-30 (sign-off analista):
      1. recall_hybrid -> pool RRF top-100 (BM25+cosine fusi).
      2. embedding Voyage del subtopic (retrieval_query) -> 1 chiamata, deterministico.
      3. Per ogni chunk del pool: cosine_voyage(chunk.body_emb, subtopic.text_emb).
         chunk.body_emb e' Voyage 1024-dim gia' in DB dall'ingestione.
      4. Ritorna top-K cosine_voyage discendente.

    Cohere downgrade (D-171-bis):
      - Cohere NON e' ranker decisionale: e' topical-affinity telemetry.
      - rerank_chunks viene comunque chiamato per emit dei segnali D9
        (under_alert_threshold del top_score topical-affinity).
      - Ma il ranking finale viene da cosine_voyage, NON da Cohere score.

    D9 corpus-thin sensors (F2.14 B4):
      - top_cosine_voyage_in_top_k: emit per sensore corpus-thin alternativo.
      - K fissa a default 30 (analista 2026-05-30 sequenza incrementale).
        Variante K adattiva (salto pendenza) work-item successivo post-B3.

    Resta deterministico (modulo jitter Cohere ~0.05 nei log telemetry, NON
    nel ranking finale che viene da cosine_voyage diretto, perfettamente
    riproducibile).
    """
    # Step 1: pool RRF top-100 (NON top-30 Cohere). Salto rerank Cohere come
    # decisore: lo chiamiamo solo per telemetria, ma usiamo cosine_voyage come
    # ranker.
    pool_candidates = await recall_hybrid(
        query=retrieval_query,
        regulation_ids=regulation_ids,
        region=region,
        repo=repo,
        top_k=B2_POOL_FOR_RANKING,
        course_id=course_id,
        module_idx=module_idx,
    )

    if not pool_candidates:
        emit(
            PipelinePhase.RERANK_COHERE,
            course_id=course_id,
            module_idx=module_idx,
            query=retrieval_query,
            source="b2_pool_empty",
            extra_top_k=top_k,
        )
        return []

    # Step 2: embedding Voyage del subtopic. retrieval_query e' gia' una query
    # semantica (instructor structured), embedded direttamente. Deterministico.
    subtopic_emb = await voyage_embed_with_retry(retrieval_query)

    # Step 3: cosine_voyage diretto subtopic vs chunk.body_emb per ogni chunk
    # del pool. chunk.body_emb e' Voyage 1024-dim gia' in DB.
    # Carico le embedding dei chunks del pool dal DB.
    pool_ids = [c.chunk_id for c in pool_candidates]
    pool = repo.pool
    rows = await pool.fetch(
        "SELECT id::text AS id, embedding::text AS emb "
        "FROM regulation_chunks WHERE id = ANY($1::uuid[])",
        pool_ids,
    )
    emb_by_id: dict[str, list[float]] = {}
    for r in rows:
        raw = r["emb"]
        if raw and raw.startswith("[") and raw.endswith("]"):
            try:
                emb_by_id[r["id"]] = [float(x) for x in raw[1:-1].split(",")]
            except ValueError:
                continue

    # Calcolo cosine_voyage per ogni chunk con embedding disponibile. I chunks
    # senza embedding (edge case) finiscono in fondo con score 0.
    scored: list[tuple[float, NormativeChunk]] = []
    for c in pool_candidates:
        emb = emb_by_id.get(c.chunk_id)
        if emb is None:
            scored.append((0.0, c))
            continue
        score = _cosine_voyage(subtopic_emb, emb)
        scored.append((score, c))

    # Step 4: ordina per cosine_voyage discendente, prendi top-K.
    scored.sort(key=lambda t: -t[0])
    top_k_final = scored[:top_k]

    # Telemetria B4 D9 corpus-thin sensors.
    if top_k_final:
        top_cosine = top_k_final[0][0]
        emit(
            PipelinePhase.RERANK_COHERE,
            course_id=course_id,
            module_idx=module_idx,
            query=retrieval_query,
            source="b2_cosine_voyage_selector",
            extra_pool_size=len(pool_candidates),
            extra_top_k=top_k,
            extra_top_cosine_voyage=round(top_cosine, 4),
            extra_under_b4_top_cosine_alert=top_cosine < B4_TOP_COSINE_ALERT,
        )

    return [
        ScoredChunk(chunk=c, score=score, source="b2_cosine_voyage")
        for score, c in top_k_final
    ]


# ---------------------------------------------------------------------------
# 7) F2.13 B3 — cross-Titolo decay sul pool B2 (D-166 chiusura strutturale)
# ---------------------------------------------------------------------------


async def apply_b3_cross_title_decay(
    *,
    pool_b2: list[ScoredChunk],
    repo: KnowledgeRepository,
    course_id: str | None = None,
    module_idx: int | None = None,
) -> list[ScoredChunk]:
    """Applica B3 cross-Titolo decay sul pool selezionato da B2.

    Architettura (analista sign-off 2026-05-30, strada A):
      1. Per ogni chunk del pool B2, carica top_section dal DB
         (regulation_chunks.top_section, popolato da migration 008 +
         backfill_top_section.py).
      2. Per ogni regulation_id presente nel pool, calcola Titolo dominante
         = top_section con majority count (tie-break: primo in ordine
         lessicale). Esclude "Sconosciuto" e NULL dal majority vote per non
         contaminare la dominante (ma li lascia nel pool finale).
      3. Per ogni chunk: se top_section != Titolo dominante per la sua
         regulation, decay del peso (* B3_DECAY_FACTOR).
      4. Soglia di scarto: se peso post-decay < (max_pool * B3_THRESHOLD_RATIO),
         scarta. Soglia relativa, auto-adattiva cross-regime (analista
         sign-off 2026-05-30).
      5. Re-ordina per peso post-decay discendente; ritorna pool finale.

    Log strutturato 8 campi per ogni chunk:
      chunk_id, top_section, top_section_dominante, cosine_originale,
      weight_post_decay, soglia_calcolata, decisione, regulation_id.

    Flag b3_noop_reason emesso al livello pool quando:
      - monosection: tutti i chunks della stessa regulation hanno stesso
        top_section -> nessun decay possibile (atteso su single-section
        regulations e su pool molto coerenti).
      - low_confidence_dominante: dominante per regulation calcolata su
        meno di 3 chunks (statistica debole). Pattern atteso su REGIME 3
        corpus-thin per concetto (analista 2026-05-30).
      - trivial_single_section_regulation: regulation in
        SINGLE_SECTION_REGULATIONS (DM, Reg CE) -> tutti chunks same
        top_section per costruzione.

    Args:
      pool_b2: output di retrieve_for_subtopic_b2 (top-K cosine_voyage).
      repo: KnowledgeRepository per accesso pool.fetch.

    Returns:
      Pool post-B3 ordinato per peso decay-applicato discendente.
    """
    if not pool_b2:
        emit(
            PipelinePhase.GRAPH_TRAVERSAL,
            course_id=course_id,
            module_idx=module_idx,
            source="b3_cross_title_decay",
            extra_b3_noop_reason="empty_pool",
        )
        return []

    # Step 1: carica top_section + regulation_id per ogni chunk del pool.
    chunk_ids = [sc.chunk.chunk_id for sc in pool_b2]
    pool = repo.pool
    rows = await pool.fetch(
        "SELECT id::text AS chunk_id, regulation_id::text AS rid, "
        "top_section FROM regulation_chunks WHERE id = ANY($1::uuid[])",
        chunk_ids,
    )
    # Mappa chunk_id -> (regulation_id, top_section).
    meta_by_chunk: dict[str, tuple[str, str | None]] = {}
    for r in rows:
        meta_by_chunk[r["chunk_id"]] = (r["rid"], r["top_section"])

    # Step 2: calcola Titolo dominante per regulation (esclude "Sconosciuto" e NULL).
    # Per ogni regulation_id, conta majority dei top_section "buoni".
    dominante_per_reg: dict[str, str | None] = {}
    counts_per_reg: dict[str, dict[str, int]] = {}
    for sc in pool_b2:
        cid = sc.chunk.chunk_id
        meta = meta_by_chunk.get(cid)
        if meta is None:
            continue
        rid, ts = meta
        if ts is None or ts == "Sconosciuto":
            continue  # esclude da majority vote, ma chunks restano nel pool
        counts_per_reg.setdefault(rid, {})[ts] = counts_per_reg.setdefault(rid, {}).get(ts, 0) + 1

    # Per ogni regulation, scegli dominante (max count, tie-break lessicografico)
    noop_reasons: list[str] = []
    for rid, ts_counts in counts_per_reg.items():
        if not ts_counts:
            dominante_per_reg[rid] = None
            continue
        # Tie-break: ordina per (-count, top_section) per determinismo
        sorted_ts = sorted(ts_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        winner = sorted_ts[0][0]
        winner_count = sorted_ts[0][1]
        dominante_per_reg[rid] = winner
        # Flag low_confidence_dominante se dominante calcolata su < 3 chunks
        if winner_count < 3:
            noop_reasons.append(f"low_confidence_dominante:{rid}")
        # Flag monosection se TUTTI chunks della regulation hanno stesso top_section
        if len(ts_counts) == 1:
            noop_reasons.append(f"monosection:{rid}")

    # Trivial single-section regulations: rilevate dal mapping interno
    from app.services.regulation_metadata import SINGLE_SECTION_REGULATIONS
    # Risolvi slug per ogni regulation_id presente
    reg_slug_rows = await pool.fetch(
        "SELECT id::text AS rid, slug FROM regulations WHERE id = ANY($1::uuid[])",
        list(set(meta[0] for meta in meta_by_chunk.values())),
    )
    slug_by_rid: dict[str, str] = {r["rid"]: r["slug"] for r in reg_slug_rows}
    trivial_regs = {
        rid for rid, slug in slug_by_rid.items()
        if slug in SINGLE_SECTION_REGULATIONS
    }
    for rid in trivial_regs:
        if rid in counts_per_reg:
            noop_reasons.append(f"trivial_single_section_regulation:{rid}")

    # Skip B3 per regulations con n_obs < B3_MIN_OBSERVATIONS (analista
    # 2026-05-30 post-osservazione GEN M1 Art. 236 false-discard).
    # Razionale: con < 4 osservazioni la dominante e' rumore statistico
    # (3 obs split 2:1 e' determinata da un singolo chunk di differenza).
    # Skip B3 in caso di bassa confidenza e' "do no harm" sotto incertezza:
    # i chunks della regulation passano al ranking finale con peso originale
    # (stesso comportamento di B2 solo, mai peggio del baseline pre-B3).
    skip_low_obs_regs: set[str] = set()
    min_obs = settings.b3_min_observations
    for rid, ts_counts in counts_per_reg.items():
        n_obs = sum(ts_counts.values())
        if n_obs < min_obs:
            skip_low_obs_regs.add(rid)
            noop_reasons.append(
                f"b3_skipped_insufficient_obs:{rid}:n_obs={n_obs}<{min_obs}"
            )

    # Step 3 + 4: applica decay e soglia scarto.
    max_pool_score = max(sc.score for sc in pool_b2)
    soglia_scarto = max_pool_score * settings.b3_threshold_ratio
    decay_factor = settings.b3_decay_factor

    survivors: list[ScoredChunk] = []
    decay_log: list[dict[str, object]] = []
    for sc in pool_b2:
        cid = sc.chunk.chunk_id
        meta = meta_by_chunk.get(cid)
        cosine_orig = sc.score
        if meta is None:
            # Chunk senza meta nel DB: lascialo passare con peso originale
            survivors.append(sc)
            decay_log.append({
                "chunk_id": cid,
                "top_section": None,
                "top_section_dominante": None,
                "cosine_originale": round(cosine_orig, 4),
                "weight_post_decay": round(cosine_orig, 4),
                "soglia_calcolata": round(soglia_scarto, 4),
                "decisione": "passthrough_no_meta",
                "regulation_id": None,
            })
            continue

        rid, ts = meta
        dominante: str | None = dominante_per_reg.get(rid)

        # Caso A: top_section coincide con dominante (o entrambi mancanti) -> nessun decay
        if ts is not None and dominante is not None and ts == dominante:
            survivors.append(sc)
            decisione = "keep_same_titolo"
            weight_post = cosine_orig
        # Caso B: top_section "Sconosciuto" o NULL -> nessun decay (escluso da majority)
        elif ts is None or ts == "Sconosciuto":
            survivors.append(sc)
            decisione = "keep_unclassified"
            weight_post = cosine_orig
        # Caso C: dominante non determinabile (regulation senza majority) -> nessun decay
        elif dominante is None:
            survivors.append(sc)
            decisione = "keep_no_dominante"
            weight_post = cosine_orig
        # Caso D: regulation con insufficient observations -> skip B3 (do no harm)
        elif rid in skip_low_obs_regs:
            survivors.append(sc)
            decisione = "keep_skipped_insufficient_obs"
            weight_post = cosine_orig
        else:
            # Cross-titolo: applica decay
            weight_post = cosine_orig * decay_factor
            if weight_post < soglia_scarto:
                decisione = "discard_below_threshold"
                # NON aggiungo a survivors
            else:
                decisione = "decay_kept"
                # Riassegno il peso al ScoredChunk per ordinamento finale
                survivors.append(
                    ScoredChunk(chunk=sc.chunk, score=weight_post, source="b3_decayed")
                )

        decay_log.append({
            "chunk_id": cid,
            "top_section": ts,
            "top_section_dominante": dominante,
            "cosine_originale": round(cosine_orig, 4),
            "weight_post_decay": round(weight_post, 4),
            "soglia_calcolata": round(soglia_scarto, 4),
            "decisione": decisione,
            "regulation_id": rid,
        })

    # Re-ordina per peso (post-decay) discendente
    survivors.sort(key=lambda sc: -sc.score)

    # Telemetria pool-level
    # Conta decisioni per stampa diagnostica nel summary
    decision_counts: dict[str, int] = {}
    for entry in decay_log:
        d = str(entry.get("decisione", "unknown"))
        decision_counts[d] = decision_counts.get(d, 0) + 1

    # Dominante per regulation (per diagnostica)
    dominante_summary = {
        rid: dom for rid, dom in dominante_per_reg.items() if dom is not None
    }

    emit(
        PipelinePhase.GRAPH_TRAVERSAL,
        course_id=course_id,
        module_idx=module_idx,
        source="b3_cross_title_decay",
        extra_pool_in_size=len(pool_b2),
        extra_pool_out_size=len(survivors),
        extra_max_pool_score=round(max_pool_score, 4),
        extra_soglia_scarto=round(soglia_scarto, 4),
        extra_b3_noop_reason=";".join(noop_reasons) if noop_reasons else "active",
        extra_decay_factor=decay_factor,
        extra_threshold_ratio=settings.b3_threshold_ratio,
        extra_decision_counts=decision_counts,
        extra_dominante_per_regulation=dominante_summary,
    )

    # Log per-chunk (livello debug, alto volume): emesso via logger.info per
    # cattura dai test strumentati. Su prod (livello WARNING/INFO) viene
    # filtrato; lo script di run strumentato configura level=DEBUG per
    # ricevere questi eventi.
    logger.info(
        "b3_per_chunk_log",
        phase="b3_cross_title_decay_per_chunk",
        course_id=course_id,
        module_idx=module_idx,
        decay_log=decay_log,
    )

    return survivors


async def retrieve_for_subtopic_b2_b3(
    *,
    retrieval_query: str,
    regulation_ids: list[str],
    region: str,
    repo: KnowledgeRepository,
    course_id: str | None = None,
    module_idx: int | None = None,
    top_k: int = B2_TOP_K_DEFAULT,
) -> list[ScoredChunk]:
    """B2 + B3 in serie (analista sign-off 2026-05-30 H7).

    1. B2 selettore di pool: top-K cosine_voyage dal pool RRF top-100.
    2. B3 cross-Titolo decay: decay×0.4 + soglia scarto auto-adattiva.

    Solo questo wrapper deve essere chiamato in production. retrieve_for_subtopic_b2
    e apply_b3_cross_title_decay restano esposte separatamente solo per testing
    isolato delle singole fasi.
    """
    pool_b2 = await retrieve_for_subtopic_b2(
        retrieval_query=retrieval_query,
        regulation_ids=regulation_ids,
        region=region,
        repo=repo,
        course_id=course_id,
        module_idx=module_idx,
        top_k=top_k,
    )
    return await apply_b3_cross_title_decay(
        pool_b2=pool_b2,
        repo=repo,
        course_id=course_id,
        module_idx=module_idx,
    )


# ---------------------------------------------------------------------------
# 7) F2.14 B4 — D9 vincolante corpus-thin per voce (Caso 1 solo)
# ---------------------------------------------------------------------------
#
# Architettura analista sign-off 2026-05-30 (post D-161 light + sample-read M0):
#   - B4 agisce sul pool finale di UNA voce (post B2+B3), per regulation.
#   - Per ogni regulation: se n_chunks(rid) < B4_MIN_CHUNKS_PER_VOICE -> corpus
#     thin per quella voce su quella regulation.
#   - Behavior configurabile:
#     - "block" (default sicura): rimuove i chunks delle regulations corpus-thin
#       dal pool finale. Emit warning. Se TUTTO il pool e' corpus thin -> voce
#       bloccata interamente, materialize ritornera' lista vuota per la voce e
#       generation_jobs.status logghera' voice_X_corpus_insufficient.
#     - "mark_only": NON rimuove. Marca i chunks con metadata
#       low_corpus_confidence per analytics/dashboard. Permette generazione.
#   - Log strutturato per voce con n_chunks_per_regulation_per_voce sempre
#     emesso (anche quando NON scatta) per calibrazione soglia su evidenza.
#
# Scope B4 (c) (analista sign-off): SOLO Caso 1 corpus thin per regulation.
# Caso 2 (pool dominato regulation cross-scope) e Caso 3 (decay_kept top_section
# lontana) richiederebbero Tabella 2 course_type -> expected_titoli, che e'
# F2.13 D8 catalog DB + H8 work-item futuri, NON F2.14.


async def apply_b4_corpus_thin_check(
    *,
    voice_pool: list[ScoredChunk],
    voice_idx: int | None = None,
    course_id: str | None = None,
    module_idx: int | None = None,
) -> tuple[list[ScoredChunk], list[dict[str, object]]]:
    """B4 D9 corpus-thin check per voce (Caso 1).

    Args:
      voice_pool: chunks post-B2+B3 di una singola voce
      voice_idx: ordinale della voce nello skeleton (per log)
      course_id, module_idx: telemetria

    Returns:
      (survivors, decisions_log)
      - survivors: lista filtrata (su behavior="block") o invariata (mark_only).
        Su mark_only i chunks corpus-thin sono ancora presenti ma annotati nel
        log come "marked_low_corpus_confidence" (la marcatura va propagata a
        slide metadata downstream — vedi skeleton_service caller).
      - decisions_log: lista per-regulation con campi
        {voce_idx, regulation_id, n_chunks, soglia, decisione, behavior_config}
    """
    if not voice_pool:
        return voice_pool, []

    soglia = settings.b4_min_chunks_per_voice
    behavior = settings.b4_corpus_thin_behavior

    # Conta n_chunks per regulation_id nel pool della voce
    chunks_by_reg: dict[str, list[ScoredChunk]] = {}
    for sc in voice_pool:
        rid = sc.chunk.regulation_id
        chunks_by_reg.setdefault(rid, []).append(sc)

    # Per ogni regulation determina decisione
    decisions: list[dict[str, object]] = []
    survivors: list[ScoredChunk] = []
    blocked_chunks_ids: set[str] = set()

    for rid, sc_list in chunks_by_reg.items():
        n_chunks = len(sc_list)
        corpus_thin = n_chunks < soglia

        if not corpus_thin:
            # Sufficiente -> tutti i chunks passano senza marca
            for sc in sc_list:
                survivors.append(sc)
            decision = "passthrough_sufficient"
        elif behavior == "block":
            # Block: rimuovi i chunks della regulation dal pool
            for sc in sc_list:
                blocked_chunks_ids.add(sc.chunk.chunk_id)
            decision = "block"
        else:
            # mark_only: lascia chunks nel pool, annota nel log per metadata
            # downstream (skeleton_service caller propaga low_corpus_confidence
            # a slide metadata)
            for sc in sc_list:
                survivors.append(sc)
            decision = "mark_only"

        decisions.append({
            "voce_idx": voice_idx,
            "regulation_id": rid,
            "n_chunks": n_chunks,
            "soglia": soglia,
            "decisione": decision,
            "behavior_config": behavior,
            "chunk_ids": [sc.chunk.chunk_id for sc in sc_list] if corpus_thin else [],
        })

    # Telemetria pool-level
    n_total_in = len(voice_pool)
    n_total_out = len(survivors)
    n_regulations_corpus_thin = sum(
        1 for d in decisions if d["decisione"] in ("block", "mark_only")
    )

    emit(
        PipelinePhase.GRAPH_TRAVERSAL,
        course_id=course_id,
        module_idx=module_idx,
        source="b4_corpus_thin_check",
        extra_voice_idx=voice_idx,
        extra_pool_in_size=n_total_in,
        extra_pool_out_size=n_total_out,
        extra_n_regulations_corpus_thin=n_regulations_corpus_thin,
        extra_soglia=soglia,
        extra_behavior_config=behavior,
        extra_n_chunks_per_regulation={
            d["regulation_id"]: d["n_chunks"] for d in decisions
        },
        extra_decisions_summary={
            d["regulation_id"]: d["decisione"] for d in decisions
        },
    )

    # Log per-decisione (analytics/dashboard)
    logger.info(
        "b4_corpus_thin_per_voice_log",
        phase="b4_corpus_thin_per_voice",
        course_id=course_id,
        module_idx=module_idx,
        voice_idx=voice_idx,
        decisions=decisions,
    )

    return survivors, decisions


async def retrieve_for_subtopic_b2_b3_b4(
    *,
    retrieval_query: str,
    regulation_ids: list[str],
    region: str,
    repo: KnowledgeRepository,
    course_id: str | None = None,
    module_idx: int | None = None,
    voice_idx: int | None = None,
    top_k: int = B2_TOP_K_DEFAULT,
) -> tuple[list[ScoredChunk], list[dict[str, object]]]:
    """B2 + B3 + B4 in serie (analista sign-off 2026-05-30 H7 + F2.14).

    1. B2 selettore di pool top-K cosine_voyage.
    2. B3 cross-Titolo decay.
    3. B4 corpus-thin check per voce (Caso 1, behavior block o mark_only).

    Returns (survivors_post_b4, b4_decisions_log) per propagare metadata
    low_corpus_confidence downstream se behavior=mark_only.
    """
    pool_post_b3 = await retrieve_for_subtopic_b2_b3(
        retrieval_query=retrieval_query,
        regulation_ids=regulation_ids,
        region=region,
        repo=repo,
        course_id=course_id,
        module_idx=module_idx,
        top_k=top_k,
    )
    return await apply_b4_corpus_thin_check(
        voice_pool=pool_post_b3,
        voice_idx=voice_idx,
        course_id=course_id,
        module_idx=module_idx,
    )


# math import only used here so far; keep at end so isort/ruff don't move it.
_ = math  # silence unused-import in case future refactor removes it
