"""Course endpoints (BLUEPRINT §10).

- POST   /api/courses                       authenticated, rate 5/min (BP §10.4)
                                            → create course + job, fire-and-forget pipeline
- GET    /api/courses                       paginated, ownership-aware
- GET    /api/courses/{id}                  detail with normative_fingerprint
- POST   /api/courses/{id}/certify          reviewer/admin → Level-2 promotion
- GET    /api/courses/{id}/download/{fmt}   pptx | pdf | zip | audio
- DELETE /api/courses/{id}                  soft-delete → status='archived'

Ownership rule (BP §10.4): non-admin users see only courses they created.
Admins see everything.
"""

from __future__ import annotations

import asyncio
import io
import uuid as uuid_mod
import zipfile
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.api.dependencies import get_current_user, limiter, require_role
from app.models.core import SlideDensity
from app.models.requests import CourseRequest, CourseResponse
from app.services.certification_service import certify_course
from app.services.dependencies import get_pool
from app.services.generation_service import run_pipeline
from app.services.pacing_engine import PacingEngine

logger = structlog.get_logger()

router = APIRouter(prefix="/api/courses", tags=["courses"])

_ACTIVE_JOB_STATES = ("queued", "research", "content", "building")
_DOWNLOAD_FORMATS = ("pptx", "pdf", "zip", "audio")


class CourseSummary(BaseModel):
    id: str
    title: str
    course_type: str
    target: str
    status: str
    duration_hours: float
    created_at: str


class CourseDetail(BaseModel):
    id: str
    title: str
    course_type: str
    target: str
    status: str
    duration_hours: float
    region: str
    pptx_path: str | None = None
    pdf_path: str | None = None
    audio_manifest_path: str | None = None
    normative_fingerprint: dict[str, Any] | None = None
    created_at: str


class CertifyResponse(BaseModel):
    approved_course_id: str


# ─────────────── helpers ───────────────


def _is_admin(user: dict[str, Any]) -> bool:
    return bool(user["role"] == "admin")


async def _load_course_or_404(course_id: str, pool: Any) -> dict[str, Any]:
    try:
        cid = uuid_mod.UUID(course_id)
    except ValueError as exc:
        raise HTTPException(400, "ID corso non valido") from exc
    row = await pool.fetchrow("SELECT * FROM courses WHERE id = $1", cid)
    if not row:
        raise HTTPException(404, "Corso non trovato")
    return dict(row)


def _enforce_ownership(course: dict[str, Any], user: dict[str, Any]) -> None:
    if _is_admin(user):
        return
    if str(course["created_by"]) != str(user["id"]):
        raise HTTPException(403, "Non sei il proprietario di questo corso")


# ─────────────── POST /api/courses ───────────────


