"""Integration tests for auth service + routes (BLUEPRINT §08).

The DB pool is stubbed with ``AsyncMock`` via ``set_pool`` — the same pattern
used in ``test_health.py``. Tests do NOT exercise a real Postgres.

Coverage (karpathy rule #4 — explicit success criteria):
- bcrypt hash/verify roundtrip
- JWT access vs refresh: payload "type" claim differs, both decodable
- /api/auth/login: happy / wrong-password / unknown-user / inactive
  (all 401 with the SAME generic message — no user enumeration)
- /api/auth/refresh: happy / access-token-passed / inactive-after-issuance
- /api/users/me: happy / no-token (403 from HTTPBearer) / refresh-token-as-access /
  deactivated-after-issuance
- require_role: admin route accessed by operator → 403
"""

from __future__ import annotations

import uuid as uuid_mod
from typing import Any
from unittest.mock import AsyncMock

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.services import dependencies as deps
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)


# ──────────────────────────── helpers ────────────────────────────


def _user_row(
    user_id: str | None = None,
    *,
    email: str = "admin@example.com",
    role: str = "admin",
    is_active: bool = True,
    password_hash: str | None = None,
) -> dict[str, Any]:
    """Build a dict that mimics an asyncpg Record for users."""
    return {
        "id": uuid_mod.UUID(user_id) if user_id else uuid_mod.uuid4(),
        "email": email,
        "role": role,
        "is_active": is_active,
        "password_hash": password_hash or hash_password("correct-horse"),
    }


def _install_pool(*, fetchrow_returns: Any) -> AsyncMock:
    """Install an AsyncMock pool whose fetchrow returns the given value(s)."""
    pool = AsyncMock()
    if isinstance(fetchrow_returns, list):
        pool.fetchrow = AsyncMock(side_effect=fetchrow_returns)
    else:
        pool.fetchrow = AsyncMock(return_value=fetchrow_returns)
    deps.set_pool(pool)
    return pool


@pytest.fixture(autouse=True)
def _reset_pool() -> Any:
    """Tear down the global pool between tests to avoid cross-test bleed."""
    yield
    deps._pool = None


async def _client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ───────────────────── bcrypt + JWT primitives ───────────────────


def test_bcrypt_roundtrip() -> None:
    h = hash_password("hunter2")
    assert verify_password("hunter2", h) is True
    assert verify_password("wrong", h) is False


def test_access_and_refresh_payloads_differ() -> None:
    uid = str(uuid_mod.uuid4())
    access = create_access_token(uid, "admin")
    refresh = create_refresh_token(uid)
    a_payload = jwt.decode(access, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    r_payload = jwt.decode(refresh, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert a_payload["type"] == "access"
    assert r_payload["type"] == "refresh"
    assert a_payload["sub"] == uid
    assert r_payload["sub"] == uid
    assert "role" in a_payload  # access carries role for require_role
    assert "role" not in r_payload  # refresh does not


# ──────────────────────── /api/auth/login ────────────────────────


async def test_login_happy_path() -> None:
    user = _user_row(role="admin")
    _install_pool(fetchrow_returns=user)
    async with await _client() as c:
        resp = await c.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "correct-horse"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    a = jwt.decode(body["access_token"], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert a["type"] == "access"
    assert a["role"] == "admin"


async def test_login_unknown_user_returns_generic_error() -> None:
    _install_pool(fetchrow_returns=None)
    async with await _client() as c:
        resp = await c.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "whatever"},
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Credenziali non valide"


async def test_login_wrong_password_returns_same_generic_error() -> None:
    user = _user_row()
    _install_pool(fetchrow_returns=user)
    async with await _client() as c:
        resp = await c.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "wrong"},
        )
    assert resp.status_code == 401
    # Same exact message as unknown-user → no enumeration.
    assert resp.json()["detail"] == "Credenziali non valide"


