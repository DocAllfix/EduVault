"""Authentication endpoints (BLUEPRINT §08).

Endpoints:
- POST /api/auth/login    — email + password → access + refresh tokens (rate-limited 10/min, BP §08.5)
- POST /api/auth/refresh  — refresh token → new access token (with is_active re-check, BP §08.3)
- GET  /api/users/me      — current authenticated user (BP §10)

Security assumptions (karpathy rule #1, see Step 1.3 audit trail):
- Login error message is generic (no enumeration of users vs wrong-password).
- Refresh re-checks is_active in DB (BP §08.3) — disabled users cannot rotate tokens.
- /api/users/me requires an ACCESS token (refresh tokens are rejected).
"""

from __future__ import annotations

import uuid as uuid_mod
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.api.dependencies import get_current_user, limiter
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.services.dependencies import get_pool

logger = structlog.get_logger()

router = APIRouter(prefix="/api", tags=["auth"])


# ─────────────────────── request/response models ───────────────────────


class LoginRequest(BaseModel):
    # ``email`` is a plain str: the DB schema stores VARCHAR(255) without
    # validation (BP §03). Adding strict RFC-email validation here would
    # require ``pydantic[email]`` extras — out of scope for v1.0.
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMe(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool


# ──────────────────────────── endpoints ────────────────────────────────


@router.post("/auth/login", response_model=LoginResponse)
@limiter.limit("10/minute")  # BP §08.5 — brute-force protection
async def login(request: Request, body: LoginRequest) -> LoginResponse:
    """Authenticate by email + password, return access + refresh tokens.

    Returns a GENERIC error for both "user not found" and "wrong password"
    (no user-enumeration).
    """
    pool = get_pool()
    user = await pool.fetchrow(
        "SELECT id, password_hash, role, is_active FROM users WHERE email = $1",
        body.email,
    )
    # Generic error: do not reveal whether the user exists.
    if not user or not user["is_active"] or not verify_password(
        body.password, user["password_hash"]
    ):
        raise HTTPException(401, "Credenziali non valide")

    user_id = str(user["id"])
    return LoginResponse(
        access_token=create_access_token(user_id, user["role"]),
        refresh_token=create_refresh_token(user_id),
    )


@router.post("/auth/refresh", response_model=RefreshResponse)
async def refresh(body: RefreshRequest) -> RefreshResponse:
    """Exchange a valid refresh token for a new access token.

    Re-checks is_active in DB (BP §08.3): a deactivated user CANNOT rotate
    tokens even with a still-cryptographically-valid refresh token.
    """
    try:
        payload = decode_token(body.refresh_token)
    except Exception:
        raise HTTPException(401, "Token non valido o scaduto")

    if payload.get("type") != "refresh":
        raise HTTPException(401, "Token type non valido — atteso refresh token")

    pool = get_pool()
    user = await pool.fetchrow(
        "SELECT id, role, is_active FROM users WHERE id = $1",
        uuid_mod.UUID(payload["sub"]),
    )
    if not user or not user["is_active"]:
        raise HTTPException(401, "Utente disattivato")

    return RefreshResponse(
        access_token=create_access_token(str(user["id"]), user["role"]),
    )


@router.get("/users/me", response_model=UserMe)
async def me(user: dict[str, Any] = Depends(get_current_user)) -> UserMe:
    """Return the current authenticated user (BP §10)."""
    return UserMe(
        id=str(user["id"]),
        email=user["email"],
        role=user["role"],
        is_active=user["is_active"],
    )
