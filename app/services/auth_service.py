"""JWT + bcrypt authentication service (BLUEPRINT §08.1).

Modifications vs BP §08.1 (declared per REI-5 and OPT-2):
- Secrets read from ``app.config.settings`` (pydantic-settings), not ``os.environ[]``
  directly. This is REI-14 / OPT-2 — see ``app/main.py`` for the same pattern.
- Single ``JWT_SECRET`` (BP §08.1, single key, token type in the payload).

Assumptions explicitly stated (karpathy rule #1) — see also Step 1.3 audit trail:
- HS256 symmetric algorithm (Settings default).
- Access token expiry 60 min, refresh expiry 7 days (Settings defaults).
- access vs refresh distinguished by the ``type`` claim, NOT by separate secrets.
- Implicit revocation via ``users.is_active`` is enforced in ``api.dependencies``
  and in the ``/refresh`` route — NOT here. This module only signs / verifies.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiry_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expiry_days),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT.

    Raises ``jwt.InvalidTokenError`` (or a subclass) if the token is invalid
    or expired. Callers MUST catch and translate to HTTP 401.
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# TOTP (v1.1) — schema field is present but the verification path is dormant.
# Do NOT enable in v1.0 (REI-9 + BP §1.1 row 21).
# def verify_totp(secret: str, code: str) -> bool:
#     import pyotp
#     return pyotp.TOTP(secret).verify(code)
