"""Authenticated WebSocket for job progress (BLUEPRINT §08.8).

JWT lives in the ``?token=`` query string because browser WebSocket clients
cannot send custom headers. The token is validated with ``decode_token``
(same secret + algorithm as the REST layer).

Ownership rule (BP §08.8):
- ``operator`` → can only watch jobs they own
- ``admin`` / ``reviewer`` → can watch any job

The endpoint streams ``get_job_progress(job_id)`` once per second and
exits cleanly when the job reaches a terminal state (``completed`` or
``failed``).

Close codes (RFC 6455 app range 4000-4999):
- 4001 invalid/expired token
- 4003 ownership denied (operator → other user's job)
- 4004 job not found
"""

from __future__ import annotations

import asyncio
import uuid as uuid_mod
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.api.dependencies import get_current_user
from app.services.auth_service import decode_token
from app.services.dependencies import get_pool

logger = structlog.get_logger()

router = APIRouter(tags=["websocket"])

POLL_INTERVAL_SECONDS = 1.0
TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})


async def get_job_progress(job_id: str) -> dict[str, Any]:
    """Fetch current state of a generation job.

    Used by both the WebSocket stream and the polling fallback endpoint.
    Returns ``{"status": "not_found"}`` if the job id has no row.

    D54: BP §08.8 line 2632 passes ``job_id`` (str) directly to asyncpg,
    which would crash because ``generation_jobs.id`` is UUID. We convert
    explicitly with ``uuid_mod.UUID``.
    """
    pool = get_pool()
    try:
        jid = uuid_mod.UUID(job_id)
    except ValueError:
        return {"status": "not_found"}
    row = await pool.fetchrow(
        "SELECT status, progress_percent, current_step, error_message "
        "FROM generation_jobs WHERE id = $1",
        jid,
    )
    return dict(row) if row else {"status": "not_found"}


@router.websocket("/ws/jobs/{job_id}")
async def websocket_endpoint(
    websocket: WebSocket, job_id: str, token: str
) -> None:
    """Stream job progress over WebSocket. JWT in ``?token=`` query string.

    Ownership: operator → own jobs only; admin/reviewer → any job.
    """
    try:
        payload = decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    if payload.get("type") != "access":
        await websocket.close(code=4001, reason="Invalid token type")
        return

    pool = get_pool()
    try:
        jid = uuid_mod.UUID(job_id)
    except ValueError:
        await websocket.close(code=4004, reason="Job non trovato")
        return

    job = await pool.fetchrow(
        "SELECT c.created_by FROM generation_jobs j "
        "JOIN courses c ON j.course_id = c.id WHERE j.id = $1",
        jid,
    )
    if not job:
        await websocket.close(code=4004, reason="Job non trovato")
        return

    role = payload.get("role")
    if role == "operator" and str(job["created_by"]) != payload["sub"]:
        await websocket.close(
            code=4003, reason="Accesso negato a job di altro utente"
        )
        return

    await websocket.accept()
    try:
        while True:
            data = await get_job_progress(job_id)
            await websocket.send_json(data)
            if data.get("status") in TERMINAL_STATES:
                break
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        # Client disconnected — the job keeps running in the background.
        logger.info("ws_client_disconnect", job_id=job_id)


# ─────────────── GET /api/jobs/{job_id}/progress ───────────────
# F11 (2026-06-02): REST fallback al WS. Necessario perche` il client
# spesso non riesce a tenere aperta una connessione WS (Railway proxy
# timeout, mobile network changes, ecc.) → cade in polling che pero`
# non aveva mai una sorgente di progress_percent + current_step e
# restava bloccato a 0%/"Avvio..." (utente segnalato 2026-06-02).
# Riusa `get_job_progress` come WS, stessa ownership rule.


@router.get("/api/jobs/{job_id}/progress")
async def get_job_progress_rest(
    job_id: str,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Snapshot single-shot del job progress (REST fallback al WS).

    Ownership: operator → own jobs only; admin/reviewer → any job.
    """
    pool = get_pool()
    try:
        jid = uuid_mod.UUID(job_id)
    except ValueError:
        raise HTTPException(404, "Job non trovato") from None

    job = await pool.fetchrow(
        "SELECT c.created_by FROM generation_jobs j "
        "JOIN courses c ON j.course_id = c.id WHERE j.id = $1",
        jid,
    )
    if not job:
        raise HTTPException(404, "Job non trovato")

    role = user.get("role")
    if role == "operator" and str(job["created_by"]) != str(user["id"]):
        raise HTTPException(403, "Accesso negato a job di altro utente")

    return await get_job_progress(job_id)


__all__ = ["POLL_INTERVAL_SECONDS", "TERMINAL_STATES", "get_job_progress", "router"]
