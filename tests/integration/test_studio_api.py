"""Integration tests — FASE 7 vast-hopping-sketch — Course Studio API.

Verifica i nuovi endpoint Studio: GET /slides, GET/PATCH /slides/{idx},
PATCH /slides/{idx}/image, GET /audio/{idx}, GET /image/search.

Mocka il pool (no DB reale) — testa wiring auth/ownership/validation/dirty flag.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import create_access_token
from app.models.core import SlideType
from app.services import dependencies as deps
from tests._helpers import make_slide

ADMIN_ID = "11111111-1111-1111-1111-111111111111"
OPERATOR_ID = "22222222-2222-2222-2222-222222222222"
COURSE_ID = "33333333-3333-3333-3333-333333333333"


def _token(user_id: str, role: str) -> str:
    return create_access_token(user_id, role)


def _user_row(user_id: str, role: str) -> dict[str, Any]:
    return {
        "id": uuid.UUID(user_id),
        "email": f"{role}@nexus-eduvault.local",
        "role": role,
        "is_active": True,
    }


def _sample_slides_json() -> str:
    """3 slide valide serializzate come JSON array (slide_contents_json)."""
    slides = [
        make_slide(SlideType.CONTENT_TEXT, index=0, title="Slide zero").model_dump(),
        make_slide(SlideType.CONTENT_TEXT, index=1, title="Slide uno").model_dump(),
        make_slide(SlideType.QUIZ, index=2, title="Domanda quiz?",
                   quiz_options=["A", "B", "C", "D"], quiz_correct=1).model_dump(),
    ]
    return json.dumps(slides)


def _course_row(created_by: str = ADMIN_ID, with_slides: bool = True) -> dict[str, Any]:
    return {
        "id": uuid.UUID(COURSE_ID),
        "title": "Corso Test",
        "course_type": "primo_soccorso_gruppo_b_c",
        "target": "discente",
        "duration_hours": 1.0,
        "region": "NAZIONALE",
        "created_by": uuid.UUID(created_by),
        "status": "completed",
        "slide_contents_json": _sample_slides_json() if with_slides else None,
        "created_at": datetime(2026, 5, 25, tzinfo=timezone.utc),
    }


def _wire_pool(pool: Any) -> Any:
    deps.set_pool(pool)
    return pool


@pytest.fixture(autouse=True)
def _reset_pool() -> Any:
    yield
    deps._pool = None


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _auth(role: str = "admin", user_id: str = ADMIN_ID) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id, role)}"}


# ─────────────── GET /slides ───────────────


def test_get_slides_returns_array(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(side_effect=[
        _user_row(ADMIN_ID, "admin"),       # auth lookup
        _course_row(),                       # _load_course_or_404
        {"slide_contents_json": _sample_slides_json()},  # get_slides
    ])
    _wire_pool(pool)
    r = client.get(f"/api/courses/{COURSE_ID}/slides", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert len(body["slides"]) == 3
    assert body["slides"][0]["index"] == 0


def test_get_slides_409_when_no_slides(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(side_effect=[
        _user_row(ADMIN_ID, "admin"),
        _course_row(with_slides=False),
        {"slide_contents_json": None},
    ])
    _wire_pool(pool)
    r = client.get(f"/api/courses/{COURSE_ID}/slides", headers=_auth())
    assert r.status_code == 409


def test_get_slides_403_when_not_owner(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(side_effect=[
        _user_row(OPERATOR_ID, "operator"),
        _course_row(created_by=ADMIN_ID),  # owned by admin, requester operator
    ])
    _wire_pool(pool)
    r = client.get(f"/api/courses/{COURSE_ID}/slides",
                   headers=_auth("operator", OPERATOR_ID))
    assert r.status_code == 403


# ─────────────── GET /slides/{idx} ───────────────


def test_get_single_slide(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(side_effect=[
        _user_row(ADMIN_ID, "admin"),
        _course_row(),
        {"slide_contents_json": _sample_slides_json()},
    ])
    _wire_pool(pool)
    r = client.get(f"/api/courses/{COURSE_ID}/slides/1", headers=_auth())
    assert r.status_code == 200
    assert r.json()["index"] == 1


def test_get_single_slide_404(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(side_effect=[
        _user_row(ADMIN_ID, "admin"),
        _course_row(),
        {"slide_contents_json": _sample_slides_json()},
    ])
    _wire_pool(pool)
    r = client.get(f"/api/courses/{COURSE_ID}/slides/99", headers=_auth())
    assert r.status_code == 404


# ─────────────── PATCH /slides/{idx} ───────────────


def test_patch_slide_updates_and_marks_dirty(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(side_effect=[
        _user_row(ADMIN_ID, "admin"),
        _course_row(),
        {"slide_contents_json": _sample_slides_json()},  # update_slide.get_slides
    ])
    pool.execute = AsyncMock(return_value=None)
    _wire_pool(pool)
    r = client.patch(
        f"/api/courses/{COURSE_ID}/slides/0",
        headers=_auth(),
        json={"title": "Nuovo titolo valido"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Nuovo titolo valido"
    # Verifica che l'UPDATE abbia settato dirty=true
    update_call = pool.execute.await_args_list[0]
    assert "dirty = true" in update_call.args[0]


def test_patch_slide_422_on_invalid(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(side_effect=[
        _user_row(ADMIN_ID, "admin"),
        _course_row(),
        {"slide_contents_json": _sample_slides_json()},
    ])
    pool.execute = AsyncMock(return_value=None)
    _wire_pool(pool)
    # title 71 char → viola constraint CONTENT_TEXT (max 70) → 422
    r = client.patch(
        f"/api/courses/{COURSE_ID}/slides/0",
        headers=_auth(),
        json={"title": "x" * 71},
    )
    assert r.status_code == 422


def test_patch_slide_operator_forbidden(client: TestClient) -> None:
    """PATCH richiede admin|reviewer — operator → 403."""
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(OPERATOR_ID, "operator"))
    _wire_pool(pool)
    r = client.patch(
        f"/api/courses/{COURSE_ID}/slides/0",
        headers=_auth("operator", OPERATOR_ID),
        json={"title": "x"},
    )
    assert r.status_code == 403


# ─────────────── GET /audio/{idx} ───────────────


def test_get_audio_404_when_missing(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(side_effect=[
        _user_row(ADMIN_ID, "admin"),
        _course_row(),
        None,  # no audio_tracks row
    ])
    _wire_pool(pool)
    r = client.get(f"/api/courses/{COURSE_ID}/audio/0", headers=_auth())
    assert r.status_code == 404
