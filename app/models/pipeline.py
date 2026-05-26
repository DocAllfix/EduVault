"""Pipeline contracts (BLUEPRINT §04.4).

NexusPipelineState (TypedDict) lives in ``app.agents.pipeline`` (PHASE 3),
NOT here. This file holds only Pydantic models.

Only import-path differs from BP §04.4: ``app.models.*`` instead of ``models.*``.
"""

from __future__ import annotations

from typing import Literal, Self

import structlog
from pydantic import BaseModel, Field, model_validator

from app.models.core import (
    DIAGRAM_VIEWBOX_LITERAL,
    LAYOUT_CONSTRAINTS,
    SlideType,
)
from app.models.knowledge import NormativeChunk, StylePattern

logger = structlog.get_logger()


class ImageStrategy(BaseModel):
    """Strategy for the visual support of a slide.

    ``diagram_code`` is inline SVG (NOT Mermaid). Generated directly by the LLM.
    ``aspect_hint`` (FASE 4 vast-hopping): passa a Pexels come ``orientation`` param
    e a ``fit_image_to_box`` per scegliere lo strategy di sizing nel SlideBuilderV2.
    """

    strategy: str = "none"  # "none" | "web_search" | "diagram"
    query: str | None = None
    query_url: str | None = None
    diagram_code: str | None = None  # inline SVG (rectangles + arrows + text)
    aspect_hint: Literal["landscape", "portrait", "square"] | None = None


