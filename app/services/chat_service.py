"""F6 — Chat LLM Course Studio (vast-hopping §F6).

Implementazione POST-MVP 2026-05-31 con 3 feature chieste dall'utente:
  1. **Memoria conversazione cross-session**: una conversation_id per
     course_id (D7), tutti i messaggi persistiti in DB, history passata
     al LLM ad ogni turno (sliding window cap a 12 messaggi).
  2. **Streaming (typing effect)**: `chat_turn_stream` async generator
     che yielda parziali della response (instructor Partial) → SSE
     endpoint nel router.
  3. **Prompt caching**: marker `cache_control` su system prompt
     (~stabile) + slide_context (~stabile dentro un turno). Anthropic
     cache esplicita (5min TTL), Azure/OpenAI cached automatica via
     prompt prefix invariato.

Vincolo D7: NO chat libera per-corso -> chat e' SEMPRE ancorata a UNA
slide (slide_index obbligatorio nel turno). Per modifiche a livello
modulo / struttura corso, F3.AI gia' offre micro-actions dedicate.

Provider chain: riusa `_FALLBACK_CHAIN_CONTENT` + `_instructor_client_for`
da ingestion_service. Stesso flusso di skeleton_ai_edit_service.

Apply: PATCH /slides/{idx} esistente (courses.py:755-776). NESSUN
re-invocation content_agent: il proposed_patch e' un dict di campi che
sostituiscono i campi corrispondenti nel slide_contents_json. Idempotente
via colonna `applied_at` su messages.
"""

from __future__ import annotations

import uuid as uuid_mod
from typing import Any, AsyncIterator, Literal

import structlog
from pydantic import BaseModel, Field

from app.config import settings
from app.services.ingestion_service import (
    _FALLBACK_CHAIN_CONTENT,
    _INSTRUCTOR_DEPTH_RETRIES,
    _instructor_client_for,
)
from app.services.pipeline_telemetry import PipelinePhase, timed

# Sliding window per memory: max N messaggi (alternati user/assistant)
# passati al LLM nel turno corrente. Riduce token cost mantenendo contesto
# locale.
_MEMORY_WINDOW = 12

logger = structlog.get_logger(__name__)


# ─── Structured response model (instructor) ─────────────────────────────────


class ProposedPatch(BaseModel):
    """Patch proposto dal LLM per la slide corrente. Campi opzionali: solo
    quelli != None vengono applicati lato backend (PATCH /slides/{idx}).
    """

    title: str | None = Field(
        None,
        description="Nuovo titolo della slide, max 80 char. None = invariato.",
    )
    body: list[str] | None = Field(
        None,
        description=(
            "Nuova lista bullets (max 6 elementi, max 12 parole ciascuno). "
            "None = invariati."
        ),
    )
    speaker_notes: str | None = Field(
        None,
        description="Nuove note narrate (max 60s parlato). None = invariate.",
    )


class ChatTurnResponse(BaseModel):
    """Output structured della chat per un turno utente."""

    assistant_message: str = Field(
        ...,
        description=(
            "Risposta in italiano per l'utente: spiega cosa proponi e perche'. "
            "Frase concisa, max 3 frasi."
        ),
    )
    proposed_patch: ProposedPatch | None = Field(
        None,
        description=(
            "Patch concreto da applicare. None = solo risposta testuale "
            "(es. domanda di chiarimento, conferma)."
        ),
    )


# ─── System prompt ──────────────────────────────────────────────────────────


_SYSTEM = (
    "Sei l'assistente di refining di Nexus EduVault, una piattaforma per la "
    "generazione di corsi di formazione sulla sicurezza sul lavoro in Italia "
    "(D.Lgs 81/08, Accordi Stato-Regioni, antincendio, primo soccorso, HACCP). "
    "L'utente sta visualizzando UNA slide in Course Studio e ti chiede di "
    "modificarla. Il tuo compito: (a) capire la richiesta, (b) proporre un "
    "patch concreto (title, body bullets, speaker_notes) coerente con il "
    "contenuto della slide e con il perimetro normativo del corso, (c) "
    "spiegare in italiano in massimo 3 frasi cosa hai proposto. Non inventi "
    "riferimenti normativi: se l'utente chiede contenuti che richiedono fonti "
    "specifiche, dillo e proponi solo struttura/forma. Rispetta i limiti: "
    "title <= 80 char, body <= 6 bullets, ogni bullet <= 12 parole, notes "
    "<= 60s parlato (~150 parole). Se non e' chiaro cosa fare, NON proporre "
    "patch: rispondi con una domanda di chiarimento (assistant_message "
    "popolato, proposed_patch=null)."
)


