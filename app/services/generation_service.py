"""Course generation pipeline wrapper (BLUEPRINT §09.1).

This module will host:
- ``_job_semaphore = asyncio.Semaphore(1)`` (BP §09.1, REI-3 architectural)
- The pipeline runner with shutdown_event awareness
- ``recover_interrupted_jobs`` startup hook

PHASE 0 STUB: only the minimum surface needed by ``app.main`` is implemented
so the container can boot. Real bodies arrive in PHASE 5.
"""

from __future__ import annotations

import asyncio

import asyncpg
import structlog

logger = structlog.get_logger()

# ═══ Single-job semaphore (BP §09.1, REI-3) ═══
# python-pptx + lxml are NOT thread-safe. Semaphore(1) is an architectural
# constraint, not a tuning knob. Do NOT raise this without converting the
# build path to a process pool or Celery.
_job_semaphore = asyncio.Semaphore(1)


async def recover_interrupted_jobs(pool: asyncpg.Pool) -> None:
    """Mark jobs left in 'running' state by a previous crash as 'failed'.

    PHASE 0 STUB: no-op until the ``courses`` table exists (PHASE 1).
    Real implementation will query ``WHERE status = 'running'`` and
    transition them to a recoverable state per BP §09 recovery rules.
    """
    logger.info("recover_interrupted_jobs_stub", note="no-op until PHASE 1 schema")
