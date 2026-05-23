"""Pipeline contracts (BLUEPRINT §04.4).

NexusPipelineState (TypedDict) lives in ``app.agents.pipeline`` (PHASE 3),
NOT here. This file holds only Pydantic models.

Only import-path differs from BP §04.4: ``app.models.*`` instead of ``models.*``.
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, Field, field_validator

from app.models.core import SlideType
from app.models.knowledge import NormativeChunk, StylePattern

logger = structlog.get_logger()


class ImageStrategy(BaseModel):
    """Strategy for the visual support of a slide.

    ``diagram_code`` is inline SVG (NOT Mermaid). Generated directly by the LLM.
    """

    strategy: str = "none"  # "none" | "web_search" | "diagram"
    query: str | None = None
    query_url: str | None = None
    diagram_code: str | None = None  # inline SVG (rectangles + arrows + text)


class SlideContent(BaseModel):
    """Single-slide content produced by the Content Agent."""

    index: int
    module_index: int
    slide_type: SlideType
    title: str = Field(..., max_length=80)
    body: str
    speaker_notes: str = ""
    normative_ref: str = ""
    source_chunk_ids: list[str] = []
    image: ImageStrategy = Field(default_factory=lambda: ImageStrategy(strategy="none"))
    quiz_options: list[str] | None = None
    quiz_correct: int | None = None

    @field_validator("body")
    @classmethod
    def validate_body_length(cls, v: str, info: Any) -> str:
        """Soft validator: TRUNCATE the body if it exceeds the per-slide-type limit.

        Truncation is logged (structlog) and surfaced into the
        ``GenerationReport.truncation_warnings`` list. This prevents text
        overflowing PPTX placeholders without raising on the spot.
        """
        limits = {
            "CONTENT_TEXT": 90,
            "CONTENT_IMAGE": 60,
            "QUIZ": 60,
            "CASE_STUDY": 100,
            "DIAGRAM": 50,
            "RECAP": 70,
        }
        slide_type = info.data.get("slide_type", "")
        # Enum value or string: normalise to its `.value` for lookup.
        key = getattr(slide_type, "value", str(slide_type))
        max_words = limits.get(key, 100)
        words = v.split()
        if len(words) > max_words:
            logger.warning(
                "slide_body_truncated",
                slide_index=info.data.get("index"),
                original_words=len(words),
                max_words=max_words,
            )
            return " ".join(words[:max_words]) + "…"
        return v


class ModuleSpec(BaseModel):
    """Specification of a module in the pacing plan."""

    module_index: int
    title: str
    slide_count: int
    slide_distribution: dict[str, int]  # e.g. {"CONTENT_TEXT": 10, "QUIZ": 2, "RECAP": 1}


class PacingPlan(BaseModel):
    """Slide distribution plan computed by the PacingEngine."""

    total_slides: int
    modules: list[ModuleSpec]


class ModuleContent(BaseModel):
    """Content Agent output for a single module."""

    module_index: int
    title: str
    slides: list[SlideContent]


class CourseContext(BaseModel):
    """Full context produced by the Research Agent for the Content Agent."""

    chunks: list[NormativeChunk]
    chunks_by_module: dict[int, list[NormativeChunk]]
    pacing_plan: PacingPlan
    style_patterns: list[StylePattern]
    regulation_ids: list[str]
    regulation_slugs: list[str]


class GenerationReport(BaseModel):
    """Final generation report."""

    total_slides: int
    slides_with_images: int
    slides_with_diagrams: int
    quiz_count: int
    modules_completed: int
    modules_failed: int
    normative_refs_count: int
    warnings: list[str] = []
    truncation_warnings: list[str] = []  # slides truncated by the body validator — visible to the operator
    generation_time_seconds: float
