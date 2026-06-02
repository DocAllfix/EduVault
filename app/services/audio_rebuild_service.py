"""Audio-only rebuild service (F11 Issue 4 — D-230).

Rigenera SOLO l'audio del corso senza ricostruire PPTX/PDF. Use case:
- Corsi vecchi con ``audio_manifest_path = NULL`` (generati pre-audio o
  con audio service disabilitato)
- Corsi dove l'audio è fallito durante la generazione iniziale

Estrae il blocco audio già esistente in ``rebuild_service.py:100-119``
in un service dedicato. Vantaggio: 10x più rapido del rebuild full e
ZERO rischio di toccare file PPTX/PDF già validi.

Concorrenza: stesso ``_job_semaphore`` di generation_service (REI-3,
benché l'audio in sé sia thread-safe, il semaforo serializza coerentemente
le operazioni heavy su un corso → evita race con eventuale rebuild full
parallelo).
"""

from __future__ import annotations

import time
import uuid as uuid_mod
from typing import Any

import structlog

from app.config import settings
from app.models.pipeline import SlideContent
from app.services.audio_service import AudioService
from app.services.dependencies import get_pool
from app.services.generation_service import _job_semaphore
from app.services.studio_service import get_slides

logger = structlog.get_logger()


async def rebuild_audio_only(course_id: str, user_id: str) -> None:
    """Rigenera solo le tracce audio del corso (PPTX/PDF non toccati).

    Async fire-and-forget: chiamato via ``asyncio.create_task``. Non
    aggiorna ``courses.status``: l'audio è secondario, il corso resta
    ``completed``. Il frontend rileva l'avanzamento via polling su
    ``audio_manifest_path`` (già implementato in course-detail page).

    Idempotente: ``DELETE FROM audio_tracks WHERE course_id=...``
    prima di rigenerare → rebuild ripetuti non duplicano le tracce.

    Errori non fatali: se il TTS fallisce per tutte le slide,
    ``audio_manifest_path`` resta NULL e l'UI continua a mostrare
    "Audio non disponibile" — coerente con stato pre-rebuild.
    """
    pool = get_pool()
    cid = uuid_mod.UUID(course_id)
    async with _job_semaphore:
        start = time.time()
        try:
            # Slide correnti (lo schema dello slide_contents_json è popolato
            # da ogni generazione completata, vedi generation_service:187).
            slides_raw = await get_slides(course_id, pool)
            if not slides_raw:
                logger.warning(
                    "audio_rebuild_no_slides",
                    course_id=course_id,
                )
                return
            slide_models = [SlideContent(**s) for s in slides_raw]

            # Idempotenza: DELETE prima di INSERT (pattern identico a
            # rebuild_service.py:101-103).
            await pool.execute(
                "DELETE FROM audio_tracks WHERE course_id=$1", cid
            )

            audio_service = AudioService(voice=settings.tts_voice)
            audio_result = await audio_service.generate_narrations(
                slide_models, course_id, pool
            )

            elapsed = time.time() - start
            logger.info(
                "audio_rebuild_completed",
                course_id=course_id,
                user_id=user_id,
                tracks_generated=audio_result.get("tracks_generated"),
                tracks_skipped=audio_result.get("tracks_skipped"),
                voice=settings.tts_voice,
                elapsed_seconds=round(elapsed, 2),
            )

            # Audit log (immutabile, pattern coerente con generation_service)
            await pool.execute(
                "INSERT INTO audit_log (user_id, action, entity_type, "
                "entity_id, details) VALUES ($1, $2, $3, $4, $5::jsonb)",
                uuid_mod.UUID(user_id),
                "audio_rebuild_completed",
                "course",
                cid,
                f'{{"tracks_generated": {audio_result.get("tracks_generated", 0)}, '
                f'"elapsed_seconds": {round(elapsed, 2)}}}',
            )
        except Exception as exc:
            logger.error(
                "audio_rebuild_failed",
                course_id=course_id,
                user_id=user_id,
                error=str(exc),
                exc_info=True,
            )
            # Non-fatal: lasciamo audio_manifest_path NULL, l'UI continua
            # a mostrare "Audio non disponibile" e l'utente può ritentare.
