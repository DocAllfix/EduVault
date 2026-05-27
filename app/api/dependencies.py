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

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.services.auth_service import decode_token
from app.services.dependencies import get_pool

security = HTTPBearer()

# Shared rate limiter, imported by both app.main (to wire app.state.limiter)
# and by route modules (to apply per-endpoint @limiter.limit decorators).
# Lives here — not in main.py — to avoid circular imports.
limiter = Limiter(key_func=get_remote_address)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """Decode JWT, enforce access-type, enforce ``is_active`` (BP §08.2)."""
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(401, "Token non valido o scaduto")

    # Token type check (BP §08.2)
    if payload.get("type") != "access":
        raise HTTPException(401, "Token type non valido — atteso access token")

    pool = get_pool()
    # Explicit UUID conversion for asyncpg (BP §08.2)
    user = await pool.fetchrow(
        "SELECT id, email, role, is_active FROM users WHERE id = $1",
        uuid_mod.UUID(payload["sub"]),
    )
    if not user or not user["is_active"]:
        raise HTTPException(401, "Utente non autorizzato o disattivato")
    return dict(user)


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
