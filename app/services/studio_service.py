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


async def get_slide_by_idx(
    course_id: str,
    idx: int,
    pool: Any,
    module_index: int | None = None,
) -> dict[str, Any]:
    """Ritorna la singola slide con ``index == idx``.

    F11 D-232 (2026-06-02): ``index`` e` module-relative (riparte da 0
    ad ogni modulo), quindi puo` duplicare tra moduli. Quando
    ``module_index`` e` fornito, match composito (univoco). Altrimenti
    fallback al match by-index (back-compat: ritorna la PRIMA slide).
    """
    slides = await get_slides(course_id, pool)
    for s in slides:
        if s.get("index") == idx and (
            module_index is None or s.get("module_index") == module_index
        ):
            return s
    raise LookupError(f"slide index {idx} (module {module_index}) not found")


async def update_slide(
    course_id: str,
    idx: int,
    patch: dict[str, Any],
    pool: Any,
    module_index: int | None = None,
) -> dict[str, Any]:
    """Aggiorna i campi specificati nella slide ``idx``, ri-valida via Pydantic
    strict (FASE 1), persiste l'intero array, marca il corso ``dirty=true``.

    F11 D-232: ``module_index`` opzionale per match composito (D-228).

    Solleva ``ValueError`` se la slide aggiornata viola i constraints
    (il caller lo traduce in HTTP 422).
    """
    cid = _parse_course_id(course_id)
    slides = await get_slides(course_id, pool)
    target_pos = next(
        (
            i
            for i, s in enumerate(slides)
            if s.get("index") == idx
            and (module_index is None or s.get("module_index") == module_index)
        ),
        None,
    )
    if target_pos is None:
        raise LookupError(
            f"slide index {idx} (module {module_index}) not found"
        )

    # FIX 2026-06-01 bug edit slide: il frontend invia `body: str` (single
    # multiline string), il backend SlideContent ha `bullets: list[str]`.
    # Senza conversione, body veniva ignorato silently nel merge e l'edit
    # Salva-modifiche nel Course Studio non aveva NESSUN effetto su bullets.
    if "body" in patch and patch["body"] is not None:
        body_str = patch.pop("body")
        # Split su newline + strip + drop empty. Frontend joina bullets con \n
        # nella GET response (vedi sotto), simmetrico qui per PATCH.
        bullets_from_body = [
            line.strip() for line in body_str.split("\n") if line.strip()
        ]
        # Solo override se non-empty (per evitare di azzerare bullets per errore)
        if bullets_from_body:
            patch["bullets"] = bullets_from_body
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
    course_id: str,
    idx: int,
    image_patch: dict[str, Any],
    pool: Any,
    module_index: int | None = None,
) -> dict[str, Any]:
    """Aggiorna il sub-doc ``image`` della slide ``idx`` + dirty=true.

    F11 D-232: ``module_index`` opzionale per match composito (D-228).
    """
    slide = await get_slide_by_idx(
        course_id, idx, pool, module_index=module_index
    )
    new_image = {**slide.get("image", {}), **image_patch}
    return await update_slide(
        course_id, idx, {"image": new_image}, pool, module_index=module_index
    )


# ─────────────────────────────────────────────────────────────────────────
# Slide management (FASE 6 — add / move / delete / duplicate)
#
# Tutte le slide vivono nell'array ``slide_contents_json``. Il PPTX finale è
# rigenerato DA quell'array via ProductionBuilder ad ogni rebuild, quindi
# manipolare l'array + reindex contiguo = PPTX corretto senza corruzione.
# L'invariante critico è: ``index`` 0..N-1 contiguo, ``module_index`` coerente.
# ─────────────────────────────────────────────────────────────────────────

# Tipi che l'operatore può aggiungere manualmente (i bookend MODULE_OPEN/CLOSE
# sono strutturali: gestiti dal pacing engine, non inseribili a mano).
_ADDABLE_TYPES = {
    "CONTENT_TEXT",
    "CONTENT_IMAGE",
    "DIAGRAM",
    "QUIZ",
    "CASE_STUDY",
    "RECAP",
}
_PROTECTED_TYPES = {"MODULE_OPEN", "MODULE_CLOSE"}