def _build_slide_context(
    *,
    slide_title: str,
    slide_body: list[str],
    slide_notes: str,
    course_title: str,
) -> str:
    """Contesto stabile del turno (slide + corso). Cached-friendly: stesse
    parole per stessa slide -> prompt prefix cache HIT su provider."""
    bullets = "\n".join(f"  - {b}" for b in slide_body) or "  (vuoto)"
    return (
        f"CORSO: {course_title}\n\n"
        f"SLIDE CORRENTE:\n"
        f"  Titolo: {slide_title}\n"
        f"  Bullets:\n{bullets}\n"
        f"  Note (audio): {slide_notes[:400]}"
    )


def _build_messages(
    *,
    user_message: str,
    slide_context: str,
    history: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Costruisce la lista messages per il LLM con:
      - system prompt (cached-friendly: stabile cross-turn)
      - slide context come system message separato (cached: stabile dentro la slide)
      - history sliding window come user/assistant alternati (memoria conv)
      - user_message finale

    Anthropic-compatible: i primi 2 system messages possono ricevere
    cache_control breakpoint dal _instructor_client_for wrapper se il
    provider lo supporta. Su Azure/OpenAI il caching e' implicito sul
    prompt prefix invariato (richiesta prompt_cache_key opzionale).
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "system", "content": slide_context},
    ]
    # Sliding window memory: ultimi N messaggi della conversation, alternati
    # user/assistant. Skip role='tool' che non serve LLM (gestiti UI side).
    if history:
        recent = [m for m in history if m["role"] in ("user", "assistant")][-_MEMORY_WINDOW:]
        for m in recent:
            messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message.strip()})
    return messages


# ─── Conversation persistence ───────────────────────────────────────────────


async def get_or_create_conversation(pool: Any, course_id: str, user_id: str) -> str:
    """Ritorna conversation_id esistente per (course_id) o ne crea uno nuovo.

    Una conversation per corso: la chat e' continua cross-sessione (D7).
    """
    cid = uuid_mod.UUID(course_id)
    existing = await pool.fetchval(
        "SELECT id FROM conversations WHERE course_id = $1 "
        "ORDER BY created_at ASC LIMIT 1",
        cid,
    )
    if existing:
        return str(existing)
    new_id = await pool.fetchval(
        "INSERT INTO conversations (course_id, created_by) VALUES ($1, $2) RETURNING id",
        cid,
        uuid_mod.UUID(user_id),
    )
    return str(new_id)


