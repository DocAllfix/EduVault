"""Detailed health check (BLUEPRINT §10.1).

GET /health -> {"status", "database", "disk_free_gb"}

Differences vs BP §10.1 (documented, not invented):
- Routed via APIRouter (BP §14.1 puts endpoints under app/api/routes/).
- Pool accessed through ``get_pool()`` from services.dependencies
  (per BLUEPRINT §14.2: "the pool is accessible via
  services.dependencies — NEVER import it from main.py").
- ``shutil.disk_usage`` falls back to the CWD when ``/app/output`` is not
  present (e.g. running tests on a developer's host); the semantics
  ("degraded" if disk < 1 GB) are unchanged.
"""

from __future__ import annotations

import shutil
from typing import Any

import structlog
from fastapi import APIRouter

from app.services.dependencies import get_pool

logger = structlog.get_logger()

router = APIRouter(tags=["health"])

_DISK_PROBE_PATH = "/app/output"


@router.get("/health")
async def health() -> dict[str, Any]:
    """Return database + disk health.

    Semantics mirror BLUEPRINT §10.1:
    - ``status``: ``"ok"`` only when DB reachable AND disk_free > 1.0 GB.
    - ``database``: ``"connected"`` or ``"unreachable"``.
    - ``disk_free_gb``: GB free on the output volume, rounded to 1 decimal.
    """
    db_ok = False
    try:
        pool = get_pool()
        await pool.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        # BP intent: any failure means "unreachable". No leak of internals.
        pass

    try:
        disk_free_gb = shutil.disk_usage(_DISK_PROBE_PATH).free / (1024 ** 3)
    except (FileNotFoundError, OSError):
        # /app/output exists in the container but not on a host running tests.
        disk_free_gb = shutil.disk_usage(".").free / (1024 ** 3)

    status = "ok" if db_ok and disk_free_gb > 1 else "degraded"
    return {
        "status": status,
        "database": "connected" if db_ok else "unreachable",
        "disk_free_gb": round(disk_free_gb, 1),
    }
