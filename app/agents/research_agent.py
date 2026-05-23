"""Research Agent (BLUEPRINT §05.4).

PHASE 3.3 — first node of the LangGraph pipeline. Takes the course request,
runs the RAG pipeline (resolve slugs → semantic query → vector search →
relevance filter), builds the pacing plan, distributes the retrieved chunks
to modules via keyword overlap, and returns the merged context.

Skill alignment:
- langgraph-fundamentals "node signatures": ``async def(state) -> dict``
  returning ONLY the fields the node writes (course_context, pacing_plan).
- langgraph-fundamentals "fix-state-must-return-dict": never mutate state.
- langchain-rag "filtri ibridi": vector search + scalar regional filter
  delegated to KnowledgeRepository.search_chunks (already implemented in 2.5).
- Embedding consistency (langchain-rag "fix-consistent-embeddings"):
  voyage-3 / 1024-dim everywhere (index + query).

Architectural notes:
- ``get_pool()`` comes from services.dependencies (BP §02.4) — never global.
- Distribution uses keyword overlap (NOT cosine on chunk embeddings) — zero
  API cost, deterministic, sufficient for Italian normative module titles
  (BP §05.4 explicit choice).
"""

from __future__ import annotations

import structlog

from app.agents.pipeline import NexusPipelineState
from app.models.knowledge import NormativeChunk
from app.models.pipeline import CourseContext, PacingPlan
from app.models.requests import CourseRequest
from app.services.dependencies import get_pool
from app.services.ingestion_service import voyage_embed_with_retry
from app.services.knowledge_repo import KnowledgeRepository
from app.services.pacing_engine import PacingEngine
from config.catalog_config import COURSE_CATALOG

logger = structlog.get_logger()

MIN_RELEVANCE = 0.3


# ─────────────────────────────────────────────────────────────────────
# Chunk distribution helpers (BP §05.4)
# ─────────────────────────────────────────────────────────────────────


def _keyword_overlap(title: str, body: str) -> int:
    """Count keywords shared between a module title and a chunk body.

    For structured Italian normative text this is sufficient: 'DPI' appears
    in chunks about DPI, 'antincendio' in firefighting chunks, etc.
    Zero API cost — no embeddings (BP §05.4).
    """
    title_words = set(title.lower().split())
    body_words = set(body.lower().split())
    return len(title_words & body_words)


def _rebalance_min(
    result: dict[int, list[NormativeChunk]],
    min_per_module: int = 3,
) -> None:
    """Guarantee at least ``min_per_module`` chunks per module.

    Redistribute from over-populated modules to under-populated ones (BP §05.4).
    """
    while True:
        under = [k for k, v in result.items() if len(v) < min_per_module]
        over = [k for k, v in result.items() if len(v) > min_per_module + 2]
        if not under or not over:
            break
        donor = max(over, key=lambda k: len(result[k]))
        receiver = min(under, key=lambda k: len(result[k]))
        result[receiver].append(result[donor].pop())


def _rebalance_max(
    result: dict[int, list[NormativeChunk]],
    max_per_module: int,
) -> None:
    """Redistribute excess chunks from over-populated modules (BP §05.4).

    Prevents keyword-overlap degeneration when generic titles
    (e.g. 'Concetti di rischio') attract ALL chunks because the word
    'rischio' is ubiquitous in safety regulations.
    """
    while True:
        over = [k for k, v in result.items() if len(v) > max_per_module]
        under = [k for k, v in result.items() if len(v) < max_per_module]
        if not over or not under:
            break
        donor = max(over, key=lambda k: len(result[k]))
        receiver = min(under, key=lambda k: len(result[k]))
        result[receiver].append(result[donor].pop())


def distribute_chunks_to_modules(
    chunks: list[NormativeChunk],
    pacing_plan: PacingPlan,
) -> dict[int, list[NormativeChunk]]:
    """Distribute chunks to modules by semantic similarity (BP §05.4).

    Falls back to round-robin if chunks are too few for meaningful semantic
    distribution. Guarantees at least 3 chunks per module via post-assignment
    rebalancing.
    """
    result: dict[int, list[NormativeChunk]] = {m.module_index: [] for m in pacing_plan.modules}

    if len(chunks) < len(pacing_plan.modules) * 3:
        # Too few chunks for semantic distribution → round-robin
        module_indices = [m.module_index for m in pacing_plan.modules]
        for i, chunk in enumerate(chunks):
            target = module_indices[i % len(module_indices)]
            result[target].append(chunk)
        return result

    # Assign each chunk to the module whose title best overlaps it
    for chunk in chunks:
        best_module = max(
            pacing_plan.modules,
            key=lambda m: _keyword_overlap(m.title, chunk.body),
        )
        result[best_module.module_index].append(chunk)

    # Guarantee a minimum coverage per module
    _rebalance_min(result, min_per_module=3)

    # Prevent over-population from keyword overlap on generic titles
    avg_per_module = len(chunks) // max(len(pacing_plan.modules), 1)
    _rebalance_max(result, max_per_module=avg_per_module + 5)

    return result


