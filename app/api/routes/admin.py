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
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.api.dependencies import require_role
from app.services.auth_service import hash_password
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


# ─────────────── F1 — Admin catalog DB-driven CRUD (D8 vast-hopping) ───────────────
# Sostituisce a regime ``GET /api/catalog`` (config-driven) quando flag
# ``v2_catalog_from_db=true``. Gate VAA-c: solo entries con approved_at IS NOT
# NULL sono disponibili per la generazione (pattern "sistema propone, umano
# valida"). Default flag OFF -> coesistenza con config-driven path.


class CatalogEntrySummary(BaseModel):
    """Single catalog entry for the admin table (paginated list)."""

    slug: str
    title: str
    hours: float
    target: str
    regulation_slugs: list[str]
    regional: bool
    source: str
    source_url: str | None = None
    scraped_at: str | None = None
    approved_at: str | None = None
    approved_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    n_modules: int


class CatalogListResponse(BaseModel):
    entries: list[CatalogEntrySummary]
    total: int
    page: int
    per_page: int


class CatalogModule(BaseModel):
    id: str
    ordinal: int
    title: str
    normative_refs: list[str]
    source: str
    created_at: str | None = None


class CatalogEntryDetail(CatalogEntrySummary):
    modules: list[CatalogModule]


class CatalogUpdateBody(BaseModel):
    """PATCH body — tutti i campi opzionali, applicati solo se forniti."""

    title: str | None = None
    hours: float | None = None
    target: str | None = None
    regulation_slugs: list[str] | None = None
    regional: bool | None = None


class CatalogBulkApproveBody(BaseModel):
    slugs: list[str]


class CatalogSummaryByTarget(BaseModel):
    target: str
    n_total: int
    n_approved: int


class CatalogSummaryResponse(BaseModel):
    total: int
    approved: int
    pending: int
    by_target: list[CatalogSummaryByTarget]
    snapshot_at: str


@router.get("/api/admin/catalog/summary", response_model=CatalogSummaryResponse)
async def admin_catalog_summary(
    user: dict[str, Any] = Depends(require_role("admin")),
) -> CatalogSummaryResponse:
    """Aggregato per header pagina catalog-review: count totale + approved + per target."""
    from app.services.catalog_service import get_catalog_summary

    pool = get_pool()
    data = await get_catalog_summary(pool)
    return CatalogSummaryResponse(**data)


