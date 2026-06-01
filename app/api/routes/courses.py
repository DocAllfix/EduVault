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
        "region, brand_preset_id, created_by, status, outputs) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, 'generating', $8) RETURNING id",
        f"Corso {req.course_type}",  # placeholder title; UI can rename later
        req.course_type,
        req.target.value,
        req.duration_hours,
        req.region,
        uuid_mod.UUID(req.brand_preset_id),
        uuid_mod.UUID(str(user["id"])),
        req.outputs,  # F-BUG-AUDIO 2026-06-01: persistere outputs (era scartato)
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


# ─────────────── F3.AI — LLM micro-actions on skeleton (richiesta cliente 2026-05-31) ───────────────


class SkeletonAIEditVoiceBody(BaseModel):
    """Body per /skeleton/ai-edit-voice — micro-azione LLM su 1 sotto-tema.

    action:
      - rephrase_subtopic: riformula sub_topic + retrieval_query mantenendo significato
      - make_operational: trasforma il sotto-tema da teorico ad operativo/pratico
      - suggest_alternatives: ritorna 3 alternative distinte (taglio diverso)
    """

    action: str  # "rephrase_subtopic" | "make_operational" | "suggest_alternatives"
    module_index: int
    voice_ordinal: int


class SkeletonAIEditModuleBody(BaseModel):
    """Body per /skeleton/ai-edit-module — free-text edit di un intero modulo."""

    module_index: int
    user_instruction: str


