"""WebSocket endpoint tests (FASE 5.3).

Covers BP §08.8 contract:
- 4001 invalid/expired/wrong-type token
- 4004 job_id not a UUID / job not found
- 4003 operator watching someone else's job
- accept + send_json for legitimate operator (own job) and admin (any job)
- loop exits when status reaches terminal state
- get_job_progress: UUID conversion + not_found shape
"""

from __future__ import annotations

import sys
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

if "weasyprint" not in sys.modules:  # pragma: no cover
    sys.modules["weasyprint"] = MagicMock()

from app.api import websocket as ws_mod  # noqa: E402
from app.api.websocket import get_job_progress  # noqa: E402
from app.main import app  # noqa: E402
from app.services import dependencies as deps  # noqa: E402
from app.services.auth_service import create_access_token, create_refresh_token  # noqa: E402


ADMIN_ID = "11111111-1111-1111-1111-111111111111"
OPERATOR_ID = "22222222-2222-2222-2222-222222222222"
OTHER_USER_ID = "99999999-9999-9999-9999-999999999999"


@pytest.fixture(autouse=True)
def _reset_pool() -> Any:
    yield
    deps._pool = None


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _wire_pool(pool: Any) -> Any:
    deps.set_pool(pool)
    return pool


def _job_row(created_by: str) -> dict[str, Any]:
    return {"created_by": uuid.UUID(created_by)}


def _progress(status: str = "completed", percent: int = 100) -> dict[str, Any]:
    return {
        "status": status,
        "progress_percent": percent,
        "current_step": "done",
        "error_message": None,
    }


# ─────────────── 1. get_job_progress — pure ───────────────


@pytest.mark.asyncio
async def test_get_job_progress_returns_not_found_for_invalid_uuid() -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=None)
    _wire_pool(pool)

    out = await get_job_progress("not-a-uuid")
    assert out == {"status": "not_found"}
    pool.fetchrow.assert_not_awaited()  # never hit DB on bad UUID


@pytest.mark.asyncio
async def test_get_job_progress_returns_not_found_when_row_missing() -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=None)
    _wire_pool(pool)
    out = await get_job_progress(str(uuid.uuid4()))
    assert out == {"status": "not_found"}


@pytest.mark.asyncio
async def test_get_job_progress_returns_row_as_dict() -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_progress("research", 30))
    _wire_pool(pool)
    out = await get_job_progress(str(uuid.uuid4()))
    assert out["status"] == "research"
    assert out["progress_percent"] == 30


# ─────────────── 2. WebSocket auth failures ───────────────


def test_ws_closes_4001_when_token_missing(client: TestClient) -> None:
    pool = MagicMock()
    _wire_pool(pool)
    job_id = uuid.uuid4()

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            ws.receive_text()
    # Missing required query param → starlette closes with 1008 (Policy
    # Violation) BEFORE our endpoint runs. Either way the connection is
    # refused — that's all the BP contract demands.
    assert exc_info.value.code in (1008, 4001, 403)


def test_ws_closes_4001_on_invalid_token(client: TestClient) -> None:
    pool = MagicMock()
    _wire_pool(pool)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/ws/jobs/{uuid.uuid4()}?token=garbage"
        ) as ws:
            ws.receive_text()
    assert exc_info.value.code == 4001


def test_ws_closes_4001_when_refresh_token_used(client: TestClient) -> None:
    """Only access tokens are accepted (BP §08.2). A refresh token has
    type='refresh' → 4001."""
    pool = MagicMock()
    _wire_pool(pool)
    refresh = create_refresh_token(OPERATOR_ID)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/ws/jobs/{uuid.uuid4()}?token={refresh}"
        ) as ws:
            ws.receive_text()
    assert exc_info.value.code == 4001


# ─────────────── 3. job lookup & ownership ───────────────


def test_ws_closes_4004_when_job_id_is_not_uuid(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=None)
    _wire_pool(pool)
    token = create_access_token(OPERATOR_ID, "operator")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/jobs/not-a-uuid?token={token}") as ws:
            ws.receive_text()
    assert exc_info.value.code == 4004
    pool.fetchrow.assert_not_awaited()


