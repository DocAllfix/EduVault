"""F3.AI — AI-assisted skeleton editing (richiesta cliente 2026-05-31).

Per F3, lo scheletro narrativo era editabile solo manualmente in UI (edit testo,
reorder up/down, add/remove). L'utente vuole anche micro-azioni LLM-driven sui
sotto-temi: rifrasare un sotto-tema, renderlo piu' operativo, suggerire 3
alternative, oppure modificare un intero modulo con free prompt.

Questo service espone 4 azioni atomiche, ognuna ritorna un patch deterministico
che il frontend applica al ModuleSkeleton corrente. Provider chain riusa
``_FALLBACK_CHAIN_CONTENT`` (Azure mini -> OpenAI -> Anthropic) come
``skeleton_service.generate_module_skeleton``, niente nuove deps.

Vincoli VAA:
  - (a) verifica al render: frontend mostra diff prima di applicare.
  - (b) provenienza: actions log via structlog (action_type, module_idx,
    voice_idx, provider_used, ms).
  - (c) safety: il service ritorna SOLO la proposta, non muta DB. Mutation
    avviene solo dopo che l'utente clicca "Applica" -> il frontend salva via
    PUT /skeleton esistente.
"""

from __future__ import annotations

from typing import Any, Literal, cast

import structlog
from pydantic import BaseModel, Field

from app.config import settings
from app.models.pipeline import ModuleSkeleton, SkeletonItem
from app.services.ingestion_service import (
    _FALLBACK_CHAIN_CONTENT,
    _INSTRUCTOR_DEPTH_RETRIES,
    _instructor_client_for,
)
from app.services.pipeline_telemetry import PipelinePhase, timed

logger = structlog.get_logger(__name__)


# ─── Response models (instructor structured) ────────────────────────────────


class SubtopicProposal(BaseModel):
    """Single sub-topic proposal returned by per-voice actions."""

    sub_topic: str = Field(..., min_length=1, max_length=160)
    retrieval_query: str = Field(..., min_length=15)


class SubtopicAlternatives(BaseModel):
    """3 alternative proposals for a sub-topic (suggest_alternatives action)."""

    alternatives: list[SubtopicProposal] = Field(..., min_length=3, max_length=3)


class ModuleSkeletonPatch(BaseModel):
    """Full new items list for a module (free_module_edit action).

    The shape mirrors ``ModuleSkeleton.items`` so the frontend can swap in-place
    after diff confirmation. Ordinals are normalized 1..N by the model.
    """

    items: list[SkeletonItem] = Field(..., min_length=6, max_length=10)


# ─── System prompts ─────────────────────────────────────────────────────────


_SYSTEM_BASE = (
    "Sei un progettista esperto di corsi di formazione sulla sicurezza sul "
    "lavoro in Italia (D.Lgs 81/08, Accordi Stato-Regioni, decreti antincendio, "
    "primo soccorso, HACCP). Stai aiutando un operatore a raffinare la struttura "
    "tassonomica di un modulo formativo. Rispetta il perimetro del modulo e del "
    "corso indicato; non sconfinare in argomenti di altri moduli/corsi."
)


# ─── Action: rephrase_subtopic ──────────────────────────────────────────────


_PROMPT_REPHRASE = (
    "Riformula il seguente sotto-tema rendendolo piu' chiaro, conciso ed "
    "espressivo per un docente. Mantieni il significato e il perimetro identici. "
    "Aggiorna anche la retrieval_query coerentemente (15-30 parole, specifica)."
    "\n\nSOTTO-TEMA ATTUALE:\n  sub_topic: {sub_topic}\n  retrieval_query: {query}"
    "\n\nCONTESTO:\n  modulo: {module_title}\n  corso: {course_title}"
)


# ─── Action: make_operational ───────────────────────────────────────────────


_PROMPT_OPERATIONAL = (
    "Trasforma il seguente sotto-tema rendendolo piu' OPERATIVO e pratico: "
    "passa da concetti teorici a azioni concrete, procedure, comportamenti "
    "osservabili. Aggiorna anche la retrieval_query per puntare a passaggi "
    "normativi di tipo procedurale/operativo (allegati, articoli con elenchi "
    "di obblighi/divieti, checklist)."
    "\n\nSOTTO-TEMA ATTUALE:\n  sub_topic: {sub_topic}\n  retrieval_query: {query}"
    "\n\nCONTESTO:\n  modulo: {module_title}\n  corso: {course_title}"
)


# ─── Action: suggest_alternatives ───────────────────────────────────────────


_PROMPT_ALTERNATIVES = (
    "Proponi 3 ALTERNATIVE distinte al seguente sotto-tema. Ogni alternativa "
    "deve coprire lo stesso terreno didattico ma con un taglio diverso "
    "(es: piu' teorico, piu' applicativo, piu' regolamentare). Mantieni il "
    "perimetro del modulo. Per ogni alternativa fornisci sub_topic + "
    "retrieval_query coerente."
    "\n\nSOTTO-TEMA ATTUALE:\n  sub_topic: {sub_topic}\n  retrieval_query: {query}"
    "\n\nCONTESTO:\n  modulo: {module_title}\n  corso: {course_title}"
)


# ─── Action: free_module_edit ───────────────────────────────────────────────


