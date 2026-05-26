"""Course rebuild service (FASE 11 vast-hopping-sketch).

Ricostruisce PPTX/PDF/audio dal ``slide_contents_json`` corrente del corso
dopo che l'utente ha modificato le slide via Course Studio. Riusa
``ProductionBuilder`` + ``prefetch_images`` esattamente come la pipeline di
generazione, ma SALTA research+content (le slide esistono già).

Concorrenza: usa lo stesso ``_job_semaphore`` di generation_service (REI-3,
python-pptx non thread-safe → Semaphore(1)).

Funziona IDENTICAMENTE per corsi nuovi e vecchi: l'unico requisito è che il
corso abbia ``slide_contents_json`` popolato (ogni corso generato lo ha, sin
dalla prima generazione — vedi generation_service line 187).
"""

from __future__ import annotations

import json
import time
import uuid as uuid_mod
from typing import Any

import structlog

from app.builders.production_builder import ProductionBuilder
from app.models.pipeline import SlideContent
from app.services.generation_service import _job_semaphore
from app.services.image_service import prefetch_images
from app.services.studio_service import get_slides

logger = structlog.get_logger()


async def _noop_ws(job_id: str, percent: int, step: str) -> None:
    """Rebuild non ha un job WS dedicato — log invece di websocket."""
    logger.info("rebuild_progress", course_id=job_id, percent=percent, step=step)


async def rebuild_course(course_id: str, user_id: str, pool: Any) -> None:
    """Ricostruisce gli artefatti del corso dal slide_contents_json corrente.

    Async fire-and-forget: aggiorna courses.status durante e dirty=false alla
    fine. Sotto il Semaphore(1) globale (REI-3).
    """
    cid = uuid_mod.UUID(course_id)
    async with _job_semaphore:
        start = time.time()
        try:
            await pool.execute(
                "UPDATE courses SET status='generating' WHERE id=$1", cid
            )
            course_row = await pool.fetchrow("SELECT * FROM courses WHERE id=$1", cid)
            if course_row is None:
                logger.error("rebuild_course_not_found", course_id=course_id)
                return
            course = dict(course_row)

            # Brand preset (se presente)
            brand: dict[str, Any] = {}
            bp_id = course.get("brand_preset_id")
            if bp_id:
                bp_row = await pool.fetchrow(
                    "SELECT * FROM brand_presets WHERE id=$1", bp_id
                )
                if bp_row:
                    brand = dict(bp_row)

            # Slide correnti (post-edit Studio)
            slides_raw = await get_slides(course_id, pool)
            slide_models = [SlideContent(**s) for s in slides_raw]

            # outputs: ri-genera tutto quello che il corso aveva
            course_dict = {
                "id": course_id,
                "course_type": course.get("course_type"),
                "title": course.get("title"),
                "outputs": ["pptx", "pdf", "audio"],
            }

            # Re-prefetch immagini + re-build
            image_map = await prefetch_images(slide_models, pool)
            builder = ProductionBuilder(brand_config=brand)
            pptx_path, pdf_path, _report = await builder.build(
                slides=slide_models,
                course=course_dict,
                job_id=course_id,  # usato solo per log nel _noop_ws
                ws_callback=_noop_ws,
                image_map=image_map,
                db=pool,
            )

            # Stato finale: completed + dirty=false + snapshot
            await pool.execute(
                "UPDATE courses SET pptx_path=$1, pdf_path=$2, status='completed', "
                "dirty=false, last_rebuilt_at=NOW(), "
                "slide_contents_json_snapshot=slide_contents_json WHERE id=$3",
                str(pptx_path),
                str(pdf_path),
                cid,
            )
            logger.info(
                "rebuild_completed",
                course_id=course_id,
                slides=len(slide_models),
                elapsed_s=round(time.time() - start, 1),
            )
        except Exception as exc:
            logger.error("rebuild_failed", course_id=course_id, error=str(exc))
            await pool.execute(
                "UPDATE courses SET status='failed' WHERE id=$1", cid
            )
