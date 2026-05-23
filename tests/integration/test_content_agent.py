"""Integration tests for content_agent (PHASE 3.4, BLUEPRINT §05.5 + FIX-3).

Mocked Anthropic via patch on app.services.ingestion_service.call_llm
(which app.agents.content_agent re-imports — D10).

Coverage:
- parse_slides_json: clean array / fenced / non-list / malformed
- prompts: target-differentiated system + module-prompt
- content_agent happy path: completed_modules populated, no exceptions
- JSON corrective retry: first call invalid, second call valid → recovered
- Circuit breaker INLINE: >50% failures → RuntimeError("Circuit breaker")
- FIX-3 structural guard: no "class ModuleCircuitBreaker" anywhere
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.agents import content_agent as ca
from app.agents.content_agent import content_agent, parse_slides_json
from app.agents.prompts import (
    SYSTEM_PROMPT_DISCENTE,
    SYSTEM_PROMPT_FORMATORE,
    build_content_system_prompt,
    build_module_prompt,
    build_previous_summary,
)
from app.models.core import ChunkType, SlideDensity, SlideType, TargetType
from app.models.knowledge import NormativeChunk, StylePattern
from app.models.pipeline import (
    CourseContext,
    ModuleSpec,
    PacingPlan,
)

REG_ID = "00000000-0000-0000-0000-000000000001"
CHUNK_ID = "11111111-1111-1111-1111-111111111111"


# ─────────── parse_slides_json ───────────


def test_parse_slides_json_accepts_plain_array() -> None:
    raw = json.dumps([{"a": 1}, {"b": 2}])
    assert parse_slides_json(raw) == [{"a": 1}, {"b": 2}]


def test_parse_slides_json_strips_markdown_fence() -> None:
    raw = "```json\n[{\"x\": 42}]\n```"
    assert parse_slides_json(raw) == [{"x": 42}]


def test_parse_slides_json_rejects_object_top_level() -> None:
    raw = json.dumps({"not": "a list"})
    assert parse_slides_json(raw) is None


def test_parse_slides_json_rejects_malformed() -> None:
    assert parse_slides_json("not json at all {") is None


# ─────────── prompts ───────────


def test_build_content_system_prompt_picks_target() -> None:
    assert build_content_system_prompt(TargetType.DISCENTE) == SYSTEM_PROMPT_DISCENTE
    assert build_content_system_prompt(TargetType.FORMATORE) == SYSTEM_PROMPT_FORMATORE


def test_module_prompt_appends_formatore_instructions() -> None:
    module = ModuleSpec(
        module_index=0, title="DPI", slide_count=5, slide_distribution={"CONTENT_TEXT": 5}
    )
    chunks: list[NormativeChunk] = []
    prompt_disc = build_module_prompt(module, chunks, [], "Nessun modulo precedente.", TargetType.DISCENTE)
    prompt_form = build_module_prompt(module, chunks, [], "Nessun modulo precedente.", TargetType.FORMATORE)
    assert "ISTRUZIONI AGGIUNTIVE PER FORMATORE" not in prompt_disc
    assert "ISTRUZIONI AGGIUNTIVE PER FORMATORE" in prompt_form


def test_module_prompt_includes_style_pattern_when_present() -> None:
    sp = StylePattern(
        avg_words_per_slide=70,
        preferred_slide_sequence=["CONTENT_TEXT", "QUIZ"],
        tone_register="tecnico-divulgativo",
        recurring_section_titles=["Introduzione"],
        avg_quiz_per_module=1.0,
        preferred_image_ratio=0.2,
    )
    module = ModuleSpec(
        module_index=0, title="X", slide_count=1, slide_distribution={"CONTENT_TEXT": 1}
    )
    prompt = build_module_prompt(module, [], [sp], "Nessun modulo precedente.", TargetType.DISCENTE)
    assert "PATTERN STILISTICI" in prompt
    assert "tecnico-divulgativo" in prompt


def test_build_previous_summary_empty() -> None:
    assert build_previous_summary([]) == "Nessun modulo precedente."


def test_build_previous_summary_lists_titles() -> None:
    completed = [
        {
            "module_index": 0,
            "title": "Modulo 1",
            "slides": [{"title": "Intro"}, {"title": "Concetti base"}],
        }
    ]
    summary = build_previous_summary(completed)
    assert "Modulo 0" in summary
    assert "Intro" in summary
    assert "Concetti base" in summary


# ─────────── content_agent flow helpers ───────────


def _chunk(body: str) -> NormativeChunk:
    return NormativeChunk(
        chunk_id=CHUNK_ID,
        regulation_id=REG_ID,
        article="Art. 1",
        hierarchy_path="Art. 1",
        body=body,
        chunk_type=ChunkType.GENERALE,
        tags=[],
        relevance_score=0.8,
    )


def _module(idx: int, title: str = "Modulo") -> ModuleSpec:
    return ModuleSpec(
        module_index=idx,
        title=title,
        slide_count=2,
        slide_distribution={"CONTENT_TEXT": 2},
    )


def _slide_json(index: int, module_index: int = 0) -> dict[str, Any]:
    return {
        "index": index,
        "module_index": module_index,
        "slide_type": SlideType.CONTENT_TEXT.value,
        "title": f"Slide {index}",
        "body": "Corpo della slide entro i limiti delle 90 parole.",
        "speaker_notes": "",
        "normative_ref": "Art. 1, D.Lgs 81/08",
        "source_chunk_ids": [CHUNK_ID],
        "image": {"strategy": "none"},
        "quiz_options": None,
        "quiz_correct": None,
    }


def _state(num_modules: int) -> dict[str, Any]:
    modules = [_module(i) for i in range(num_modules)]
    plan = PacingPlan(total_slides=num_modules * 2, modules=modules)
    ctx = CourseContext(
        chunks=[_chunk("corpo")],
        chunks_by_module={i: [_chunk("corpo")] for i in range(num_modules)},
        pacing_plan=plan,
        style_patterns=[],
        regulation_ids=[REG_ID],
        regulation_slugs=["dlgs_81_08"],
    )
    return {
        "course_request": {
            "course_type": "sicurezza_lavoratori_generale",
            "target": TargetType.DISCENTE.value,
            "duration_hours": 1.0,
            "region": "NAZIONALE",
            "brand_preset_id": "22222222-2222-2222-2222-222222222222",
            "slide_density": SlideDensity.STANDARD.value,
            "outputs": ["pptx", "pdf"],
        },
        "brand_config": {},
        "course_context": ctx.model_dump(),
        "pacing_plan": plan.model_dump(),
        "completed_modules": [],
        "current_module_index": 0,
        "job_id": "job-test",
        "errors": [],
    }


# ─────────── content_agent happy path ───────────


async def test_content_agent_happy_path_returns_completed_modules() -> None:
    """3 modules, LLM returns valid JSON for each → 3 completed modules."""
    state = _state(num_modules=3)

    def _ok_response(*_a: Any, **_k: Any) -> str:
        return json.dumps([_slide_json(0), _slide_json(1)])

    with patch.object(ca, "call_llm", AsyncMock(side_effect=_ok_response)):
        result = await content_agent(state)

    assert set(result.keys()) == {"completed_modules", "current_module_index"}
    completed = result["completed_modules"]
    assert isinstance(completed, list)
    assert len(completed) == 3
    assert result["current_module_index"] == 3


# ─────────── JSON corrective retry ───────────


async def test_content_agent_corrective_retry_recovers_invalid_json() -> None:
    """First LLM call malformed, second (correction prompt) valid → module saved."""
    state = _state(num_modules=1)
    valid_payload = json.dumps([_slide_json(0)])
    # 2 LLM calls per module: first malformed, second valid via correction
    responses = ["not json at all {", valid_payload]
    call_mock = AsyncMock(side_effect=responses)

    with patch.object(ca, "call_llm", call_mock):
        result = await content_agent(state)

    assert len(result["completed_modules"]) == 1  # type: ignore[arg-type]
    assert call_mock.await_count == 2


# ─────────── Circuit breaker INLINE (FIX-3) ───────────


async def test_content_agent_circuit_breaker_trips_above_50_percent() -> None:
    """4 modules, 3 fail → 3/4 = 75% > 50% → RuntimeError."""
    state = _state(num_modules=4)

    # First 3 modules fail (call_llm raises), 4th would succeed but breaker
    # triggers at the END of the loop — so we need ≥3 failures out of 4.
    # Each failure costs 1 await (the first call_llm raises, parse_slides_json
    # path isn't reached for those modules).
    responses: list[Any] = [
        RuntimeError("api boom 1"),
        RuntimeError("api boom 2"),
        RuntimeError("api boom 3"),
        json.dumps([_slide_json(0)]),
    ]
    call_mock = AsyncMock(side_effect=responses)

    with patch.object(ca, "call_llm", call_mock):
        with pytest.raises(RuntimeError, match="Circuit breaker"):
            await content_agent(state)


async def test_content_agent_circuit_breaker_does_not_trip_at_exactly_50_percent() -> None:
    """2 of 4 modules fail → 50% exactly → strict > comparator does NOT trip."""
    state = _state(num_modules=4)
    valid_payload = json.dumps([_slide_json(0)])
    responses: list[Any] = [
        RuntimeError("boom 1"),
        valid_payload,
        RuntimeError("boom 2"),
        valid_payload,
    ]
    call_mock = AsyncMock(side_effect=responses)

    with patch.object(ca, "call_llm", call_mock):
        result = await content_agent(state)  # MUST NOT raise

    # Only the 2 successful modules end up in completed_modules
    assert len(result["completed_modules"]) == 2  # type: ignore[arg-type]


# ─────────── FIX-3 structural guard ───────────


def test_no_circuit_breaker_class_anywhere() -> None:
    """FIX-3 + karpathy rule #2: no separate class for the breaker.

    Greps the agents package for any ``class .*[Cc]ircuit[Bb]reaker``
    definition. Also confirms no ``circuit_breaker.py`` module exists.
    """
    agents_dir = Path(__file__).resolve().parents[2] / "app" / "agents"

    # No circuit_breaker module
    assert not (agents_dir / "circuit_breaker.py").exists(), (
        "FIX-3 violation: agents/circuit_breaker.py exists. Inline counter required."
    )

    # No `class XxxCircuitBreaker` DEFINED anywhere under app/agents/.
    # Match only top-level / module-level class definitions (start of line
    # after optional whitespace); mentions inside docstrings / comments are
    # allowed (the FIX-3 docstring itself references the forbidden name).
    forbidden = re.compile(r"^[ \t]*class\s+\w*[Cc]ircuit[Bb]reaker\b", re.MULTILINE)
    for py_file in agents_dir.rglob("*.py"):
        src = py_file.read_text(encoding="utf-8")
        # Strip docstrings/comments to avoid false positives on FIX-3 mentions
        stripped = re.sub(r'""".*?"""', "", src, flags=re.DOTALL)
        stripped = re.sub(r"'''.*?'''", "", stripped, flags=re.DOTALL)
        stripped = re.sub(r"#[^\n]*", "", stripped)
        assert not forbidden.search(stripped), (
            f"FIX-3 violation in {py_file.name}: "
            f"a CircuitBreaker class is defined. Use inline failed_count: int."
        )
