"""LangGraph pipeline state + graph (BLUEPRINT §05.2 / §05.3).

PHASE 3.1 — defines NexusPipelineState (the ONLY TypedDict of the project,
per CLAUDE.md) and the compiled graph factory.

═══ ARCHITECTURAL CONSTRAINT (FIX-1 v2.0) ═══
The graph has EXACTLY 2 nodes: research + content. The Production Builder
(PPTX/PDF/Audio) is a POST-PIPELINE function called from generation_service
in PHASE 5, NOT a graph node. Do NOT add a third node (e.g. "finalize" or
"build"). Doing so is a hard architectural error.

═══ ARCHITECTURAL CONSTRAINT (state shape) ═══
Per BP §05.2 the state intentionally OMITS pptx_path / pdf_path / generation_report:
those live in the DB (courses table), not in the graph state. If they were
here, a future maintainer would be tempted to add a third node to populate
them — see FIX-1 above.

═══ DISCREPANCY vs BP §05.3 (REI-16 D18) ═══
BP §05.3 writes ``checkpointer = AsyncPostgresSaver.from_conn_string(database_url)``
as if it returned the saver directly. In langgraph-checkpoint-postgres 3.1.0,
``from_conn_string`` is an ``@asynccontextmanager`` that yields the saver and
closes the underlying connection on exit. ``create_pipeline`` is therefore an
``@asynccontextmanager`` itself — callers (FASE 5 generation_service) must
``async with create_pipeline(url) as graph:``. This matches the documented
production pattern in langgraph-persistence skill (``ex-production-postgres``).

═══ DEPLOY NOTE (langgraph-persistence skill) ═══
``AsyncPostgresSaver(...).setup()`` must be run ONCE at deploy time (not at
every app startup) to create the ``checkpoints`` / ``checkpoint_writes`` /
``checkpoint_migrations`` tables. setup_roles.sql (FASE 1) already contains
the deferred GRANT block for those tables.
"""

from __future__ import annotations

import operator
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator, TypedDict

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

# Note: research_agent and content_agent are imported inside create_pipeline()
# to avoid a circular import — both agent modules need NexusPipelineState
# from this file.


class NexusPipelineState(TypedDict):
    """The ONLY TypedDict of the project (BP §05.2).

    LangGraph requires TypedDict for state — Pydantic BaseModel is not
    supported here. Validation happens at the boundaries of each node by
    rehydrating ``state["course_request"]`` -> ``CourseRequest``, etc.

    Reducers (``Annotated[..., operator.add]``) ensure that node returns
    APPEND rather than overwrite. Without them, the second node's return
    would clobber the first node's contribution (langgraph-fundamentals
    skill, ``fix-forgot-reducer-for-list``).
    """

    # Input (validated with CourseRequest / brand dict)
    course_request: dict[str, object]
    brand_config: dict[str, object]

    # Research Agent output (validated with CourseContext + PacingPlan)
    course_context: dict[str, object] | None
    pacing_plan: dict[str, object] | None

    # Content Agent output — reducer-appended across module iterations
    completed_modules: Annotated[list[dict[str, object]], operator.add]
    current_module_index: int

    # Metadata
    job_id: str
    errors: Annotated[list[str], operator.add]


@asynccontextmanager
async def create_pipeline(
    database_url: str,
    *,
    stop_before_content: bool = False,
) -> AsyncIterator[CompiledStateGraph[NexusPipelineState, None, NexusPipelineState, NexusPipelineState]]:
    """Build and compile the 2-node LangGraph pipeline with PG checkpointing.

    Usage (FASE 5 generation_service)::

        async with create_pipeline(settings.database_url) as graph:
            result = await graph.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": job_id}},
            )

    ``stop_before_content`` (D3, vast-hopping-sketch): when True, compile with
    ``interrupt_before=["content"]`` so the graph HALTS after ``research`` and
    before ``content``. This is a human-in-the-loop STOP for the skeleton
    validation gate — NOT a third node (the graph stays research→content per the
    blueprint invariant). The orchestrator (generation_service) generates the
    skeleton, persists it, and stops; on approval it resumes ``content`` via
    ``aupdate_state(..., as_node="research")`` + ``ainvoke(None, config)`` so the
    edited skeleton's chunks (not the checkpoint's stale ones) drive content.
    With False the behavior is exactly today's (flag-off path unchanged).

    The ``async with`` is mandatory: it owns the underlying psycopg
    connection used by the checkpointer (REI-16 D18).
    """
    # Lazy import to break the agents -> pipeline -> agents cycle
    # (agent modules type-annotate state as NexusPipelineState).
    from app.agents.content_agent import content_agent
    from app.agents.research_agent import research_agent

    async with AsyncPostgresSaver.from_conn_string(database_url) as checkpointer:
        builder = StateGraph(NexusPipelineState)
        builder.add_node("research", research_agent)
        builder.add_node("content", content_agent)
        builder.set_entry_point("research")
        builder.add_edge("research", "content")
        builder.set_finish_point("content")
        if stop_before_content:
            yield builder.compile(
                checkpointer=checkpointer, interrupt_before=["content"]
            )
        else:
            yield builder.compile(checkpointer=checkpointer)
