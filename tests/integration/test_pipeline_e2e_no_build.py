"""Pipeline E2E without the Production Builder (PHASE 3.5).

Two test layers:

1. PRIMARY (default suite) — ``test_pipeline_e2e_mocked``
   Fully mocked external dependencies (InMemorySaver instead of Postgres,
   stubbed Voyage, stubbed Anthropic, AsyncMock KnowledgeRepository).
   Exercises:
   - initial_state shaped per BP §05.2 (all 8 TypedDict fields)
   - create_pipeline() as async context manager (D18)
   - graph.ainvoke wrapped in asyncio.wait_for(timeout=PIPELINE_TIMEOUT)
   - reducer (operator.add on completed_modules) accumulates module output
   - checkpointer persists state (graph.aget_state returns final values)

2. LIVE (@pytest.mark.live — skipped by default) — ``test_pipeline_e2e_real``
   Skeleton that runs against real Postgres + Voyage + Anthropic + the
   real DM 388/2003 PDF when all resources are available. Skipped with a
   precise message when any prerequisite is missing.

The mocked test is what guards the default CI gate; the live test is the
manual smoke once VERIFICATION_DEBT.md resources #R1/#R2/#R3/#R4 are
fulfilled.
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.agents import content_agent as ca_mod
from app.agents import pipeline as pipeline_mod
from app.agents import research_agent as ra_mod
from app.agents.pipeline import create_pipeline
from app.config import settings
from app.models.core import ChunkType, SlideDensity, SlideType, TargetType
from app.models.knowledge import NormativeChunk
from app.services import dependencies as deps

REG_ID = "00000000-0000-0000-0000-000000000001"
CHUNK_ID = "11111111-1111-1111-1111-111111111111"
JOB_ID = "e2e-test-job-001"


# ─────────────── shared helpers ───────────────


def _initial_state() -> dict[str, Any]:
    """Build an initial_state dict matching NexusPipelineState BP §05.2 verbatim.

    All 8 fields present, types match the TypedDict (research_agent will
    rehydrate ``course_request`` into a Pydantic CourseRequest).
    """
    return {
        "course_request": {
            "course_type": "primo_soccorso_gruppo_b_c",
            "target": TargetType.DISCENTE.value,
            "duration_hours": 1.0,  # → 120 slides, 3 modules
            "region": "NAZIONALE",
            "brand_preset_id": "22222222-2222-2222-2222-222222222222",
            "slide_density": SlideDensity.STANDARD.value,
            "outputs": ["pptx", "pdf"],
        },
        "brand_config": {},
        "course_context": None,
        "pacing_plan": None,
        "completed_modules": [],
        "current_module_index": 0,
        "job_id": JOB_ID,
        "errors": [],
    }


def _fake_chunks(n: int = 40) -> list[NormativeChunk]:
    return [
        NormativeChunk(
            chunk_id=f"{CHUNK_ID[:-1]}{i % 10}",
            regulation_id=REG_ID,
            article=f"Art. {i + 1}",
            paragraph=None,
            hierarchy_path=f"Art. {i + 1}",
            body=f"Disposizione normativa di primo soccorso intervento {i}.",
            chunk_type=ChunkType.GENERALE,
            tags=["primo_soccorso"],
            relevance_score=0.8,
        )
        for i in range(n)
    ]


def _fake_llm_slides(module_index: int = 0) -> str:
    """Return a JSON array of valid SlideContent slides per LAYOUT_CONSTRAINTS (FASE 1).

    Body: 3 bullet brevi (≤6 max per CONTENT_TEXT).
    Speaker notes: 80 parole (range 75-90 per CONTENT_TEXT, 25-35s TTS).
    """
    long_notes = " ".join(["parola"] * 80)
    slides = [
        {
            "index": i,
            "module_index": module_index,
            "slide_type": SlideType.CONTENT_TEXT.value,
            "title": f"Slide {i} modulo {module_index}",
            "body": (
                "Primo bullet del contenuto\n"
                "Secondo bullet importante\n"
                "Terzo punto da memorizzare"
            ),
            "speaker_notes": long_notes,
            "normative_ref": "Art. 1, DM 388/2003",
            "source_chunk_ids": [CHUNK_ID],
            "image": {"strategy": "none"},
            "quiz_options": None,
            "quiz_correct": None,
        }
        for i in range(3)  # 3 slides per module → easy to assert >= 1
    ]
    return json.dumps(slides)


@asynccontextmanager
async def _fake_pg_saver(_conn_string: str) -> AsyncIterator[InMemorySaver]:
    yield InMemorySaver()


@pytest.fixture(autouse=True)
def _reset_pool() -> Any:
    yield
    deps._pool = None


# ─────────────── PRIMARY: fully mocked E2E ───────────────


async def test_pipeline_e2e_mocked() -> None:
    """Full 2-node pipeline runs under asyncio.wait_for with stubbed externals.

    Verifies: graph compiles, both nodes execute, reducer appends modules,
    checkpointer records the final state, timeout wrapper is respected.
    """
    deps.set_pool(AsyncMock())

    with patch.object(
        pipeline_mod.AsyncPostgresSaver, "from_conn_string", _fake_pg_saver
    ), patch.object(
        ra_mod.KnowledgeRepository, "resolve_slugs_to_ids",
        AsyncMock(return_value=[REG_ID, REG_ID]),
    ), patch.object(
        ra_mod, "voyage_embed_with_retry",
        AsyncMock(return_value=[0.1] * 1024),
    ), patch.object(
        ra_mod.KnowledgeRepository, "search_chunks",
        AsyncMock(return_value=_fake_chunks(40)),
    ), patch.object(
        ra_mod.KnowledgeRepository, "get_style_patterns",
        AsyncMock(return_value=[]),
    ), patch.object(
        ca_mod, "call_llm",
        AsyncMock(side_effect=lambda **_kw: _fake_llm_slides()),
    ):
        async with create_pipeline("postgresql://fake/url") as graph:
            config: dict[str, Any] = {"configurable": {"thread_id": JOB_ID}}
            result = await asyncio.wait_for(
                graph.ainvoke(_initial_state(), config),
                timeout=settings.pipeline_timeout,
            )

            # ─ structural assertions on the final state ─
            assert "completed_modules" in result
            assert "pacing_plan" in result
            assert "course_context" in result

            completed = result["completed_modules"]
            assert isinstance(completed, list)
            assert len(completed) >= 1, "at least one module must be produced"

            # at least one slide across all modules
            all_slides = [s for m in completed for s in m.get("slides", [])]
            assert len(all_slides) >= 1

            # the Content Agent advances current_module_index to len(modules)
            pacing = result["pacing_plan"]
            assert result["current_module_index"] == len(pacing["modules"])

            # ─ checkpoint persistence ─
            snapshot = await graph.aget_state(config)
            assert snapshot is not None
            # The persisted state must carry the same completed_modules count
            assert len(snapshot.values["completed_modules"]) == len(completed)


async def test_pipeline_e2e_respects_timeout_wrapper() -> None:
    """If a node hangs longer than the timeout, asyncio.wait_for raises."""
    deps.set_pool(AsyncMock())

    async def _hanging_research(_state: Any) -> dict[str, object]:
        await asyncio.sleep(5)
        return {"course_context": {}, "pacing_plan": {}}

    with patch.object(
        pipeline_mod.AsyncPostgresSaver, "from_conn_string", _fake_pg_saver
    ), patch.object(
        ra_mod, "research_agent", _hanging_research
    ):
        async with create_pipeline("postgresql://fake/url") as graph:
            config: dict[str, Any] = {"configurable": {"thread_id": "timeout-test"}}
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    graph.ainvoke(_initial_state(), config),
                    timeout=0.1,  # force a short timeout
                )


# ─────────────── LIVE: real Postgres + Voyage + Anthropic ───────────────


REAL_PDF = Path("storage/pdfs/dm388_03.pdf")


def _live_prereqs_missing() -> str | None:
    """Return a human-readable reason string if any prerequisite is missing."""
    if not REAL_PDF.is_file():
        return f"missing {REAL_PDF} (VERIFICATION_DEBT #R1)"
    if not os.getenv("DATABASE_URL"):
        return "missing DATABASE_URL env (VERIFICATION_DEBT #R2)"
    if not os.getenv("VOYAGE_API_KEY"):
        return "missing VOYAGE_API_KEY env (VERIFICATION_DEBT #R4)"
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "missing ANTHROPIC_API_KEY env (VERIFICATION_DEBT #R3)"
    return None


@pytest.mark.live
async def test_pipeline_e2e_real() -> None:
    """End-to-end pipeline against live Postgres + Voyage + Anthropic + real PDF.

    Skipped by default (``addopts = -m 'not live'`` in pyproject). Run
    explicitly with ``pytest -m live tests/integration/test_pipeline_e2e_no_build.py``
    when all four prerequisites are met.

    Manual setup (one-time per environment):
      1. docker compose up -d postgres
      2. apply db/migrations/001_initial.sql + setup_roles.sql
      3. python scripts/seed.py
      4. POST /api/regulations/upload of dm388_03.pdf as admin
      5. ensure .env has working ANTHROPIC_API_KEY + VOYAGE_API_KEY
    """
    missing = _live_prereqs_missing()
    if missing:
        pytest.skip(f"live prerequisites not met: {missing}")

    # The actual live invocation lives in the same shape as the mocked test:
    # no patching, real AsyncPostgresSaver via settings.database_url.
    # Kept minimal — the real value of this test is exercising the wiring
    # against real services, asserting that BP §05.4 + §05.5 work end-to-end.
    async with create_pipeline(settings.database_url) as graph:
        config: dict[str, Any] = {"configurable": {"thread_id": f"{JOB_ID}-live"}}
        result = await asyncio.wait_for(
            graph.ainvoke(_initial_state(), config),
            timeout=settings.pipeline_timeout,
        )

    assert result["completed_modules"], "live pipeline produced no modules"
