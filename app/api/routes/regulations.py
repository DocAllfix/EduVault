"""Regulation endpoints (BLUEPRINT §10).

- POST   /api/regulations/upload      admin only, rate 3/min (BP §08.5) → ingest PDF
- GET    /api/regulations             paginated (?page=1&per_page=20)
- GET    /api/regulations/{id}/chunks paginated (?page=1&per_page=50)
- DELETE /api/regulations/{id}        soft-delete → status='ABROGATA'

Routes stay thin (CLAUDE.md: business logic lives in services). The upload
orchestration is in ingestion_service.ingest_regulation_file().
"""

from __future__ import annotations

import os
import tempfile
import uuid as uuid_mod
from typing import Any

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from app.api.dependencies import get_current_user, limiter, require_role
from app.services.dependencies import get_pool
from app.services.ingestion_service import ingest_regulation_file

logger = structlog.get_logger()

router = APIRouter(prefix="/api/regulations", tags=["regulations"])


class UploadResponse(BaseModel):
    regulation_id: str
    chunks_count: int


class RegulationSummary(BaseModel):
    id: str
    title: str
    type: str
    region: str
    status: str
    slug: str | None = None


class ChunkSummary(BaseModel):
    id: str
    article: str | None = None
    paragraph: str | None = None
    hierarchy_path: str
    body: str
    chunk_type: str
    tags: list[str] = []


class LinkedCourseSummary(BaseModel):
    """Un corso del catalogo che dichiara questa normativa come riferimento.

    Esposto dall'endpoint /regulations/{slug_or_id}/linked-courses così la UI
    può rendere "Questa normativa è usata da N corsi" sulla pagina normativa.
    Il flag `link_source` traccia la provenienza VAA del link (scrape automatico
    vs remap con conferma vs manuale admin vs ereditato v1).
    """

    course_type_slug: str
    title: str
    hours: float
    target: str
    link_source: str  # 'scrape' | 'remap' | 'manual' | 'imported_v1'
    link_notes: str | None = None
    course_approved: bool


@router.post("/upload", response_model=UploadResponse)
@limiter.limit("3/minute")  # BP §08.5 — prevent repeated uploads
async def upload_regulation(
    request: Request,
    file: UploadFile = File(...),
    slug: str = Form(...),
    title: str = Form(...),
    reg_type: str = Form(...),
    issuing_body: str | None = Form(None),
    region: str = Form("NAZIONALE"),
    source_url: str | None = Form(None),
    user: dict[str, Any] = Depends(require_role("admin")),
) -> UploadResponse:
    """Ingest a normative PDF: insert regulation row + run the full pipeline.

    Admin only. The uploaded file is written to a temp path, parsed,
    chunked, classified, embedded and indexed (BP §06.1.1 stages 1-4).
    """
    pool = get_pool()
    raw = await file.read()

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(tmp_fd, "wb") as fh:
            fh.write(raw)
        regulation_id, chunks_count = await ingest_regulation_file(
            tmp_path,
            slug=slug,
            title=title,
            reg_type=reg_type,
            issuing_body=issuing_body,
            region=region,
            source_url=source_url,
            pool=pool,
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return UploadResponse(regulation_id=regulation_id, chunks_count=chunks_count)


@router.get("", response_model=list[RegulationSummary])
async def list_regulations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: dict[str, Any] = Depends(get_current_user),
) -> list[RegulationSummary]:
    """List regulations, paginated (BP §10 — ?page=1&per_page=20)."""
    pool = get_pool()
    offset = (page - 1) * per_page
    rows = await pool.fetch(
        "SELECT id, title, type, region, status, slug FROM regulations "
        "ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        per_page,
        offset,
    )
    return [
        RegulationSummary(
            id=str(r["id"]),
            title=r["title"],
            type=r["type"],
            region=r["region"],
            status=r["status"],
            slug=r["slug"],
        )
        for r in rows
    ]


@router.get("/{regulation_id}/chunks", response_model=list[ChunkSummary])
async def list_chunks(
    regulation_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: dict[str, Any] = Depends(get_current_user),
) -> list[ChunkSummary]:
    """List chunks of a regulation, paginated (BP §10 — ?page=1&per_page=50)."""
    pool = get_pool()
    offset = (page - 1) * per_page
    rows = await pool.fetch(
        "SELECT id, article, paragraph, hierarchy_path, body, chunk_type, tags "
        "FROM regulation_chunks WHERE regulation_id = $1 AND is_current = true "
        "ORDER BY created_at LIMIT $2 OFFSET $3",
        uuid_mod.UUID(regulation_id),
        per_page,
        offset,
    )
    return [
        ChunkSummary(
            id=str(r["id"]),
            article=r["article"],
            paragraph=r["paragraph"],
            hierarchy_path=r["hierarchy_path"],
            body=r["body"],
            chunk_type=r["chunk_type"],
            tags=r["tags"] or [],
        )
        for r in rows
    ]


@router.get("/{slug_or_id}/linked-courses", response_model=list[LinkedCourseSummary])
async def list_linked_courses(
    slug_or_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[LinkedCourseSummary]:
    """Lista dei corsi del catalogo che dichiarano questa normativa come ref.

    Accetta sia lo slug (`dlgs_81_08`) sia il UUID. Risolve via `regulations.slug`
    prima per UX (la UI userà gli slug), poi cade su UUID se non match. Output
    JOIN con `course_type_catalog` per esporre title/hours/target/approved
    senza N+1 lookup lato client.
    """
    pool = get_pool()

    # Risolvi slug -> slug canonico (la tabella regulation_course_type_links usa
    # regulation_slug, non l'UUID, perché i link possono pre-esistere alla
    # ingestione della normativa). Se l'input è già uno slug, lo prendiamo
    # diretto; se è un UUID, lo mappiamo.
    canonical_slug: str | None = None
    try:
        uuid_mod.UUID(slug_or_id)
        canonical_slug = await pool.fetchval(
            "SELECT slug FROM regulations WHERE id = $1",
            uuid_mod.UUID(slug_or_id),
        )
    except ValueError:
        canonical_slug = slug_or_id

    if not canonical_slug:
        raise HTTPException(404, "Normativa non trovata")

    rows = await pool.fetch(
        """
        SELECT
            l.course_type_slug,
            c.title,
            c.hours,
            c.target,
            l.source AS link_source,
            l.notes  AS link_notes,
            (c.approved_at IS NOT NULL) AS course_approved
        FROM regulation_course_type_links AS l
        JOIN course_type_catalog AS c
          ON c.slug = l.course_type_slug
        WHERE l.regulation_slug = $1
        ORDER BY c.title
        """,
        canonical_slug,
    )
    return [
        LinkedCourseSummary(
            course_type_slug=r["course_type_slug"],
            title=r["title"],
            hours=float(r["hours"]),
            target=r["target"],
            link_source=r["link_source"],
            link_notes=r["link_notes"],
            course_approved=r["course_approved"],
        )
        for r in rows
    ]


@router.delete("/{regulation_id}")
async def delete_regulation(
    regulation_id: str,
    user: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, str]:
    """Soft-delete a regulation → status='ABROGATA' (BP §10). Admin only."""
    pool = get_pool()
    result = await pool.execute(
        "UPDATE regulations SET status = 'ABROGATA' WHERE id = $1",
        uuid_mod.UUID(regulation_id),
    )
    if result.endswith("0"):
        raise HTTPException(404, "Normativa non trovata")
    return {"status": "ABROGATA", "regulation_id": regulation_id}
