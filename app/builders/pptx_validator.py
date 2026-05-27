"""Post-build PPTX sanity check (BP §07.1 line 2257).

Loads the freshly written .pptx and asserts the slide count matches the
plan. Returns a dict that ``ProductionBuilder._build_report`` reads via
``validation.get("warnings", [])`` (BP §07.1 line 2296).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
from pptx import Presentation

from app.models.pipeline import SlideContent

logger = structlog.get_logger()


class PptxValidator:
    """Validate a generated PPTX against the slide list that produced it."""

    def validate(
        self, pptx_path: str, slides: list[SlideContent]
    ) -> dict[str, Any]:
        warnings: list[str] = []
        expected = len(slides)
        path = Path(pptx_path)

        if not path.is_file():
            warnings.append(f"pptx_missing:{pptx_path}")
            logger.warning("pptx_validate_missing", path=pptx_path)
            return {"valid": False, "slide_count": 0, "warnings": warnings}

        prs = Presentation(str(path))
        actual = len(prs.slides)
        valid = actual == expected
        if not valid:
            warnings.append(f"slide_count_mismatch:expected={expected},actual={actual}")

        logger.info(
            "pptx_validated",
            path=pptx_path,
            slide_count=actual,
            expected=expected,
            valid=valid,
        )
        return {"valid": valid, "slide_count": actual, "warnings": warnings}


__all__ = ["PptxValidator"]
