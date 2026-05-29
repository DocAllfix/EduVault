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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.api.dependencies import get_current_user, limiter, require_role
from app.models.core import SlideDensity
from app.models.pipeline import ModuleSkeleton
from app.models.requests import CourseRequest, CourseResponse
from app.services import studio_service
from app.services.certification_service import certify_course
from app.services.dependencies import get_pool
from app.services.generation_service import run_pipeline
from app.services.image_search import search_image
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


# ─── FASE 7 Course Studio body models ───


class SlidePatch(BaseModel):
    """Campi editabili di una slide via Studio (tutti opzionali)."""

    title: str | None = None
    body: str | None = None
    speaker_notes: str | None = None
    normative_ref: str | None = None
    quiz_options: list[str] | None = None
    quiz_correct: int | None = None


class ImagePatch(BaseModel):
    strategy: str | None = None
    query: str | None = None
    query_url: str | None = None
    aspect_hint: str | None = None
    diagram_code: str | None = None


class ImageSearchResult(BaseModel):
    candidates: list[str]


# ─── D3 skeleton review body models (vast-hopping-sketch) ───


class SkeletonResponse(BaseModel):
    """The course's module skeletons + approval state, for the review UI."""

    course_id: str
    status: str
    modules: list[ModuleSkeleton]
    approved_at: str | None = None


class SkeletonUpdate(BaseModel):
    """Operator edit of the skeleton (reorder / text / add-remove).

    Each module is validated by ``ModuleSkeleton`` (6-10 items, contiguous
    ordinals) on the way in — the manual edit path (NL chat is D7).
    """

    modules: list[ModuleSkeleton]


class SkeletonApproveResponse(BaseModel):
    status: str
    job_id: str


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


# ─────────────── D3 skeleton review (vast-hopping-sketch) ───────────────


