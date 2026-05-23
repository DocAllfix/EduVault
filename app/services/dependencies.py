"""Dependency injection for shared resources (BLUEPRINT §02.4).

The asyncpg pool and the Voyage AI client are initialised once in
``app.main.startup()`` and accessed everywhere via ``get_*()``. The shutdown
event is created here and shared between ``main.py`` and
``generation_service.py``.

VINCOLO ARCHITETTURALE (BP §02.4 + v2.0 pipeline note):
- No semaphore in this module. ``_job_semaphore`` lives in
  ``generation_service.py`` (BP §09.1).
- This is the UNIQUE ``asyncio.Event`` for shutdown across the project.
  Do not create another one anywhere.
"""

from __future__ import annotations

import asyncio
from typing import Any

import asyncpg

# voyageai ships without py.typed, so mypy cannot introspect AsyncClient.
# We alias the type to Any for static analysis; the runtime object is the
# real ``voyageai.AsyncClient`` set by ``main.startup()``.
VoyageClient = Any

_pool: asyncpg.Pool | None = None
_voyage_client: VoyageClient | None = None
_shutdown_event = asyncio.Event()


def set_pool(pool: asyncpg.Pool) -> None:
    """Called ONCE in main.startup(). Do not call elsewhere."""
    global _pool
    _pool = pool


def get_pool() -> asyncpg.Pool:
    """Return the connection pool.

    Raises ``RuntimeError`` if ``set_pool()`` was not called yet.
    Used by LangGraph agents, services, and API routes.
    """
    if _pool is None:
        raise RuntimeError(
            "Pool not initialised — set_pool() was not called in startup()"
        )
    return _pool


def set_voyage_client(client: VoyageClient) -> None:
    """Called ONCE in main.startup(). Do not call elsewhere."""
    global _voyage_client
    _voyage_client = client


def get_voyage_client() -> VoyageClient:
    """Return the Voyage AI client.

    Raises ``RuntimeError`` if ``set_voyage_client()`` was not called yet.
    Used by ingestion_service and research_agent.
    """
    if _voyage_client is None:
        raise RuntimeError(
            "Voyage client not initialised — set_voyage_client() was not called in startup()"
        )
    return _voyage_client


def get_shutdown_event() -> asyncio.Event:
    """Return the SHARED shutdown event.

    ═══ ARCHITECTURAL CONSTRAINT (BP §02.4) ═══
    This is the ONLY shutdown event in the entire project.
    ``main.shutdown()`` sets it, ``generation_service._run_pipeline_inner()``
    reads it. Do NOT create other ``asyncio.Event()`` for shutdown anywhere.
    """
    return _shutdown_event