@router.get("/api/admin/catalog", response_model=CatalogListResponse)
async def admin_list_catalog(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    approved_only: bool = Query(False),
    target: str | None = Query(None),
    search: str | None = Query(None),
    user: dict[str, Any] = Depends(require_role("admin")),
) -> CatalogListResponse:
    """Lista paginata + filtri (target, approved, search)."""
    from app.services.catalog_service import list_catalog_entries

    pool = get_pool()
    entries, total = await list_catalog_entries(
        pool,
        page=page,
        per_page=per_page,
        approved_only=approved_only,
        target_filter=target,
        search=search,
    )
    return CatalogListResponse(
        entries=[CatalogEntrySummary(**e) for e in entries],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/api/admin/catalog/{slug}", response_model=CatalogEntryDetail)
async def admin_get_catalog_entry(
    slug: str,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> CatalogEntryDetail:
    """Dettaglio entry + moduli (ordered by ordinal)."""
    from fastapi import HTTPException

    from app.services.catalog_service import get_catalog_entry

    pool = get_pool()
    data = await get_catalog_entry(pool, slug)
    if data is None:
        raise HTTPException(404, f"Catalog entry '{slug}' non trovata")
    return CatalogEntryDetail(**data)


@router.patch("/api/admin/catalog/{slug}", response_model=CatalogEntryDetail)
async def admin_update_catalog_entry(
    slug: str,
    body: CatalogUpdateBody,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> CatalogEntryDetail:
    """PATCH parziale (solo campi forniti). Ritorna l'entry aggiornata."""
    from fastapi import HTTPException

    from app.services.catalog_service import get_catalog_entry, update_catalog_entry

    pool = get_pool()
    ok = await update_catalog_entry(
        pool,
        slug,
        title=body.title,
        hours=body.hours,
        target=body.target,
        regulation_slugs=body.regulation_slugs,
        regional=body.regional,
    )
    if not ok:
        raise HTTPException(404, f"Catalog entry '{slug}' non trovata")
    data = await get_catalog_entry(pool, slug)
    if data is None:
        raise HTTPException(404, f"Catalog entry '{slug}' sparita post-update")
    return CatalogEntryDetail(**data)


@router.post("/api/admin/catalog/{slug}/approve", response_model=CatalogEntryDetail)
async def admin_approve_catalog_entry(
    slug: str,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> CatalogEntryDetail:
    """Gate VAA-c — stamp approved_at + approved_by, l'entry diventa disponibile
    per la generazione quando flag v2_catalog_from_db=true."""
    from fastapi import HTTPException

    from app.services.catalog_service import approve_catalog_entry, get_catalog_entry

    pool = get_pool()
    ok = await approve_catalog_entry(pool, slug, approver_user_id=str(user["id"]))
    if not ok:
        raise HTTPException(404, f"Catalog entry '{slug}' non trovata")
    data = await get_catalog_entry(pool, slug)
    if data is None:
        raise HTTPException(404, f"Catalog entry '{slug}' sparita post-approve")
    return CatalogEntryDetail(**data)


@router.post("/api/admin/catalog/{slug}/unapprove", response_model=CatalogEntryDetail)
async def admin_unapprove_catalog_entry(
    slug: str,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> CatalogEntryDetail:
    """Revoca approval — l'entry torna draft (non disponibile per generazione)."""
    from fastapi import HTTPException

    from app.services.catalog_service import get_catalog_entry, unapprove_catalog_entry

    pool = get_pool()
    ok = await unapprove_catalog_entry(pool, slug)
    if not ok:
        raise HTTPException(404, f"Catalog entry '{slug}' non trovata")
    data = await get_catalog_entry(pool, slug)
    if data is None:
        raise HTTPException(404, f"Catalog entry '{slug}' sparita post-unapprove")
    return CatalogEntryDetail(**data)


@router.post("/api/admin/catalog/bulk-approve")
async def admin_bulk_approve_catalog(
    body: CatalogBulkApproveBody,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, int]:
    """Approve in batch (UI tabella checkbox + bottone 'Approva selezionati')."""
    from app.services.catalog_service import bulk_approve_catalog_entries

    pool = get_pool()
    n = await bulk_approve_catalog_entries(
        pool, body.slugs, approver_user_id=str(user["id"])
    )
    return {"approved_count": n}


# ─────────────── F5.2 — Image library admin audit ───────────────


class ImageLibraryEntry(BaseModel):
    """Single image_library row for admin table."""

    id: str
    file_path: str
    tags: list[str]
    source: str
    license: str | None = None
    attribution: str | None = None
    source_url: str | None = None
    width: int | None = None
    height: int | None = None
    bytes: int | None = None
    usage_count: int
    created_at: str | None = None
    updated_at: str | None = None


class ImageLibraryListResponse(BaseModel):
    entries: list[ImageLibraryEntry]
    total: int
    page: int
    per_page: int


@router.get("/api/admin/images/library", response_model=ImageLibraryListResponse)
async def admin_list_image_library(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    source: str | None = Query(None),
    user: dict[str, Any] = Depends(require_role("admin")),
) -> ImageLibraryListResponse:
    """Lista paginata image_library + filtro source per UI admin audit (F5.2)."""
    from app.services.image_library_service import list_admin

    pool = get_pool()
    entries, total = await list_admin(
        pool, page=page, per_page=per_page, source_filter=source
    )
    return ImageLibraryListResponse(
        entries=[ImageLibraryEntry(**e) for e in entries],
        total=total,
        page=page,
        per_page=per_page,
    )


# ─────────────── Step B — Image library upload + delete ───────────────


class ImageUploadResponse(BaseModel):
    id: str
    file_path: str


@router.post("/api/admin/images/library", response_model=ImageUploadResponse)
async def admin_upload_image(
    file: UploadFile = File(...),
    tags: str = Form(...),
    source: str = Form("manual_upload"),
    license: str | None = Form("Proprietary"),
    attribution: str | None = Form(None),
    source_url: str | None = Form(None),
    user: dict[str, Any] = Depends(require_role("admin")),
) -> ImageUploadResponse:
    """Step B — admin upload PNG/JPG → embed Voyage → INSERT image_library.

    Pillow.verify + size check + Voyage multimodal embed sync (server-side).
    Idempotente su file_path UNIQUE constraint.
    """
    from pathlib import Path
    import uuid

    from PIL import Image

    from app.services.embeddings import embed_image_multimodal
    from app.services.image_library_service import insert_admin

    # Validate ext + size
    if file.content_type not in ("image/png", "image/jpeg"):
        raise HTTPException(400, "only PNG/JPEG supported")
    contents = await file.read()
    if len(contents) > 5_000_000:
        raise HTTPException(400, "file too large (max 5MB)")
    if len(contents) < 1000:
        raise HTTPException(400, "file too small")

    # Persist to disk: assets/seeds/uploads/{uuid}.{ext}
    ext = "png" if file.content_type == "image/png" else "jpg"
    uid = str(uuid.uuid4())
    rel_path = f"assets/seeds/uploads/{uid}.{ext}"
    abs_path = Path(rel_path).resolve()
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(contents)

    # Validate via Pillow
    try:
        with Image.open(abs_path) as im:
            im.verify()
        with Image.open(abs_path) as im2:
            width, height = im2.size
    except Exception as exc:
        abs_path.unlink(missing_ok=True)
        raise HTTPException(400, f"invalid image: {exc}")

    # Parse tags (comma-separated -> lowercase normalized list)
    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
    if not tag_list:
        raise HTTPException(400, "at least 1 tag required")

    # Voyage embed (multimodal: image + tag string)
    caption = " ".join(tag_list[:5]) if tag_list else None
    embedding = await embed_image_multimodal(abs_path, caption=caption)

    pool = get_pool()
    new_id = await insert_admin(
        pool,
        file_path=rel_path,
        tags=tag_list,
        embedding=embedding,
        source=source,
        license=license,
        attribution=attribution,
        source_url=source_url,
        width=width,
        height=height,
        bytes_=len(contents),
    )
    return ImageUploadResponse(id=new_id, file_path=rel_path)


@router.delete("/api/admin/images/library/{image_id}")
async def admin_delete_image(
    image_id: str,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, str]:
    """Step B — DELETE row from image_library by id. File on disk preserved."""
    from app.services.image_library_service import delete_admin

    pool = get_pool()
    deleted = await delete_admin(pool, image_id)
    if not deleted:
        raise HTTPException(404, "image not found")
    return {"status": "deleted"}


# ─────────────── Step C — Diagrams catalog admin viewer ───────────────


class DiagramSlotInfo(BaseModel):
    name: str
    max_chars: int


class DiagramTemplateInfo(BaseModel):
    name: str
    description: str
    slots: list[DiagramSlotInfo]
    usage_count: int
    svg_available: bool
    svg_content: str | None = None  # inline SVG markup (sicuro: lo controlliamo noi)


@router.get("/api/admin/diagrams/{name}/svg")
async def admin_diagram_svg(
    name: str,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
):
    """Step C — serve SVG template content for /admin/diagrams iframe preview.

    Path validation: name must match DIAGRAM_CATALOG keys (no path traversal).
    """
    from fastapi.responses import FileResponse

    from app.services.diagram_service import DIAGRAM_CATALOG

    tpl = DIAGRAM_CATALOG.get(name)
    if tpl is None:
        raise HTTPException(404, "diagram template not found")
    if not tpl.template_path.exists():
        raise HTTPException(404, "svg file not found on disk")
    return FileResponse(
        str(tpl.template_path),
        media_type="image/svg+xml",
        filename=f"{name}.svg",
    )


@router.get("/api/admin/diagrams/catalog", response_model=list[DiagramTemplateInfo])
async def admin_diagrams_catalog(
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> list[DiagramTemplateInfo]:
    """Step C — lista template diagram disponibili + usage count + slot info.

    Read-only catalog viewer. SVG content NON serializzato per response size
    (frontend lo richiedera' via path separato se necessario).
    """
    from app.services.diagram_service import DIAGRAM_CATALOG

    pool = get_pool()
    # Count usage from slide_contents_json LIKE '%"template_name":"{name}"%'
    rows = await pool.fetch(
        """
        SELECT
          regexp_matches(slide_contents_json::text, '"template_name"\\s*:\\s*"([^"]+)"', 'g')
            AS m
        FROM courses
        WHERE slide_contents_json IS NOT NULL
        """
    )
    from collections import Counter
    usage_counter: Counter[str] = Counter()
    for r in rows:
        # m is regexp_matches group array
        m = r["m"]
        if m and len(m) > 0:
            usage_counter[m[0]] += 1

    out: list[DiagramTemplateInfo] = []
    for tpl in DIAGRAM_CATALOG.values():
        svg_content: str | None = None
        if tpl.template_path.exists():
            try:
                svg_content = tpl.template_path.read_text(encoding="utf-8")
            except Exception:
                svg_content = None
        out.append(DiagramTemplateInfo(
            name=tpl.name,
            description=tpl.description,
            slots=[
                DiagramSlotInfo(name=s.name, max_chars=s.max_chars)
                for s in tpl.slots
            ],
            usage_count=usage_counter.get(tpl.name, 0),
            svg_available=svg_content is not None,
            svg_content=svg_content,
        ))
    return out


# ─────────────── POST /api/admin/users ───────────────


class CreateUserRequest(BaseModel):
    email: str
    password: str
    role: str = "admin"


class CreateUserResponse(BaseModel):
    id: str
    email: str
    role: str


@router.post("/api/admin/users", response_model=CreateUserResponse, status_code=201)
async def create_user(
    body: CreateUserRequest,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> CreateUserResponse:
    if body.role not in ("admin", "operator", "reviewer"):
        raise HTTPException(400, "role must be admin/operator/reviewer")
    if len(body.password) < 8:
        raise HTTPException(400, "password must be at least 8 chars")

    pool = get_pool()
    existing = await pool.fetchval("SELECT id FROM users WHERE email = $1", body.email)
    if existing:
        raise HTTPException(409, "email already registered")

    pwd_hash = hash_password(body.password)
    row = await pool.fetchrow(
        "INSERT INTO users (email, password_hash, role, is_active) "
        "VALUES ($1, $2, $3, true) RETURNING id, email, role",
        body.email, pwd_hash, body.role,
    )
    logger.info("admin_user_created", email=body.email, role=body.role, created_by=user["email"])
    return CreateUserResponse(id=str(row["id"]), email=row["email"], role=row["role"])
