"""Unit tests for Pydantic models (BLUEPRINT §04).

Coverage:
- core enums basic identity
- CourseRequest happy path + validators (outputs whitelist, duration_hours bounds)
- CourseResponse happy path
- NormativeChunk happy path
- StylePattern happy path + anti-poisoning structural assertion
- SlideContent body soft-truncation (logged, not raised)
- PacingPlan / ModuleSpec / ModuleContent / CourseContext / GenerationReport happy path
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.core import ChunkType, SlideDensity, SlideType, TargetType
from app.models.knowledge import NormativeChunk, StylePattern
from app.models.pipeline import (
    CourseContext,
    GenerationReport,
    ImageStrategy,
    ModuleContent,
    ModuleSpec,
    PacingPlan,
    SlideContent,
)
from app.models.requests import CourseRequest, CourseResponse


# ───────────────────────────── core ─────────────────────────────


def test_core_enums_values() -> None:
    assert TargetType.DISCENTE.value == "discente"
    assert SlideDensity.STANDARD.value == "standard"
    assert SlideType.CONTENT_TEXT.value == "CONTENT_TEXT"
    assert ChunkType.OBBLIGO.value == "OBBLIGO"


# ─────────────────────── CourseRequest ──────────────────────────


def _valid_request_kwargs() -> dict[str, object]:
    return {
        "course_type": "sicurezza_lavoratori_generale",
        "target": TargetType.DISCENTE,
        "duration_hours": 4.0,
        "brand_preset_id": "uuid-brand",
    }


def test_course_request_happy_path() -> None:
    req = CourseRequest(**_valid_request_kwargs())  # type: ignore[arg-type]
    assert req.region == "NAZIONALE"
    assert req.slide_density == SlideDensity.STANDARD
    assert req.outputs == ["pptx", "pdf"]


def test_course_request_audio_output_allowed() -> None:
    """v3.0 GAP-3: 'audio' must be accepted in outputs."""
    req = CourseRequest(outputs=["pptx", "pdf", "audio"], **_valid_request_kwargs())  # type: ignore[arg-type]
    assert "audio" in req.outputs


def test_course_request_rejects_unknown_output() -> None:
    with pytest.raises(ValidationError) as exc:
        CourseRequest(outputs=["pptx", "docx"], **_valid_request_kwargs())  # type: ignore[arg-type]
    assert "unknown output" in str(exc.value)


def test_course_request_rejects_empty_outputs() -> None:
    with pytest.raises(ValidationError) as exc:
        CourseRequest(outputs=[], **_valid_request_kwargs())  # type: ignore[arg-type]
    assert "empty" in str(exc.value)


def test_course_request_duration_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        CourseRequest(
            course_type="x",
            target=TargetType.DISCENTE,
            duration_hours=0,
            brand_preset_id="b",
        )


def test_course_request_duration_capped_at_16() -> None:
    with pytest.raises(ValidationError):
        CourseRequest(
            course_type="x",
            target=TargetType.DISCENTE,
            duration_hours=17,
            brand_preset_id="b",
        )


def test_course_response_happy_path() -> None:
    resp = CourseResponse(
        course_id="c",
        job_id="j",
        estimated_slides=120,
        estimated_minutes=60.0,
    )
    assert resp.queue_position == 0


# ───────────────────────── knowledge ────────────────────────────


def test_normative_chunk_happy_path() -> None:
    c = NormativeChunk(
        chunk_id="ch1",
        regulation_id="r1",
        hierarchy_path="Art. 1 § 2",
        body="Il datore di lavoro deve...",
        chunk_type=ChunkType.OBBLIGO,
    )
    assert c.tags == []
    assert c.relevance_score is None


def test_style_pattern_happy_path() -> None:
    sp = StylePattern(
        avg_words_per_slide=42,
        preferred_slide_sequence=["CONTENT_TEXT", "QUIZ", "RECAP"],
        tone_register="tecnico-divulgativo",
        recurring_section_titles=["Introduzione", "Obblighi"],
        avg_quiz_per_module=1.5,
        preferred_image_ratio=0.20,
    )
    assert sp.avg_words_per_slide == 42


def test_style_pattern_has_no_text_block_fields() -> None:
    """Anti-poisoning structural assertion (BP §04.3).

    No field on StylePattern may be a free-form text block. Allowed text-bearing
    fields are short, structured strings (tone_register) and lists of short
    titles. The presence of a field whose name suggests free text (body, content,
    excerpt, paragraph, sentence) would break the anti-Model-Collapse barrier.
    """
    forbidden_substrings = ("body", "content", "excerpt", "paragraph", "sentence")
    field_names = set(StylePattern.model_fields.keys())
    leaks = [
        name
        for name in field_names
        if any(forbidden in name.lower() for forbidden in forbidden_substrings)
    ]
    assert not leaks, f"StylePattern leaks free-text fields: {leaks}"


# ─────────────────────── SlideContent ───────────────────────────


# FASE 1 vast-hopping-sketch — i 3 test "soft-truncate" pre-esistenti sono stati
# riscritti per testare il nuovo strict reject (no truncation). Per i casi
# completi vedi tests/unit/test_slide_constraints.py.


def test_slide_content_valid_passes_strict_validator() -> None:
    """Slide CONTENT_TEXT entro LAYOUT_CONSTRAINTS → istanziabile, niente '…'."""
    from tests._helpers import make_slide

    slide = make_slide(SlideType.CONTENT_TEXT)
    assert slide.bullets, "CONTENT_TEXT deve avere bullets"
    assert not any(b.endswith("…") for b in slide.bullets)
    assert slide.slide_type == SlideType.CONTENT_TEXT


def test_slide_content_body_over_limit_is_rejected_strict() -> None:
    """FASE 1: CONTENT_TEXT body > 6 bullets → ValueError (no truncation)."""
    from tests._helpers import make_slide

    too_many_bullets = "\n".join(f"bullet {i}" for i in range(7))
    with pytest.raises(ValidationError):
        make_slide(SlideType.CONTENT_TEXT, body=too_many_bullets)


def test_slide_content_title_max_length_enforced() -> None:
    """FASE 1: title > 70 char (CONTENT_TEXT default) → rigettato dal validator."""
    from tests._helpers import make_slide

    with pytest.raises(ValidationError):
        make_slide(SlideType.CONTENT_TEXT, title="x" * 71)


# ───────────────── PacingPlan / ModuleContent / Context ─────────


def test_pacing_plan_and_module_content() -> None:
    spec = ModuleSpec(
        module_index=0,
        title="Modulo 1",
        slide_count=10,
        slide_distribution={"CONTENT_TEXT": 8, "QUIZ": 1, "RECAP": 1},
    )
    plan = PacingPlan(total_slides=10, modules=[spec])
    assert plan.total_slides == 10
    assert plan.modules[0].slide_distribution["QUIZ"] == 1

    module_content = ModuleContent(module_index=0, title="Modulo 1", slides=[])
    assert module_content.slides == []


def test_course_context_happy_path() -> None:
    plan = PacingPlan(total_slides=0, modules=[])
    ctx = CourseContext(
        chunks=[],
        chunks_by_module={},
        pacing_plan=plan,
        style_patterns=[],
        regulation_ids=[],
        regulation_slugs=[],
    )
    assert ctx.regulation_ids == []


def test_image_strategy_defaults() -> None:
    img = ImageStrategy()
    assert img.strategy == "none"
    assert img.query is None


def test_generation_report_happy_path() -> None:
    rep = GenerationReport(
        total_slides=120,
        slides_with_images=20,
        slides_with_diagrams=0,
        quiz_count=12,
        modules_completed=4,
        modules_failed=0,
        normative_refs_count=80,
        generation_time_seconds=42.5,
    )
    assert rep.warnings == []
    assert rep.truncation_warnings == []
