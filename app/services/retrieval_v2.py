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
  ScoredChunk[]  +  module_top_rerank_score loggato (sensore badge D9
                   `module_corpus_thin` quando sotto MIN_RERANK_SCORE_ALERT)

VAA:
  - (a) verifica al render: `module_top_rerank_score` esposto, non scartato.
  - (b) provenienza: ogni ScoredChunk porta `source='rerank_cohere'` o `'bm25'`
        a seconda dello stadio in cui ha vinto. In caso di disabilitazione
        Cohere fallback al solo recall RRF con `source='rrf_fallback'`.
  - (d) sensore vs gate: il vecchio MIN_RELEVANCE filtrava silenziosamente.
        Qui MIN_RERANK_SCORE_ALERT NON filtra: tutti i top-30 entrano sempre,
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
MIN_RERANK_SCORE_ALERT = 0.45

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


@dataclass(frozen=True)
class ScoredChunk:
    """Risultato finale del retrieval: chunk + score + provenienza.

    Importante: `score` puo' essere su scale diverse a seconda di `source`:
      - 'rerank_cohere': 0..1 (Cohere normalizza)
      - 'rrf_fallback' / 'bm25_only': il valore RRF grezzo (sommatorie di 1/k+rank)
    Il caller usa `source` per sapere come interpretarlo. La soglia
    MIN_RERANK_SCORE_ALERT vale solo per `source='rerank_cohere'`.
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
        Emette `module_top_rerank_score` per il sensore badge.
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
            ev["top_score"] = out[0].score
            ev["under_alert_threshold"] = out[0].score < MIN_RERANK_SCORE_ALERT
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
    """End-to-end pipeline v2 per un singolo modulo.

    Step 1: autogen query (LLM)
    Step 2: recall_hybrid (BM25+cosine RRF top_k=200)
    Step 3: rerank Cohere top_n=30 (o fallback RRF se chiave non settata)
    Step 4: (F2.8 opzionale) 1-hop KG traversal dei top reranked quando
            `v2_kg_traversal_enabled=True` — aggiunge chunk collegati via edge
            deterministici con weight decay 0.7.

    NaN / corpus vuoto / Cohere down sono tutti gestiti senza eccezioni:
    si ottiene una lista (possibilmente vuota) e i sensori D9 ne segnalano la
    natura nei log.
    """
    query = await autogen_module_query(
        module_title=module_title,
        course_target=course_target,
        normative_slug=normative_slug,
        course_id=course_id,
        module_idx=module_idx,
    )
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


# math import only used here so far; keep at end so isort/ruff don't move it.
_ = math  # silence unused-import in case future refactor removes it
