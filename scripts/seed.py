"""First-run seeding script (BLUEPRINT §02.7).

Creates the bootstrap admin user and the default brand preset.
Run ONCE after the first ``docker compose up`` and after the migrations.
Connects as ``nexus_admin`` (DATABASE_ADMIN_URL) — the only role with full
INSERT rights across all tables.

Modifications vs BP §02.7 (declared per REI-5):
- Env access via ``settings`` (OPT-2), not ``os.environ[]``.
- Admin email/password read from settings (REI-13: no hardcoded domain).
- ``print()`` replaced by structlog (REI-7).
- Seeding logic factored into a single ``seed(pool)`` coroutine so tests can
  inject a mock pool without spinning up Postgres.

Idempotent: re-running this script on a database that already has an admin
and a default brand preset is a no-op (both checks use ``SELECT ... WHERE``
and skip the INSERT if the row exists).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
import bcrypt
import structlog

from app.config import settings

logger = structlog.get_logger()


DEFAULT_PALETTE: dict[str, str] = {
    "primary": "#1a365d",
    "secondary": "#2b6cb0",
    "accent": "#ed8936",
    "danger": "#e53e3e",
    "success": "#38a169",
}
DEFAULT_FONTS: dict[str, str] = {
    "heading": "Montserrat",
    "body": "Open Sans",
}


async def seed(pool: Any) -> dict[str, bool]:
    """Run the seed operations against ``pool``.

    Returns a dict summarising what was inserted vs skipped, useful for tests
    and for the CLI summary logged at the end.
    """
    result = {"admin_inserted": False, "brand_inserted": False}

    # 1) Bootstrap admin
    admin = await pool.fetchrow("SELECT id FROM users WHERE role='admin'")
    if not admin:
        pw_hash = bcrypt.hashpw(
            settings.admin_bootstrap_password.encode(), bcrypt.gensalt()
        ).decode()
        await pool.execute(
            "INSERT INTO users (email, password_hash, role) VALUES ($1, $2, 'admin')",
            settings.admin_bootstrap_email,
            pw_hash,
        )
        result["admin_inserted"] = True
        logger.info("seed_admin_created", email=settings.admin_bootstrap_email)
    else:
        logger.info("seed_admin_skipped", reason="admin already exists")

    # 2) Default brand preset
    preset = await pool.fetchrow(
        "SELECT id FROM brand_presets WHERE is_default=true"
    )
    if not preset:
        await pool.execute(
            "INSERT INTO brand_presets (name, palette, fonts, is_default) "
            "VALUES ($1, $2, $3, true)",
            "Default",
            json.dumps(DEFAULT_PALETTE),
            json.dumps(DEFAULT_FONTS),
        )
        result["brand_inserted"] = True
        logger.info("seed_brand_preset_created", name="Default")
    else:
        logger.info("seed_brand_preset_skipped", reason="default preset already exists")

    return result


async def main() -> None:
    """CLI entry point: build the admin pool, run ``seed``, close cleanly."""
    pool = await asyncpg.create_pool(dsn=settings.database_admin_url)
    try:
        result = await seed(pool)
        logger.info("seed_completed", **result)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
