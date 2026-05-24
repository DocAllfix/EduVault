"""Admin endpoints tests (FASE 5.4).

Per endpoint: admin → 200 + shape coerente; operator → 403.
audit_log metrics aggregation tested with both empty result and
mixed payload (JSON-string vs dict, asyncpg JSONB can return either
depending on codec).
"""

from __future__ import annotations

import json
import sys
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

if "weasyprint" not in sys.modules:  # pragma: no cover
    sys.modules["weasyprint"] = MagicMock()

from app.main import app  # noqa: E402
from app.services import dependencies as deps  # noqa: E402
from app.services.auth_service import create_access_token  # noqa: E402


ADMIN_ID = "11111111-1111-1111-1111-111111111111"
OPERATOR_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(autouse=True)
def _reset_pool() -> Any:
    yield
    deps._pool = None


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _token(user_id: str, role: str) -> str:
    return create_access_token(user_id, role)


def _user_row(user_id: str, role: str) -> dict[str, Any]:
    return {
        "id": uuid.UUID(user_id),
        "email": f"{role}@x",
        "role": role,
        "is_active": True,
    }


def _wire_pool(pool: Any) -> None:
    deps.set_pool(pool)


# ─────────────── GET /api/admin/metrics ───────────────


def test_metrics_returns_403_for_operator(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(OPERATOR_ID, "operator"))
    _wire_pool(pool)
    r = client.get(
        "/api/admin/metrics",
        headers={"Authorization": f"Bearer {_token(OPERATOR_ID, 'operator')}"},
    )
    assert r.status_code == 403


def test_metrics_returns_zeros_when_no_audit_rows(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(ADMIN_ID, "admin"))
    pool.fetch = AsyncMock(return_value=[])
    _wire_pool(pool)
    r = client.get(
        "/api/admin/metrics",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "total_runs": 0,
        "avg_elapsed_seconds": 0.0,
        "avg_slides": 0.0,
        "total_images_resolved": 0,
        "period_days": 7,
    }


def test_metrics_aggregates_mixed_json_payloads(client: TestClient) -> None:
    """asyncpg JSONB sometimes returns dict, sometimes str — both must work."""
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(ADMIN_ID, "admin"))
    pool.fetch = AsyncMock(
        return_value=[
            {"details": {"elapsed_seconds": 100, "total_slides": 120, "images_resolved": 5}},
            {"details": json.dumps({"elapsed_seconds": 200, "total_slides": 240, "images_resolved": 7})},
            {"details": {"elapsed_seconds": 300, "total_slides": 360, "images_resolved": 8}},
        ]
    )
    _wire_pool(pool)
    r = client.get(
        "/api/admin/metrics?days=30",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_runs"] == 3
    assert body["avg_elapsed_seconds"] == 200.0  # (100+200+300)/3
    assert body["avg_slides"] == 240.0
    assert body["total_images_resolved"] == 20
    assert body["period_days"] == 30


def test_metrics_rejects_invalid_days_param(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(ADMIN_ID, "admin"))
    _wire_pool(pool)
    r = client.get(
        "/api/admin/metrics?days=0",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 422


# ─────────────── GET /api/dashboard/stats ───────────────


def test_dashboard_stats_returns_403_for_operator(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(OPERATOR_ID, "operator"))
    _wire_pool(pool)
    r = client.get(
        "/api/dashboard/stats",
        headers={"Authorization": f"Bearer {_token(OPERATOR_ID, 'operator')}"},
    )
    assert r.status_code == 403


def test_dashboard_stats_returns_three_counts_for_admin(
    client: TestClient,
) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(ADMIN_ID, "admin"))
    pool.fetchval = AsyncMock(side_effect=[12, 3, 1])  # courses, regs, l2
    _wire_pool(pool)
    r = client.get(
        "/api/dashboard/stats",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 200
    assert r.json() == {"courses_count": 12, "regulations_count": 3, "l2_count": 1}


def test_dashboard_stats_handles_null_counts(client: TestClient) -> None:
    """COUNT(*) never returns NULL but defensive coercion is in the route."""
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(ADMIN_ID, "admin"))
    pool.fetchval = AsyncMock(side_effect=[None, None, None])
    _wire_pool(pool)
    r = client.get(
        "/api/dashboard/stats",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 200
    assert r.json() == {"courses_count": 0, "regulations_count": 0, "l2_count": 0}


# ─────────────── GET /api/brand-presets ───────────────


def test_brand_presets_returns_403_for_operator(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(OPERATOR_ID, "operator"))
    _wire_pool(pool)
    r = client.get(
        "/api/brand-presets",
        headers={"Authorization": f"Bearer {_token(OPERATOR_ID, 'operator')}"},
    )
    assert r.status_code == 403


def test_brand_presets_lists_with_default_first(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(ADMIN_ID, "admin"))
    default_id = uuid.uuid4()
    other_id = uuid.uuid4()
    pool.fetch = AsyncMock(
        return_value=[
            {
                "id": default_id,
                "name": "Default CFP Montessori",
                "palette": {"primary": "#1a365d"},
                "is_default": True,
            },
            {
                "id": other_id,
                "name": "Alt Preset",
                "palette": json.dumps({"primary": "#222"}),
                "is_default": False,
            },
        ]
    )
    _wire_pool(pool)
    r = client.get(
        "/api/brand-presets",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert body[0]["id"] == str(default_id)
    assert body[0]["is_default"] is True
    # JSON-string palette must be decoded to a dict
    assert body[1]["palette"] == {"primary": "#222"}


# ─────────────── GET /api/catalog ───────────────


def test_catalog_returns_403_for_operator(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(OPERATOR_ID, "operator"))
    _wire_pool(pool)
    r = client.get(
        "/api/catalog",
        headers={"Authorization": f"Bearer {_token(OPERATOR_ID, 'operator')}"},
    )
    assert r.status_code == 403


def test_catalog_returns_six_course_types_for_admin(client: TestClient) -> None:
    from config.catalog_config import COURSE_CATALOG

    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_user_row(ADMIN_ID, "admin"))
    _wire_pool(pool)
    r = client.get(
        "/api/catalog",
        headers={"Authorization": f"Bearer {_token(ADMIN_ID, 'admin')}"},
    )
    assert r.status_code == 200
    body = r.json()
    # The 6 BP §13 course types must be present
    assert set(body.keys()) == set(COURSE_CATALOG.keys())
    assert len(body) == 6


# ─────────────── unauth surface ───────────────


def test_all_admin_endpoints_require_auth(client: TestClient) -> None:
    pool = MagicMock()
    _wire_pool(pool)
    for path in (
        "/api/admin/metrics",
        "/api/dashboard/stats",
        "/api/brand-presets",
        "/api/catalog",
    ):
        r = client.get(path)
        assert r.status_code in (401, 403), f"{path} → {r.status_code}"
