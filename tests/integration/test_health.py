"""Integration tests for GET /health (BLUEPRINT §10.1).

The pool is stubbed via ``app.services.dependencies.set_pool`` with an
``AsyncMock``. The startup hook of ``app.main`` is intentionally NOT
triggered (no ``lifespan``) — we drive the ASGI app directly.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import dependencies as deps


@pytest.fixture
def healthy_pool() -> AsyncMock:
    """A fake pool whose ``fetchval`` returns 1, like a live Postgres."""
    pool = AsyncMock()
    pool.fetchval = AsyncMock(return_value=1)
    deps.set_pool(pool)
    yield pool
    deps._pool = None  # tear down to avoid cross-test bleed


@pytest.fixture
def unreachable_pool() -> AsyncMock:
    """A fake pool whose ``fetchval`` raises, simulating DB down."""
    pool = AsyncMock()
    pool.fetchval = AsyncMock(side_effect=RuntimeError("db down"))
    deps.set_pool(pool)
    yield pool
    deps._pool = None


async def _get_health() -> dict[str, Any]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    return resp.json()


async def test_health_returns_required_keys(healthy_pool: AsyncMock) -> None:
    """BP §10.1: response must expose status, database, disk_free_gb."""
    body = await _get_health()
    assert set(body.keys()) == {"status", "database", "disk_free_gb"}


async def test_health_database_connected_when_pool_works(
    healthy_pool: AsyncMock,
) -> None:
    body = await _get_health()
    assert body["database"] == "connected"
    healthy_pool.fetchval.assert_awaited_once_with("SELECT 1")


async def test_health_database_unreachable_when_pool_raises(
    unreachable_pool: AsyncMock,
) -> None:
    body = await _get_health()
    assert body["database"] == "unreachable"
    # status must drop to degraded as soon as the DB is unreachable
    assert body["status"] == "degraded"


async def test_health_disk_free_gb_is_numeric(healthy_pool: AsyncMock) -> None:
    body = await _get_health()
    assert isinstance(body["disk_free_gb"], (int, float))
    assert body["disk_free_gb"] >= 0