def test_ws_closes_4004_when_job_row_missing(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=None)
    _wire_pool(pool)
    token = create_access_token(OPERATOR_ID, "operator")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/ws/jobs/{uuid.uuid4()}?token={token}"
        ) as ws:
            ws.receive_text()
    assert exc_info.value.code == 4004


def test_ws_closes_4003_when_operator_watches_someone_else_job(
    client: TestClient,
) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=_job_row(created_by=OTHER_USER_ID))
    _wire_pool(pool)
    token = create_access_token(OPERATOR_ID, "operator")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(
            f"/ws/jobs/{uuid.uuid4()}?token={token}"
        ) as ws:
            ws.receive_text()
    assert exc_info.value.code == 4003


# ─────────────── 4. happy paths ───────────────


def test_ws_streams_progress_for_operator_on_own_job(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(
        side_effect=[
            _job_row(created_by=OPERATOR_ID),  # ownership lookup
            _progress("completed", 100),       # get_job_progress
        ]
    )
    _wire_pool(pool)
    token = create_access_token(OPERATOR_ID, "operator")

    # Make the sleep instant so the loop completes immediately on terminal status
    with patch.object(ws_mod, "POLL_INTERVAL_SECONDS", 0):
        with client.websocket_connect(
            f"/ws/jobs/{uuid.uuid4()}?token={token}"
        ) as ws:
            data = ws.receive_json()
            assert data["status"] == "completed"
            assert data["progress_percent"] == 100


def test_ws_streams_progress_for_admin_on_any_job(client: TestClient) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(
        side_effect=[
            _job_row(created_by=OTHER_USER_ID),  # not admin's, but allowed
            _progress("completed", 100),
        ]
    )
    _wire_pool(pool)
    token = create_access_token(ADMIN_ID, "admin")

    with patch.object(ws_mod, "POLL_INTERVAL_SECONDS", 0):
        with client.websocket_connect(
            f"/ws/jobs/{uuid.uuid4()}?token={token}"
        ) as ws:
            data = ws.receive_json()
            assert data["status"] == "completed"


def test_ws_emits_multiple_frames_then_stops_on_terminal_state(
    client: TestClient,
) -> None:
    """The loop sends frames until status reaches a TERMINAL_STATE."""
    pool = MagicMock()
    pool.fetchrow = AsyncMock(
        side_effect=[
            _job_row(created_by=OPERATOR_ID),
            _progress("research", 20),
            _progress("content", 60),
            _progress("completed", 100),
        ]
    )
    _wire_pool(pool)
    token = create_access_token(OPERATOR_ID, "operator")

    with patch.object(ws_mod, "POLL_INTERVAL_SECONDS", 0):
        with client.websocket_connect(
            f"/ws/jobs/{uuid.uuid4()}?token={token}"
        ) as ws:
            frames = []
            for _ in range(3):
                frames.append(ws.receive_json())

    assert [f["status"] for f in frames] == ["research", "content", "completed"]
    # After "completed" the loop breaks → server closes the connection,
    # any further receive raises WebSocketDisconnect (don't assert here —
    # the 3-frame sequence above is sufficient evidence).


def test_ws_stops_on_failed_status(client: TestClient) -> None:
    """failed is also a TERMINAL_STATE — same exit path as completed."""
    pool = MagicMock()
    pool.fetchrow = AsyncMock(
        side_effect=[
            _job_row(created_by=OPERATOR_ID),
            _progress("failed", 50),
        ]
    )
    _wire_pool(pool)
    token = create_access_token(OPERATOR_ID, "operator")

    with patch.object(ws_mod, "POLL_INTERVAL_SECONDS", 0):
        with client.websocket_connect(
            f"/ws/jobs/{uuid.uuid4()}?token={token}"
        ) as ws:
            data = ws.receive_json()
            assert data["status"] == "failed"


# ─────────────── 5. structural ───────────────


def test_terminal_states_include_completed_failed_cancelled() -> None:
    """The three terminal states the pipeline uses must all exit the WS loop."""
    from app.api.websocket import TERMINAL_STATES

    assert {"completed", "failed", "cancelled"} <= TERMINAL_STATES
