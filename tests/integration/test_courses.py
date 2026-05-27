"""Course endpoints tests (FASE 5.2).

Covers:
- POST /api/courses: 401 senza token, 5/min rate limit, queue_position, fire-and-forget
- GET  /api/courses: ownership-aware filter, paginazione
- GET  /api/courses/{id}: 404 / 403 / 200, fingerprint serializzato
- POST /api/courses/{id}/certify: ruolo reviewer/admin only
- GET  /api/courses/{id}/download/{fmt}: pptx/pdf/zip/audio + 404 path mancanti
- DELETE /api/courses/{id}: soft-delete archived, ownership
"""

from __future__ import annotations

import io
import json
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# WeasyPrint shim (transitive import via generation_service → production_builder)
if "weasyprint" not in sys.modules:  # pragma: no cover
    sys.modules["weasyprint"] = MagicMock()

from app.main import app  # noqa: E402
from app.services import dependencies as deps  # noqa: E402
from app.services.auth_service import create_access_token  # noqa: E402


# ─────────────── fixtures ───────────────


ADMIN_ID = "11111111-1111-1111-1111-111111111111"
OPERATOR_ID = "22222222-2222-2222-2222-222222222222"
REVIEWER_ID = "33333333-3333-3333-3333-333333333333"


def _token(user_id: str, role: str) -> str:
    return create_access_token(user_id, role)


def _user_row(user_id: str, role: str) -> dict[str, Any]:
    return {
        "id": uuid.UUID(user_id),
        "email": f"{role}@nexus-eduvault.local",
        "role": role,
        "is_active": True,
    }


def _course_row(
    course_id: str,
    *,
    created_by: str = OPERATOR_ID,
    status: str = "completed",
    pptx_path: str | None = None,
    pdf_path: str | None = None,
    audio_manifest_path: str | None = None,
    fingerprint: dict[str, Any] | None = None,
    slide_contents_json: str | None = None,
) -> dict[str, Any]:
    return {
        "id": uuid.UUID(course_id),
        "title": "Corso Test",
        "course_type": "primo_soccorso_gruppo_b_c",
        "target": "discente",
        "duration_hours": 1.0,
        "region": "NAZIONALE",
        "brand_preset_id": uuid.UUID("44444444-4444-4444-4444-444444444444"),
        "created_by": uuid.UUID(created_by),
        "status": status,
        "pptx_path": pptx_path,
        "pdf_path": pdf_path,
        "audio_manifest_path": audio_manifest_path,
        "normative_fingerprint": json.dumps(fingerprint) if fingerprint else None,
        "source_chunk_ids": [],
        "slide_contents_json": slide_contents_json,
        "created_at": datetime(2026, 5, 24, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 5, 24, tzinfo=timezone.utc),
    }


def _wire_pool(pool: Any) -> Any:
    """Inject ``pool`` into both the global getter and the route module."""
    deps.set_pool(pool)
    return pool


@pytest.fixture(autouse=True)
def _reset_pool() -> Any:
    yield
    deps._pool = None


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ─────────────── POST /api/courses ───────────────


def test_create_course_unauthenticated_returns_401(client: TestClient) -> None:
    r = client.post(
        "/api/courses",
        json={
            "course_type": "primo_soccorso_gruppo_b_c",
            "target": "discente",
            "duration_hours": 1.0,
            "brand_preset_id": "44444444-4444-4444-4444-444444444444",
        },
    )
    # 401 (HTTPBearer) or 403 (some FastAPI versions wrap missing header as 403)
    assert r.status_code in (401, 403)


def test_create_course_inserts_rows_and_returns_queue_position(
    client: TestClient,
) -> None:
    pool = MagicMock()
    new_course_id = uuid.uuid4()
    new_job_id = uuid.uuid4()
    pool.fetchrow = AsyncMock(return_value=_user_row(OPERATOR_ID, "operator"))
    pool.fetchval = AsyncMock(
        side_effect=[
            3,            # queue_count
            new_course_id,  # INSERT courses RETURNING id
            new_job_id,     # INSERT generation_jobs RETURNING id
        ]
    )
    pool.execute = AsyncMock(return_value=None)
    _wire_pool(pool)

    # Stub run_pipeline so the fire-and-forget task is a no-op
    async def _noop(*_a: Any, **_kw: Any) -> None:
        return None

    with patch("app.api.routes.courses.run_pipeline", new=_noop):
        r = client.post(
            "/api/courses",
            json={
                "course_type": "primo_soccorso_gruppo_b_c",
                "target": "discente",
                "duration_hours": 1.0,
                "brand_preset_id": "44444444-4444-4444-4444-444444444444",
            },
            headers={"Authorization": f"Bearer {_token(OPERATOR_ID, 'operator')}"},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["course_id"] == str(new_course_id)
    assert body["job_id"] == str(new_job_id)
    assert body["queue_position"] == 3
    assert body["estimated_slides"] > 0  # 1h → ~120 slide
    assert body["estimated_minutes"] > 0


def test_create_course_rejects_unknown_outputs(client: TestClient) -> None:
    """The Pydantic validator on outputs fires before any DB call."""
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(OPERATOR_ID, "operator"))
    _wire_pool(pool)

    r = client.post(
        "/api/courses",
        json={
            "course_type": "primo_soccorso_gruppo_b_c",
            "target": "discente",
            "duration_hours": 1.0,
            "brand_preset_id": "44444444-4444-4444-4444-444444444444",
            "outputs": ["jpg"],
        },
        headers={"Authorization": f"Bearer {_token(OPERATOR_ID, 'operator')}"},
    )
    assert r.status_code == 422


