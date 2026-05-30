"""ProductionBuilder — orchestrates PPTX + PDF (+ Audio in 4.6) post-pipeline.

BP §07.1 verbatim:
    1. ``check_memory_before_build`` (psutil) — prevent OOM on huge courses
    2. ``check_disk_before_build`` — fail fast if no space for output
    3. SlideBuilder.build (sync, wrapped in asyncio.to_thread)
    4. PptxValidator.validate (sync, asyncio.to_thread)
    5. PdfBuilder.build (sync, asyncio.to_thread)
    6. ``_cleanup_tmp`` — remove output/tmp_*, output/diagrams/*.png,
       output/images/*.png older than 1 hour

REI-3: python-pptx + lxml are NOT thread-safe. The Semaphore(1) that
enforces single-build concurrency lives in ``generation_service`` (FASE 5.1),
NOT here. ProductionBuilder is a pure builder — concurrency control is
the caller's job.

karpathy regola #2 applicata: zero retry, zero fallback parziale, zero
strategie di recovery oltre i 2 guard pre-build e l'image fallback già
nel SlideBuilder. Audio (FASE 4.6) si aggiunge come tappa addizionale
dopo il PDF.
"""

from __future__ import annotations

import asyncio
import glob
import os
import shutil
import time
from pathlib import Path
from typing import Any

import psutil
import structlog

from app.builders.pdf_builder import PdfBuilder
from app.builders.pptx_validator import PptxValidator
from app.builders.slide_builder_v2 import SlideBuilderV2  # FASE 3: drop-in v2 (XML find/replace)
from app.models.pipeline import GenerationReport, SlideContent
from app.services.citation_normalizer import find_hallucinated_citations

logger = structlog.get_logger()

# BP §07.1 line 2208 — "estimated_mb = slide_count * 1.5"
MEMORY_PER_SLIDE_MB = 1.5
# BP line 2208 — "if estimated_mb > available_mb * 0.6"
MEMORY_SAFETY_RATIO = 0.6
# BP line 2224 — minimum 1GB free for build
MIN_DISK_FREE_GB = 1.0
# BP line 2277 — files older than 1 hour are tmp leftovers
CLEANUP_AGE_SECONDS = 3600
# BP line 2278 — patterns covered by _cleanup_tmp
# FIX #30.0-novies (2026-05-26): rimosso "output/images/*.png" dalla blacklist.
# Le foto Pexels sono cached via image_cache (DB local_path) e ri-referenziate
# da rebuild successivi. Cancellarle dopo 1h faceva fallire _maybe_insert_image
# sui file UUID-cached condivisi (16 fallback su 35 nel test). I diagrammi
# restano nel cleanup perché generati ex-novo per ogni run (no cache).
CLEANUP_PATTERNS = [
    "output/tmp_*",
    "output/diagrams/*.png",
]

DEFAULT_OUTPUT_DIR = Path("output")


def check_memory_before_build(slide_count: int) -> None:
    """Raise MemoryError if estimated build RAM exceeds 60% of available.

    python-pptx keeps the entire Presentation in memory; 700 slides with
    images can take 500MB-1GB. BP §07.1 line 2202-2218 verbatim.
    """
    available_mb = psutil.virtual_memory().available / (1024 * 1024)
    estimated_mb = slide_count * MEMORY_PER_SLIDE_MB
    if estimated_mb > available_mb * MEMORY_SAFETY_RATIO:
        raise MemoryError(
            f"RAM insufficient for PPTX build: "
            f"{available_mb:.0f}MB available, "
            f"~{estimated_mb:.0f}MB estimated for {slide_count} slides. "
            f"Reduce course duration or restart the server."
        )
    logger.info(
        "memory_check_passed",
        available_mb=round(available_mb),
        estimated_mb=round(estimated_mb),
        slides=slide_count,
    )


def check_disk_before_build(output_dir: Path = DEFAULT_OUTPUT_DIR) -> None:
    """Raise IOError if free space on the output partition is below 1GB.

    BP §07.1 line 2221-2228. The check targets the output directory so
    container vs host paths work transparently.
    """
    target = output_dir if output_dir.exists() else Path.cwd()
    disk_free_gb = shutil.disk_usage(str(target)).free / (1024**3)
    if disk_free_gb < MIN_DISK_FREE_GB:
        raise IOError(
            f"Insufficient disk space: {disk_free_gb:.1f}GB free. "
            f"At least {MIN_DISK_FREE_GB:.0f}GB required."
        )
    logger.info("disk_check_passed", free_gb=round(disk_free_gb, 1))