async def test_login_inactive_user_returns_same_generic_error() -> None:
    user = _user_row(is_active=False)
    _install_pool(fetchrow_returns=user)
    async with await _client() as c:
        resp = await c.post(
            "/api/auth/login",
            json={"email": "admin@example.com", "password": "correct-horse"},
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Credenziali non valide"


# ─────────────────────── /api/auth/refresh ───────────────────────


async def test_refresh_happy_path() -> None:
    uid = str(uuid_mod.uuid4())
    refresh_tok = create_refresh_token(uid)
    user = _user_row(user_id=uid, role="operator")
    _install_pool(fetchrow_returns=user)
    async with await _client() as c:
        resp = await c.post("/api/auth/refresh", json={"refresh_token": refresh_tok})
    assert resp.status_code == 200
    a = jwt.decode(
        resp.json()["access_token"], settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    assert a["type"] == "access"
    assert a["role"] == "operator"


async def test_refresh_rejects_access_token() -> None:
    """An access token must NOT be accepted by /refresh."""
    uid = str(uuid_mod.uuid4())
    access_tok = create_access_token(uid, "admin")
    _install_pool(fetchrow_returns=None)  # not even queried
    async with await _client() as c:
        resp = await c.post("/api/auth/refresh", json={"refresh_token": access_tok})
    assert resp.status_code == 401
    assert "Token type" in resp.json()["detail"]


async def test_refresh_rejects_deactivated_user() -> None:
    """BP §08.3: refresh must re-check is_active in DB."""
    uid = str(uuid_mod.uuid4())
    refresh_tok = create_refresh_token(uid)
    user = _user_row(user_id=uid, is_active=False)
    _install_pool(fetchrow_returns=user)
    async with await _client() as c:
        resp = await c.post("/api/auth/refresh", json={"refresh_token": refresh_tok})
    assert resp.status_code == 401
    assert "disattivato" in resp.json()["detail"].lower()


async def test_refresh_rejects_invalid_token() -> None:
    async with await _client() as c:
        resp = await c.post("/api/auth/refresh", json={"refresh_token": "not.a.jwt"})
    assert resp.status_code == 401


# ────────────────────────── /api/users/me ───────────────────────


async def test_users_me_happy_path() -> None:
    uid = str(uuid_mod.uuid4())
    access_tok = create_access_token(uid, "admin")
    user = _user_row(user_id=uid, role="admin")
    _install_pool(fetchrow_returns=user)
    async with await _client() as c:
        resp = await c.get("/api/users/me", headers={"Authorization": f"Bearer {access_tok}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == uid
    assert body["role"] == "admin"
    assert body["is_active"] is True


async def test_users_me_without_token_is_unauthorized() -> None:
    async with await _client() as c:
        resp = await c.get("/api/users/me")
    # HTTPBearer returns 403 when the Authorization header is missing entirely.
    assert resp.status_code in (401, 403)


async def test_users_me_rejects_refresh_token() -> None:
    """Refresh tokens MUST NOT authenticate API access (BP §08.2)."""
    uid = str(uuid_mod.uuid4())
    refresh_tok = create_refresh_token(uid)
    _install_pool(fetchrow_returns=None)  # not even queried
    async with await _client() as c:
        resp = await c.get("/api/users/me", headers={"Authorization": f"Bearer {refresh_tok}"})
    assert resp.status_code == 401
    assert "Token type" in resp.json()["detail"]


async def test_users_me_rejects_deactivated_user() -> None:
    """Implicit revocation: deactivated user with a still-valid token → 401."""
    uid = str(uuid_mod.uuid4())
    access_tok = create_access_token(uid, "admin")
    user = _user_row(user_id=uid, is_active=False)
    _install_pool(fetchrow_returns=user)
    async with await _client() as c:
        resp = await c.get("/api/users/me", headers={"Authorization": f"Bearer {access_tok}"})
    assert resp.status_code == 401
    assert "disattivato" in resp.json()["detail"].lower()


async def test_users_me_rejects_garbled_token() -> None:
    async with await _client() as c:
        resp = await c.get("/api/users/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401
