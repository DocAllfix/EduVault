"""F6 — Unit test chat_service.

Test pure logic + DB mock (asyncpg AsyncMock). NO chiamate LLM reali.
Coverage:
  - _build_slide_context formatta correttamente
  - _build_messages applica sliding window (max 12)
  - _build_messages skippa role=tool/system in history
  - get_or_create_conversation: hit + miss
  - insert_message + list_messages roundtrip shape
  - mark_message_applied: idempotency 200 → 409
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.services.chat_service import (
    _MEMORY_WINDOW,
    _build_messages,
    _build_slide_context,
    get_or_create_conversation,
    insert_message,
    list_messages,
    mark_message_applied,
)


def test_build_slide_context_full():
    ctx = _build_slide_context(
        slide_title="Concetto incendio",
        slide_body=["Combustibile", "Comburente", "Innesco"],
        slide_notes="Spiegare il triangolo del fuoco brevemente.",
        course_title="Antincendio L1 4h",
    )
    assert "Antincendio L1 4h" in ctx
    assert "Concetto incendio" in ctx
    assert "Combustibile" in ctx
    assert "triangolo del fuoco" in ctx


def test_build_slide_context_empty_body():
    ctx = _build_slide_context(
        slide_title="Titolo",
        slide_body=[],
        slide_notes="",
        course_title="X",
    )
    assert "(vuoto)" in ctx


def test_build_messages_no_history():
    msgs = _build_messages(
        user_message="rendi piu' operativo il bullet 3",
        slide_context="CORSO: X\nSLIDE: Y",
    )
    # system_prompt + slide_context + user
    assert len(msgs) == 3
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "system"
    assert "SLIDE: Y" in msgs[1]["content"]
    assert msgs[2]["role"] == "user"
    assert msgs[2]["content"] == "rendi piu' operativo il bullet 3"


def test_build_messages_sliding_window():
    """Memoria sliding window: solo gli ultimi _MEMORY_WINDOW (=12) messaggi."""
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
        for i in range(20)  # 20 msgs alternati
    ]
    msgs = _build_messages(
        user_message="nuovo turno",
        slide_context="ctx",
        history=history,
    )
    # 2 system + 12 history (cap) + 1 user = 15
    assert len(msgs) == 15
    # Verifica ultimi 12 della history sono inclusi (msg8..msg19)
    history_msgs = msgs[2:-1]
    assert len(history_msgs) == 12
    assert history_msgs[0]["content"] == "msg8"
    assert history_msgs[-1]["content"] == "msg19"


def test_build_messages_skip_tool_system_history():
    """Role tool e system in history vengono saltati (non in context LLM)."""
    history = [
        {"role": "user", "content": "u1"},
        {"role": "tool", "content": "tool_call_result"},
        {"role": "system", "content": "old system"},
        {"role": "assistant", "content": "a1"},
    ]
    msgs = _build_messages(user_message="new", slide_context="ctx", history=history)
    # 2 system iniziali + 2 user/assistant (tool e system skippati) + 1 user final
    assert len(msgs) == 5
    history_msgs = msgs[2:-1]
    assert all(m["role"] in ("user", "assistant") for m in history_msgs)


def test_memory_window_constant():
    assert _MEMORY_WINDOW == 12


# ─── DB persistence (asyncpg AsyncMock) ─────────────────────────────────────


@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    return pool


@pytest.mark.asyncio
async def test_get_or_create_conversation_existing(mock_pool):
    existing_id = uuid.uuid4()
    mock_pool.fetchval = AsyncMock(return_value=existing_id)
    course_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    result = await get_or_create_conversation(mock_pool, course_id, user_id)
    assert result == str(existing_id)
    # Una sola fetchval (SELECT), no INSERT
    assert mock_pool.fetchval.call_count == 1


@pytest.mark.asyncio
async def test_get_or_create_conversation_new(mock_pool):
    new_id = uuid.uuid4()
    # Prima fetchval (SELECT) → None, seconda (INSERT) → new_id
    mock_pool.fetchval = AsyncMock(side_effect=[None, new_id])
    course_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    result = await get_or_create_conversation(mock_pool, course_id, user_id)
    assert result == str(new_id)
    assert mock_pool.fetchval.call_count == 2


@pytest.mark.asyncio
async def test_insert_message_basic(mock_pool):
    new_id = uuid.uuid4()
    mock_pool.fetchval = AsyncMock(return_value=new_id)
    conv_id = str(uuid.uuid4())
    result = await insert_message(
        mock_pool,
        conversation_id=conv_id,
        role="user",
        content="ciao",
        slide_index=3,
    )
    assert result == str(new_id)
    # Verifica args: role+content presenti
    call_args = mock_pool.fetchval.call_args
    assert call_args[0][2] == "user"  # role
    assert call_args[0][3] == "ciao"  # content
    assert call_args[0][4] == 3  # slide_index


@pytest.mark.asyncio
async def test_insert_message_with_tool_calls(mock_pool):
    new_id = uuid.uuid4()
    mock_pool.fetchval = AsyncMock(return_value=new_id)
    tool_calls = {"proposed_patch": {"title": "Nuovo titolo"}}
    await insert_message(
        mock_pool,
        conversation_id=str(uuid.uuid4()),
        role="assistant",
        content="ho proposto un titolo",
        slide_index=2,
        tool_calls=tool_calls,
    )
    # tool_calls serializzato JSON
    call_args = mock_pool.fetchval.call_args
    import json
    assert json.loads(call_args[0][5]) == tool_calls


@pytest.mark.asyncio
async def test_list_messages_reverse_order(mock_pool):
    """DB ritorna DESC, list_messages reverse a ASC per UI cronologico."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    mock_pool.fetch = AsyncMock(
        return_value=[
            {
                "id": uuid.uuid4(),
                "role": "assistant",
                "content": "a2",
                "slide_index": 1,
                "tool_calls": None,
                "applied_at": None,
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "role": "user",
                "content": "u2",
                "slide_index": 1,
                "tool_calls": None,
                "applied_at": None,
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "role": "assistant",
                "content": "a1",
                "slide_index": 0,
                "tool_calls": None,
                "applied_at": None,
                "created_at": now,
            },
            {
                "id": uuid.uuid4(),
                "role": "user",
                "content": "u1",
                "slide_index": 0,
                "tool_calls": None,
                "applied_at": None,
                "created_at": now,
            },
        ]
    )
    result = await list_messages(mock_pool, str(uuid.uuid4()))
    # Reversed: ASC cronologico
    assert [m["content"] for m in result] == ["u1", "a1", "u2", "a2"]


@pytest.mark.asyncio
async def test_mark_message_applied_idempotency_first(mock_pool):
    """Prima volta: row.applied_at = None → True + UPDATE."""
    mock_pool.fetchrow = AsyncMock(return_value={"applied_at": None})
    mock_pool.execute = AsyncMock()
    result = await mark_message_applied(mock_pool, str(uuid.uuid4()))
    assert result is True
    mock_pool.execute.assert_called_once()


@pytest.mark.asyncio
async def test_mark_message_applied_idempotency_second(mock_pool):
    """Seconda volta: row.applied_at != None → False, NO UPDATE."""
    from datetime import datetime

    mock_pool.fetchrow = AsyncMock(return_value={"applied_at": datetime.now()})
    mock_pool.execute = AsyncMock()
    result = await mark_message_applied(mock_pool, str(uuid.uuid4()))
    assert result is False
    mock_pool.execute.assert_not_called()


@pytest.mark.asyncio
async def test_mark_message_applied_not_found(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=None)
    with pytest.raises(ValueError, match="not found"):
        await mark_message_applied(mock_pool, str(uuid.uuid4()))