# ─────────────────────────────────────────────────────────────────────
# Research Agent — LangGraph node (BP §05.4)
# ─────────────────────────────────────────────────────────────────────


async def research_agent(state: NexusPipelineState) -> dict[str, object]:
    """RAG retrieval + pacing + chunk distribution per module.

    Pydantic validation at the input boundary (rehydrate ``course_request``
    into ``CourseRequest``) and at the output boundary (build a
    ``CourseContext`` Pydantic model before serialising).

    Returns ONLY the fields this node writes (langgraph-fundamentals
    ``fix-state-must-return-dict``): ``course_context`` and ``pacing_plan``.
    The reducers on ``completed_modules`` / ``errors`` are not touched here.
    """
    # ═══ INPUT VALIDATION ═══
    request = CourseRequest(**state["course_request"])
    pool = get_pool()
    knowledge_repo = KnowledgeRepository(pool)

    # 1. Resolve slug → UUID (raises ValueError if any slug is missing)
    catalog_entry = COURSE_CATALOG[request.course_type]
    regulation_slugs_raw = catalog_entry["regs"]
    assert isinstance(regulation_slugs_raw, list)
    regulation_slugs: list[str] = [str(s) for s in regulation_slugs_raw]
    regulation_ids = await knowledge_repo.resolve_slugs_to_ids(regulation_slugs)

    # ═══ REGIONAL VALIDATION ═══
    # Courses flagged ``"regional": True`` in COURSE_CATALOG (e.g. HACCP)
    # REQUIRE a specific region (not "NAZIONALE"). CourseRequest.region
    # defaults to "NAZIONALE", so this guard catches the wizard-default
    # case for a regional course (BP §05.4).
    if catalog_entry.get("regional") and request.region == "NAZIONALE":
        raise ValueError(
            f"Il tipo corso '{request.course_type}' richiede la specifica della regione "
            f"(es. 'LAZIO', 'LOMBARDIA'). Il valore 'NAZIONALE' non è valido per corsi regionali. "
            f"Selezionare una regione nel wizard prima di generare."
        )

    # 2. Build the RAG query embedding — SEMANTIC, not slug-based (D-20).
    #    Concatenate catalog title + default module names so the query is
    #    natural-language Italian (high cosine similarity with the indexed
    #    normative chunks).
    default_modules_raw = catalog_entry.get("default_modules", [])
    assert isinstance(default_modules_raw, list)
    default_modules: list[str] = [str(m) for m in default_modules_raw]
    title_str = str(catalog_entry["title"])
    query_parts = [title_str] + default_modules
    query = " ".join(query_parts)
    query_embedding = await voyage_embed_with_retry(query)

    # 3. Vector search with DYNAMIC top_k scaled by course duration.
    top_k = max(30, int(request.duration_hours * 10))  # 30 for 1h, 80 for 8h
    chunks = await knowledge_repo.search_chunks(
        query_embedding=query_embedding,
        regulation_ids=regulation_ids,
        region=request.region,
        top_k=top_k,
    )

    # ═══ RAG GATE: too few chunks → pipeline aborts ═══
    if len(chunks) < 5:
        raise ValueError(
            f"RAG insufficiente: solo {len(chunks)} chunk trovati per "
            f"{regulation_slugs}. Verificare che l'ingestion sia stata "
            f"completata correttamente per queste normative."
        )

    # ═══ RELEVANCE FILTER ═══
    chunks = [c for c in chunks if c.relevance_score and c.relevance_score > MIN_RELEVANCE]

    if len(chunks) < 5:
        raise ValueError(
            f"RAG post-filtro insufficiente: solo {len(chunks)} chunk con "
            f"rilevanza > {MIN_RELEVANCE}. Verificare la qualità degli embedding."
        )

    # 4. Pre-group chunks per module — semantic titles from COURSE_CATALOG
    module_titles = default_modules if default_modules else None
    pacing_plan = PacingEngine().calculate(
        request.duration_hours, request.slide_density, module_titles=module_titles
    )
    chunks_by_module = distribute_chunks_to_modules(chunks, pacing_plan)

    # 5. Retrieve stylistic patterns from Level 2
    style_patterns = await knowledge_repo.get_style_patterns(
        course_type=request.course_type,
        target=request.target.value,
    )

    # ═══ OUTPUT VALIDATION ═══
    context = CourseContext(
        chunks=chunks,
        chunks_by_module=chunks_by_module,
        pacing_plan=pacing_plan,
        style_patterns=style_patterns,
        regulation_ids=regulation_ids,
        regulation_slugs=regulation_slugs,
    )

    logger.info(
        "research_completed",
        chunks=len(chunks),
        top_k=top_k,
        modules=len(pacing_plan.modules),
        style_patterns=len(style_patterns),
    )

    return {
        "course_context": context.model_dump(),
        "pacing_plan": pacing_plan.model_dump(),
    }
