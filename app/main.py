"""FastAPI entry point (BLUEPRINT §02.5).

Modernised vs. BP §02.5 on two points (REI-14, OPT-2):
- env access goes through ``app.config.settings``, never ``os.environ[...]``
- ``recover_interrupted_jobs`` is imported lazily inside ``startup()`` to
  avoid a circular import while ``generation_service`` is still empty
  (this is a documented BP intent — see "NESSUN _shutdown_event LOCALE"
  comment block — applied here as a lazy import).
"""

from __future__ import annotations

import asyncio

import structlog
import voyageai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.api.dependencies import limiter
from app.api.routes import auth as auth_routes
from app.api.routes import health as health_routes
from app.api.routes import regulations as regulations_routes
from app.config import configure_logging, settings
from app.db.connection import create_pool
from app.services.dependencies import (
    get_shutdown_event,
    set_pool,
    set_voyage_client,
)

logger = structlog.get_logger()

app = FastAPI(title="Nexus EduVault API", version="6.0")

# ═══ RATE LIMITING (BP §02.5) ═══
# limiter instance lives in app.api.dependencies (shared with route modules).
app.state.limiter = limiter
# Note: slowapi's handler is typed for RateLimitExceeded, but Starlette's
# add_exception_handler expects a generic Exception handler. Functionally
# compatible at runtime — only the static signature differs.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# ═══ CORS — explicit origin, NEVER wildcard (REI-10, BP §02.5) ═══
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# ═══ NO LOCAL _shutdown_event ═══
# The shutdown event lives in services/dependencies.py — get_shutdown_event().
# Do NOT create an asyncio.Event() here. Architectural constraint (BP D-18).

# ═══ ROUTES ═══
app.include_router(health_routes.router)
app.include_router(auth_routes.router)
app.include_router(regulations_routes.router)


@app.on_event("startup")
async def startup() -> None:
    configure_logging()
    pool = await create_pool()
    app.state.db = pool
    set_pool(pool)  # make the pool accessible via get_pool() everywhere
    # voyageai has no py.typed; the construct works at runtime.
    set_voyage_client(voyageai.AsyncClient(api_key=settings.voyage_api_key))  # type: ignore[attr-defined]

    # Lazy import: generation_service is still unwritten in PHASE 0.
    # Once PHASE 5 lands the module, this resolves at startup time.
    from app.services.generation_service import recover_interrupted_jobs

    await recover_interrupted_jobs(pool)
    logger.info("nexus_started", version="6.0")


@app.on_event("shutdown")
async def shutdown() -> None:
    """Graceful shutdown.

    Signal in-flight jobs to stop, wait up to 30 seconds, then close the pool.
    Uses the SHARED shutdown event from dependencies.py (BP §02.5).
    """
    # Lazy import for the same reason as startup().
    from app.services.generation_service import _job_semaphore

    get_shutdown_event().set()  # tell the pipeline to stop
    try:
        await asyncio.wait_for(_job_semaphore.acquire(), timeout=30)
    except asyncio.TimeoutError:
        logger.warning(
            "shutdown_timeout",
            msg="Job in flight did not terminate within 30s",
        )
    await app.state.db.close()
    logger.info("nexus_shutdown")
