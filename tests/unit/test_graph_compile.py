"""Unit tests for the LangGraph pipeline (PHASE 3.1).

Verifies:
- NexusPipelineState exposes the 8 BP §05.2 fields with correct reducers
- create_pipeline() compiles to exactly 2 nodes (research + content) — FIX-1 v2.0
- Edges form the linear flow START -> research -> content -> END
- The Postgres checkpointer is wired (mocked here so no live DB is needed)

The AsyncPostgresSaver.from_conn_string call is patched to yield an
InMemorySaver — same checkpointer protocol, no Postgres connection. This
covers structural correctness; live PG checkpoint integration is in
VERIFICATION_DEBT #R2.
"""

from __future__ import annotations

import operator
from contextlib import asynccontextmanager
from typing import AsyncIterator, get_type_hints
from unittest.mock import patch

from langgraph.checkpoint.memory import InMemorySaver

from app.agents import pipeline as pipeline_mod
from app.agents.pipeline import NexusPipelineState, create_pipeline


# ─────────────── NexusPipelineState shape ───────────────


EXPECTED_FIELDS = {
    "course_request",
    "brand_config",
    "course_context",
    "pacing_plan",
    "completed_modules",
    "current_module_index",
    "job_id",
    "errors",
}


def test_state_has_exactly_bp_05_2_fields() -> None:
    """The TypedDict must carry the 8 fields BP §05.2 lists, no more, no less."""
    assert set(NexusPipelineState.__annotations__.keys()) == EXPECTED_FIELDS


def test_state_omits_post_pipeline_fields() -> None:
    """pptx_path / pdf_path / generation_report MUST NOT be in the state.

    BP §05.2 forbids them — the Production Builder is post-pipeline (FIX-1).
    """
    forbidden = {"pptx_path", "pdf_path", "generation_report", "audio_manifest_path"}
    assert not (forbidden & set(NexusPipelineState.__annotations__.keys()))


def test_completed_modules_has_add_reducer() -> None:
    """completed_modules MUST use operator.add (langgraph-fundamentals fix-forgot-reducer)."""
    hints = get_type_hints(NexusPipelineState, include_extras=True)
    metadata = hints["completed_modules"].__metadata__  # type: ignore[attr-defined]
    assert operator.add in metadata


def test_errors_has_add_reducer() -> None:
    hints = get_type_hints(NexusPipelineState, include_extras=True)
    metadata = hints["errors"].__metadata__  # type: ignore[attr-defined]
    assert operator.add in metadata


# ─────────────── create_pipeline() shape ───────────────


@asynccontextmanager
async def _fake_pg_saver(_conn_string: str) -> AsyncIterator[InMemorySaver]:
    """Replacement for AsyncPostgresSaver.from_conn_string in tests.

    Yields an InMemorySaver — same checkpointer protocol, no Postgres needed.
    """
    yield InMemorySaver()


async def test_graph_compiles_with_two_nodes_and_linear_edges() -> None:
    """The compiled graph has EXACTLY research + content, wired START->research->content->END."""
    with patch.object(
        pipeline_mod.AsyncPostgresSaver, "from_conn_string", _fake_pg_saver
    ):
        async with create_pipeline("postgresql://fake/url") as graph:
            g = graph.get_graph()

            # 4 logical nodes: START, research, content, END (langgraph prefixes
            # the implicit start/end with __start__ / __end__).
            node_names = set(g.nodes.keys())
            assert "research" in node_names
            assert "content" in node_names

            # FIX-1 v2.0: the two user-defined nodes are EXACTLY research + content
            user_nodes = node_names - {"__start__", "__end__"}
            assert user_nodes == {"research", "content"}, (
                f"Graph must have ONLY research + content nodes, found: {user_nodes}"
            )

            # Linear edges: START -> research -> content -> END
            edge_pairs = {(e.source, e.target) for e in g.edges}
            assert ("__start__", "research") in edge_pairs
            assert ("research", "content") in edge_pairs
            assert ("content", "__end__") in edge_pairs


async def test_graph_uses_checkpointer() -> None:
    """The compiled graph must wire the checkpointer (BP §05.3 + langgraph-persistence)."""
    with patch.object(
        pipeline_mod.AsyncPostgresSaver, "from_conn_string", _fake_pg_saver
    ):
        async with create_pipeline("postgresql://fake/url") as graph:
            assert graph.checkpointer is not None
            assert isinstance(graph.checkpointer, InMemorySaver)


def test_create_pipeline_is_async_context_manager() -> None:
    """create_pipeline is an @asynccontextmanager (REI-16 D18 — diverges from BP §05.3 literal)."""
    # An @asynccontextmanager-decorated function exposes __wrapped__ on the
    # generator factory; calling it returns an _AsyncGeneratorContextManager.
    result = create_pipeline("postgresql://fake/url")
    assert hasattr(result, "__aenter__")
    assert hasattr(result, "__aexit__")