@router.post("", response_model=CourseResponse)
@limiter.limit("5/minute")  # BP §10.4 — prevent job flood
async def create_course(
    request: Request,
    req: CourseRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> CourseResponse:
    """Create a course row + a generation_jobs row, schedule the pipeline,
    return the position in the queue (0 = running now)."""
    pool = get_pool()

    # Pacing estimate (deterministic, no DB)
    pacing = PacingEngine().calculate(
        duration_hours=req.duration_hours,
        density=SlideDensity(req.slide_density),
    )
    estimated_minutes = pacing.total_slides * PacingEngine.SECONDS_PER_SLIDE / 60.0

    # Queue position = #jobs not yet completed/failed/cancelled
    queued_count = await pool.fetchval(
        "SELECT COUNT(*) FROM generation_jobs WHERE status = ANY($1::text[])",
        list(_ACTIVE_JOB_STATES),
    )

    course_id = await pool.fetchval(
        "INSERT INTO courses (title, course_type, target, duration_hours, "
        "region, brand_preset_id, created_by, status) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, 'generating') RETURNING id",
        f"Corso {req.course_type}",  # placeholder title; UI can rename later
        req.course_type,
        req.target.value,
        req.duration_hours,
        req.region,
        uuid_mod.UUID(req.brand_preset_id),
        uuid_mod.UUID(str(user["id"])),
    )
    job_id = await pool.fetchval(
        "INSERT INTO generation_jobs (course_id, status, progress_percent) "
        "VALUES ($1, 'queued', 0) RETURNING id",
        course_id,
    )

    # Fire-and-forget pipeline — generation_service.run_pipeline owns
    # the Semaphore(1), so concurrent POSTs serialize naturally.
    asyncio.create_task(run_pipeline(str(job_id), str(course_id)))

    logger.info(
        "course_created",
        course_id=str(course_id),
        job_id=str(job_id),
        user_id=str(user["id"]),
        queue_position=queued_count,
    )

    return CourseResponse(
        course_id=str(course_id),
        job_id=str(job_id),
        estimated_slides=pacing.total_slides,
        estimated_minutes=round(estimated_minutes, 1),
        queue_position=int(queued_count or 0),
    )


# ─────────────── GET /api/courses ───────────────


@router.get("", response_model=list[CourseSummary])
async def list_courses(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    user: dict[str, Any] = Depends(get_current_user),
) -> list[CourseSummary]:
    """List courses, paginated, ownership-aware."""
    pool = get_pool()
    offset = (page - 1) * per_page

    where_clauses: list[str] = []
    params: list[Any] = []
    if not _is_admin(user):
        where_clauses.append(f"created_by = ${len(params) + 1}")
        params.append(uuid_mod.UUID(str(user["id"])))
    if status:
        where_clauses.append(f"status = ${len(params) + 1}")
        params.append(status)
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    params.extend([per_page, offset])
    rows = await pool.fetch(
        f"SELECT id, title, course_type, target, status, duration_hours, "
        f"created_at FROM courses {where_sql} "
        f"ORDER BY created_at DESC LIMIT ${len(params) - 1} OFFSET ${len(params)}",
        *params,
    )
    return [
        CourseSummary(
            id=str(r["id"]),
            title=r["title"],
            course_type=r["course_type"],
            target=r["target"],
            status=r["status"],
            duration_hours=float(r["duration_hours"]),
            created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ]


# ─────────────── GET /api/courses/{id} ───────────────


@router.get("/{course_id}", response_model=CourseDetail)
async def get_course(
    course_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> CourseDetail:
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)

    fingerprint = course.get("normative_fingerprint")
    if isinstance(fingerprint, str):
        import json

        fingerprint = json.loads(fingerprint)

    return CourseDetail(
        id=str(course["id"]),
        title=course["title"],
        course_type=course["course_type"],
        target=course["target"],
        status=course["status"],
        duration_hours=float(course["duration_hours"]),
        region=course["region"],
        pptx_path=course.get("pptx_path"),
        pdf_path=course.get("pdf_path"),
        audio_manifest_path=course.get("audio_manifest_path"),
        normative_fingerprint=fingerprint,
        created_at=course["created_at"].isoformat(),
    )


# ─────────────── POST /api/courses/{id}/certify ───────────────


@router.post("/{course_id}/certify", response_model=CertifyResponse)
async def certify(
    course_id: str,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> CertifyResponse:
    """Promote a course to Level 2 (approved_courses)."""
    pool = get_pool()
    try:
        approved_id = await certify_course(course_id, str(user["id"]), pool)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return CertifyResponse(approved_course_id=approved_id)


# ─────────────── GET /api/courses/{id}/download/{format} ───────────────


def _stream_zip_of_files(files: list[tuple[str, Path]]) -> StreamingResponse:
    """Build an in-memory ZIP and stream it.

    ``files`` is a list of ``(arcname, fs_path)`` tuples; missing files
    are silently skipped (404 only if the ZIP would be empty).
    """
    buf = io.BytesIO()
    written = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, fs_path in files:
            if fs_path.is_file():
                zf.write(fs_path, arcname)
                written += 1
    if written == 0:
        raise HTTPException(404, "Nessun file disponibile per il download")
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip")


@router.get("/{course_id}/download/{fmt}")
async def download_course(
    course_id: str,
    fmt: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> Any:
    """Download artifact: pptx | pdf | zip (pptx+pdf) | audio (zip of MP3s)."""
    if fmt not in _DOWNLOAD_FORMATS:
        raise HTTPException(
            400, f"Formato non valido. Ammessi: {', '.join(_DOWNLOAD_FORMATS)}"
        )
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)

    if fmt == "pptx":
        path = course.get("pptx_path")
        if not path or not Path(path).is_file():
            raise HTTPException(404, "PPTX non disponibile")
        return FileResponse(
            path,
            media_type=(
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ),
            filename=Path(path).name,
        )
    if fmt == "pdf":
        path = course.get("pdf_path")
        if not path or not Path(path).is_file():
            raise HTTPException(404, "PDF non disponibile")
        return FileResponse(path, media_type="application/pdf", filename=Path(path).name)

    if fmt == "zip":
        files = []
        if course.get("pptx_path"):
            files.append((Path(course["pptx_path"]).name, Path(course["pptx_path"])))
        if course.get("pdf_path"):
            files.append((Path(course["pdf_path"]).name, Path(course["pdf_path"])))
        return _stream_zip_of_files(files)

    # fmt == "audio" — zip the directory of MP3s tied to this course
    manifest = course.get("audio_manifest_path")
    if not manifest:
        raise HTTPException(404, "Audio non disponibile per questo corso")
    audio_dir = Path(manifest).parent
    if not audio_dir.is_dir():
        raise HTTPException(404, "Cartella audio non trovata")
    mp3s = sorted(audio_dir.glob("*.mp3"))
    if not mp3s:
        raise HTTPException(404, "Nessun MP3 in cartella audio")
    files = [(f.name, f) for f in mp3s]
    files.append((Path(manifest).name, Path(manifest)))
    return _stream_zip_of_files(files)


# ─────────────── DELETE /api/courses/{id} ───────────────


@router.delete("/{course_id}")
async def delete_course(
    course_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """Soft-delete: status='archived'. Ownership-aware."""
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    await pool.execute(
        "UPDATE courses SET status = 'archived' WHERE id = $1",
        uuid_mod.UUID(course_id),
    )
    return {"status": "archived", "course_id": course_id}