class ProductionBuilder:
    """Orchestrates PPTX + PDF build. python-pptx / WeasyPrint are SYNC →
    every call is wrapped in ``asyncio.to_thread``."""

    def __init__(self, brand_config: dict[str, Any] | None = None) -> None:
        cfg = brand_config or {}
        self.brand_config = cfg
        self.slide_builder = SlideBuilderV2(brand_config=cfg)
        self.pdf_builder = PdfBuilder(brand_config=cfg)
        self.validator = PptxValidator()

    async def build(
        self,
        slides: list[SlideContent],
        course: dict[str, Any],
        job_id: str,
        ws_callback: Any,
        image_map: dict[int, str],
        db: Any | None = None,
    ) -> tuple[str, str, dict[str, Any]]:
        """Run the full build: memory check → PPTX → validate → PDF → cleanup.

        FIX #31 MOSSA 3 (2026-05-27): la generazione audio NON viene più
        eseguita qui. Il caller (``generation_service._run_pipeline_inner``)
        la spawna come ``asyncio.create_task`` DOPO il return dei path
        PPTX/PDF, così l'utente riceve gli artefatti immediati e l'audio
        arriva 2-3 min dopo via polling di ``courses.audio_manifest_path``.
        Il parametro ``db`` resta nella signature per backward compat
        (no-op rispetto a questo metodo).
        """
        check_memory_before_build(len(slides))
        check_disk_before_build()

        # D-178 V1.5 (analista sign-off 2026-05-30): post-render check
        # citazioni decreti nei bullets/notes/quiz_options vs course.regulation_ids.
        # Marca-only (NON scarta, NON rigenera): log strutturato + report.
        # Patologia coperta: slide 67 PPTX `ANT_L1_0dfe39ad` bullet
        # "Decreto ministeriale 3 agosto 2015" non in ANT L1 regulation_ids.
        hallucination_report = self._check_bullet_citations(slides, course)

        await ws_callback(job_id, 87, "Generazione PPTX...")
        pptx_path = await asyncio.to_thread(
            self.slide_builder.build, slides, course, image_map
        )

        await ws_callback(job_id, 92, "Validazione PPTX...")
        validation = await asyncio.to_thread(
            self.validator.validate, pptx_path, slides
        )

        await ws_callback(job_id, 95, "Generazione PDF dispensa...")
        pdf_path = await asyncio.to_thread(self.pdf_builder.build, slides, course)

        await asyncio.to_thread(self._cleanup_tmp)

        report = self._build_report(slides, validation, hallucination_report)
        return pptx_path, pdf_path, report

    def _cleanup_tmp(self) -> None:
        """Remove tmp files older than 1 hour to avoid deleting files in
        use by a parallel build. BP §07.1 line 2270-2284."""
        cutoff = time.time() - CLEANUP_AGE_SECONDS
        for pattern in CLEANUP_PATTERNS:
            for f in glob.glob(pattern):
                try:
                    if os.path.getmtime(f) < cutoff:
                        os.remove(f)
                except OSError:
                    pass

    def _check_bullet_citations(
        self,
        slides: list[SlideContent],
        course: dict[str, Any],
    ) -> dict[str, Any]:
        """D-178 V1.5 post-render check: cita decreti nei text_fields
        coerenti con course.regulation_ids?

        Per ogni slide: scansiona bullets + speaker_notes + quiz_options.
        Estrae slug citati (citation_normalizer pattern regex). Confronta con
        allowed_slugs = set(course['regulation_ids']) [oppure derivato da
        catalog se assente]. Slide con citazioni fuori scope: emit log +
        accumula in report.

        Comportamento marca-only: NESSUNA modifica alle slide, NESSUNA
        rigenerazione. Trasparenza visibile (telemetria + report), operatore
        review.
        """
        allowed_raw = course.get("regulation_ids") or course.get("regs") or []
        if not isinstance(allowed_raw, list):
            allowed_raw = []
        allowed_slugs: set[str] = {str(s) for s in allowed_raw}

        if not allowed_slugs:
            # No allowed list known -> skip check (no false positives).
            return {
                "total_slides": len(slides),
                "slides_with_warnings": 0,
                "warnings": [],
                "skipped": True,
                "skip_reason": "no_allowed_slugs_in_course",
            }

        warnings: list[dict[str, Any]] = []
        for idx, s in enumerate(slides):
            text_fields: list[str] = []
            text_fields.extend(s.bullets or [])
            if s.speaker_notes:
                text_fields.append(s.speaker_notes)
            if s.quiz_options:
                text_fields.extend(s.quiz_options)
            hallucinated = find_hallucinated_citations(text_fields, allowed_slugs)
            if hallucinated:
                warnings.append(
                    {
                        "slide_index": idx,
                        "slide_title": s.title,
                        "module_index": s.module_index,
                        "hallucinated_slugs": hallucinated,
                    }
                )
                logger.warning(
                    "bullet_citation_warning",
                    slide_index=idx,
                    slide_title=s.title,
                    module_index=s.module_index,
                    hallucinated_slugs=hallucinated,
                    allowed_slugs=sorted(allowed_slugs),
                )

        logger.info(
            "bullet_citation_check_done",
            total_slides=len(slides),
            slides_with_warnings=len(warnings),
            allowed_slugs=sorted(allowed_slugs),
        )
        return {
            "total_slides": len(slides),
            "slides_with_warnings": len(warnings),
            "warnings": warnings,
            "skipped": False,
        }

    def _build_report(
        self,
        slides: list[SlideContent],
        validation: dict[str, Any],
        hallucination_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base = GenerationReport(
            total_slides=len(slides),
            slides_with_images=sum(
                1 for s in slides if s.image.strategy == "web_search"
            ),
            slides_with_diagrams=sum(
                1 for s in slides if s.image.strategy == "diagram"
            ),
            quiz_count=sum(1 for s in slides if s.slide_type.value == "QUIZ"),
            modules_completed=len({s.module_index for s in slides}),
            modules_failed=0,
            normative_refs_count=sum(1 for s in slides if s.normative_ref),
            warnings=validation.get("warnings", []),
            generation_time_seconds=0,
        ).model_dump()
        if hallucination_report is not None:
            base["bullet_citation_check"] = hallucination_report
        return base


__all__ = [
    "CLEANUP_AGE_SECONDS",
    "CLEANUP_PATTERNS",
    "DEFAULT_OUTPUT_DIR",
    "MEMORY_PER_SLIDE_MB",
    "MEMORY_SAFETY_RATIO",
    "MIN_DISK_FREE_GB",
    "ProductionBuilder",
    "check_disk_before_build",
    "check_memory_before_build",
]