def _reindex(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ricompatta ``index`` a 0..N-1 nell'ordine corrente dell'array.

    ``module_index`` NON viene toccato (resta quello assegnato alle slide):
    serve a tenere i bookend coerenti col loro modulo. Restituisce la stessa
    lista (mutata in place) per comodità.
    """
    for new_idx, s in enumerate(slides):
        s["index"] = new_idx
    return slides


def _blank_slide(slide_type: str, module_index: int) -> dict[str, Any]:
    """Crea una slide vuota VALIDA del tipo dato (passa SlideContent strict).

    I placeholder rispettano i minimi di LAYOUT_CONSTRAINTS (es. CONTENT_TEXT
    richiede ≥4 bullet, notes ≥90 parole). L'operatore poi sostituisce il
    contenuto via l'editor. ``index`` viene assegnato dal reindex del caller.
    """
    notes = (
        "Questa slide è stata aggiunta manualmente. Sostituisci questo testo "
        "con la narrazione desiderata, descrivendo i contenuti della slide in "
        "modo chiaro e discorsivo per la voce. Ricordati di mantenere un tono "
        "professionale e adatto alla formazione sulla sicurezza sul lavoro, "
        "fornendo agli operatori indicazioni pratiche e comprensibili su come "
        "comportarsi correttamente nelle situazioni descritte in questa slide."
    )
    base: dict[str, Any] = {
        "index": 0,
        "module_index": module_index,
        "slide_type": slide_type,
        "title": "Nuova slide (da completare)",
        "bullets": [],
        "sezioni": [],
        "speaker_notes": notes,
        "normative_ref": "",
        "source_chunk_ids": [],
        "image": {"strategy": "none"},
        "quiz_options": None,
        "quiz_correct": None,
    }

    placeholder_bullet = "Punto da completare con il contenuto della slide"
    if slide_type in ("CONTENT_TEXT",):
        base["bullets"] = [placeholder_bullet] * 4
    elif slide_type == "CONTENT_IMAGE":
        base["bullets"] = [placeholder_bullet] * 3
        base["image"] = {"strategy": "web_search", "query": "sicurezza sul lavoro"}
    elif slide_type == "DIAGRAM":
        base["bullets"] = ["Didascalia del diagramma da completare"]
        base["image"] = {"strategy": "diagram"}
    elif slide_type == "RECAP":
        base["bullets"] = ["Concetto chiave da completare"] * 5
    elif slide_type == "CASE_STUDY":
        base["sezioni"] = [
            "Situazione: descrivi il contesto del caso da completare.",
            "Azione: descrivi l'intervento corretto da completare.",
            "Risultato: descrivi l'esito atteso da completare.",
        ]
    elif slide_type == "QUIZ":
        base["title"] = "Domanda del quiz (da completare)?"
        base["quiz_options"] = [
            "Prima opzione",
            "Seconda opzione",
            "Terza opzione",
            "Quarta opzione",
        ]
        base["quiz_correct"] = 0
        base["speaker_notes"] = (
            "Spiega perché la risposta corretta è quella indicata e perché le "
            "altre opzioni non sono adeguate, in modo chiaro per l'operatore."
        )

    # Validazione strict: se il template viola i constraint, solleva subito
    # (errore di programmazione, non input utente).
    return SlideContent(**base).model_dump()


async def add_slide(
    course_id: str, after_idx: int, slide_type: str, pool: Any
) -> list[dict[str, Any]]:
    """Inserisce una nuova slide vuota del tipo dato DOPO ``after_idx``.

    Eredita ``module_index`` dalla slide ``after_idx`` (la nuova slide entra
    nello stesso modulo). Reindex + persist + dirty=true. Ritorna l'array
    aggiornato.
    """
    if slide_type not in _ADDABLE_TYPES:
        raise ValueError(
            f"slide_type '{slide_type}' non aggiungibile manualmente "
            f"(consentiti: {sorted(_ADDABLE_TYPES)})"
        )
    cid = _parse_course_id(course_id)
    slides = await get_slides(course_id, pool)
    pos = next((i for i, s in enumerate(slides) if s.get("index") == after_idx), None)
    if pos is None:
        raise LookupError(f"slide index {after_idx} not found")

    module_index = int(slides[pos].get("module_index", 0))
    new_slide = _blank_slide(slide_type, module_index)
    slides.insert(pos + 1, new_slide)
    _reindex(slides)

    await pool.execute(
        "UPDATE courses SET slide_contents_json = $1, dirty = true WHERE id = $2",
        json.dumps(slides),
        cid,
    )
    logger.info("studio_slide_added", course_id=course_id, after_idx=after_idx,
                slide_type=slide_type, total=len(slides))
    return slides


async def move_slide(
    course_id: str, idx: int, direction: str, pool: Any
) -> list[dict[str, Any]]:
    """Sposta la slide ``idx`` su/giù scambiandola con l'adiacente.

    Vincolo: lo scambio è permesso solo se la slide adiacente è nello STESSO
    modulo (``module_index``), per non rompere i bookend MODULE_OPEN/CLOSE.
    Reindex + persist + dirty=true.
    """
    if direction not in ("up", "down"):
        raise ValueError("direction deve essere 'up' o 'down'")
    cid = _parse_course_id(course_id)
    slides = await get_slides(course_id, pool)
    pos = next((i for i, s in enumerate(slides) if s.get("index") == idx), None)
    if pos is None:
        raise LookupError(f"slide index {idx} not found")

    swap = pos - 1 if direction == "up" else pos + 1
    if swap < 0 or swap >= len(slides):
        raise ValueError("impossibile spostare oltre i bordi del corso")

    cur = slides[pos]
    other = slides[swap]
    if cur.get("module_index") != other.get("module_index"):
        raise ValueError(
            "spostamento bloccato: la slide adiacente appartiene a un altro "
            "modulo (i confini dei moduli sono protetti)"
        )
    if cur.get("slide_type") in _PROTECTED_TYPES or other.get("slide_type") in _PROTECTED_TYPES:
        raise ValueError(
            "spostamento bloccato: non si possono spostare le slide di "
            "apertura/chiusura modulo"
        )

    slides[pos], slides[swap] = slides[swap], slides[pos]
    _reindex(slides)

    await pool.execute(
        "UPDATE courses SET slide_contents_json = $1, dirty = true WHERE id = $2",
        json.dumps(slides),
        cid,
    )
    logger.info("studio_slide_moved", course_id=course_id, idx=idx, direction=direction)
    return slides


async def delete_slide(course_id: str, idx: int, pool: Any) -> list[dict[str, Any]]:
    """Elimina la slide ``idx`` (vietato sui bookend modulo). Reindex + persist."""
    cid = _parse_course_id(course_id)
    slides = await get_slides(course_id, pool)
    pos = next((i for i, s in enumerate(slides) if s.get("index") == idx), None)
    if pos is None:
        raise LookupError(f"slide index {idx} not found")
    if slides[pos].get("slide_type") in _PROTECTED_TYPES:
        raise ValueError(
            "eliminazione bloccata: non si possono eliminare le slide di "
            "apertura/chiusura modulo (romperebbero la struttura del modulo)"
        )
    if len(slides) <= 1:
        raise ValueError("impossibile eliminare l'unica slide del corso")

    slides.pop(pos)
    _reindex(slides)

    await pool.execute(
        "UPDATE courses SET slide_contents_json = $1, dirty = true WHERE id = $2",
        json.dumps(slides),
        cid,
    )
    logger.info("studio_slide_deleted", course_id=course_id, idx=idx, total=len(slides))
    return slides


async def duplicate_slide(course_id: str, idx: int, pool: Any) -> list[dict[str, Any]]:
    """Duplica la slide ``idx`` inserendo la copia subito dopo. Reindex + persist."""
    cid = _parse_course_id(course_id)
    slides = await get_slides(course_id, pool)
    pos = next((i for i, s in enumerate(slides) if s.get("index") == idx), None)
    if pos is None:
        raise LookupError(f"slide index {idx} not found")

    clone = json.loads(json.dumps(slides[pos]))  # deep copy
    title = clone.get("title", "")
    clone["title"] = (title + " (copia)")[:200]
    slides.insert(pos + 1, clone)
    _reindex(slides)

    await pool.execute(
        "UPDATE courses SET slide_contents_json = $1, dirty = true WHERE id = $2",
        json.dumps(slides),
        cid,
    )
    logger.info("studio_slide_duplicated", course_id=course_id, idx=idx, total=len(slides))
    return slides


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