@router.get("/{course_id}/skeleton", response_model=SkeletonResponse)
async def get_skeleton(
    course_id: str,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> SkeletonResponse:
    """Return the course's per-module skeletons for the review gate.

    404 if the course has no skeleton yet (flag off, or not at skeleton_pending).
    """
    import json as _json

    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    raw = course.get("module_skeletons_json")
    if raw is None:
        raise HTTPException(404, "Nessuno scheletro per questo corso")
    payload = _json.loads(raw) if isinstance(raw, str) else raw
    modules = [ModuleSkeleton.model_validate(m) for m in payload.get("modules", [])]
    approved_at = course.get("skeleton_approved_at")
    return SkeletonResponse(
        course_id=course_id,
        status=str(course.get("status")),
        modules=modules,
        approved_at=approved_at.isoformat() if approved_at else None,
    )


@router.put("/{course_id}/skeleton", response_model=SkeletonResponse)
async def update_skeleton(
    course_id: str,
    body: SkeletonUpdate,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> SkeletonResponse:
    """Persist an operator edit of the skeleton (reorder / text / add-remove).

    Only allowed while the course is at ``skeleton_pending`` (before approval).
    Each module is already validated by ``ModuleSkeleton`` (6-10 items,
    contiguous ordinals) via the request body.
    """
    import json as _json

    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    if course.get("status") != "skeleton_pending":
        raise HTTPException(
            409, "Lo scheletro è modificabile solo prima dell'approvazione"
        )
    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "modules": [m.model_dump() for m in body.modules],
    }
    await pool.execute(
        "UPDATE courses SET module_skeletons_json=$1 WHERE id=$2",
        _json.dumps(payload),
        uuid_mod.UUID(course_id),
    )
    return SkeletonResponse(
        course_id=course_id,
        status="skeleton_pending",
        modules=body.modules,
        approved_at=None,
    )


@router.post("/{course_id}/skeleton/approve", response_model=SkeletonApproveResponse)
@limiter.limit("10/minute")
async def approve_skeleton(
    request: Request,
    course_id: str,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> SkeletonApproveResponse:
    """1-click validation gate: stamp approval + fire the content phase.

    The (possibly edited) skeleton in ``module_skeletons_json`` becomes the
    source for per-sub-topic retrieval. Fires ``run_pipeline(phase="content")``
    fire-and-forget under the global Semaphore(1) (REI-3).
    """
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    if course.get("status") != "skeleton_pending":
        raise HTTPException(409, "Il corso non è in attesa di approvazione scheletro")
    if course.get("module_skeletons_json") is None:
        raise HTTPException(409, "Nessuno scheletro da approvare")

    await pool.execute(
        "UPDATE courses SET skeleton_approved_at=NOW(), skeleton_approved_by=$1, "
        "status='content' WHERE id=$2",
        str(user["id"]),
        uuid_mod.UUID(course_id),
    )
    job_id = await pool.fetchval(
        "INSERT INTO generation_jobs (course_id, status, progress_percent) "
        "VALUES ($1, 'queued', 0) RETURNING id",
        uuid_mod.UUID(course_id),
    )
    asyncio.create_task(run_pipeline(str(job_id), course_id, "content"))
    return SkeletonApproveResponse(status="content", job_id=str(job_id))


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


# ─────────────── POST /api/courses/{id}/artifact (admin) ──
# Replace the PPTX or PDF on disk for an already-existing course. Used when
# the operator hand-edited the file in PowerPoint and wants it to BE the
# downloadable / preview source of truth without going through a rebuild.
# Marks the course `dirty=false` and bumps `last_rebuilt_at` so the preview
# cache (output/previews/{course_id}/{rebuild_token}/) invalidates correctly.


_UPLOADABLE_FORMATS = {"pptx", "pdf"}


@router.post("/{course_id}/artifact")
async def upload_course_artifact(
    course_id: str,
    fmt: str = Form(...),
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Admin-only: replace the PPTX or PDF artifact of an existing course."""
    fmt = fmt.lower()
    if fmt not in _UPLOADABLE_FORMATS:
        raise HTTPException(400, f"fmt deve essere uno di {sorted(_UPLOADABLE_FORMATS)}")

    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)

    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)
    if fmt == "pptx":
        target = out_dir / f"{course_id}.pptx"
        col = "pptx_path"
    else:
        target = out_dir / f"{course_id}_dispensa.pdf"
        col = "pdf_path"

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty file")
    with open(target, "wb") as fh:
        fh.write(raw)

    # Bump last_rebuilt_at so the preview PNG cache key changes → users get
    # a fresh render of the new file instead of the cached old pages.
    await pool.execute(
        f"UPDATE courses SET {col}=$1, dirty=false, last_rebuilt_at=NOW() WHERE id=$2",
        str(target),
        uuid_mod.UUID(course_id),
    )
    return {
        "status": "ok",
        "course_id": course_id,
        "fmt": fmt,
        "path": str(target),
        "bytes": len(raw),
    }


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


# ─────────────── FASE 7 — Course Studio endpoints ───────────────


@router.get("/{course_id}/slides")
async def get_course_slides(
    course_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Ritorna l'array di slide del corso (deserializzato da slide_contents_json).

    409 se il corso non ha ancora slide (es. legacy o generazione fallita).
    """
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    try:
        slides = await studio_service.get_slides(course_id, pool)
    except LookupError as exc:
        raise HTTPException(404, "Corso non trovato") from exc
    if not slides:
        raise HTTPException(409, "Corso non editabile: nessuna slide generata")
    return {"course_id": course_id, "total": len(slides), "slides": slides}


@router.get("/{course_id}/slides/{idx}")
async def get_course_slide(
    course_id: str,
    idx: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Ritorna una singola slide per index."""
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    try:
        return await studio_service.get_slide_by_idx(course_id, idx, pool)
    except LookupError as exc:
        raise HTTPException(404, f"Slide {idx} non trovata") from exc


@router.patch("/{course_id}/slides/{idx}")
async def patch_course_slide(
    course_id: str,
    idx: int,
    patch: SlidePatch,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> dict[str, Any]:
    """Aggiorna i campi specificati di una slide. Ri-valida strict (422 se viola
    i constraints FASE 1). Marca il corso dirty=true (RebuildBanner)."""
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    changes = {k: v for k, v in patch.model_dump().items() if v is not None}
    if not changes:
        raise HTTPException(400, "Nessun campo da aggiornare")
    try:
        updated = await studio_service.update_slide(course_id, idx, changes, pool)
    except LookupError as exc:
        raise HTTPException(404, f"Slide {idx} non trovata") from exc
    except Exception as exc:  # Pydantic ValidationError → 422
        raise HTTPException(422, f"Slide non valida dopo modifica: {exc}") from exc
    return updated


@router.patch("/{course_id}/slides/{idx}/image")
async def patch_course_slide_image(
    course_id: str,
    idx: int,
    patch: ImagePatch,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> dict[str, Any]:
    """Aggiorna il sub-doc image di una slide (query/url/aspect/diagram)."""
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    image_changes = {k: v for k, v in patch.model_dump().items() if v is not None}
    if not image_changes:
        raise HTTPException(400, "Nessun campo immagine da aggiornare")
    try:
        return await studio_service.set_slide_image(course_id, idx, image_changes, pool)
    except LookupError as exc:
        raise HTTPException(404, f"Slide {idx} non trovata") from exc
    except Exception as exc:
        raise HTTPException(422, f"Immagine non valida: {exc}") from exc


@router.get("/{course_id}/audio/{idx}")
async def get_course_slide_audio(
    course_id: str,
    idx: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> FileResponse:
    """Stream del singolo MP3 della slide (per AudioPlayer in-app FASE 10)."""
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    row = await pool.fetchrow(
        "SELECT audio_path FROM audio_tracks WHERE course_id = $1 AND slide_index = $2",
        uuid_mod.UUID(course_id),
        idx,
    )
    if not row or not row["audio_path"]:
        raise HTTPException(404, f"Audio slide {idx} non trovato")
    audio_path = Path(row["audio_path"])
    if not audio_path.is_file():
        raise HTTPException(404, "File audio mancante su disco")
    return FileResponse(str(audio_path), media_type="audio/mpeg",
                        filename=f"slide_{idx:04d}.mp3")


@router.get("/{course_id}/slides/{idx}/preview.png")
async def get_slide_preview_png(
    course_id: str,
    idx: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> FileResponse:
    """Render of the actual PDF page as PNG so Course Studio shows what the
    operator will get in the PPTX/PDF (real layout, real images, real diagrams).

    Cached on disk under output/previews/{course_id}/{rebuild_token}/{idx}.png
    so repeat opens of the same slide are instant; cache is keyed on the
    course's `last_rebuilt_at` timestamp so a rebuild invalidates it
    automatically without manual cleanup.
    """
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)

    pdf_path_str = course.get("pdf_path")
    if not pdf_path_str:
        raise HTTPException(404, "PDF non disponibile per questo corso (mai rigenerato).")
    pdf_path = Path(pdf_path_str)
    if not pdf_path.is_file():
        raise HTTPException(404, "PDF mancante su disco — rigenera il corso.")

    # Cache token derived from the rebuild timestamp (or created_at fallback).
    ts = course.get("last_rebuilt_at") or course.get("created_at")
    token = str(int(ts.timestamp())) if ts else "v0"

    cache_dir = Path("output") / "previews" / str(course_id) / token
    cache_dir.mkdir(parents=True, exist_ok=True)
    png_path = cache_dir / f"{idx:04d}.png"

    if not png_path.is_file():
        # Lazy import keeps cold-start cheap when nobody opens the preview.
        import pypdfium2 as pdfium  # type: ignore[import-not-found]

        pdf = pdfium.PdfDocument(str(pdf_path))
        try:
            if idx < 0 or idx >= len(pdf):
                raise HTTPException(404, f"Slide {idx} fuori range PDF ({len(pdf)} pagine).")
            page = pdf[idx]
            # 1.6 ≈ 153 DPI: leggible on retina without bloating the cache.
            pil_image = page.render(scale=1.6).to_pil()
            pil_image.save(png_path, format="PNG", optimize=True)
        finally:
            pdf.close()

    return FileResponse(
        str(png_path),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/{course_id}/image/search", response_model=ImageSearchResult)
@limiter.limit("30/minute")
async def search_slide_images(
    request: Request,
    course_id: str,
    q: str = Query(..., min_length=2),
    orientation: str | None = Query(None),
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> ImageSearchResult:
    """Cerca immagini candidate (Pexels orientation + Wikimedia) per ImagePicker.

    Rate-limit 30/min (FASE 7 R3 mitigation). Ritorna fino a 1 URL per ora
    (search_image cascade ritorna il best match); estendibile a multi-result
    in v2.
    """
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    url = await search_image(q, orientation=orientation)
    return ImageSearchResult(candidates=[url] if url else [])


# ─────────────── FASE 11 — Regenerate + Rebuild ───────────────


class RegenerateBody(BaseModel):
    instruction: str


@router.post("/{course_id}/slides/{idx}/regenerate")
async def regenerate_slide(
    course_id: str,
    idx: int,
    body: RegenerateBody,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> dict[str, Any]:
    """Rigenera UNA slide via LLM secondo l'istruzione utente (FASE 11).

    Mantiene source_chunk_ids (provenance) e slide_type. Ri-valida strict.
    Marca dirty=true.
    """
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    try:
        updated = await studio_service.regenerate_slide(
            course_id, idx, body.instruction, pool
        )
    except LookupError as exc:
        raise HTTPException(404, f"Slide {idx} non trovata") from exc
    except Exception as exc:
        raise HTTPException(422, f"Rigenerazione fallita: {exc}") from exc
    return updated


# ── Slide management (FASE 6 — add / move / delete / duplicate) ──────────


class AddSlideBody(BaseModel):
    after_idx: int
    slide_type: str


class MoveSlideBody(BaseModel):
    direction: str  # "up" | "down"


@router.post("/{course_id}/slides")
async def add_course_slide(
    course_id: str,
    body: AddSlideBody,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> list[dict[str, Any]]:
    """Inserisce una nuova slide vuota del tipo scelto dopo ``after_idx``.

    Ritorna l'array slide aggiornato. Marca dirty=true (RebuildBanner).
    """
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    try:
        return await studio_service.add_slide(
            course_id, body.after_idx, body.slide_type, pool
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, f"Impossibile aggiungere slide: {exc}") from exc


@router.post("/{course_id}/slides/{idx}/move")
async def move_course_slide(
    course_id: str,
    idx: int,
    body: MoveSlideBody,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> list[dict[str, Any]]:
    """Sposta la slide su/giù (solo nello stesso modulo)."""
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    try:
        return await studio_service.move_slide(course_id, idx, body.direction, pool)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, f"Impossibile spostare slide: {exc}") from exc


@router.post("/{course_id}/slides/{idx}/duplicate")
async def duplicate_course_slide(
    course_id: str,
    idx: int,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> list[dict[str, Any]]:
    """Duplica la slide (copia inserita subito dopo)."""
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    try:
        return await studio_service.duplicate_slide(course_id, idx, pool)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, f"Impossibile duplicare slide: {exc}") from exc


@router.delete("/{course_id}/slides/{idx}")
async def delete_course_slide(
    course_id: str,
    idx: int,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> list[dict[str, Any]]:
    """Elimina la slide (vietato sui bookend di modulo)."""
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    try:
        return await studio_service.delete_slide(course_id, idx, pool)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, f"Impossibile eliminare slide: {exc}") from exc


@router.post("/{course_id}/rebuild")
async def rebuild_course(
    course_id: str,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> dict[str, str]:
    """Ricostruisce PPTX/PDF/audio dal slide_contents_json corrente (FASE 11).

    Async fire-and-forget sotto il Semaphore(1) di generation_service (REI-3).
    Dopo la rebuild il corso torna dirty=false.
    """
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    from app.services.rebuild_service import rebuild_course as do_rebuild

    asyncio.create_task(do_rebuild(course_id, str(user["id"]), pool))
    return {"status": "rebuilding", "course_id": course_id}