@router.post("/{course_id}/skeleton/ai-edit-voice")
@limiter.limit("20/minute")
async def ai_edit_skeleton_voice(
    request: Request,
    course_id: str,
    body: SkeletonAIEditVoiceBody,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> dict[str, Any]:
    """Apply an LLM micro-action to a single sub-topic. Returns proposal(s).

    Pure proposal — no DB mutation. Caller applies via PUT /skeleton if accepted.
    """
    from app.services.skeleton_ai_edit_service import ai_edit_voice
    from config.catalog_config import COURSE_CATALOG

    if body.action not in ("rephrase_subtopic", "make_operational", "suggest_alternatives"):
        raise HTTPException(400, f"Azione non valida: {body.action}")

    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    if course.get("status") != "skeleton_pending":
        raise HTTPException(409, "Il corso non è in attesa di approvazione struttura")
    raw = course.get("module_skeletons_json")
    if raw is None:
        raise HTTPException(409, "Nessuna struttura disponibile")

    # BUG #6 fix: asyncpg restituisce JSONB come str → decode a dict.
    import json as _json_skel
    if isinstance(raw, str):
        try:
            raw = _json_skel.loads(raw)
        except Exception:
            raise HTTPException(500, "Struttura corrotta (parse error)")

    # raw è dict {"version", "modules": [...]}
    modules_list = raw.get("modules", []) if isinstance(raw, dict) else []
    target_module = next(
        (m for m in modules_list if m.get("module_index") == body.module_index),
        None,
    )
    if target_module is None:
        raise HTTPException(404, f"Modulo {body.module_index} non trovato nella struttura")
    target_item_raw = next(
        (it for it in target_module.get("items", []) if it.get("ordinal") == body.voice_ordinal),
        None,
    )
    if target_item_raw is None:
        raise HTTPException(
            404, f"Sotto-tema {body.voice_ordinal} non trovato nel modulo {body.module_index}"
        )
    target_item = ModuleSkeleton(**target_module).items[body.voice_ordinal - 1]

    catalog_entry = COURSE_CATALOG.get(course["course_type"], {})
    course_title_human = str(catalog_entry.get("title") or course["title"])

    result = await ai_edit_voice(
        action=body.action,  # type: ignore[arg-type]
        current_item=target_item,
        module_title=str(target_module.get("title", "")),
        course_title=course_title_human,
        course_id=course_id,
    )
    return result


@router.post("/{course_id}/skeleton/ai-edit-module")
@limiter.limit("10/minute")
async def ai_edit_skeleton_module(
    request: Request,
    course_id: str,
    body: SkeletonAIEditModuleBody,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> dict[str, Any]:
    """Apply a free-text user instruction to an entire module. Returns patch.items.

    Pure proposal — no DB mutation. Caller applies via PUT /skeleton if accepted.
    """
    from app.services.skeleton_ai_edit_service import ai_edit_module
    from config.catalog_config import COURSE_CATALOG

    instr = (body.user_instruction or "").strip()
    if len(instr) < 5:
        raise HTTPException(400, "Istruzione troppo corta (min 5 caratteri)")
    if len(instr) > 1000:
        raise HTTPException(400, "Istruzione troppo lunga (max 1000 caratteri)")

    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    if course.get("status") != "skeleton_pending":
        raise HTTPException(409, "Il corso non è in attesa di approvazione struttura")
    raw = course.get("module_skeletons_json")
    if raw is None:
        raise HTTPException(409, "Nessuna struttura disponibile")

    # BUG #6 fix: asyncpg restituisce JSONB come str → decode a dict.
    import json as _json_skel2
    if isinstance(raw, str):
        try:
            raw = _json_skel2.loads(raw)
        except Exception:
            raise HTTPException(500, "Struttura corrotta (parse error)")

    modules_list = raw.get("modules", []) if isinstance(raw, dict) else []
    target_module = next(
        (m for m in modules_list if m.get("module_index") == body.module_index),
        None,
    )
    if target_module is None:
        raise HTTPException(404, f"Modulo {body.module_index} non trovato nella struttura")

    current_sk = ModuleSkeleton(**target_module)
    sibling_titles = [
        str(m.get("title", "")) for m in modules_list if m.get("module_index") != body.module_index
    ]
    catalog_entry = COURSE_CATALOG.get(course["course_type"], {})
    course_title_human = str(catalog_entry.get("title") or course["title"])

    result = await ai_edit_module(
        current_skeleton=current_sk,
        user_instruction=instr,
        course_title=course_title_human,
        sibling_module_titles=sibling_titles,
        course_id=course_id,
    )
    return result


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


def _enrich_slide_with_body(slide: dict[str, Any]) -> dict[str, Any]:
    """FIX 2026-06-01 bug edit: frontend Studio si aspetta `body: str` ma il
    backend SlideContent ha `bullets: list[str]`. Aggiungo `body` derivato
    qui sul GET response cosi' il TextArea del slide-editor mostra i bullets
    veri (era empty -> utente vedeva slide vuota e l'edit non aveva effetto).
    """
    bullets = slide.get("bullets") or []
    sezioni = slide.get("sezioni") or []
    # CASE_STUDY usa sezioni (3 elementi) invece di bullets. Per quel tipo
    # joina sezioni nel body cosi' il textarea editor le mostra. Per tutti
    # gli altri tipi joina bullets.
    if slide.get("slide_type") == "CASE_STUDY" and sezioni:
        slide["body"] = "\n".join(sezioni)
    else:
        slide["body"] = "\n".join(bullets) if bullets else ""
    return slide


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
    slides = [_enrich_slide_with_body(s) for s in slides]
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
        slide = await studio_service.get_slide_by_idx(course_id, idx, pool)
    except LookupError as exc:
        raise HTTPException(404, f"Slide {idx} non trovata") from exc
    return _enrich_slide_with_body(slide)


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
    return _enrich_slide_with_body(updated)


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


@router.get("/{course_id}/audio/{idx}/info")
async def get_course_slide_audio_info(
    course_id: str,
    idx: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """F7.4 — Metadata audio track per UI badge (vast-hopping post-MVP 2026-05-31).

    Ritorna provider (edge | azure) + voice + duration. Usato da audio-player.tsx
    per mostrare badge "Azure" premium signal accanto al play button.
    """
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    row = await pool.fetchrow(
        "SELECT provider, voice, duration_seconds "
        "FROM audio_tracks WHERE course_id = $1 AND slide_index = $2",
        uuid_mod.UUID(course_id),
        idx,
    )
    if not row:
        raise HTTPException(404, f"Audio track slide {idx} non trovato")
    return {
        "provider": row["provider"] or "edge",
        "voice": row["voice"],
        "duration_seconds": float(row["duration_seconds"])
        if row["duration_seconds"] is not None
        else None,
    }


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


# ─────────────── F5.2 — Image library semantic search (tier 1 cascade) ───────────────


class LibraryHitDTO(BaseModel):
    """LibraryHit per UI Library tab. Mirror di
    app.services.image_library_service.LibraryHit."""

    id: str
    file_path: str
    tags: list[str]
    source: str
    license: str | None = None
    attribution: str | None = None
    source_url: str | None = None
    width: int | None = None
    height: int | None = None
    usage_count: int
    score: float


class LibrarySearchResponse(BaseModel):
    hits: list[LibraryHitDTO]
    query: str


@router.get(
    "/{course_id}/image/library/search",
    response_model=LibrarySearchResponse,
)
@limiter.limit("60/minute")
async def search_image_library(
    request: Request,
    course_id: str,
    q: str = Query(..., min_length=2),
    k: int = Query(8, ge=1, le=24),
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> LibrarySearchResponse:
    """F5.2 — Semantic search su image_library locale.

    Riusa ``image_library_service.search`` (voyage-multimodal-3 cosine + GIN
    tag fallback). Rate 60/min (search-side, ben sopra 30/min Pexels). Ritorna
    fino a 24 hit con license/attribution per chip UI.
    """
    from app.services.image_library_service import search as library_search

    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    hits = await library_search(q, pool, k=k)
    return LibrarySearchResponse(
        hits=[LibraryHitDTO(**hit.model_dump()) for hit in hits],
        query=q,
    )


# ─────────────── FASE 11 — Regenerate + Rebuild ───────────────


class RegenerateBody(BaseModel):
    instruction: str = ""
    # F4b (analista 2026-05-31): flag per usare H8 voce-aware regen invece di
    # legacy instruction-based regen. Quando True, ignora instruction e usa
    # build_voice_prompt con chunks della voce skeleton owner della slide.
    use_h8: bool = False


@router.post("/{course_id}/slides/{idx}/regenerate")
async def regenerate_slide(
    course_id: str,
    idx: int,
    body: RegenerateBody,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> dict[str, Any]:
    """Rigenera UNA slide via LLM (FASE 11 + F4b H8 voce-aware 2026-05-31).

    Due modalita`:
      - Legacy (default, use_h8=False): rigenera secondo body.instruction
        passato dall'utente (es. "rendi piu` operativo", "accorcia speaker_notes").
        Mantiene source_chunk_ids + slide_type. Usato da F6 chat Studio futuro.
      - H8 voce-aware (use_h8=True): ignora instruction, identifica voce skeleton
        owner della slide via heuristica + materializza chunks B2+B3+B4 per voce
        + genera slide con build_voice_prompt. Usato da F4b bottone "Rigenera
        questa slide" su slide flagged da quality-issues.

    Entrambe le modalita`: marca dirty=true, persiste slide nel JSON. Cliente
    deve poi POST /rebuild per ricostruire PPTX.
    """
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)

    if body.use_h8:
        # F4b H8 voce-aware path
        # Verifica slide_type rigenerabile (no bookends)
        try:
            slide = await studio_service.get_slide_by_idx(course_id, idx, pool)
        except LookupError as exc:
            raise HTTPException(404, f"Slide {idx} non trovata") from exc
        slide_type = slide.get("slide_type", "")
        if slide_type in ("MODULE_OPEN", "MODULE_CLOSE", "TITLE", "CLOSING"):
            raise HTTPException(
                409,
                f"Slide {idx} di tipo {slide_type} e' bookend programmatico, non rigenerabile via LLM H8. "
                "Edita manualmente via PATCH /slides/{idx} se necessario."
            )
        # Verifica prerequisito skeleton
        if course.get("module_skeletons_json") is None:
            raise HTTPException(
                409,
                "Corso senza module_skeletons_json: rigenerazione H8 richiede skeleton. "
                "Genera il corso con flag v2_skeleton_validation=true."
            )
        from app.agents.content_agent import regenerate_single_slide_h8
        try:
            return await regenerate_single_slide_h8(
                course_id=course_id, slide_index=idx, pool=pool
            )
        except RuntimeError as exc:
            raise HTTPException(409, f"Rigenerazione H8 fallita: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(500, f"Errore interno rigenerazione H8: {exc}") from exc

    # Legacy path (instruction-based, retro-compat)
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


# ─────────────────────────────────────────────────────────────────────────────
# F4 D9 Slide Quality Issues (analista sign-off 2026-05-31 post-H8b rollback)
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/{course_id}/quality-issues")
async def get_quality_issues(
    course_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Ritorna issue D9 per le slide del corso (badge UI Course Studio).

    Compute on-the-fly via slide_quality_service.compute_slide_issues() da
    slide_contents_json + course.regulation_ids. NON blocca download (decisione
    D9 VAA-c: visibilita' si, coercizione no).

    Output:
      {
        "course_id": str,
        "total_issues": int,
        "by_severity": {error: N, warning: N, info: N},
        "by_type": {issue_type: count, ...},
        "issues": [{slide_index, module_index, issue_type, severity, context}, ...]
      }
    """
    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)

    try:
        slides = await studio_service.get_slides(course_id, pool)
    except LookupError as exc:
        raise HTTPException(404, "Corso non trovato") from exc
    if not slides:
        return {
            "course_id": course_id,
            "total_issues": 0,
            "by_severity": {},
            "by_type": {},
            "issues": [],
        }

    # Resolve course.regulation_ids → regulation_slugs per bullet/title citation checks
    from config.catalog_config import COURSE_CATALOG
    catalog_entry = COURSE_CATALOG.get(course["course_type"], {})
    regulation_slugs_raw = catalog_entry.get("regs") if catalog_entry else None
    regulation_slugs = [str(s) for s in (regulation_slugs_raw or []) if s]

    from app.services.slide_quality_service import compute_slide_issues
    result = compute_slide_issues(
        slides=slides,
        course_regulation_ids=regulation_slugs,
        expected_slides_per_module=70,
    )
    result["course_id"] = course_id
    return result


# ─────────────── F6 — Chat LLM Course Studio (vast-hopping post-MVP) ───────────────


class ChatTurnBody(BaseModel):
    """Body per POST /chat: utente manda messaggio ancorato a una slide."""

    message: str
    slide_index: int


class ChatMessageDTO(BaseModel):
    id: str
    role: str
    content: str
    slide_index: int | None = None
    tool_calls: dict[str, Any] | None = None
    applied_at: str | None = None
    created_at: str | None = None


class ChatHistoryResponse(BaseModel):
    conversation_id: str
    messages: list[ChatMessageDTO]


@router.get("/{course_id}/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    course_id: str,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> ChatHistoryResponse:
    """Ritorna la cronologia chat per il corso (memoria cross-session)."""
    from app.services.chat_service import get_or_create_conversation, list_messages

    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)
    conv_id = await get_or_create_conversation(pool, course_id, str(user["id"]))
    msgs = await list_messages(pool, conv_id, limit=200)
    return ChatHistoryResponse(
        conversation_id=conv_id,
        messages=[ChatMessageDTO(**m) for m in msgs],
    )


@router.post("/{course_id}/chat")
@limiter.limit("30/minute")
async def chat_send(
    request: Request,
    course_id: str,
    body: ChatTurnBody,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> StreamingResponse:
    """Streaming SSE: invia un turno chat, ritorna parziali ChatTurnResponse
    via SSE mentre il LLM compila. Frontend rende typing-effect.

    Format SSE event:
      event: partial
      data: {"assistant_message": "...", "proposed_patch": null}

      event: done
      data: {"message_id_user": "...", "message_id_assistant": "...", "provider": "azure"}

      event: error
      data: {"detail": "..."}
    """
    import json as _json

    from app.services.chat_service import (
        ChatTurnResponse,
        chat_turn_stream,
        get_or_create_conversation,
        insert_message,
        list_messages,
    )

    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)

    msg = (body.message or "").strip()
    if len(msg) < 2:
        raise HTTPException(400, "Messaggio troppo corto")
    if len(msg) > 2000:
        raise HTTPException(400, "Messaggio troppo lungo (max 2000 char)")

    # Carica slide context. BUG #3 fix: slide_contents_json può essere wrappato
    # in struttura {completed_modules: [{slides: [...]}]} o {slides: [...]} o
    # list flat. Riusa studio_service._deserialize_slides per normalizzare.
    from app.services.studio_service import _deserialize_slides

    slides_flat = _deserialize_slides(course.get("slide_contents_json"))
    if not slides_flat:
        raise HTTPException(409, "Slide non disponibili (corso non generato)")
    target_slide = next(
        (s for s in slides_flat if s.get("index") == body.slide_index), None
    )
    if target_slide is None:
        raise HTTPException(404, f"Slide {body.slide_index} non trovata")

    slide_title = str(target_slide.get("title", ""))
    slide_body = target_slide.get("body", []) or []
    slide_notes = str(target_slide.get("speaker_notes", ""))

    # Course title
    from config.catalog_config import COURSE_CATALOG

    catalog_entry = COURSE_CATALOG.get(course["course_type"], {})
    course_title = str(catalog_entry.get("title") or course["title"])

    # Conversation persistente (memoria cross-session)
    conv_id = await get_or_create_conversation(pool, course_id, str(user["id"]))
    history = await list_messages(pool, conv_id, limit=24)

    # INSERT user message subito (visibile anche se streaming fallisce)
    user_msg_id = await insert_message(
        pool,
        conversation_id=conv_id,
        role="user",
        content=msg,
        slide_index=body.slide_index,
    )

    async def _stream() -> "Any":
        last_partial: ChatTurnResponse | None = None
        try:
            async for partial in chat_turn_stream(
                user_message=msg,
                slide_title=slide_title,
                slide_body=slide_body,
                slide_notes=slide_notes,
                course_title=course_title,
                history=history,
                course_id=course_id,
            ):
                last_partial = partial
                payload = partial.model_dump(exclude_none=False)
                yield f"event: partial\ndata: {_json.dumps(payload)}\n\n"
            # Stream done: INSERT assistant message + done event
            if last_partial is not None:
                tool_calls_dict = (
                    {"proposed_patch": last_partial.proposed_patch.model_dump()}
                    if last_partial.proposed_patch
                    else None
                )
                assistant_msg_id = await insert_message(
                    pool,
                    conversation_id=conv_id,
                    role="assistant",
                    content=last_partial.assistant_message or "",
                    slide_index=body.slide_index,
                    tool_calls=tool_calls_dict,
                )
                done = {
                    "message_id_user": user_msg_id,
                    "message_id_assistant": assistant_msg_id,
                    "conversation_id": conv_id,
                }
                yield f"event: done\ndata: {_json.dumps(done)}\n\n"
        except Exception as exc:  # noqa: BLE001
            err = {"detail": str(exc)[:200]}
            yield f"event: error\ndata: {_json.dumps(err)}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx/Railway proxy: disable buffering
        },
    )


@router.post("/{course_id}/chat/messages/{message_id}/apply")
@limiter.limit("30/minute")
async def chat_apply_message(
    request: Request,
    course_id: str,
    message_id: str,
    user: dict[str, Any] = Depends(require_role("admin", "reviewer")),
) -> dict[str, Any]:
    """Applica il proposed_patch di un assistant message alla slide.

    Idempotente: se gia' applicato → 409. Riusa PATCH /slides/{idx} esistente
    via update_slide del studio_service.
    """
    from app.services.chat_service import mark_message_applied

    pool = get_pool()
    course = await _load_course_or_404(course_id, pool)
    _enforce_ownership(course, user)

    # Verifica esistenza message + recupera tool_calls (proposed_patch)
    row = await pool.fetchrow(
        "SELECT id, role, slide_index, tool_calls, applied_at "
        "FROM messages WHERE id = $1::uuid",
        message_id,
    )
    if row is None:
        raise HTTPException(404, "Messaggio non trovato")
    if row["role"] != "assistant":
        raise HTTPException(400, "Solo i messaggi assistant possono essere applicati")
    if row["applied_at"] is not None:
        raise HTTPException(409, "Messaggio gia' applicato")
    # BUG #4 fix: asyncpg restituisce JSONB come str → decodifica a dict
    tool_calls_raw = row["tool_calls"]
    tool_calls: dict[str, Any] | None
    if tool_calls_raw is None:
        tool_calls = None
    elif isinstance(tool_calls_raw, dict):
        tool_calls = tool_calls_raw
    else:
        import json as _json3
        try:
            tool_calls = _json3.loads(tool_calls_raw)
        except Exception:
            tool_calls = None

    if not tool_calls or not isinstance(tool_calls, dict):
        raise HTTPException(400, "Nessun patch proposto in questo messaggio")
    patch = tool_calls.get("proposed_patch")
    if not patch or not isinstance(patch, dict):
        raise HTTPException(400, "Nessun proposed_patch nel messaggio")

    slide_idx = row["slide_index"]
    if slide_idx is None:
        raise HTTPException(400, "Messaggio senza slide_index ancorato")

    # Applica patch: riusa studio_service.update_slide come PATCH /slides/{idx}
    # Solo i campi != None del proposed_patch vengono inviati.
    patch_clean: dict[str, Any] = {}
    if patch.get("title") is not None:
        patch_clean["title"] = patch["title"]
    if patch.get("body") is not None:
        patch_clean["body"] = patch["body"]
    if patch.get("speaker_notes") is not None:
        patch_clean["speaker_notes"] = patch["speaker_notes"]
    if not patch_clean:
        raise HTTPException(400, "proposed_patch vuoto (nessun campo da applicare)")

    await studio_service.update_slide(course_id, slide_idx, patch_clean, pool)

    # Marca message come applicato (idempotency)
    await mark_message_applied(pool, message_id)
    return {"applied": True, "message_id": message_id, "slide_index": slide_idx}

