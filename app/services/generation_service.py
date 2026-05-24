"""Course generation pipeline wrapper (BLUEPRINT §09).

Implementa BP §09.1 verbatim con tre adattamenti REI/OPT (segnalati come
discrepanze):

- ``PIPELINE_TIMEOUT_SECONDS`` da ``settings.pipeline_timeout`` (OPT-2).
- ``settings.database_url`` invece di ``from app.config import DATABASE_URL``.
- ``create_pipeline`` è ``@asynccontextmanager`` (D18 storica) → ``async with``.

REI-3 / FIX-7 v2.0: ``_job_semaphore = asyncio.Semaphore(1)`` vive QUI,
non in ``services/dependencies.py``. È un vincolo architetturale
(python-pptx + lxml non thread-safe) — NON alzare a 2+ senza convertire
a process pool o Celery.

D-18: shutdown event LETTO da ``dependencies.get_shutdown_event()``.
Nessun ``asyncio.Event()`` locale in questo modulo.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any

import asyncpg
import structlog

from app.agents.pipeline import NexusPipelineState, create_pipeline
from app.builders.production_builder import ProductionBuilder
from app.config import settings
from app.models.pipeline import SlideContent
from app.services.dependencies import get_pool, get_shutdown_event
from app.services.image_service import prefetch_images

logger = structlog.get_logger()

# ═══ SEMAFORO DI CONCORRENZA (REI-3 / FIX-7 v2.0) ═══
# VINCOLO ARCHITETTURALE: python-pptx + lxml NON sono thread-safe.
# NON alzare MAI a Semaphore(2+) senza passare a process pool o Celery.
MAX_CONCURRENT_JOBS = 1
_job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

# ═══ TIMEOUT GLOBALE PIPELINE (OPT-2 — settings.pipeline_timeout) ═══
PIPELINE_TIMEOUT_SECONDS = settings.pipeline_timeout


async def send_ws_progress(job_id: str, percent: int, step: str) -> None:
    """Update job progress in the DB. The WebSocket reads it via
    ``get_job_progress()``. Decoupling pipeline from WS: pipeline writes,
    WS polls the DB."""
    db = get_pool()
    await db.execute(
        "UPDATE generation_jobs SET progress_percent=$1, current_step=$2 WHERE id=$3",
        percent,
        step,
        job_id,
    )


def build_normative_fingerprint(slides: list[dict[str, Any]]) -> dict[str, Any]:
    """Compose a normative fingerprint for the future Delta-Update.

    Shape: ``{refs: [unique normative_ref strings], chunk_count: int,
    generated_at: ISO 8601}``.
    """
    refs: list[str] = []
    seen_refs: set[str] = set()
    all_chunk_ids: set[str] = set()
    for slide in slides:
        ref = slide.get("normative_ref", "") or ""
        if ref and ref not in seen_refs:
            refs.append(ref)
            seen_refs.add(ref)
        for cid in slide.get("source_chunk_ids", []) or []:
            all_chunk_ids.add(cid)
    return {
        "refs": refs,
        "chunk_count": len(all_chunk_ids),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def run_pipeline(job_id: str, course_id: str) -> None:
    """Main wrapper: acquires the semaphore and wraps the pipeline in a
    global timeout. A stuck job must never monopolise the instance.

    Maps every failure mode to a terminal ``generation_jobs.status`` so the
    UI / WS layer can stop polling.
    """
    async with _job_semaphore:
        try:
            await asyncio.wait_for(
                _run_pipeline_inner(job_id, course_id),
                timeout=PIPELINE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.error(
                "pipeline_timeout",
                job_id=job_id,
                timeout=PIPELINE_TIMEOUT_SECONDS,
            )
            db = get_pool()
            await db.execute(
                "UPDATE generation_jobs SET status='failed', "
                "error_message='Pipeline timeout dopo 30 minuti' WHERE id=$1",
                job_id,
            )
        except asyncio.CancelledError:
            db = get_pool()
            await db.execute(
                "UPDATE generation_jobs SET status='cancelled' WHERE id=$1",
                job_id,
            )
            raise
        except Exception as e:
            logger.error("pipeline_failed", job_id=job_id, error=str(e))
            db = get_pool()
            await db.execute(
                "UPDATE generation_jobs SET status='failed', "
                "error_message=$1 WHERE id=$2",
                str(e)[:500],
                job_id,
            )


async def _run_pipeline_inner(job_id: str, course_id: str) -> None:
    """Inner pipeline logic, isolated for clean timeout/cancel propagation."""
    db = get_pool()
    start_time = time.time()

    if get_shutdown_event().is_set():
        raise asyncio.CancelledError("Server in shutdown")

    # ═══ DB LOAD ═══
    course_row = await db.fetchrow("SELECT * FROM courses WHERE id = $1", course_id)
    if course_row is None:
        raise ValueError(f"Course {course_id} not found")
    course = dict(course_row)

    brand_row = await db.fetchrow(
        "SELECT * FROM brand_presets WHERE id = $1", course["brand_preset_id"]
    )
    if brand_row is None:
        raise ValueError(f"Brand preset {course['brand_preset_id']} not found")
    brand = dict(brand_row)

    # ═══ LANGGRAPH INITIAL STATE (BP §05.2 — 8 fields, no extras) ═══
    initial_state: dict[str, Any] = {
        "course_request": course,
        "brand_config": brand,
        "course_context": None,
        "pacing_plan": None,
        "completed_modules": [],
        "current_module_index": 0,
        "job_id": job_id,
        "errors": [],
    }

    await db.execute(
        "UPDATE generation_jobs SET status='research', started_at=NOW() WHERE id=$1",
        job_id,
    )

    # ═══ LANGGRAPH PIPELINE (D18: create_pipeline è @asynccontextmanager) ═══
    # cast() needed because RunnableConfig + NexusPipelineState are TypedDicts
    # and mypy strict rejects the literal-dict overload, even though
    # `{"configurable": {"thread_id": ...}}` is the canonical LangGraph idiom
    # (BP §05.3) and our initial_state already matches the 8-field shape.
    from typing import cast

    from langchain_core.runnables import RunnableConfig

    pipeline_config = cast(
        RunnableConfig, {"configurable": {"thread_id": job_id}}
    )
    async with create_pipeline(settings.database_url) as pipeline:
        result = await pipeline.ainvoke(
            cast(NexusPipelineState, initial_state), config=pipeline_config
        )

    all_slides = [s for m in result["completed_modules"] for s in m["slides"]]

    # ═══ CRASH-SAFE SAVE (slides JSON + fingerprint BEFORE the build) ═══
    await db.execute(
        "UPDATE courses SET slide_contents_json = $1 WHERE id = $2",
        json.dumps(all_slides),
        course_id,
    )

    fingerprint = build_normative_fingerprint(all_slides)
    chunk_ids = sorted(
        {cid for s in all_slides for cid in (s.get("source_chunk_ids") or [])}
    )
    await db.execute(
        "UPDATE courses SET normative_fingerprint=$1, source_chunk_ids=$2 WHERE id=$3",
        json.dumps(fingerprint),
        chunk_ids,
        course_id,
    )

    await db.execute(
        "UPDATE generation_jobs SET status='building' WHERE id=$1", job_id
    )

    # ═══ IMAGE PRE-FETCH (BP §07.0) ═══
    slide_models = [SlideContent(**s) for s in all_slides]
    image_map = await prefetch_images(slide_models, db)

    # ═══ PRODUCTION BUILD (PPTX + PDF + optional audio) ═══
    builder = ProductionBuilder(brand_config=brand)
    pptx_path, pdf_path, _report = await builder.build(
        slides=slide_models,
        course=course,
        job_id=job_id,
        ws_callback=send_ws_progress,
        image_map=image_map,
        db=db,
    )

    elapsed = time.time() - start_time

    # ═══ FINAL DB STATE ═══
    await db.execute(
        "UPDATE courses SET pptx_path=$1, pdf_path=$2, status='completed' WHERE id=$3",
        str(pptx_path),
        str(pdf_path),
        course_id,
    )
    await db.execute(
        "UPDATE generation_jobs SET status='completed', completed_at=NOW(), "
        "progress_percent=100 WHERE id=$1",
        job_id,
    )

    # ═══ TELEMETRY → audit_log ═══
    await db.execute(
        "INSERT INTO audit_log (action, entity_type, entity_id, details) "
        "VALUES ('pipeline_metrics', 'course', $1, $2)",
        course_id,
        json.dumps(
            {
                "elapsed_seconds": round(elapsed, 1),
                "total_slides": len(all_slides),
                "images_resolved": len(image_map),
            }
        ),
    )

    logger.info(
        "pipeline_completed",
        job_id=job_id,
        slides=len(all_slides),
        elapsed_seconds=round(elapsed, 1),
    )


async def recover_interrupted_jobs(pool: asyncpg.Pool) -> None:
    """v1.0: reset every job stuck mid-flight to 'failed'. The smarter
    LangGraph-checkpoint resume lands in v1.1 (BP §09.2)."""
    result = await pool.execute(
        "UPDATE generation_jobs SET status='failed', "
        "error_message='Interrotto da restart server' "
        "WHERE status IN ('research', 'content', 'building')"
    )
    if result != "UPDATE 0":
        logger.warning("jobs_recovered_to_failed", result=result)


__all__ = [
    "MAX_CONCURRENT_JOBS",
    "PIPELINE_TIMEOUT_SECONDS",
    "build_normative_fingerprint",
    "recover_interrupted_jobs",
    "run_pipeline",
    "send_ws_progress",
]
