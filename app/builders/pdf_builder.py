"""PdfBuilder — dispensa generation via Jinja2 + WeasyPrint (BP §07.2 + OPT-3).

OPT-3 swaps BP's ``PDF_TEMPLATE.format(...)`` for a Jinja2 template loaded
from ``app/templates/dispensa.html``: structured loops + conditionals
instead of brittle f-string interpolation of a multi-line HTML blob.

The rendered HTML preserves the BP §07.2 contract exactly:
    - @page A4, 2cm margin, page counter in @bottom-center
    - Open Sans body, Montserrat headings
    - h1 with page-break-before per module (h1:first-of-type avoid)
    - CSS classes ``.normative-ref``, ``.quiz``, ``.speaker-notes``
    - Brand palette injected via ``{{ palette.primary | default('#1a365d') }}``

The class is SYNCHRONOUS (BP §07.1 wraps it in ``asyncio.to_thread``;
the Semaphore(1) for python-pptx — REI-3 — lives in generation_service
FASE 5.1, NOT here).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.pipeline import SlideContent

logger = structlog.get_logger()

DEFAULT_TEMPLATES_DIR = Path("app/templates")
DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_TEMPLATE_NAME = "dispensa.html"

# BP §07.2 palette defaults — overridable via brand_config["palette"].
DEFAULT_PRIMARY = "#1a365d"
DEFAULT_SECONDARY = "#2b6cb0"


def _group_slides_by_module(slides: list[SlideContent]) -> list[dict[str, Any]]:
    """Group a flat slide list into ``[{index, title, slides: [...]}]``.

    The Content Agent emits slides ordered by ``module_index`` already
    (FASE 3.4), but we don't rely on that — we partition by ``module_index``
    in the order encountered.
    """
    modules: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for s in slides:
        if current is None or s.module_index != current["index"]:
            current = {"index": s.module_index, "title": "", "slides": []}
            modules.append(current)
        current["slides"].append(_slide_to_dict(s))
    return modules


def _slide_body_text(s: SlideContent) -> str:
    """Flatten bullets/sezioni (FIX #28.1 schema) into a printable body
    string for the dispensa PDF template, which renders one paragraph.

    Priority: ``sezioni`` (CASE_STUDY, 3 sections joined by blank line) →
    ``bullets`` (CONTENT_TEXT/IMAGE/RECAP, joined with "• " prefix). Empty
    when neither is populated (TITLE/CLOSING/DIAGRAM caption-only).
    """
    if getattr(s, "sezioni", None):
        return "\n\n".join(s.sezioni)
    if getattr(s, "bullets", None):
        return "\n".join(f"• {b}" for b in s.bullets)
    return ""


def _slide_to_dict(s: SlideContent) -> dict[str, Any]:
    """Pydantic → plain dict shaped for the Jinja2 template.

    ``slide_type_value`` is the enum's ``.value`` (string) so the template
    can do ``{% if slide.slide_type_value == 'QUIZ' %}`` without importing
    the enum into Jinja.
    """
    return {
        "index": s.index,
        "module_index": s.module_index,
        "slide_type_value": s.slide_type.value,
        "title": s.title,
        "body": _slide_body_text(s),
        "normative_ref": s.normative_ref,
        "speaker_notes": s.speaker_notes,
        "quiz_options": s.quiz_options,
        "quiz_correct": s.quiz_correct,
    }


class PdfBuilder:
    """Build the dispensa PDF for a course. SYNCHRONOUS."""

    def __init__(
        self,
        brand_config: dict[str, Any] | None = None,
        templates_dir: Path = DEFAULT_TEMPLATES_DIR,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        template_name: str = DEFAULT_TEMPLATE_NAME,
    ) -> None:
        if not templates_dir.is_dir():
            raise FileNotFoundError(
                f"Templates dir not found at {templates_dir}. "
                f"Expected {DEFAULT_TEMPLATE_NAME} inside."
            )
        self.brand_config = brand_config or {}
        # FIX 2026-05-25: brand_config["palette"] da DB asyncpg arriva come
        # JSON string (jsonb non auto-deserializzato in tutti i path). Parse
        # difensivo per evitare AttributeError 'str' has no attribute 'get'.
        import json as _json
        _palette_raw = self.brand_config.get("palette", {})
        if isinstance(_palette_raw, str):
            try:
                _palette_raw = _json.loads(_palette_raw)
            except (_json.JSONDecodeError, TypeError):
                _palette_raw = {}
        self.palette: dict[str, str] = (
            _palette_raw if isinstance(_palette_raw, dict) else {}
        )
        self.output_dir = output_dir
        self.template_name = template_name

        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            keep_trailing_newline=True,
        )
        # Load eagerly so a typo'd template name fails at construction,
        # not on the first build().
        self.template = self.env.get_template(template_name)

    def build(self, slides: list[SlideContent], course: dict[str, Any]) -> str:
        """Render the dispensa template to PDF and return the absolute path.

        Synchronous; ProductionBuilder (FASE 4.5) wraps in asyncio.to_thread.
        """
        modules = _group_slides_by_module(slides)
        palette_view = {
            "primary": self.palette.get("primary", DEFAULT_PRIMARY),
            "secondary": self.palette.get("secondary", DEFAULT_SECONDARY),
        }
        html = self.template.render(
            course=course,
            modules=modules,
            palette=palette_view,
            date=datetime.now().strftime("%d/%m/%Y"),
        )
        pdf_path = self._compute_output_path(course)
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        # Lazy import: weasyprint pulls libgobject/cairo/pango at import time,
        # which is only guaranteed available in the Docker image. Importing
        # at call site keeps unit tests on dev machines functional via patch.
        import weasyprint

        weasyprint.HTML(string=html).write_pdf(str(pdf_path))
        logger.info(
            "pdf_generated",
            path=str(pdf_path),
            modules=len(modules),
            slides=len(slides),
        )
        return str(pdf_path)

    def render_html(
        self, slides: list[SlideContent], course: dict[str, Any]
    ) -> str:
        """Render the Jinja2 template WITHOUT going through WeasyPrint.

        Exposed for tests (and future preview endpoints): asserting against
        the rendered HTML is deterministic and does not require GTK runtime.
        """
        modules = _group_slides_by_module(slides)
        palette_view = {
            "primary": self.palette.get("primary", DEFAULT_PRIMARY),
            "secondary": self.palette.get("secondary", DEFAULT_SECONDARY),
        }
        return self.template.render(
            course=course,
            modules=modules,
            palette=palette_view,
            date=datetime.now().strftime("%d/%m/%Y"),
        )

    def _compute_output_path(self, course: dict[str, Any]) -> Path:
        import os

        course_id = course.get("id") or course.get("course_id") or "course"
        safe_id = str(course_id).replace(os.sep, "_").replace("/", "_")
        return self.output_dir / f"{safe_id}_dispensa.pdf"


__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_PRIMARY",
    "DEFAULT_SECONDARY",
    "DEFAULT_TEMPLATE_NAME",
    "DEFAULT_TEMPLATES_DIR",
    "PdfBuilder",
]