class SlideContent(BaseModel):
    """Single-slide content produced by the Content Agent.

    FASE 1 vast-hopping-sketch: ``model_validator(mode="after")`` STRICT (no truncation):
    se la slide viola i constraints di LAYOUT_CONSTRAINTS per il suo ``slide_type``,
    raise ``ValueError`` → il content_agent intercetta e chiede SPLIT all'LLM (FASE 2),
    mai compressione né "…" troncamento.
    """

    index: int
    module_index: int
    slide_type: SlideType
    title: str = Field(..., max_length=200)  # bound largo, il vincolo vero è per-type
    body: str = ""
    speaker_notes: str = ""
    normative_ref: str = ""
    source_chunk_ids: list[str] = []
    image: ImageStrategy = Field(default_factory=lambda: ImageStrategy(strategy="none"))
    quiz_options: list[str] | None = None
    quiz_correct: int | None = None

    @model_validator(mode="after")
    def enforce_layout_constraints(self) -> Self:
        """STRICT validation per-SlideType (FASE 1 vast-hopping-sketch).

        Rigetta — non tronca — quando i numeri sforano. Il caller (content_agent)
        intercetta il ValueError, manda corrective prompt SPLIT, ri-tenta una volta.
        Filosofia: meglio una slide in meno che una slide rotta.
        """
        rules = LAYOUT_CONSTRAINTS.get(self.slide_type)
        if rules is None:
            return self  # tipo non mappato (dev/test) — pass-through

        # ─── TITLE char count ───
        if len(self.title) > rules.title_max_chars:
            raise ValueError(
                f"slide_type={self.slide_type.value} title={len(self.title)} char > "
                f"{rules.title_max_chars} max. NON troncare: emetti 2 slide con "
                f"titoli più corti."
            )

        # ─── BODY bullets/words (STRICT — slide COMPLETE e PRECISE 2026-05-25) ───
        # Filosofia: meglio una slide in meno che una slide rotta. Lo SPLIT retry
        # in content_agent.py:_generate_one_module gestisce il recupero chiedendo
        # all'LLM di emettere 2 slide consecutive. Validator NON tronca mai —
        # il troncamento produce slide incomplete/imprecise (vietato esplicitamente).
        if rules.body_max_bullets > 0 and self.body.strip():
            from app.models.core import SlideType as _ST

            if self.slide_type == _ST.CASE_STUDY:
                bullets = [b.strip() for b in self.body.split("---") if b.strip()]
                unit_label = "sezioni"
            else:
                bullets = [b.strip() for b in self.body.split("\n") if b.strip()]
                unit_label = "bullets"
            if len(bullets) > rules.body_max_bullets:
                raise ValueError(
                    f"slide_type={self.slide_type.value} body ha {len(bullets)} {unit_label} > "
                    f"{rules.body_max_bullets} max. SPLITTA il concetto in 2 slide "
                    f"consecutive (NON troncare, NON comprimere)."
                )
            # FIX #27.3 (2026-05-26): MINIMO bullet — slide piena, no spazi vuoti.
            # Il content_agent SPLIT-retry intercetta il ValueError e ri-genera
            # con più contenuto (NON inventato: altri aspetti dello stesso chunk).
            if rules.body_min_bullets > 0 and len(bullets) < rules.body_min_bullets:
                raise ValueError(
                    f"slide_type={self.slide_type.value} body ha {len(bullets)} {unit_label} < "
                    f"{rules.body_min_bullets} min. AGGIUNGI {unit_label} fino ad almeno "
                    f"{rules.body_min_bullets} (espandi con altri aspetti del chunk "
                    f"normativo, NON inventare, NON ripetere)."
                )
            for i, bullet in enumerate(bullets):
                n_words = len(bullet.split())
                if n_words > rules.bullet_max_words:
                    raise ValueError(
                        f"slide_type={self.slide_type.value} {unit_label}[{i}] ha {n_words} "
                        f"parole > {rules.bullet_max_words} max. Riscrivi più "
                        f"sintetico o splitta in 2 slide."
                    )
        elif rules.body_max_bullets == 0 and self.body.strip():
            raise ValueError(
                f"slide_type={self.slide_type.value} non deve avere body (è "
                f"{'title-only' if self.slide_type.value in ('TITLE', 'CLOSING') else 'options-only'})."
            )

        # ─── SPEAKER NOTES word range (TTS 25-35s @180wpm) ───
        notes_words = len(self.speaker_notes.split()) if self.speaker_notes else 0
        if notes_words < rules.notes_min_words:
            raise ValueError(
                f"slide_type={self.slide_type.value} speaker_notes ha {notes_words} "
                f"parole < {rules.notes_min_words} min (TTS sotto-target). Espandi "
                f"con esempio concreto o citazione normativa."
            )
        if notes_words > rules.notes_max_words:
            raise ValueError(
                f"slide_type={self.slide_type.value} speaker_notes ha {notes_words} "
                f"parole > {rules.notes_max_words} max (TTS sopra-target). Sposta "
                f"il contenuto eccedente in una slide successiva."
            )

        # ─── IMAGE required ───
        if rules.requires_image:
            if self.slide_type == SlideType.DIAGRAM:
                if not self.image.diagram_code:
                    raise ValueError(
                        "slide_type=DIAGRAM richiede image.diagram_code (SVG inline)."
                    )
                # FIX #11 (2026-05-25): rilasso il viewBox check — l'LLM emette
                # spesso viewBox custom (es. "0 0 800 600"). Cairosvg può renderizzare
                # qualsiasi viewBox e noi forziamo output_width/height 1760x800.
                # Verifica solo che CI SIA un viewBox attribute valido (qualunque).
                if "viewBox" not in self.image.diagram_code:
                    raise ValueError(
                        "slide_type=DIAGRAM image.diagram_code deve avere "
                        "un attributo viewBox SVG (qualunque dimensione)."
                    )
            else:  # CONTENT_IMAGE
                if not self.image.query:
                    raise ValueError(
                        "slide_type=CONTENT_IMAGE richiede image.query (2-4 parole "
                        "italiane descrittive del concetto da illustrare)."
                    )
                # FIX #11: aspect_hint opzionale, default landscape (la maggior
                # parte delle foto sicurezza/cantiere sono landscape).
                if self.image.aspect_hint is None:
                    object.__setattr__(self.image, "aspect_hint", "landscape")

        # ─── QUIZ options ───
        if rules.requires_options:
            if not self.quiz_options or len(self.quiz_options) != 4:
                raise ValueError(
                    f"slide_type=QUIZ richiede esattamente 4 quiz_options, "
                    f"ricevute {len(self.quiz_options) if self.quiz_options else 0}."
                )
            if self.quiz_correct is None or self.quiz_correct not in (0, 1, 2, 3):
                raise ValueError(
                    f"slide_type=QUIZ richiede quiz_correct INTERO ∈ {{0,1,2,3}}, "
                    f"ricevuto {self.quiz_correct!r} (tipo {type(self.quiz_correct).__name__})."
                )
            for i, opt in enumerate(self.quiz_options):
                if len(opt) > 80:
                    raise ValueError(
                        f"slide_type=QUIZ option[{i}] ha {len(opt)} char > 80 max. "
                        f"Riscrivi l'opzione più sintetica."
                    )

        return self


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
