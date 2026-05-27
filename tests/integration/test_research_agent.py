"""Integration tests for research_agent (PHASE 3.3, BLUEPRINT §05.4).

Covers:
- Helpers (_keyword_overlap, _rebalance_min, _rebalance_max,
  distribute_chunks_to_modules) on synthetic chunks
- Full research_agent() flow with mocked pool + voyage + KnowledgeRepository:
  - happy path returns dict with course_context + pacing_plan
  - RAG gate < 5 chunks → ValueError
  - regional course + region="NAZIONALE" → ValueError (HACCP-shaped guard)
  - relevance filter strips chunks below MIN_RELEVANCE
  - dynamic top_k scales with duration_hours

No live DB / no live Voyage / no live Anthropic — pure orchestration test.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.agents import research_agent as ra
from app.agents.research_agent import (
    _keyword_overlap,
    _rebalance_max,
    _rebalance_min,
    distribute_chunks_to_modules,
    research_agent,
)
from app.models.core import ChunkType, SlideDensity, TargetType
from app.models.knowledge import NormativeChunk
from app.models.pipeline import ModuleSpec, PacingPlan
from app.services import dependencies as deps

REG_ID = "00000000-0000-0000-0000-000000000001"


def _chunk(body: str, *, cid: str = "c1", score: float = 0.8) -> NormativeChunk:
    return NormativeChunk(
        chunk_id=cid,
        regulation_id=REG_ID,
        article="Art. 1",
        hierarchy_path="Art. 1",
        body=body,
        chunk_type=ChunkType.GENERALE,
        tags=[],
        relevance_score=score,
    )


def _pacing_plan(num_modules: int, titles: list[str] | None = None) -> PacingPlan:
    titles = titles or [f"Modulo {i + 1}" for i in range(num_modules)]
    return PacingPlan(
        total_slides=40 * num_modules,
        modules=[
            ModuleSpec(
                module_index=i,
                title=titles[i],
                slide_count=40,
                slide_distribution={"CONTENT_TEXT": 40},
            )
            for i in range(num_modules)
        ],
    )


# ─────────── _keyword_overlap ───────────


def test_keyword_overlap_counts_shared_lowercased() -> None:
    assert _keyword_overlap("DPI obbligatori", "I DPI sono obbligatori") == 2
    assert _keyword_overlap("antincendio", "rischio elettrico") == 0
    assert _keyword_overlap("Concetti di rischio", "concetti generali") == 1


# ─────────── _rebalance_min / _rebalance_max ───────────


def test_rebalance_min_redistributes_to_underpopulated() -> None:
    # 12 chunks on module 0, 0 on the others. With min=3 and max=min+2=5,
    # rebalance moves chunks from 0 to 1 and 2 until donor stops being >5.
    result: dict[int, list[NormativeChunk]] = {
        0: [_chunk(f"a{i}", cid=f"a{i}") for i in range(12)],
        1: [],
        2: [],
    }
    _rebalance_min(result, min_per_module=3)
    assert all(len(v) >= 3 for v in result.values()), result
    assert sum(len(v) for v in result.values()) == 12  # no chunks lost


def test_rebalance_min_stops_when_no_donor_available() -> None:
    """If no module exceeds min+2, no rebalance happens (loop exits)."""
    result: dict[int, list[NormativeChunk]] = {
        0: [_chunk("a", cid="a")],
        1: [_chunk("b", cid="b")],
    }
    _rebalance_min(result, min_per_module=3)
    # No donor (nobody > 5), so under stays under — loop ended cleanly
    assert sum(len(v) for v in result.values()) == 2


def test_rebalance_max_caps_overpopulated() -> None:
    result: dict[int, list[NormativeChunk]] = {
        0: [_chunk(f"x{i}", cid=f"x{i}") for i in range(12)],
        1: [_chunk(f"y{i}", cid=f"y{i}") for i in range(2)],
        2: [_chunk(f"z{i}", cid=f"z{i}") for i in range(2)],
    }
    _rebalance_max(result, max_per_module=6)
    assert len(result[0]) <= 6


# ─────────── distribute_chunks_to_modules ───────────


def test_distribute_uses_round_robin_when_too_few_chunks() -> None:
    plan = _pacing_plan(3)
    chunks = [_chunk(f"c{i}", cid=f"c{i}") for i in range(4)]  # 4 < 3*3 → round-robin
    result = distribute_chunks_to_modules(chunks, plan)
    # 4 chunks across 3 modules round-robin → 2,1,1 distribution
    assert sum(len(v) for v in result.values()) == 4


def test_distribute_uses_semantic_overlap_when_enough_chunks() -> None:
    """Chunks whose body matches a module title gravitate to that module."""
    plan = _pacing_plan(2, titles=["antincendio", "primo soccorso"])
    chunks = (
        [_chunk(f"antincendio principi {i}", cid=f"fire{i}") for i in range(10)]
        + [_chunk(f"primo soccorso intervento {i}", cid=f"med{i}") for i in range(10)]
    )
    result = distribute_chunks_to_modules(chunks, plan)
    # Both modules receive most of their thematic chunks
    fire_module = result[0]
    med_module = result[1]
    assert any("antincendio" in c.body for c in fire_module)
    assert any("primo soccorso" in c.body for c in med_module)
    # All 20 chunks accounted for
    assert sum(len(v) for v in result.values()) == 20


def test_distribute_guarantees_min_three_per_module() -> None:
    """Even if a topic is rare, every module ends with ≥3 chunks (when enough)."""
    plan = _pacing_plan(2, titles=["antincendio", "soccorso"])
    # 20 chunks all matching only "antincendio" — without rebalance the
    # second module would be empty.
    chunks = [_chunk(f"antincendio principio {i}", cid=f"c{i}") for i in range(20)]
    result = distribute_chunks_to_modules(chunks, plan)
    assert all(len(v) >= 3 for v in result.values())


# ─────────── research_agent() full flow ───────────


def _state(
    *,
    course_type: str = "primo_soccorso_gruppo_b_c",
    duration_hours: float = 1.0,
    region: str = "NAZIONALE",
    target: TargetType = TargetType.DISCENTE,
) -> dict[str, Any]:
    """Build a NexusPipelineState-shaped dict (only fields research_agent reads)."""
    return {
        "course_request": {
            "course_type": course_type,
            "target": target.value,
            "duration_hours": duration_hours,
            "region": region,
            "brand_preset_id": "11111111-1111-1111-1111-111111111111",
            "slide_density": SlideDensity.STANDARD.value,
            "outputs": ["pptx", "pdf"],
        },
        "brand_config": {},
        "course_context": None,
        "pacing_plan": None,
        "completed_modules": [],
        "current_module_index": 0,
        "job_id": "job-test",
        "errors": [],
    }


@pytest.fixture(autouse=True)
def _reset_pool() -> Any:
    yield
    deps._pool = None


async def test_research_agent_happy_path_returns_context_and_pacing() -> None:
    """Full flow with enough chunks returns both fields the node owns."""
    deps.set_pool(AsyncMock())

    fake_chunks = [
        _chunk(f"primo soccorso intervento corpo {i}", cid=f"c{i}", score=0.85)
        for i in range(40)
    ]

    with patch.object(
        ra.KnowledgeRepository, "resolve_slugs_to_ids",
        AsyncMock(return_value=[REG_ID, REG_ID]),
    ), patch.object(
        ra, "voyage_embed_with_retry",
        AsyncMock(return_value=[0.1] * 1024),
    ), patch.object(
        ra.KnowledgeRepository, "search_chunks",
        AsyncMock(return_value=fake_chunks),
    ), patch.object(
        ra.KnowledgeRepository, "get_style_patterns",
        AsyncMock(return_value=[]),
    ):
        result = await research_agent(_state(duration_hours=12.0))

    assert "course_context" in result
    assert "pacing_plan" in result
    # Only these two keys (langgraph fix-state-must-return-dict)
    assert set(result.keys()) == {"course_context", "pacing_plan"}


async def test_research_agent_rag_gate_raises_below_5_chunks() -> None:
    deps.set_pool(AsyncMock())
    few_chunks = [_chunk("solo uno", cid="c1")]

    with patch.object(
        ra.KnowledgeRepository, "resolve_slugs_to_ids",
        AsyncMock(return_value=[REG_ID, REG_ID]),
    ), patch.object(
        ra, "voyage_embed_with_retry",
        AsyncMock(return_value=[0.1] * 1024),
    ), patch.object(
        ra.KnowledgeRepository, "search_chunks",
        AsyncMock(return_value=few_chunks),
    ):
        with pytest.raises(ValueError, match="RAG insufficiente"):
            await research_agent(_state())


async def test_research_agent_regional_course_rejects_nazionale() -> None:
    """HACCP (regional=True) with region='NAZIONALE' must raise (BP §05.4).

    resolve_slugs must be mocked to succeed — the regional guard fires
    AFTER slug resolution in BP §05.4 (step 1: slugs, step 2: regional).
    """
    deps.set_pool(AsyncMock())
    with patch.object(
        ra.KnowledgeRepository, "resolve_slugs_to_ids",
        AsyncMock(return_value=[REG_ID]),
    ):
        with pytest.raises(ValueError, match="regional"):
            await research_agent(
                _state(course_type="haccp_addetto", region="NAZIONALE")
            )


async def test_research_agent_regional_course_accepts_specific_region() -> None:
    """HACCP with region='CAMPANIA' must NOT raise the regional guard."""
    deps.set_pool(AsyncMock())

    fake_chunks = [
        _chunk(f"haccp igiene alimentare corpo {i}", cid=f"c{i}", score=0.85)
        for i in range(20)
    ]
    with patch.object(
        ra.KnowledgeRepository, "resolve_slugs_to_ids",
        AsyncMock(return_value=[REG_ID]),
    ), patch.object(
        ra, "voyage_embed_with_retry",
        AsyncMock(return_value=[0.1] * 1024),
    ), patch.object(
        ra.KnowledgeRepository, "search_chunks",
        AsyncMock(return_value=fake_chunks),
    ), patch.object(
        ra.KnowledgeRepository, "get_style_patterns",
        AsyncMock(return_value=[]),
    ):
        result = await research_agent(
            _state(course_type="haccp_addetto", region="CAMPANIA", duration_hours=4.0)
        )

    assert "course_context" in result


async def test_research_agent_relevance_filter_strips_low_score() -> None:
    """Chunks with relevance ≤ 0.3 are dropped; if too few remain → ValueError."""
    deps.set_pool(AsyncMock())
    # 6 chunks above threshold (passes initial gate of 5), but only 4 pass filter
    fake_chunks = (
        [_chunk(f"high {i}", cid=f"h{i}", score=0.7) for i in range(4)]
        + [_chunk(f"low {i}", cid=f"l{i}", score=0.1) for i in range(2)]
    )
    with patch.object(
        ra.KnowledgeRepository, "resolve_slugs_to_ids",
        AsyncMock(return_value=[REG_ID, REG_ID]),
    ), patch.object(
        ra, "voyage_embed_with_retry",
        AsyncMock(return_value=[0.1] * 1024),
    ), patch.object(
        ra.KnowledgeRepository, "search_chunks",
        AsyncMock(return_value=fake_chunks),
    ):
        with pytest.raises(ValueError, match="post-filtro insufficiente"):
            await research_agent(_state())


async def test_research_agent_top_k_scales_with_duration() -> None:
    """top_k = max(30, duration_hours * 10) — 8h → 80, 1h → 30."""
    deps.set_pool(AsyncMock())
    fake_chunks = [
        _chunk(f"corpo {i}", cid=f"c{i}", score=0.85) for i in range(40)
    ]
    search_mock = AsyncMock(return_value=fake_chunks)

    with patch.object(
        ra.KnowledgeRepository, "resolve_slugs_to_ids",
        AsyncMock(return_value=[REG_ID, REG_ID]),
    ), patch.object(
        ra, "voyage_embed_with_retry",
        AsyncMock(return_value=[0.1] * 1024),
    ), patch.object(
        ra.KnowledgeRepository, "search_chunks", search_mock,
    ), patch.object(
        ra.KnowledgeRepository, "get_style_patterns",
        AsyncMock(return_value=[]),
    ):
        await research_agent(_state(duration_hours=8.0))

    # search_chunks called with top_k=80 (kwarg)
    assert search_mock.await_args.kwargs["top_k"] == 80
