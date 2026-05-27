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