async def list_messages(
    pool: Any, conversation_id: str, *, limit: int = 100
) -> list[dict[str, Any]]:
    """Ritorna gli ultimi N messaggi della conversazione, ordinati cronologici."""
    rows = await pool.fetch(
        """
        SELECT id, role, content, slide_index, tool_calls, applied_at, created_at
        FROM messages
        WHERE conversation_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        uuid_mod.UUID(conversation_id),
        limit,
    )
    # Reverse cronologico ascendente per UI
    return list(
        reversed(
            [
                {
                    "id": str(r["id"]),
                    "role": r["role"],
                    "content": r["content"],
                    "slide_index": r["slide_index"],
                    "tool_calls": r["tool_calls"],
                    "applied_at": r["applied_at"].isoformat() if r["applied_at"] else None,
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]
        )
    )


async def insert_message(
    pool: Any,
    *,
    conversation_id: str,
    role: Literal["user", "assistant", "tool", "system"],
    content: str,
    slide_index: int | None = None,
    tool_calls: dict[str, Any] | None = None,
) -> str:
    """INSERT message + return id."""
    import json as _json

    new_id = await pool.fetchval(
        """
        INSERT INTO messages
        (conversation_id, role, content, slide_index, tool_calls)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        RETURNING id
        """,
        uuid_mod.UUID(conversation_id),
        role,
        content,
        slide_index,
        _json.dumps(tool_calls) if tool_calls else None,
    )
    return str(new_id)


async def mark_message_applied(pool: Any, message_id: str) -> bool:
    """Set applied_at=NOW() su un assistant message. Idempotente:
    se gia' applicato, ritorna False; altrimenti True.
    """
    row = await pool.fetchrow(
        "SELECT applied_at FROM messages WHERE id = $1::uuid",
        message_id,
    )
    if row is None:
        raise ValueError(f"message {message_id} not found")
    if row["applied_at"] is not None:
        return False  # gia' applicato
    await pool.execute(
        "UPDATE messages SET applied_at = NOW() WHERE id = $1::uuid",
        message_id,
    )
    return True


# ─── LLM call (instructor structured) ───────────────────────────────────────


async def chat_turn(
    *,
    user_message: str,
    slide_title: str,
    slide_body: list[str],
    slide_notes: str,
    course_title: str,
    history: list[dict[str, Any]] | None = None,
    course_id: str | None = None,
) -> tuple[ChatTurnResponse, str]:
    """Un turno chat NON-streaming (instructor structured).

    Riusa _build_messages → memory sliding window + slide context cached.
    Fallback chain Azure mini → OpenAI 4o → Anthropic Sonnet.
    """
    slide_context = _build_slide_context(
        slide_title=slide_title,
        slide_body=slide_body,
        slide_notes=slide_notes,
        course_title=course_title,
    )
    messages = _build_messages(
        user_message=user_message,
        slide_context=slide_context,
        history=history,
    )

    with timed(
        PipelinePhase.SKELETON_GENERATE,
        course_id=course_id,
        source="llm_chat_content_chain",
    ) as ev:
        last_exc: Exception | None = None
        for provider, deployment_key, level_name in _FALLBACK_CHAIN_CONTENT:
            model_id = getattr(settings, deployment_key, None)
            if not model_id:
                continue
            try:
                client, eff_model, _reask = _instructor_client_for(provider, model_id)
                response: ChatTurnResponse = await client.chat.completions.create(
                    model=eff_model,
                    response_model=ChatTurnResponse,
                    max_retries=_INSTRUCTOR_DEPTH_RETRIES,
                    messages=messages,
                )
                ev["provider_used"] = level_name
                ev["has_patch"] = response.proposed_patch is not None
                ev["history_len"] = len(history) if history else 0
                return response, level_name
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "chat_turn_provider_failed",
                    provider=level_name,
                    error_class=type(exc).__name__,
                    error_msg=str(exc)[:200],
                )
                continue
        raise RuntimeError("chat_turn: all providers failed") from last_exc


async def chat_turn_stream(
    *,
    user_message: str,
    slide_title: str,
    slide_body: list[str],
    slide_notes: str,
    course_title: str,
    history: list[dict[str, Any]] | None = None,
    course_id: str | None = None,
) -> AsyncIterator[ChatTurnResponse]:
    """Streaming variant: yield Partial[ChatTurnResponse] progressivamente
    mentre il LLM compila la risposta. Frontend riceve via SSE i parziali
    e mostra typing effect.

    Pattern instructor `create_partial(stream=True)`: ad ogni token validable
    contro `ChatTurnResponse`, yielda l'oggetto parziale (campi non ancora
    riempiti = None). Il client UI mostra `assistant_message` mentre cresce,
    e quando arriva `proposed_patch` (o lo stream termina), mostra il diff.

    Fallback chain identica a chat_turn. Su error provider → log + try next.
    """
    import instructor  # noqa: F401 — gia' importato in _instructor_client_for

    slide_context = _build_slide_context(
        slide_title=slide_title,
        slide_body=slide_body,
        slide_notes=slide_notes,
        course_title=course_title,
    )
    messages = _build_messages(
        user_message=user_message,
        slide_context=slide_context,
        history=history,
    )

    last_exc: Exception | None = None
    for provider, deployment_key, level_name in _FALLBACK_CHAIN_CONTENT:
        model_id = getattr(settings, deployment_key, None)
        if not model_id:
            continue
        try:
            client, eff_model, _reask = _instructor_client_for(provider, model_id)
            # instructor `chat.completions.create_partial` yielda incrementi
            # del response_model man mano che vengono parsate.
            stream = client.chat.completions.create_partial(
                model=eff_model,
                response_model=ChatTurnResponse,
                max_retries=_INSTRUCTOR_DEPTH_RETRIES,
                messages=messages,
            )
            logger.info(
                "chat_turn_stream_started",
                provider=level_name,
                history_len=len(history) if history else 0,
            )
            async for partial in stream:
                # partial e' un ChatTurnResponse con campi None per quelli
                # non ancora compilati. Il client UI riceve via SSE.
                yield partial
            logger.info("chat_turn_stream_done", provider=level_name)
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "chat_turn_stream_provider_failed",
                provider=level_name,
                error_class=type(exc).__name__,
                error_msg=str(exc)[:200],
            )
            continue
    raise RuntimeError("chat_turn_stream: all providers failed") from last_exc
