"""Admin / dashboard endpoints (BLUEPRINT §10).

All four endpoints in this file are admin-only per the FASE 5.4 prompt
(D57): even ``dashboard/stats``, ``brand-presets`` and ``catalog`` —
which by topic could be open to any authenticated user — are gated to
``require_role("admin")`` here. If a future prompt needs them open to
operator/reviewer, relax the dependency in 5.5 or in the frontend layer.

- GET /api/admin/metrics       → aggregate pipeline metrics from audit_log
- GET /api/dashboard/stats     → courses/regulations/L2 counts
- GET /api/brand-presets       → list of brand presets
- GET /api/catalog             → COURSE_CATALOG (config-driven)
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.dependencies import require_role
from app.services.dependencies import get_pool
from config.catalog_config import COURSE_CATALOG

logger = structlog.get_logger()

router = APIRouter(tags=["admin"])


class MetricsResponse(BaseModel):
    total_runs: int
    avg_elapsed_seconds: float
    avg_slides: float
    total_images_resolved: int
    period_days: int


class RecentCourse(BaseModel):
    id: str
    title: str
    status: str
    created_at: str


class DashboardStats(BaseModel):
    courses_count: int
    regulations_count: int
    l2_count: int
    # FASE 13 vast-hopping — 4 dati arricchimento dashboard
    status_breakdown: dict[str, int]  # {generating: 2, completed: 10, ...}
    recent_courses: list[RecentCourse]  # ultimi 5 corsi generati
    dirty_count: int  # corsi con modifiche non rigenerate
    total_training_hours: float  # somma duration_hours di tutti i corsi


class BrandPresetSummary(BaseModel):
    id: str
    name: str
    palette: dict[str, Any]
    is_default: bool


# ─────────────── GET /api/admin/metrics ───────────────


@router.get("/api/admin/metrics", response_model=MetricsResponse)
async def admin_metrics(
    days: int = Query(7, ge=1, le=365),
    user: dict[str, Any] = Depends(require_role("admin")),
) -> MetricsResponse:
    """Aggregate ``pipeline_metrics`` rows from audit_log over the last
    ``?days=N`` window (default 7, max 365).

    FASE 5.1 _run_pipeline_inner inserts one row per completed pipeline:
        action='pipeline_metrics'
        details={"elapsed_seconds": float, "total_slides": int,
                 "images_resolved": int}
    """
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT details FROM audit_log "
        "WHERE action = 'pipeline_metrics' "
        "AND created_at >= NOW() - ($1 || ' days')::interval",
        str(days),
    )

    if not rows:
        return MetricsResponse(
            total_runs=0,
            avg_elapsed_seconds=0.0,
            avg_slides=0.0,
            total_images_resolved=0,
            period_days=days,
        )

    total_runs = len(rows)
    total_elapsed = 0.0
    total_slides = 0
    total_images = 0
    for r in rows:
        d = r["details"]
        if isinstance(d, str):
            d = json.loads(d)
        total_elapsed += float(d.get("elapsed_seconds", 0))
        total_slides += int(d.get("total_slides", 0))
        total_images += int(d.get("images_resolved", 0))

    return MetricsResponse(
        total_runs=total_runs,
        avg_elapsed_seconds=round(total_elapsed / total_runs, 2),
        avg_slides=round(total_slides / total_runs, 2),
        total_images_resolved=total_images,
        period_days=days,
    )


# ─────────────── GET /api/dashboard/stats ───────────────


@router.get("/api/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats(
    user: dict[str, Any] = Depends(require_role("admin")),
) -> DashboardStats:
    """Counts for the dashboard: courses, regulations, approved_courses (L2),
    + FASE 13: status breakdown, recent 5 courses, dirty count, total hours."""
    pool = get_pool()
    courses_count = await pool.fetchval("SELECT COUNT(*) FROM courses")
    regulations_count = await pool.fetchval("SELECT COUNT(*) FROM regulations")
    l2_count = await pool.fetchval("SELECT COUNT(*) FROM approved_courses")

    # 1. status breakdown
    status_rows = await pool.fetch(
        "SELECT status, COUNT(*) AS n FROM courses GROUP BY status"
    )
    status_breakdown = {str(r["status"]): int(r["n"]) for r in status_rows}

    # 2. ultimi 5 corsi generati
    recent_rows = await pool.fetch(
        "SELECT id, title, status, created_at FROM courses "
        "ORDER BY created_at DESC LIMIT 5"
    )
    recent_courses = [
        RecentCourse(
            id=str(r["id"]),
            title=str(r["title"]),
            status=str(r["status"]),
            created_at=r["created_at"].isoformat() if r["created_at"] else "",
        )
        for r in recent_rows
    ]

    # 3. corsi con modifiche non rigenerate (dirty=true)
    dirty_count = await pool.fetchval(
        "SELECT COUNT(*) FROM courses WHERE dirty = true"
    )

    # 4. ore totali di formazione prodotte
    total_hours = await pool.fetchval(
        "SELECT COALESCE(SUM(duration_hours), 0) FROM courses "
        "WHERE status IN ('completed', 'certified', 'reviewed')"
    )

    return DashboardStats(
        courses_count=int(courses_count or 0),
        regulations_count=int(regulations_count or 0),
        l2_count=int(l2_count or 0),
        status_breakdown=status_breakdown,
        recent_courses=recent_courses,
        dirty_count=int(dirty_count or 0),
        total_training_hours=float(total_hours or 0),
    )


# ─────────────── GET /api/brand-presets ───────────────


@router.get("/api/brand-presets", response_model=list[BrandPresetSummary])
async def list_brand_presets(
    user: dict[str, Any] = Depends(require_role("admin")),
) -> list[BrandPresetSummary]:
    """List brand presets — default first, then alphabetical."""
    pool = get_pool()
    rows = await pool.fetch(
        "SELECT id, name, palette, is_default FROM brand_presets "
        "ORDER BY is_default DESC, name ASC"
    )
    out: list[BrandPresetSummary] = []
    for r in rows:
        palette = r["palette"]
        if isinstance(palette, str):
            palette = json.loads(palette)
        out.append(
            BrandPresetSummary(
                id=str(r["id"]),
                name=r["name"],
                palette=palette or {},
                is_default=bool(r["is_default"]),
            )
        )
    return out


# ─────────────── GET /api/catalog ───────────────


@router.get("/api/catalog")
async def get_catalog(
    user: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, dict[str, Any]]:
    """Return the COURSE_CATALOG dict (config/catalog_config.py).

    Read-only snapshot — modifications require a code change + redeploy.
    """
    return COURSE_CATALOG