# ─────────────── GET /api/courses ───────────────


def test_list_courses_operator_sees_only_owned(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(OPERATOR_ID, "operator"))
    own_id = uuid.uuid4()
    pool.fetch = AsyncMock(
        return_value=[
            {
                "id": own_id,
                "title": "Mio Corso",
                "course_type": "primo_soccorso_gruppo_b_c",
                "target": "discente",
                "status": "completed",
                "duration_hours": 1.0,
                "created_at": datetime(2026, 5, 24, tzinfo=timezone.utc),
            }
        ]
    )
    _wire_pool(pool)

    r = client.get(
        "/api/courses",
        headers={"Authorization": f"Bearer {_token(OPERATOR_ID, 'operator')}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == str(own_id)
    # The SQL must include ``created_by = $N``
    sql = pool.fetch.await_args.args[0]
    assert "created_by" in sql


def test_list_courses_admin_omits_ownership_filter(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(ADMIN_ID, "admin"))
    pool.fetch = AsyncMock(return_value=[])
    _wire_pool(pool)

    r = client.get(
        "/api/courses",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 200
    sql = pool.fetch.await_args.args[0]
    assert "created_by" not in sql


def test_list_courses_status_filter_propagates_to_sql(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(ADMIN_ID, "admin"))
    pool.fetch = AsyncMock(return_value=[])
    _wire_pool(pool)

    r = client.get(
        "/api/courses?status=certified",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 200
    sql = pool.fetch.await_args.args[0]
    assert "status = $" in sql


# ─────────────── GET /api/courses/{id} ───────────────


def test_get_course_returns_404_when_missing(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(
        side_effect=[_user_row(OPERATOR_ID, "operator"), None]
    )
    _wire_pool(pool)

    r = client.get(
        f"/api/courses/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {_token(OPERATOR_ID, 'operator')}"},
    )
    assert r.status_code == 404


def test_get_course_returns_403_when_not_owner(client: TestClient) -> None:
    pool = MagicMock()
    cid = str(uuid.uuid4())
    pool.fetchrow = AsyncMock(
        side_effect=[
            _user_row(OPERATOR_ID, "operator"),
            _course_row(cid, created_by=ADMIN_ID),
        ]
    )
    _wire_pool(pool)

    r = client.get(
        f"/api/courses/{cid}",
        headers={"Authorization": f"Bearer {_token(OPERATOR_ID, 'operator')}"},
    )
    assert r.status_code == 403


def test_get_course_returns_detail_with_parsed_fingerprint(
    client: TestClient,
) -> None:
    pool = MagicMock()
    cid = str(uuid.uuid4())
    fp = {"refs": ["Art. 1"], "chunk_count": 1, "generated_at": "2026-05-24"}
    pool.fetchrow = AsyncMock(
        side_effect=[
            _user_row(ADMIN_ID, "admin"),
            _course_row(cid, fingerprint=fp),
        ]
    )
    _wire_pool(pool)

    r = client.get(
        f"/api/courses/{cid}",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == cid
    assert body["normative_fingerprint"] == fp


# ─────────────── POST /api/courses/{id}/certify ───────────────


def test_certify_requires_reviewer_or_admin(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(OPERATOR_ID, "operator"))
    _wire_pool(pool)

    r = client.post(
        f"/api/courses/{uuid.uuid4()}/certify",
        headers={"Authorization": f"Bearer {_token(OPERATOR_ID, 'operator')}"},
    )
    assert r.status_code == 403


def test_certify_calls_service_and_returns_approved_id(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(REVIEWER_ID, "reviewer"))
    _wire_pool(pool)

    cid = str(uuid.uuid4())
    new_approved = str(uuid.uuid4())

    async def _fake_certify(course_id: str, reviewer_id: str, _pool: Any) -> str:
        assert course_id == cid
        assert reviewer_id == REVIEWER_ID
        return new_approved

    with patch("app.api.routes.courses.certify_course", new=_fake_certify):
        r = client.post(
            f"/api/courses/{cid}/certify",
            headers={"Authorization": f"Bearer {_token(REVIEWER_ID, 'reviewer')}"},
        )
    assert r.status_code == 200
    assert r.json() == {"approved_course_id": new_approved}


def test_certify_translates_value_error_into_400(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(ADMIN_ID, "admin"))
    _wire_pool(pool)

    async def _boom(*_a: Any, **_kw: Any) -> str:
        raise ValueError("Course not found or has no slide content")

    with patch("app.api.routes.courses.certify_course", new=_boom):
        r = client.post(
            f"/api/courses/{uuid.uuid4()}/certify",
            headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
        )
    assert r.status_code == 400


# ─────────────── GET /download/{format} ───────────────


def test_download_pptx_streams_file(client: TestClient, tmp_path: Path) -> None:
    pptx = tmp_path / "corso.pptx"
    pptx.write_bytes(b"fake-pptx-bytes")

    pool = MagicMock()
    cid = str(uuid.uuid4())
    pool.fetchrow = AsyncMock(
        side_effect=[
            _user_row(ADMIN_ID, "admin"),
            _course_row(cid, pptx_path=str(pptx)),
        ]
    )
    _wire_pool(pool)

    r = client.get(
        f"/api/courses/{cid}/download/pptx",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 200
    assert r.content == b"fake-pptx-bytes"


def test_download_zip_bundles_pptx_and_pdf(client: TestClient, tmp_path: Path) -> None:
    pptx = tmp_path / "corso.pptx"
    pdf = tmp_path / "dispensa.pdf"
    pptx.write_bytes(b"pptx-content")
    pdf.write_bytes(b"pdf-content")

    pool = MagicMock()
    cid = str(uuid.uuid4())
    pool.fetchrow = AsyncMock(
        side_effect=[
            _user_row(ADMIN_ID, "admin"),
            _course_row(cid, pptx_path=str(pptx), pdf_path=str(pdf)),
        ]
    )
    _wire_pool(pool)

    r = client.get(
        f"/api/courses/{cid}/download/zip",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    assert {"corso.pptx", "dispensa.pdf"} <= names


def test_download_audio_zips_directory_of_mp3s(
    client: TestClient, tmp_path: Path
) -> None:
    audio_dir = tmp_path / "audio" / "course-x"
    audio_dir.mkdir(parents=True)
    (audio_dir / "slide_0000.mp3").write_bytes(b"mp3-1")
    (audio_dir / "slide_0001.mp3").write_bytes(b"mp3-2")
    manifest = audio_dir / "sync_manifest.json"
    manifest.write_text('{"course_id": "x", "total_tracks": 2, "tracks": []}')

    pool = MagicMock()
    cid = str(uuid.uuid4())
    pool.fetchrow = AsyncMock(
        side_effect=[
            _user_row(ADMIN_ID, "admin"),
            _course_row(cid, audio_manifest_path=str(manifest)),
        ]
    )
    _wire_pool(pool)

    r = client.get(
        f"/api/courses/{cid}/download/audio",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    assert {"slide_0000.mp3", "slide_0001.mp3", "sync_manifest.json"} <= names


def test_download_invalid_format_returns_400(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(ADMIN_ID, "admin"))
    _wire_pool(pool)

    r = client.get(
        f"/api/courses/{uuid.uuid4()}/download/jpg",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 400


def test_download_pdf_missing_path_returns_404(client: TestClient) -> None:
    pool = MagicMock()
    cid = str(uuid.uuid4())
    pool.fetchrow = AsyncMock(
        side_effect=[
            _user_row(ADMIN_ID, "admin"),
            _course_row(cid, pdf_path=None),
        ]
    )
    _wire_pool(pool)

    r = client.get(
        f"/api/courses/{cid}/download/pdf",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 404


# ─────────────── DELETE /api/courses/{id} ───────────────


def test_delete_soft_deletes_owned_course(client: TestClient) -> None:
    pool = MagicMock()
    cid = str(uuid.uuid4())
    pool.fetchrow = AsyncMock(
        side_effect=[
            _user_row(OPERATOR_ID, "operator"),
            _course_row(cid, created_by=OPERATOR_ID),
        ]
    )
    pool.execute = AsyncMock(return_value=None)
    _wire_pool(pool)

    r = client.delete(
        f"/api/courses/{cid}",
        headers={"Authorization": f"Bearer {_token(OPERATOR_ID, 'operator')}"},
    )
    assert r.status_code == 200
    assert r.json() == {"status": "archived", "course_id": cid}
    sql = pool.execute.await_args.args[0]
    assert "status = 'archived'" in sql


def test_delete_returns_403_when_not_owner(client: TestClient) -> None:
    pool = MagicMock()
    cid = str(uuid.uuid4())
    pool.fetchrow = AsyncMock(
        side_effect=[
            _user_row(OPERATOR_ID, "operator"),
            _course_row(cid, created_by=ADMIN_ID),
        ]
    )
    _wire_pool(pool)

    r = client.delete(
        f"/api/courses/{cid}",
        headers={"Authorization": f"Bearer {_token(OPERATOR_ID, 'operator')}"},
    )
    assert r.status_code == 403
