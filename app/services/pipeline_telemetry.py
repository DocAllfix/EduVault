"""Pipeline telemetry — structured events for v2 RAG/Graph/Skeleton.

Standardizza il payload degli eventi che le componenti v2 emettono durante la
generazione di un corso. Un singolo helper `emit(...)` con campi vincolati
serve due scopi:

1. **Monitoring permanente** (richiesta analista, decisione D2): la query
   auto-generata per ogni modulo + il `top_rerank_score` risultante devono
   essere loggati *sempre*. Se la qualità del retrieval cala in produzione,
   ci accorgiamo da questi eventi prima del cliente.

2. **Sensori per il badge D9**: alcuni issue type (`module_corpus_thin`,
   `module_underpopulated`) sono calcolati a partire da metriche emesse qui.
   Tracciandole strutturate, slide_quality_service le riusa senza dover
   re-eseguire il retrieval.

Pattern d'uso (importato da retrieval_v2, skeleton_service, content_agent, …):

    from app.services.pipeline_telemetry import emit, PipelinePhase
    emit(PipelinePhase.QUERY_AUTOGEN, course_id=cid, module_idx=2,
         query="Rischi specifici DPI termici officina chimica",
         top_score=0.62, source="llm_verified", elapsed_ms=482)

Tutto finisce su structlog (configurato in `app/config.py:configure_logging`),
quindi su Railway/stdout/json.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from enum import Enum
from typing import Any, Iterator

import structlog

_log = structlog.get_logger("pipeline_event")


class PipelinePhase(str, Enum):
    """Fasi del piano v2 (vast-hopping-sketch). Ogni emit() ne menziona una.

    Manteniamo l'enum stretto per evitare drift di stringhe sparse nel codice:
    quando aggiungiamo una fase nuova, la dichiariamo qui e ci agganciamo i
    consumer (dashboard analytics, badge service) in un punto solo.
    """

    # D2 — Hybrid RAG
    RECALL_HYBRID = "recall_hybrid"          # BM25 + cosine RRF top_k=200
    QUERY_AUTOGEN = "query_autogen"          # LLM genera la query per il modulo
    RERANK_COHERE = "rerank_cohere"          # rerank-multilingual-v3.0 → top 30
    # D1 — Knowledge Graph
    EDGE_EXTRACT_DET = "edge_extract_deterministic"
    EDGE_EXTRACT_LLM = "edge_extract_llm"
    EDGE_GATE_REJECT = "edge_gate_reject"    # gate VAA respinge un edge llm_verified
    GRAPH_TRAVERSAL = "graph_traversal"      # 1-hop post-rerank
    # D3 — Scheletro narrativo
    SKELETON_GENERATE = "skeleton_generate"
    SKELETON_APPROVE = "skeleton_approve"    # gate utente 1-click
    # D4 — Image library
    IMAGE_LIBRARY_HIT = "image_library_hit"  # match locale, no web
    IMAGE_LIBRARY_MISS = "image_library_miss"  # fallback Pexels web
    # D7 — Chat
    CHAT_MESSAGE = "chat_message"
    CHAT_APPLY = "chat_apply"
    # D9 — Badge
    QUALITY_COMPUTED = "quality_computed"
    # D6 — Performance
    AUDIO_SYNTHESIZE = "audio_synthesize"
    PPTX_BUILD = "pptx_build"


def emit(
    phase: PipelinePhase,
    *,
    course_id: str | None = None,
    module_idx: int | None = None,
    slide_index: int | None = None,
    query: str | None = None,
    top_score: float | None = None,
    source: str | None = None,
    elapsed_ms: int | None = None,
    **extra: Any,
) -> None:
    """Emette un evento strutturato sulla pipeline v2.

    I campi sono opzionali per accomodare fasi eterogenee (es. EDGE_EXTRACT non
    ha module_idx; SKELETON_GENERATE non ha top_score). I consumer downstream
    (Loki/Grafana, slide_quality_service) si attendono i nomi *standard*
    elencati nella signature — `extra` raccoglie tutto il resto senza shape fissa.

    `source` è la dimensione VAA-b: traccia "da dove arriva il dato"
    (deterministic / llm_verified / library / web_fallback / scraped / manual…).
    """
    payload: dict[str, Any] = {"phase": phase.value}
    if course_id is not None:
        payload["course_id"] = course_id
    if module_idx is not None:
        payload["module_idx"] = module_idx
    if slide_index is not None:
        payload["slide_index"] = slide_index
    if query is not None:
        payload["query"] = query
    if top_score is not None:
        payload["top_score"] = round(top_score, 4)
    if source is not None:
        payload["source"] = source
    if elapsed_ms is not None:
        payload["elapsed_ms"] = elapsed_ms
    payload.update(extra)
    _log.info("pipeline_event", **payload)


@contextmanager
def timed(
    phase: PipelinePhase,
    *,
    course_id: str | None = None,
    module_idx: int | None = None,
    slide_index: int | None = None,
    **extra: Any,
) -> Iterator[dict[str, Any]]:
    """Context manager che misura il tempo e emette al termine.

    Il dict yielded permette al chiamante di arricchire l'evento (es. settare
    `top_score` solo dopo che il rerank è ritornato). Il timing parte
    all'enter del with-block, finisce all'exit (anche su eccezione: in quel
    caso l'evento riceve `error_class`).

    Uso:
        with timed(PipelinePhase.RECALL_HYBRID, course_id=cid, module_idx=2) as ev:
            chunks = await recall(...)
            ev["candidates"] = len(chunks)
            ev["top_score"] = chunks[0].score
    """
    bag: dict[str, Any] = dict(extra)
    start = time.perf_counter()
    try:
        yield bag
    except Exception as exc:
        bag["error_class"] = type(exc).__name__
        raise
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        emit(
            phase,
            course_id=course_id,
            module_idx=module_idx,
            slide_index=slide_index,
            elapsed_ms=elapsed_ms,
            **bag,
        )
