"""Integration tests for /api/regulations routes (PHASE 2.6, BLUEPRINT §10).

Same harness as test_auth: ASGITransport + AsyncMock pool installed via
set_pool, real JWTs for auth. get_current_user / require_role read the user
from the mocked pool, so each test seeds the right user row.

Coverage:
- authorization: admin-only on upload/delete (operator → 403, no token → 403)
- list / chunks: pagination params reach SQL (LIMIT/OFFSET)
- delete: UPDATE → ABROGATA, 404 when not found
- upload: orchestration delegated to ingest_regulation_file (mocked)
"""

from __future__ import annotations

import uuid as uuid_mod
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import dependencies as deps
from app.services.auth_service import create_access_token

REG_UUID = "11111111-1111-1111-1111-111111111111"


def _user_row(role: str = "admin") -> dict[str, Any]:
    return {
        "id": uuid_mod.uuid4(),
        "email": f"{role}@example.com",
        "role": role,
        "is_active": True,
    }


def _token(user: dict[str, Any]) -> str:
    return create_access_token(str(user["id"]), user["role"])


@pytest.fixture(autouse=True)
def _reset_pool() -> Any:
    yield
    deps._pool = None


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ─────────────── authorization ───────────────


async def test_upload_requires_token() -> None:
    deps.set_pool(AsyncMock())
    async with _client() as ac:
        resp = await ac.post("/api/regulations/upload")
    # Missing/!malformed bearer → unauthenticated (Starlette returns 401/403
    # depending on path; either is a hard auth rejection, never 2xx).
    assert resp.status_code in (401, 403)


async def test_upload_forbidden_for_operator() -> None:
    operator = _user_row("operator")
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=operator)  # get_current_user lookup
    deps.set_pool(pool)

    async with _client() as ac:
        resp = await ac.post(
            "/api/regulations/upload",
            headers={"Authorization": f"Bearer {_token(operator)}"},
            files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
            data={"slug": "x", "title": "X", "reg_type": "DM"},
        )
    assert resp.status_code == 403


async def test_delete_forbidden_for_operator() -> None:
    operator = _user_row("operator")
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=operator)
    deps.set_pool(pool)

    async with _client() as ac:
        resp = await ac.delete(
            f"/api/regulations/{REG_UUID}",
            headers={"Authorization": f"Bearer {_token(operator)}"},
        )
    assert resp.status_code == 403


# ─────────────── upload (admin) ───────────────


async def test_upload_admin_runs_ingestion() -> None:
    admin = _user_row("admin")
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=admin)
    deps.set_pool(pool)

    fake_ingest = AsyncMock(return_value=(REG_UUID, 7))
    with patch("app.api.routes.regulations.ingest_regulation_file", fake_ingest):
        async with _client() as ac:
            resp = await ac.post(
                "/api/regulations/upload",
                headers={"Authorization": f"Bearer {_token(admin)}"},
                files={"file": ("dm388.pdf", b"%PDF-1.4 fake", "application/pdf")},
                data={
                    "slug": "dm_388_2003",
                    "title": "DM 388/2003",
                    "reg_type": "DM",
                    "region": "NAZIONALE",
                },
            )

    assert resp.status_code == 200
    assert resp.json() == {"regulation_id": REG_UUID, "chunks_count": 7}
    fake_ingest.assert_awaited_once()


# ─────────────── list (paginated) ───────────────


async def test_list_regulations_paginated() -> None:
    admin = _user_row("admin")
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=admin)
    pool.fetch = AsyncMock(
        return_value=[
            {
                "id": REG_UUID,
                "title": "DM 388/2003",
                "type": "DM",
                "region": "NAZIONALE",
                "status": "VIGENTE",
                "slug": "dm_388_2003",
            }
        ]
    )
    deps.set_pool(pool)

    async with _client() as ac:
        resp = await ac.get(
            "/api/regulations?page=2&per_page=10",
            headers={"Authorization": f"Bearer {_token(admin)}"},
        )

    assert resp.status_code == 200
    assert resp.json()[0]["slug"] == "dm_388_2003"
    # LIMIT/OFFSET reach SQL: per_page=10, page=2 → offset 10
    limit_arg, offset_arg = pool.fetch.await_args.args[1:3]
    assert limit_arg == 10
    assert offset_arg == 10


# ─────────────── chunks (paginated) ───────────────


async def test_list_chunks_paginated() -> None:
    admin = _user_row("admin")
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=admin)
    pool.fetch = AsyncMock(
        return_value=[
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "article": "Art. 1",
                "paragraph": None,
                "hierarchy_path": "Art. 1",
                "body": "Le aziende sono classificate.",
                "chunk_type": "GENERALE",
                "tags": ["primo_soccorso"],
            }
        ]
    )
    deps.set_pool(pool)

    async with _client() as ac:
        resp = await ac.get(
            f"/api/regulations/{REG_UUID}/chunks?page=1&per_page=50",
            headers={"Authorization": f"Bearer {_token(admin)}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["hierarchy_path"] == "Art. 1"
    assert body[0]["tags"] == ["primo_soccorso"]


# ─────────────── delete (soft) ───────────────


async def test_delete_soft_deletes() -> None:
    admin = _user_row("admin")
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=admin)
    pool.execute = AsyncMock(return_value="UPDATE 1")
    deps.set_pool(pool)

    async with _client() as ac:
        resp = await ac.delete(
            f"/api/regulations/{REG_UUID}",
            headers={"Authorization": f"Bearer {_token(admin)}"},
        )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ABROGATA", "regulation_id": REG_UUID}
    # The UPDATE sets ABROGATA
    sql = pool.execute.await_args.args[0]
    assert "status = 'ABROGATA'" in sql


async def test_delete_not_found_returns_404() -> None:
    admin = _user_row("admin")
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=admin)
    pool.execute = AsyncMock(return_value="UPDATE 0")  # no row matched
    deps.set_pool(pool)

    async with _client() as ac:
        resp = await ac.delete(
            f"/api/regulations/{REG_UUID}",
            headers={"Authorization": f"Bearer {_token(admin)}"},
        )

    assert resp.status_code == 404
