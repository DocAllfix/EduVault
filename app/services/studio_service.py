"""Course Studio service (FASE 7 vast-hopping-sketch).

Logica per leggere/modificare slide individuali nel ``slide_contents_json``
JSONB del corso, con ri-validazione Pydantic strict (FASE 1) ad ogni PATCH e
mark ``dirty=true`` quando il contenuto cambia (→ RebuildBanner FASE 11).

Niente over-engineering (karpathy): funzioni pure async, nessuna classe.
"""

from __future__ import annotations

import json
import uuid as uuid_mod
from typing import Any

import structlog

from app.models.pipeline import SlideContent

logger = structlog.get_logger()


def _parse_course_id(course_id: str) -> uuid_mod.UUID:
    try:
        return uuid_mod.UUID(course_id)
    except ValueError as exc:
        raise ValueError(f"invalid course id: {course_id}") from exc


def _deserialize_slides(raw: Any) -> list[dict[str, Any]]:
    """Normalizza slide_contents_json (JSONB) → list[dict].

    Il campo può essere salvato come list (slide flat) o come struttura
    completa con moduli. Gestiamo entrambe ritornando l'array flat di slide.
    """
    if raw is None:
        return []
    data = raw if isinstance(raw, (list, dict)) else json.loads(raw)
    if isinstance(data, list):
        # Già flat? oppure list di moduli con "slides"?
        if data and isinstance(data[0], dict) and "slides" in data[0]:
            flat: list[dict[str, Any]] = []
            for module in data:
                flat.extend(module.get("slides", []))
            return flat
        return data
    if isinstance(data, dict):
        if "slides" in data:
            return list(data["slides"])
        # struttura {completed_modules: [...]}
        modules = data.get("completed_modules", [])
        flat = []
        for module in modules:
            flat.extend(module.get("slides", []))
        return flat
    return []


async def get_slides(course_id: str, pool: Any) -> list[dict[str, Any]]:
    """Ritorna l'array flat di slide del corso (deserializzato)."""
    cid = _parse_course_id(course_id)
    row = await pool.fetchrow(
        "SELECT slide_contents_json FROM courses WHERE id = $1", cid
    )
    if row is None:
        raise LookupError("course not found")
    return _deserialize_slides(row["slide_contents_json"])


async def get_slide_by_idx(course_id: str, idx: int, pool: Any) -> dict[str, Any]:
    """Ritorna la singola slide con ``index == idx``."""
    slides = await get_slides(course_id, pool)
    for s in slides:
        if s.get("index") == idx:
            return s
    raise LookupError(f"slide index {idx} not found")


async def update_slide(
    course_id: str, idx: int, patch: dict[str, Any], pool: Any
) -> dict[str, Any]:
    """Aggiorna i campi specificati nella slide ``idx``, ri-valida via Pydantic
    strict (FASE 1), persiste l'intero array, marca il corso ``dirty=true``.

    Solleva ``ValueError`` se la slide aggiornata viola i constraints
    (il caller lo traduce in HTTP 422).
    """
    cid = _parse_course_id(course_id)
    slides = await get_slides(course_id, pool)
    target_pos = next((i for i, s in enumerate(slides) if s.get("index") == idx), None)
    if target_pos is None:
        raise LookupError(f"slide index {idx} not found")

    merged = {**slides[target_pos], **patch}
    # Ri-validazione strict: solleva ValidationError → ValueError leggibile
    validated = SlideContent(**merged).model_dump()
    slides[target_pos] = validated

    await pool.execute(
        "UPDATE courses SET slide_contents_json = $1, dirty = true WHERE id = $2",
        json.dumps(slides),
        cid,
    )
    logger.info("studio_slide_updated", course_id=course_id, slide_idx=idx,
                fields=list(patch.keys()))
    return validated


async def set_slide_image(
    course_id: str, idx: int, image_patch: dict[str, Any], pool: Any
) -> dict[str, Any]:
    """Aggiorna il sub-doc ``image`` della slide ``idx`` + dirty=true."""
    slide = await get_slide_by_idx(course_id, idx, pool)
    new_image = {**slide.get("image", {}), **image_patch}
    return await update_slide(course_id, idx, {"image": new_image}, pool)


async def regenerate_slide(
    course_id: str, idx: int, instruction: str, pool: Any
) -> dict[str, Any]:
    """Rigenera UNA slide via LLM secondo l'istruzione utente (FASE 11).

    Costruisce un prompt mirato che fornisce la slide corrente + l'istruzione,
    chiede all'LLM di riscriverla mantenendo slide_type, source_chunk_ids
    (provenance) e index. Ri-valida strict (FASE 1) e persiste.
    """
    from app.agents.content_agent import parse_slides_json
    from app.services.ingestion_service import call_llm

    current = await get_slide_by_idx(course_id, idx, pool)

    system = (
        "Sei un esperto di formazione sulla sicurezza sul lavoro. Riscrivi UNA "
        "slide secondo l'istruzione dell'utente, mantenendo lo stesso slide_type, "
        "lo stesso index, gli stessi source_chunk_ids (provenance normativa). "
        "Rispetta i vincoli: title max 70 char, body max 6 bullet brevi, "
        "speaker_notes 75-90 parole. Per QUIZ: quiz_correct INTERO 0-3. "
        "Rispondi con un oggetto JSON con key 'slides' contenente UNA sola slide."
    )
    user_prompt = (
        f"SLIDE ATTUALE (JSON):\n{json.dumps(current, ensure_ascii=False)}\n\n"
        f"ISTRUZIONE UTENTE: {instruction}\n\n"
        f"Riscrivi la slide applicando l'istruzione. Mantieni index={idx}, "
        f"slide_type={current.get('slide_type')}, "
        f"source_chunk_ids={current.get('source_chunk_ids')}."
    )
    raw = await call_llm([{"role": "user", "content": user_prompt}], system)
    parsed = parse_slides_json(raw)
    if not parsed:
        raise ValueError("LLM non ha prodotto una slide valida")
    new_slide = parsed[0]
    # Forza invarianti (l'LLM potrebbe driftare)
    new_slide["index"] = idx
    new_slide["slide_type"] = current.get("slide_type")
    new_slide["source_chunk_ids"] = current.get("source_chunk_ids", [])

    # update_slide ri-valida strict + persiste + dirty=true
    return await update_slide(course_id, idx, new_slide, pool)
