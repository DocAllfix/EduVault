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

import time
import uuid as uuid_mod
from typing import Any

import structlog

from app.builders.production_builder import ProductionBuilder
from app.config import settings
from app.models.pipeline import SlideContent
from app.services.audio_service import AudioService
from app.services.generation_service import _job_semaphore
from app.services.image_service import prefetch_images
from app.services.studio_service import get_slides

logger = structlog.get_logger()


async def _noop_ws(job_id: str, percent: int, step: str) -> None:
    """Rebuild non ha un job WS dedicato — log invece di websocket."""
    logger.info("rebuild_progress", course_id=job_id, percent=percent, step=step)


async def rebuild_course(
    course_id: str,
    user_id: str,
    pool: Any,
    skip_audio: bool = False,
) -> None:
    """Ricostruisce gli artefatti del corso dal slide_contents_json corrente.

    Async fire-and-forget: aggiorna courses.status durante e dirty=false alla
    fine. Sotto il Semaphore(1) globale (REI-3).

    F12 (2026-06-02): ``skip_audio=True`` per "rebuild silenzioso" post-edit
    (es. cambio immagine in Course Studio). Audio resta valido (era già
    coerente con le slide perché solo il sub-doc image è cambiato), evitando
    30-60s di TTS Azure inutili. Il rebuild PPTX+PDF dura ~15-30s vs 60-180s
    full. Pattern simile a `audio_rebuild_service` ma inverso (skip audio
    invece di skip pptx/pdf).
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

            # F12 (2026-06-02): se skip_audio=True (es. rebuild silenzioso
            # post-edit immagine), saltiamo TTS Azure perché le tracce
            # esistenti sono ancora coerenti con le slide (cambiato solo
            # il sub-doc image). Risparmio 30-90s di TTS inutile.
            if skip_audio:
                logger.info(
                    "rebuild_audio_skipped",
                    course_id=course_id,
                    reason="skip_audio=True (post-edit fast rebuild)",
                )
            else:
                # Re-genera la narrazione audio dal slide_contents_json corrente.
                # ProductionBuilder costruisce solo PPTX/PDF; l'audio è un passo
                # separato (come in generation_service). Senza questo, un rebuild
                # post-edit lascerebbe audio_manifest_path stale o NULL.
                # generate_narrations fa solo INSERT in audio_tracks → DELETE prima
                # per idempotenza (rebuild ripetuti non duplicano le tracce).
                # L'audio è secondario: se fallisce, PPTX/PDF restano validi.
                try:
                    await pool.execute(
                        "DELETE FROM audio_tracks WHERE course_id=$1", cid
                    )
                    audio_service = AudioService(voice=settings.tts_voice)
                    audio_result = await audio_service.generate_narrations(
                        slide_models, course_id, pool
                    )
                    logger.info(
                        "rebuild_audio_generated",
                        course_id=course_id,
                        tracks=audio_result.get("tracks_generated"),
                        voice=settings.tts_voice,
                    )
                except Exception as audio_exc:
                    logger.error(
                        "rebuild_audio_failed",
                        course_id=course_id,
                        error=str(audio_exc),
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
