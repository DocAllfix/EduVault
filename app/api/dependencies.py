"""FastAPI auth dependencies (BLUEPRINT §08.2).

Only import-path differs from BP §08.2: ``app.services.*`` instead of bare ``services.*``.

Architectural notes (BP §08.2):
- IMPLICIT REVOCATION: every authenticated request performs ``SELECT is_active``
  from ``users``. A token that is still cryptographically valid but whose user
  has been deactivated → 401. No Redis blacklist required.
- TOKEN TYPE CHECK: ``get_current_user`` requires ``payload["type"] == "access"``;
  refresh tokens are rejected here (they are accepted only by ``/api/auth/refresh``).
- UUID CONVERSION: ``payload["sub"]`` is a string; ``users.id`` is a UUID column.
  asyncpg needs an explicit ``uuid.UUID(...)`` conversion.
- ``require_role`` factory is intentionally NON-async; if it were async,
  ``Depends(require_role(...))`` would return a coroutine instead of the
  ``checker`` callable, breaking FastAPI's dependency injection.
"""

from __future__ import annotations

import uuid as uuid_mod
from typing import Any, Callable, Coroutine

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.services.auth_service import decode_token
from app.services.dependencies import get_pool

security = HTTPBearer()
# Variant ``auto_error=False`` per endpoint che accettano ANCHE token in
# query string (browser <audio>/<img> cross-origin non possono settare
# header Authorization — vedi get_current_user_streaming).
security_optional = HTTPBearer(auto_error=False)

# Shared rate limiter, imported by both app.main (to wire app.state.limiter)
# and by route modules (to apply per-endpoint @limiter.limit decorators).
# Lives here — not in main.py — to avoid circular imports.
limiter = Limiter(key_func=get_remote_address)


async def _decode_and_load_user(token: str) -> dict[str, Any]:
    """Shared helper: decode JWT + load+validate user. Solleva 401 se invalido."""
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(401, "Token non valido o scaduto")
    if payload.get("type") != "access":
        raise HTTPException(401, "Token type non valido — atteso access token")
    pool = get_pool()
    user = await pool.fetchrow(
        "SELECT id, email, role, is_active FROM users WHERE id = $1",
        uuid_mod.UUID(payload["sub"]),
    )
    if not user or not user["is_active"]:
        raise HTTPException(401, "Utente non autorizzato o disattivato")
    return dict(user)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """Decode JWT, enforce access-type, enforce ``is_active`` (BP §08.2)."""
    return await _decode_and_load_user(credentials.credentials)


async def get_current_user_streaming(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_optional),
) -> dict[str, Any]:
    """Variant per endpoint ``<audio>``/``<img>`` cross-origin (audio MP3,
    preview PNG): accetta JWT in ``Authorization: Bearer`` OPPURE in
    ``?token=`` query string (stesso pattern WebSocket BP §08.8). Browser
    cross-origin tag elements non possono settare custom headers, quindi
    fallback obbligatorio sul query param.
    """
    token: str | None = None
    if credentials is not None:
        token = credentials.credentials
    if not token:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(401, "Token mancante")
    return await _decode_and_load_user(token)


def require_role(
    *roles: str,
) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
    """Role-based dependency factory (BP §08.2).

    Usage: ``Depends(require_role("admin", "reviewer"))``.

    The OUTER function is intentionally synchronous — see module docstring.
    """

    async def checker(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if user["role"] not in roles:
            raise HTTPException(403, f"Ruolo {user['role']} non autorizzato")
        return user

    return checker