_PROMPT_FREE_MODULE = (
    "Modifica la STRUTTURA del seguente modulo formativo applicando l'istruzione "
    "dell'utente. Ritorna una NUOVA lista di 6-10 sotto-temi ordinati che "
    "rispetti l'istruzione, il perimetro del modulo, e la coerenza con gli altri "
    "moduli del corso. Ogni sotto-tema deve avere sub_topic + retrieval_query "
    "(15-30 parole, specifica)."
    "\n\nMODULO ATTUALE: {module_title}\n"
    "CORSO: {course_title}\n"
    "ALTRI MODULI DEL CORSO (perimetro inter-modulo da rispettare):\n{siblings}\n\n"
    "STRUTTURA ATTUALE DEL MODULO (sotto-temi numerati):\n{current_items}\n\n"
    "ISTRUZIONE DELL'UTENTE:\n{user_instruction}"
)


# ─── Public types ───────────────────────────────────────────────────────────


VoiceActionType = Literal["rephrase_subtopic", "make_operational", "suggest_alternatives"]


# ─── Implementation ─────────────────────────────────────────────────────────


async def _call_instructor(
    *,
    response_model: type[BaseModel],
    system: str,
    prompt: str,
    course_id: str | None,
    phase: PipelinePhase,
    action_type: str,
    extra_log: dict[str, Any] | None = None,
) -> BaseModel:
    """Walk the content fallback chain; raise if all providers fail."""
    extra_kwargs: dict[str, Any] = {
        "action_type": action_type,
        "source": "llm_content_chain",
        **(extra_log or {}),
    }
    with timed(phase, course_id=course_id, **extra_kwargs) as ev:
        last_exc: Exception | None = None
        for provider, deployment_key, level_name in _FALLBACK_CHAIN_CONTENT:
            model_id = getattr(settings, deployment_key, None)
            if not model_id:
                continue
            try:
                client, eff_model, _reask = _instructor_client_for(provider, model_id)
                result = await client.chat.completions.create(
                    model=eff_model,
                    response_model=response_model,
                    max_retries=_INSTRUCTOR_DEPTH_RETRIES,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                )
                ev["provider_used"] = level_name
                return cast(BaseModel, result)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "skeleton_ai_edit_provider_failed",
                    action_type=action_type,
                    provider=level_name,
                    error_class=type(exc).__name__,
                    error_msg=str(exc)[:200],
                )
                continue
        raise RuntimeError(
            f"skeleton AI edit failed: action={action_type} all providers exhausted"
        ) from last_exc


async def ai_edit_voice(
    *,
    action: VoiceActionType,
    current_item: SkeletonItem,
    module_title: str,
    course_title: str,
    course_id: str | None = None,
) -> dict[str, object]:
    """Apply an LLM-driven micro-action to a single sub-topic.

    Returns a dict shaped per action type:
      - rephrase_subtopic / make_operational: {"proposal": SubtopicProposal}
      - suggest_alternatives: {"alternatives": [SubtopicProposal x3]}

    Pure proposal: caller decides whether to apply (no DB mutation here).
    """
    fmt = {
        "sub_topic": current_item.sub_topic,
        "query": current_item.retrieval_query,
        "module_title": module_title,
        "course_title": course_title,
    }

    if action == "rephrase_subtopic":
        proposal = await _call_instructor(
            response_model=SubtopicProposal,
            system=_SYSTEM_BASE,
            prompt=_PROMPT_REPHRASE.format(**fmt),
            course_id=course_id,
            phase=PipelinePhase.SKELETON_GENERATE,
            action_type=action,
            extra_log={"voice_ordinal": current_item.ordinal},
        )
        return {"proposal": proposal.model_dump()}

    if action == "make_operational":
        proposal = await _call_instructor(
            response_model=SubtopicProposal,
            system=_SYSTEM_BASE,
            prompt=_PROMPT_OPERATIONAL.format(**fmt),
            course_id=course_id,
            phase=PipelinePhase.SKELETON_GENERATE,
            action_type=action,
            extra_log={"voice_ordinal": current_item.ordinal},
        )
        return {"proposal": proposal.model_dump()}

    if action == "suggest_alternatives":
        alts = await _call_instructor(
            response_model=SubtopicAlternatives,
            system=_SYSTEM_BASE,
            prompt=_PROMPT_ALTERNATIVES.format(**fmt),
            course_id=course_id,
            phase=PipelinePhase.SKELETON_GENERATE,
            action_type=action,
            extra_log={"voice_ordinal": current_item.ordinal},
        )
        return {"alternatives": [a.model_dump() for a in alts.alternatives]}  # type: ignore[attr-defined]

    raise ValueError(f"unknown voice action: {action}")


async def ai_edit_module(
    *,
    current_skeleton: ModuleSkeleton,
    user_instruction: str,
    course_title: str,
    sibling_module_titles: list[str],
    course_id: str | None = None,
) -> dict[str, object]:
    """Apply a free-text user instruction to an entire module skeleton.

    Returns {"patch": ModuleSkeletonPatch dict} — the new items list, ordinals
    normalized 1..N. Caller swaps current items with patch.items after diff
    confirmation.
    """
    siblings = "\n".join(
        f"  - {t}" for t in sibling_module_titles if t != current_skeleton.title
    ) or "  (nessun altro modulo)"
    current_items = "\n".join(
        f"  {it.ordinal}. {it.sub_topic} (query: {it.retrieval_query})"
        for it in current_skeleton.items
    )
    prompt = _PROMPT_FREE_MODULE.format(
        module_title=current_skeleton.title,
        course_title=course_title,
        siblings=siblings,
        current_items=current_items,
        user_instruction=user_instruction.strip(),
    )
    patch = await _call_instructor(
        response_model=ModuleSkeletonPatch,
        system=_SYSTEM_BASE,
        prompt=prompt,
        course_id=course_id,
        phase=PipelinePhase.SKELETON_GENERATE,
        action_type="free_module_edit",
        extra_log={
            "module_index": current_skeleton.module_index,
            "instruction_len": len(user_instruction),
        },
    )
    return {"patch": patch.model_dump()}
