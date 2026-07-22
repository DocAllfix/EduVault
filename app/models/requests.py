"""Request/Response contracts for the REST layer (BLUEPRINT §04.2).

Modifications vs BP §04.2 (declared per REI-5):
- Import path is ``app.models.core`` (project package), not bare ``models.core``.
- ``outputs`` accepts a fixed set of literals: ``pptx``, ``pdf``, ``audio``, ``quiz``.
  Reason: PHASE 5 / 6 branch on membership (e.g. ``"audio" in outputs``), so a
  silent typo would break the pipeline at runtime. The validator restricts to
  the known set; ``audio`` is the new v3.0 GAP-3 output (FAD narration).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.models.core import SlideDensity, TargetType


_ALLOWED_OUTPUTS: frozenset[str] = frozenset({"pptx", "pdf", "audio", "quiz"})


class CourseRequest(BaseModel):
    """Input from the wizard. All fields required to start the pipeline."""

    course_type: str = Field(
        ...,
        description="Slug del tipo corso da COURSE_CATALOG, es. 'sicurezza_lavoratori_generale'",
    )
    target: TargetType
    duration_hours: float = Field(..., gt=0, le=16)
    region: str = Field(default="NAZIONALE")
    brand_preset_id: str
    slide_density: SlideDensity = SlideDensity.STANDARD
    # FASE 2 (2026-07-21): durata-slide scelta dall'utente. Piu` alta → meno
    # slide, ognuna con narrazione piu` lunga. Default 45 = comportamento
    # pre-esistente; range guidato 40-240s (sotto i 40 si torna ai problemi di
    # budget output LLM; sopra i 240 il batch andrebbe riscritto).
    seconds_per_slide: float = Field(default=45.0, ge=40.0, le=240.0)
    outputs: list[str] = Field(
        default=["pptx", "pdf"],
        description="Formati richiesti: pptx, pdf, audio, quiz",
    )

    @field_validator("outputs")
    @classmethod
    def validate_outputs(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("outputs cannot be empty — at least one format required")
        unknown = [o for o in v if o not in _ALLOWED_OUTPUTS]
        if unknown:
            raise ValueError(
                f"unknown output(s): {unknown}. Allowed: {sorted(_ALLOWED_OUTPUTS)}"
            )
        return v


class CourseResponse(BaseModel):
    """Response to course creation.

    ``queue_position``: 0 = running now, 1+ = waiting in queue.
    """

    course_id: str
    job_id: str
    estimated_slides: int
    estimated_minutes: float
    queue_position: int = 0
