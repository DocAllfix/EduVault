"""Integration tests for scripts/seed.py (BLUEPRINT §02.7).

The pool is stubbed with ``AsyncMock`` — same pattern as test_health/test_auth.
We verify:
- both inserts happen on a virgin DB
- idempotency: admin-only / brand-only / fully-seeded → only the missing row is inserted
- the bcrypt hash actually verifies against the configured bootstrap password
- the brand preset INSERT carries JSON-encoded palette + fonts
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import bcrypt

from app.config import settings
from scripts.seed import DEFAULT_FONTS, DEFAULT_PALETTE, seed


def _virgin_pool() -> AsyncMock:
    """Pool whose fetchrow always returns None (no admin, no default preset)."""
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock(return_value="INSERT 0 1")
    return pool


def _already_seeded_pool() -> AsyncMock:
    """Pool whose fetchrow returns a fake row for both queries."""
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value={"id": "fake-uuid"})
    pool.execute = AsyncMock(return_value="INSERT 0 1")
    return pool


def _admin_only_pool() -> AsyncMock:
    """Admin exists, default preset does not."""
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(
        side_effect=[{"id": "admin-uuid"}, None]  # 1st call = users, 2nd = brand_presets
    )
    pool.execute = AsyncMock(return_value="INSERT 0 1")
    return pool


def _brand_only_pool() -> AsyncMock:
    """Default preset exists, admin does not."""
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(
        side_effect=[None, {"id": "brand-uuid"}]
    )
    pool.execute = AsyncMock(return_value="INSERT 0 1")
    return pool


# ─────────────────────────── tests ───────────────────────────────


async def test_seed_virgin_db_inserts_both() -> None:
    pool = _virgin_pool()
    result = await seed(pool)
    assert result == {"admin_inserted": True, "brand_inserted": True}
    assert pool.execute.await_count == 2


async def test_seed_idempotent_when_fully_seeded() -> None:
    pool = _already_seeded_pool()
    result = await seed(pool)
    assert result == {"admin_inserted": False, "brand_inserted": False}
    # fetchrow checked twice; execute NEVER called
    assert pool.fetchrow.await_count == 2
    assert pool.execute.await_count == 0


async def test_seed_inserts_only_brand_when_admin_exists() -> None:
    pool = _admin_only_pool()
    result = await seed(pool)
    assert result == {"admin_inserted": False, "brand_inserted": True}
    assert pool.execute.await_count == 1
    # The single execute call must target brand_presets, not users.
    insert_sql = pool.execute.await_args_list[0].args[0]
    assert "brand_presets" in insert_sql


async def test_seed_inserts_only_admin_when_brand_exists() -> None:
    pool = _brand_only_pool()
    result = await seed(pool)
    assert result == {"admin_inserted": True, "brand_inserted": False}
    assert pool.execute.await_count == 1
    insert_sql = pool.execute.await_args_list[0].args[0]
    assert "users" in insert_sql


async def test_admin_password_hash_verifies_against_configured_password() -> None:
    """The bcrypt hash actually inserted must round-trip with the configured password."""
    pool = _virgin_pool()
    await seed(pool)
    # users INSERT: args = (sql, email, password_hash)
    admin_call = pool.execute.await_args_list[0]
    _, email_arg, hash_arg = admin_call.args
    assert email_arg == settings.admin_bootstrap_email
    assert bcrypt.checkpw(
        settings.admin_bootstrap_password.encode(), hash_arg.encode()
    ) is True


async def test_brand_preset_carries_json_palette_and_fonts() -> None:
    pool = _virgin_pool()
    await seed(pool)
    # brand_presets INSERT: args = (sql, name, palette_json, fonts_json)
    brand_call = pool.execute.await_args_list[1]
    _, name_arg, palette_arg, fonts_arg = brand_call.args
    assert name_arg == "Default"
    assert json.loads(palette_arg) == DEFAULT_PALETTE
    assert json.loads(fonts_arg) == DEFAULT_FONTS
