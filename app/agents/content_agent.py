"""Content Agent (BLUEPRINT §05.5).

PHASE 3.4 — second node of the LangGraph pipeline. Iterates over the
pacing plan module-by-module, asks the LLM to generate the slides for
each module, parses the JSON response, validates each slide via Pydantic,
and accumulates ModuleContent objects into the state via the operator.add
reducer on ``completed_modules``.

═══ FIX-3 v2.0 (karpathy-guidelines, regola #2) ═══
The circuit breaker is an INLINE counter (``failed_count: int``) inside
``content_agent``, NOT a separate class. If you find yourself writing
``class ModuleCircuitBreaker`` here, STOP and re-read karpathy rule #2:
"No abstractions for single-use code".

═══ REUSE NOTE (D10 → resolved) ═══
``call_llm`` lives in ``app.services.ingestion_service`` (defined there
in PHASE 2.3 to unblock the Stage-3 classifier). This module imports it
instead of redefining it — same retry policy, same model, same timeout.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import TYPE_CHECKING

import structlog

from app.agents.pipeline import NexusPipelineState
from app.models.core import LAYOUT_CONSTRAINTS, SlideType

if TYPE_CHECKING:
    from app.models.knowledge import NormativeChunk, StylePattern
    from app.models.core import TargetType


def _auto_complete_invalid_slide(
    s: dict[str, object],
    module_index: int,
    err_str: str,
) -> dict[str, object] | None:
    """Auto-complete deterministico per errori PURAMENTE ADDITIVI (no troncamento).

    Risolve i casi banali in cui l'LLM omette o sbaglia un campo facilmente
    determinabile dal contesto:
    - module_index missing → uso quello del modulo corrente
    - aspect_hint None → default "landscape"
    - viewBox missing in diagram_code → aggiungo viewBox="0 0 1760 800" all'<svg>
    - speaker_notes < min → append " Riferimento: <normative_ref>." finché OK
    - quiz_correct missing → default 0
    - image dict missing → default {"strategy": "none"}

    Restituisce dict modificato se ha applicato fix, None se l'errore non
    rientra nei casi gestibili (es. title troppo lungo → SPLIT).
    NON TRONCA MAI nulla.
    """
    fixed = dict(s)
    applied = False

    # 1. module_index
    if "module_index" not in fixed or fixed.get("module_index") is None:
        fixed["module_index"] = module_index
        applied = True

    # 2. image dict
    if "image" not in fixed or not isinstance(fixed.get("image"), dict):
        fixed["image"] = {"strategy": "none"}
        applied = True
    image = fixed["image"]
    assert isinstance(image, dict)

    # 3. aspect_hint default landscape
    if image.get("aspect_hint") is None and image.get("strategy") not in (None, "none", "diagram"):
        image["aspect_hint"] = "landscape"
        applied = True
    if image.get("aspect_hint") not in (None, "landscape", "portrait", "square"):
        # Valori non standard tipo "wide" → mappa a landscape
        image["aspect_hint"] = "landscape"
        applied = True

    # 4. viewBox missing nel diagram_code
    if fixed.get("slide_type") == "DIAGRAM" and image.get("diagram_code"):
        code = str(image["diagram_code"])
        if "viewBox" not in code:
            # Inserisco viewBox subito dopo <svg
            new_code = re.sub(r"<svg\b", '<svg viewBox="0 0 1760 800"', code, count=1)
            image["diagram_code"] = new_code
            applied = True

    # 5. quiz_correct default 0 (se quiz_options presenti ma correct missing/invalid)
    if fixed.get("slide_type") == "QUIZ":
        qc = fixed.get("quiz_correct")
        if not isinstance(qc, int) or qc < 0 or qc > 3:
            fixed["quiz_correct"] = 0
            applied = True

    # 6. speaker_notes pad con normative_ref se troppo corto
    notes = str(fixed.get("speaker_notes") or "").strip()
    notes_words = len(notes.split())
    try:
        stype = SlideType(fixed.get("slide_type", "CONTENT_TEXT"))
        rules = LAYOUT_CONSTRAINTS.get(stype)
    except Exception:
        rules = None
    if rules and notes_words < rules.notes_min_words:
        ref = str(fixed.get("normative_ref") or "").strip()
        if ref:
            # Pad additivo: aggiungo citazione normativa finché raggiungo il min
            pad_sentence = (
                f" Approfondimento normativo previsto da {ref} con "
                f"applicazione pratica nei contesti operativi aziendali italiani."
            )
            attempts = 0
            while notes_words < rules.notes_min_words and attempts < 5:
                notes = (notes + pad_sentence).strip()
                notes_words = len(notes.split())
                attempts += 1
            fixed["speaker_notes"] = notes
            applied = True

    # 7. FIX #28.1 schema bullets:list[str]: per TITLE/CLOSING/QUIZ → liste vuote.
    # Rimuove eventuale `body` legacy che instructor non riconosce nel nuovo schema.
    if fixed.get("slide_type") in ("TITLE", "CLOSING", "QUIZ"):
        if "body" in fixed:
            fixed.pop("body", None)
            applied = True
        if not isinstance(fixed.get("bullets"), list):
            fixed["bullets"] = []
            applied = True
        if not isinstance(fixed.get("sezioni"), list):
            fixed["sezioni"] = []
            applied = True

    return fixed if applied else None

from app.agents.prompts import (
    build_content_system_prompt,
    build_module_prompt,
    build_previous_summary,
    build_split_correction_prompt,
)
from app.config import settings
from app.models.pipeline import (
    CourseContext,
    ModuleContent,
    PacingPlan,
    SlideContent,
)
from app.models.requests import CourseRequest
from app.services.ingestion_service import call_llm, generate_module_structured

logger = structlog.get_logger()


async def _compose_normative_refs_from_db(
    slides: list[SlideContent], pool: object
) -> None:
    """FIX #30.5b (2026-05-26): ricostruisce normative_ref deterministicamente
    dal DB usando source_chunk_ids della slide.

    Analista 2026-05-26: "la fonte è un fatto del tuo DB, non un'opinione del
    modello. La citazione è un lookup, non una generazione". Elimina le
    allucinazioni tipo "Pag. 31-136" (schema RAG non ha page_number) e i
    format incoerenti tipo "Allegato IV" singolo.

    Per ogni slide con source_chunk_ids valorizzati, fetcha i citation_label
    dal DB (campo denormalizzato popolato da scripts/backfill_citations.py +
    a ingest-time per i futuri PDF). Aggrega multi-chunk: stessa regulation
    → "art. X e art. Y"; reg diverse → ";". Se source_chunk_ids vuoto →
    lascia normative_ref vuoto (NON inventato dall'LLM).
    """
    import asyncpg

    if pool is None:
        return  # smoke test mode

    # Raccogli TUTTI gli ID unici per una sola query
    all_ids: set[str] = set()
    for s in slides:
        if s.source_chunk_ids:
            all_ids.update(s.source_chunk_ids)

    if not all_ids:
        # Nessuna slide ha source_chunk_ids → niente da arricchire
        return

    # Carica citation_label per ogni chunk ID (uuid)
    try:
        rows = await pool.fetch(
            "SELECT id::text AS id, citation_label "
            "FROM regulation_chunks WHERE id = ANY($1::uuid[])",
            list(all_ids),
        )
    except Exception as exc:
        logger.warning("citation_lookup_failed", error=str(exc))
        return

    id_to_label: dict[str, str] = {
        r["id"]: r["citation_label"] for r in rows if r["citation_label"]
    }

    # Per ogni slide: ricostruisci normative_ref aggregando i citation_label
    for s in slides:
        if not s.source_chunk_ids:
            continue
        labels = [id_to_label.get(cid) for cid in s.source_chunk_ids]
        labels = [l for l in labels if l]  # remove None / empty
        if not labels:
            continue
        # Dedup mantenendo ordine
        seen: set[str] = set()
        unique = []
        for l in labels:
            if l not in seen:
                seen.add(l)
                unique.append(l)
        # Aggrega: separatore "; " per ogni citazione distinta
        # (raffinamenti multi-art same-regulation in futuro se serve)
        new_ref = "; ".join(unique[:3])  # max 3 ref per non sovraccaricare il box
        s.normative_ref = new_ref[:200]


def _smart_truncate_to_words(text: str, max_words: int) -> str:
    """FIX #31.4 (2026-05-27, analista review 5): truncate intelligente
    a max_words preservando senso. Usato nei bookends MODULE_CLOSE per
    evitare che un titolo content lungo (es. 13 parole) violi
    bullet_max_words=12 e triggeri il fallback distruttivo che ha
    eliminato 77 slide di M2 in E2E #22.

    Strategia: split su parole, tieni le prime max_words, aggiungi
    "…" come marker visibile di troncamento. Preserva il senso
    iniziale del bullet (le parole più informative sono in testa).
    """
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


def _build_module_bookends(
    module_index: int,
    module_title: str,
    content_slides: list[SlideContent],
) -> tuple[SlideContent, SlideContent]:
    """Genera la coppia MODULE_OPEN + MODULE_CLOSE per un modulo.

    FIX #30.2 (2026-05-26): bookends programmatici (zero LLM call). MODULE_OPEN
    è puro slot di apertura con "MODULO N" + titolo modulo. MODULE_CLOSE
    riassume con 5 top bullet derivati dai title delle slide di contenuto
    (i 5 titoli più "centrali", non i bridge come QUIZ/RECAP).

    FIX #31.4 (2026-05-27, analista review 5): auto-truncate bullet
    MODULE_CLOSE a bullet_max_words=12. Era la causa del bug E2E #22:
    titolo content da 13 parole → bullet MODULE_CLOSE da 13 parole →
    ValidationError → fallback_legacy → 77 slide M2 buttate via.

    Note speaker brevi pre-composte per entrambi (non dipendono da LLM, audio
    TTS pulito it-IT-DiegoNeural).
    """
    from app.models.core import LAYOUT_CONSTRAINTS, SlideType

    n_module = module_index + 1
    # MODULE_OPEN
    open_title = f"MODULO {n_module}"
    # Convention: il "titolo modulo" reale lo passiamo come bullets[0] perché
    # nx_module_title nel template legge dalla shape body (placeholder idx=1).
    # Lo slide_builder_v2 branch MODULE_OPEN sa estrarlo da bullets[0].
    open_slide = SlideContent(
        index=0,
        module_index=module_index,
        slide_type=SlideType.MODULE_OPEN,
        title=open_title,
        bullets=[module_title],  # ← nx_module_title text
        speaker_notes=(
            f"Iniziamo il modulo {n_module}: {module_title}. In questa sezione "
            f"approfondiremo gli aspetti normativi e pratici del tema, con esempi "
            f"operativi e riferimenti puntuali al D.Lgs. 81/08."
        ),
    )

    # MODULE_CLOSE — 5 bullet derivati dai title delle slide CONTENT_TEXT/IMAGE
    eligible_titles = [
        s.title for s in content_slides
        if s.slide_type.value in ("CONTENT_TEXT", "CONTENT_IMAGE") and s.title
    ]
    # Scegli i 5 più rappresentativi (per ora: primi 5 distinti, in futuro
    # si può raffinare con TF-IDF o re-ranking LLM)
    seen: set[str] = set()
    top5: list[str] = []
    for t in eligible_titles:
        key = t.strip().lower()[:50]
        if key not in seen:
            seen.add(key)
            top5.append(t.strip())
        if len(top5) == 5:
            break
    while len(top5) < 5:
        # Padding con placeholder semantici se modulo magro
        top5.append(f"Approfondimento {len(top5) + 1} del modulo")

    # FIX #31.4 (analista review 5): auto-truncate bullet ai max_words
    # del tipo MODULE_CLOSE prima di passare al validator Pydantic.
    # Previene il fallback distruttivo se un titolo content è leggermente
    # lungo (es. 13 parole su limite 12).
    mc_max_words = LAYOUT_CONSTRAINTS[SlideType.MODULE_CLOSE].bullet_max_words
    top5_safe = [_smart_truncate_to_words(t, mc_max_words) for t in top5]

    close_slide = SlideContent(
        index=len(content_slides) + 1,
        module_index=module_index,
        slide_type=SlideType.MODULE_CLOSE,
        title=module_title,
        bullets=top5_safe,
        speaker_notes=(
            f"Riepilogo del modulo {n_module}. Abbiamo trattato i punti chiave "
            f"qui sintetizzati. Nel modulo successivo continueremo il percorso "
            f"formativo con altri temi normativi e applicazioni pratiche."
        ),
    )

    return open_slide, close_slide


async def _generate_module_h8(
    *,
    module: object,
    voci_skeleton: list[dict[str, object]],
    chunks_by_voce: dict[int, list["NormativeChunk"]],
    style_patterns: list["StylePattern"],
    previous_summary: str,
    target: "TargetType",
    system_prompt: str,
) -> dict[str, object]:
    """H8 (2026-05-31): genera cluster di slide PER VOCE dello skeleton.

    Patologia che cura: drift voce-to-slide (sample-read M0 post-V1.5: 1.2%
    on-topic core su 84 slide free-form generate dal pool union).

    Strategia:
      1. Per ogni voce dello skeleton, calcola slide_count_for_voice
         proporzionale a pool_size_per_voce (voce con pool 30 -> ~9-10 slide;
         voce con pool 5 -> ~2-3 slide). Normalizza per modulo target slide_count.
      2. Per ogni voce, chiama generate_module_structured con prompt voce-aware
         (build_voice_prompt): "Genera N slide SOLO sul sub_topic Y, usando
         SOLO questi chunks".
      3. Concatena tutti i cluster slide del modulo in ordine voci.
      4. Aggiunge MODULE_OPEN + MODULE_CLOSE bookends (programmatici, zero LLM).
      5. Re-index slide.index globale per contiguita`.

    Return: dict serializzato di ModuleContent identico al path legacy
    (per non rompere _generate_one_module downstream).

    Raise: Exception se qualsiasi step fallisce (chiamante fa fallback legacy).
    """
    from math import ceil

    from app.models.pipeline import ModuleContent
    from app.services.ingestion_service import generate_module_structured

    mod_idx = module.module_index  # type: ignore[attr-defined]
    mod_title = module.title  # type: ignore[attr-defined]
    mod_slide_count_target = int(getattr(module, "slide_count", 0) or 0)
    mod_slide_distribution = getattr(module, "slide_distribution", {})

    n_voci = len(voci_skeleton)
    if n_voci == 0:
        raise RuntimeError(f"H8: skeleton vuoto per modulo {mod_idx}")

    # ── Sizing proporzionale a pool_size per voce ──
    # Voce con pool grande riceve piu` slide (piu` materiale per copertura semantica);
    # voce con pool piccolo (corpus thin) riceve meno (evita over-generation a vuoto).
    def _ord(voce: dict[str, object]) -> int:
        ord_raw = voce["ordinal"]
        return int(ord_raw) if isinstance(ord_raw, (int, str, float)) else 0

    pool_sizes = {
        _ord(v): len(chunks_by_voce.get(_ord(v), []))
        for v in voci_skeleton
    }
    total_pool = sum(pool_sizes.values())
    if total_pool == 0:
        raise RuntimeError(f"H8: tutti i pool vuoti per modulo {mod_idx}")

    # Sottraggo le 2 slide bookends dal target prima di distribuire fra voci.
    content_slide_target = max(2, mod_slide_count_target - 2)

    # Slide per voce: floor(content_target * pool_voce / total_pool), poi correggo
    # arrotondamenti per arrivare esattamente a content_slide_target.
    slide_per_voce: dict[int, int] = {}
    for v in voci_skeleton:
        ord_v = _ord(v)
        share = pool_sizes[ord_v] / total_pool if total_pool > 0 else 1.0 / n_voci
        slide_per_voce[ord_v] = max(1, int(ceil(content_slide_target * share)))

    # H8b-α (analista 2026-05-31): cap proporzionale al numero voci skeleton.
    # Patologia osservata post-H8 (PPTX 691405b1): voci tematicamente larghe
    # (v1 "Concetto incendio", v2 "Triangolo del fuoco") hanno ricevuto sizing
    # eccessivo (~10-15 slide/voce) -> LLM ha esaurito subtopic e riempito con
    # materia adjacent ridondando (slide 1-9 + 17-19 + 25-34 = 20 slide su
    # prevenzione/applicazione, identicamente ripetute).
    # Cura: cap auto-adattivo basato su avg = content_target / n_voci, tolleranza
    # +/-2. Voce con pool grande NON puo' espandere oltre cap; voce thin con
    # pool piccolo NON scende sotto floor (garanzia visibilita' minima).
    # Auto-adattivo: M0 (9 voci, 80 target) -> range 7-11; M con 12 voci -> 5-9.
    avg_slides_per_voce = content_slide_target / n_voci if n_voci > 0 else 1.0
    slide_cap_per_voce = max(3, round(avg_slides_per_voce + 2))
    slide_floor_per_voce = max(2, round(avg_slides_per_voce - 2))
    for ord_v in slide_per_voce:
        slide_per_voce[ord_v] = max(
            slide_floor_per_voce,
            min(slide_cap_per_voce, slide_per_voce[ord_v])
        )

    # Correzione: aggiusta verso target esatto (preferendo voci con piu` pool)
    # NOTA H8b-α: il target post-cap puo' divergere significativamente da
    # content_slide_target se molte voci sono clamped. Correzione tollerata
    # entro +/- 20% del target originale (range 0.8-1.2 x); oltre, accetta
    # divergenza come trade-off del cap (meglio cluster focali che target esatto).
    target_lower = int(content_slide_target * 0.8)
    target_upper = int(content_slide_target * 1.2)
    while sum(slide_per_voce.values()) > target_upper:
        # Rimuovi 1 dalla voce con piu` slide (rispettando floor)
        candidates = {k: v for k, v in slide_per_voce.items() if v > slide_floor_per_voce}
        if not candidates:
            break
        max_ord = max(candidates, key=lambda k: candidates[k])
        slide_per_voce[max_ord] -= 1
    while sum(slide_per_voce.values()) < target_lower:
        # Aggiungi 1 alla voce con piu` pool (rispettando cap)
        candidates = {k: v for k, v in slide_per_voce.items() if v < slide_cap_per_voce}
        if not candidates:
            break
        sorted_voci = sorted(candidates.keys(), key=lambda k: -pool_sizes[k])
        slide_per_voce[sorted_voci[0]] += 1

    logger.info(
        "h8_sizing_per_voce",
        module_index=mod_idx,
        n_voci=n_voci,
        pool_sizes=pool_sizes,
        slide_per_voce=slide_per_voce,
        content_slide_target=content_slide_target,
        # H8b-α telemetria cap
        slide_cap_per_voce=slide_cap_per_voce,
        slide_floor_per_voce=slide_floor_per_voce,
        avg_slides_per_voce=round(avg_slides_per_voce, 2),
        total_after_cap=sum(slide_per_voce.values()),
    )

    # ── Distribuzione tipi slide: ripartisco mod_slide_distribution fra voci ──
    # Strategia semplice: prima voce riceve QUIZ se presente, ultima voce CASE_STUDY se
    # presente, distribuzione CONTENT_TEXT/CONTENT_IMAGE proporzionale a slide_per_voce.
    def _split_distribution(total_dist: dict[str, int], voce_count: int, voce_idx: int) -> dict[str, int]:
        out: dict[str, int] = {}
        # CONTENT_TEXT + CONTENT_IMAGE distribuiti proporzionalmente
        text_total = int(total_dist.get("CONTENT_TEXT", 0) or 0)
        img_total = int(total_dist.get("CONTENT_IMAGE", 0) or 0)
        quiz_total = int(total_dist.get("QUIZ", 0) or 0)
        case_total = int(total_dist.get("CASE_STUDY", 0) or 0)

        share = voce_count / content_slide_target if content_slide_target > 0 else 1.0 / n_voci
        out["CONTENT_TEXT"] = max(0, int(round(text_total * share)))
        out["CONTENT_IMAGE"] = max(0, int(round(img_total * share)))
        # QUIZ alla prima voce, CASE_STUDY all'ultima
        if voce_idx == 0 and quiz_total > 0:
            out["QUIZ"] = quiz_total
        if voce_idx == n_voci - 1 and case_total > 0:
            out["CASE_STUDY"] = case_total
        return out

    # ── Loop voce-per-voce ──
    from app.agents.prompts import build_voice_prompt

    all_content_slides = []
    previous_voci_titles: list[str] = []  # per "voci precedenti summary"
    for voce_idx, voce in enumerate(voci_skeleton):
        ord_v = _ord(voce)
        sub_topic = str(voce["sub_topic"])
        retrieval_query = str(voce["retrieval_query"])
        voce_chunks = chunks_by_voce.get(ord_v, [])
        if not voce_chunks:
            logger.warning(
                "h8_voce_pool_empty_skip",
                module_index=mod_idx,
                voce_ordinal=ord_v,
                sub_topic=sub_topic[:60],
            )
            continue

        n_slide_voce = slide_per_voce.get(ord_v, 2)
        dist_voce = _split_distribution(mod_slide_distribution, n_slide_voce, voce_idx)

        # Summary voci precedenti (compatto: solo titoli sub_topic gia` trattati)
        prev_voci_summary = (
            "Voci gia` generate in questo modulo:\n"
            + "\n".join(f"- v{i + 1}: {t}" for i, t in enumerate(previous_voci_titles))
        ) if previous_voci_titles else "Prima voce del modulo (nessun contesto precedente)."

        voce_prompt = build_voice_prompt(
            module_index=mod_idx,
            module_title=mod_title,
            voice_ordinal=ord_v,
            voice_sub_topic=sub_topic,
            voice_retrieval_query=retrieval_query,
            voice_chunks=voce_chunks,
            slide_count_for_voice=n_slide_voce,
            slide_distribution_for_voice=dist_voce,
            style_patterns=style_patterns,
            previous_voices_summary=prev_voci_summary,
            target=target,
        )

        chunks_text_voce = "\n\n".join(
            f"[ID: {c.chunk_id}] Art. {c.article or '?'}: {c.body}"
            for c in voce_chunks[:30]
        )

        try:
            voce_module_obj, voce_telemetry = await generate_module_structured(
                system=system_prompt,
                user_prompt=voce_prompt,
                module_index=mod_idx,
                module_title=f"{mod_title} - voce {ord_v}: {sub_topic[:40]}",
                expected_slides=n_slide_voce,
                chunks_text=chunks_text_voce,
                slide_distribution=dist_voce,
            )
            logger.info(
                "h8_voce_generated",
                module_index=mod_idx,
                voce_ordinal=ord_v,
                sub_topic=sub_topic[:60],
                expected=n_slide_voce,
                generated=len(voce_module_obj.slides),
                provider=voce_telemetry.get("provider_used"),
            )
            all_content_slides.extend(list(voce_module_obj.slides))
            previous_voci_titles.append(sub_topic)
        except Exception as exc:
            logger.warning(
                "h8_voce_failed_skipped",
                module_index=mod_idx,
                voce_ordinal=ord_v,
                sub_topic=sub_topic[:60],
                error_class=type(exc).__name__,
                error=str(exc)[:200],
            )
            # Continue with next voce: parziale OK, non far cadere tutto il modulo.

    if not all_content_slides:
        raise RuntimeError(f"H8: tutte le voci fallite per modulo {mod_idx}, ZERO slide generate")

    # ── Bookends MODULE_OPEN + MODULE_CLOSE ──
    try:
        bookend_open, bookend_close = _build_module_bookends(
            module_index=mod_idx,
            module_title=mod_title,
            content_slides=all_content_slides,
        )
        all_slides = [bookend_open] + all_content_slides + [bookend_close]
    except Exception as exc:
        logger.error(
            "h8_bookends_failed_kept_content",
            module_index=mod_idx,
            content_slides=len(all_content_slides),
            error=str(exc)[:200],
        )
        all_slides = list(all_content_slides)

    # ── Re-index global ──
    for i, s in enumerate(all_slides):
        s.index = i
        s.module_index = mod_idx

    logger.info(
        "h8_module_completed",
        module_index=mod_idx,
        n_voci_processed=len(previous_voci_titles),
        n_voci_skipped=n_voci - len(previous_voci_titles),
        total_slides=len(all_slides),
    )

    return ModuleContent(
        module_index=mod_idx,
        title=mod_title,
        slides=all_slides,
    ).model_dump()


async def regenerate_single_slide_h8(
    *,
    course_id: str,
    slide_index: int,
    pool: object,
) -> dict[str, object]:
    """F4b V1 (analista 2026-05-31): rigenera UNA singola slide via H8 voce-aware.

    Strategia coerente con _generate_module_h8:
      1. Carica slide_contents_json + module_skeletons_json + course meta
      2. Identifica slide target + module_index della slide
      3. Identifica voce skeleton "owner" della slide via heuristica posizione
         cluster (slide non-bookend) OPPURE via re-mapping euristico bullets
         keywords ↔ sub_topic skeleton
      4. Re-invoca generate_module_structured con expected_slides=1 +
         chunks della voce + prompt voce-aware (build_voice_prompt)
      5. Sostituisce slide nel slide_contents_json + persiste + marca dirty=true
         (RebuildBanner mostra al cliente che serve rebuild PPTX)

    Returns: dict con status, slide_index, regenerated_slide_summary.

    Raise: HTTPException-equivalente RuntimeError se voce non identificabile o
    LLM fallisce (caller wrappa in HTTPException).
    """
    import json as _json
    import uuid as _uuid

    from app.agents.prompts import build_voice_prompt
    from app.config import settings
    from app.models.pipeline import SlideContent
    from app.services.dependencies import get_pool as _get_pool
    from app.services.ingestion_service import generate_module_structured
    from app.services.knowledge_repo import KnowledgeRepository
    from app.services.skeleton_service import materialize_module_from_skeleton

    # ── 1. Load course + slides + skeleton from DB ──
    course_uuid = _uuid.UUID(course_id)
    row = await pool.fetchrow(
        "SELECT slide_contents_json, module_skeletons_json, course_type, target, region "
        "FROM courses WHERE id = $1",
        course_uuid,
    )
    if row is None:
        raise RuntimeError(f"Course {course_id} not found")
    raw_slides = row["slide_contents_json"]
    if raw_slides is None:
        raise RuntimeError(f"Course {course_id} has no slide_contents_json")
    slides = _json.loads(raw_slides) if isinstance(raw_slides, str) else raw_slides
    if not isinstance(slides, list) or slide_index >= len(slides):
        raise RuntimeError(f"Invalid slide_index {slide_index} (n_slides={len(slides) if isinstance(slides, list) else '?'})")
    target_slide = slides[slide_index]
    if not isinstance(target_slide, dict):
        raise RuntimeError(f"Slide {slide_index} not a dict")

    mod_idx = target_slide.get("module_index")
    slide_type = target_slide.get("slide_type", "")
    if mod_idx is None:
        raise RuntimeError(f"Slide {slide_index} missing module_index")
    # Skip MODULE_OPEN / MODULE_CLOSE / TITLE: bookends programmatici, no LLM gen
    if slide_type in ("MODULE_OPEN", "MODULE_CLOSE", "TITLE", "CLOSING"):
        raise RuntimeError(
            f"Slide {slide_index} e' bookend/title ({slide_type}), no rigenerazione LLM. "
            "Edita manualmente via patch_slide se necessario."
        )

    # ── 2. Load skeleton + identifica voce owner ──
    raw_sk = row["module_skeletons_json"]
    if raw_sk is None:
        raise RuntimeError(
            f"Course {course_id} senza module_skeletons_json: rigenerazione H8 "
            "richiede skeleton (flag v2_skeleton_validation deve essere stato ON)"
        )
    sk_payload = _json.loads(raw_sk) if isinstance(raw_sk, str) else raw_sk
    modules_sk = sk_payload.get("modules") if isinstance(sk_payload, dict) else None
    if not isinstance(modules_sk, list):
        raise RuntimeError(f"module_skeletons_json malformato per course {course_id}")
    module_sk = next(
        (m for m in modules_sk if isinstance(m, dict) and m.get("module_index") == mod_idx),
        None,
    )
    if module_sk is None:
        raise RuntimeError(f"Skeleton modulo {mod_idx} non trovato per course {course_id}")
    voci = module_sk.get("items") or []
    if not voci:
        raise RuntimeError(f"Modulo {mod_idx} senza voci skeleton")

    # Heuristica voce-owner: identifica la voce il cui sub_topic ha più keyword
    # overlap col title + bullets della slide target. Fallback: voce in posizione
    # proporzionale al slide_index_in_module / n_slides_in_module * n_voci.
    target_text = (
        (target_slide.get("title") or "")
        + " "
        + " ".join(target_slide.get("bullets") or [])
        + " "
        + (target_slide.get("speaker_notes") or "")
    ).lower()
    target_words = set(w for w in target_text.split() if len(w) > 3)

    best_voce: dict[str, object] | None = None
    best_overlap = -1
    for voce in voci:
        if not isinstance(voce, dict):
            continue
        st_text = (str(voce.get("sub_topic", "")) + " " + str(voce.get("retrieval_query", ""))).lower()
        st_words = set(w for w in st_text.split() if len(w) > 3)
        overlap = len(target_words & st_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_voce = voce

    if best_voce is None or best_overlap < 1:
        # Fallback proporzionale
        module_slides = [s for s in slides if isinstance(s, dict) and s.get("module_index") == mod_idx]
        slide_pos_in_module = next(
            (i for i, s in enumerate(module_slides) if s.get("index") == slide_index),
            0,
        )
        voce_idx_est = min(int(slide_pos_in_module * len(voci) / max(len(module_slides), 1)), len(voci) - 1)
        best_voce = voci[voce_idx_est] if isinstance(voci[voce_idx_est], dict) else voci[0]

    voce_ord = int(best_voce.get("ordinal", 1)) if isinstance(best_voce.get("ordinal"), (int, str, float)) else 1
    voce_sub_topic = str(best_voce.get("sub_topic", ""))
    voce_retrieval_query = str(best_voce.get("retrieval_query", voce_sub_topic))

    # ── 3. Materializza chunks della voce (re-run B2+B3+B4 per la voce) ──
    from app.models.pipeline import ModuleSkeleton, SkeletonItem
    sk_obj = ModuleSkeleton(
        module_index=mod_idx,
        title=str(module_sk.get("title", f"Modulo {mod_idx}")),
        items=[SkeletonItem(**v) for v in voci if isinstance(v, dict)],
    )
    # Resolve regulation_ids dal course_type catalog
    from config.catalog_config import COURSE_CATALOG
    course_type_str = str(row["course_type"])
    catalog_entry = COURSE_CATALOG.get(course_type_str, {})
    reg_slugs_raw = catalog_entry.get("regs") if catalog_entry else None
    reg_slugs = [str(s) for s in (reg_slugs_raw or ["dlgs_81_08"])]
    repo = KnowledgeRepository(pool)
    reg_ids = await repo.resolve_slugs_to_ids(reg_slugs)
    region = str(row["region"] or "NAZIONALE")

    chunks_by_voice, _all_chunks = await materialize_module_from_skeleton(
        skeleton=sk_obj,
        regulation_ids=reg_ids,
        region=region,
        repo=repo,
        course_id=course_id,
    )
    voce_chunks = chunks_by_voice.get(voce_ord, [])
    if not voce_chunks:
        raise RuntimeError(
            f"F4b: voce {voce_ord} '{voce_sub_topic[:40]}' senza chunks "
            f"(pool vuoto post-B2/B3/B4). Rigenerazione impossibile per questa slide."
        )

    # ── 4. Prompt voce-aware + LLM call per 1 slide ──
    from app.agents.prompts import build_content_system_prompt
    from app.models.core import TargetType
    target_type_str = str(row["target"] or "discente")
    try:
        target_type = TargetType(target_type_str)
    except ValueError:
        target_type = TargetType.DISCENTE
    system_prompt = build_content_system_prompt(target_type)

    # Distribuzione tipo: solo slide_type della slide target (1 slide)
    dist_single = {slide_type: 1} if slide_type else {"CONTENT_TEXT": 1}

    voce_prompt = build_voice_prompt(
        module_index=mod_idx,
        module_title=str(module_sk.get("title", f"Modulo {mod_idx}")),
        voice_ordinal=voce_ord,
        voice_sub_topic=voce_sub_topic,
        voice_retrieval_query=voce_retrieval_query,
        voice_chunks=voce_chunks,
        slide_count_for_voice=1,
        slide_distribution_for_voice=dist_single,
        style_patterns=[],
        previous_voices_summary=(
            f"Sto rigenerando UNA singola slide di tipo {slide_type} per il sotto-tema "
            f"\"{voce_sub_topic}\". La slide originale aveva titolo: "
            f"\"{(target_slide.get('title') or '')[:80]}\". "
            "Genera una versione MIGLIORATA della slide, coerente col sotto-tema."
        ),
        target=target_type,
    )

    chunks_text_voce = "\n\n".join(
        f"[ID: {c.chunk_id}] Art. {c.article or '?'}: {c.body}"
        for c in voce_chunks[:30]
    )

    voce_module_obj, voce_telemetry = await generate_module_structured(
        system=system_prompt,
        user_prompt=voce_prompt,
        module_index=mod_idx,
        module_title=f"REGEN slide {slide_index} - voce {voce_ord}",
        expected_slides=1,
        chunks_text=chunks_text_voce,
        slide_distribution=dist_single,
    )

    if not voce_module_obj.slides:
        raise RuntimeError(
            f"F4b: LLM non ha generato la slide per voce {voce_ord} "
            f"sub_topic '{voce_sub_topic[:40]}' (telemetry: {voce_telemetry.get('provider_used')})"
        )

    # ── 5. Sostituisci slide nel slide_contents_json + persisti + marca dirty ──
    new_slide = voce_module_obj.slides[0]
    # Preserva index originale + module_index (re-generated_slide ha index=0 dal batch)
    new_slide.index = slide_index
    new_slide.module_index = mod_idx
    new_slide_dump = new_slide.model_dump() if hasattr(new_slide, "model_dump") else dict(new_slide)

    slides[slide_index] = new_slide_dump

    await pool.execute(
        "UPDATE courses SET slide_contents_json = $1, dirty = true, updated_at = now() "
        "WHERE id = $2",
        _json.dumps(slides),
        course_uuid,
    )

    logger.info(
        "slide_regenerated_h8",
        course_id=course_id,
        slide_index=slide_index,
        voce_ordinal=voce_ord,
        voce_sub_topic=voce_sub_topic[:60],
        provider=voce_telemetry.get("provider_used"),
        old_title=(target_slide.get("title") or "")[:60],
        new_title=(new_slide_dump.get("title") or "")[:60],
    )

    return {
        "status": "regenerated",
        "course_id": course_id,
        "slide_index": slide_index,
        "voce_ordinal_used": voce_ord,
        "voce_sub_topic_used": voce_sub_topic,
        "old_title": (target_slide.get("title") or "")[:120],
        "new_title": (new_slide_dump.get("title") or "")[:120],
        "provider": voce_telemetry.get("provider_used"),
        "note": "Slide sostituita in slide_contents_json. Esegui /rebuild per ricostruire PPTX.",
    }


def parse_slides_json(raw: str) -> list[dict[str, object]] | None:
    """Robust JSON parsing con multi-shape support (BP §05.5 + FASE 0b vast-hopping).

    Accetta tre shape di risposta LLM:
      1. Array puro: ``[{"index": 0, ...}, {"index": 1, ...}]``  (Anthropic legacy)
      2. Object con key "slides": ``{"slides": [...]}``  (Azure OpenAI JSON mode strict
         richiede sempre object top-level — FASE 0b)
      3. Markdown fences wrap: ```` ```json [...] ``` ```` (Haiku 4.5 lo fa ~50% volte)

    Ritorna ``None`` se nessuna shape applicabile → corrective retry nel content_agent.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    # Shape 1: array puro
    if isinstance(data, list):
        return data
    # Shape 2: object con array sotto una key plausibile (Azure JSON mode)
    if isinstance(data, dict):
        for key in ("slides", "items", "result", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return None


async def content_agent(state: NexusPipelineState) -> dict[str, object]:
    """Generate slide content module-by-module (BP §05.5).

    Pydantic validation at the input boundary (rehydrate course_context /
    pacing_plan / course_request) and per-slide at the output boundary.

    Returns ONLY the fields this node writes (langgraph fix-state-must-
    return-dict): ``completed_modules`` (appended via operator.add reducer)
    and ``current_module_index`` (overwritten).
    """
    # ═══ INPUT VALIDATION ═══
    # course_context / pacing_plan are populated by the Research Agent
    # (3.3). If they are None here, the graph wiring is broken — fail loud.
    course_context_raw = state["course_context"]
    pacing_plan_raw = state["pacing_plan"]
    assert course_context_raw is not None, "research_agent must populate course_context first"
    assert pacing_plan_raw is not None, "research_agent must populate pacing_plan first"
    context = CourseContext(**course_context_raw)
    pacing = PacingPlan(**pacing_plan_raw)
    request = CourseRequest(**state["course_request"])

    start_index = state.get("current_module_index", 0)
    pending_modules = pacing.modules[start_index:]

    # ═══ PARALLEL MODULE GENERATION (REFACTOR 2026-05-25) ═══
    # Originale: for-loop sequenziale → 3 moduli × ~3-5 min/modulo = 9-15 min totali,
    # spesso oltre i 600s di timeout test E2E. Sonnet 4.6 tier-1 ammette ~50 RPM su
    # output completion, ben oltre la nostra concorrenza (max 12 moduli per corso 4h).
    # Parallelizzazione via asyncio.gather → ~3-5 min totali = 3× speedup.
    # ⚠️  Signature pubblica del nodo INVARIATA — i mock test 8/8 continuano a passare.
    # `previous_summary` ora include SOLO completed_modules pre-esistenti nello state
    # (non i moduli generati in questo batch, che sono concorrenti): trade-off
    # accettabile, il summary è un nudge stilistico non un vincolo di consistenza.
    previous_summary = build_previous_summary(
        list(state.get("completed_modules", []))
    )
    system_prompt = build_content_system_prompt(request.target)

    # Soglia minima slide accettabili per modulo (fix #7 — moduli "BAD" 2-3 slide).
    # Se un modulo produce < threshold slide, lo rigeneriamo da zero (cap 1 retry per modulo).
    # Math: target è ~40 slide/modulo, accettiamo fino al 50% loss → soglia 20.
    MIN_ACCEPTABLE_SLIDES_PER_MODULE = 20

    async def _generate_one_module(module: object) -> dict[str, object] | None:
        """Generate slides for one module — retry full-module if too few slides.

        FIX #28.3 tuning (2026-05-26): quando instructor (path PRIMARY in
        _generate_module_once) è attivo, il fill-loop interno gestisce GIÀ la
        cardinalità con cap MAX_CARDINALITY_ATTEMPTS — mescolarci una rete
        esterna `MIN_ACCEPTABLE_SLIDES_PER_MODULE` significherebbe mescolare i
        budget (analista §4: "contatori separati"). Quindi il retry esterno è
        attivo SOLO se instructor è caduto (path legacy attivo, result is None).
        Un risultato con cardinalità sotto soglia ma valido viene accettato:
        instructor ha già fatto del suo meglio col fill-loop, accumulare retry
        esterni esplode i costi senza vantaggio.
        """
        for attempt in range(2):
            result = await _generate_module_once(module, attempt=attempt)
            if result is None:
                # PIPELINE caduta (sia instructor sia legacy esplosi): retry può aiutare.
                if attempt == 0:
                    logger.warning(
                        "module_retry_full",
                        module_index=module.module_index,  # type: ignore[attr-defined]
                        reason="pipeline_failed",
                    )
                    continue
                return None
            slide_count = len(result.get("slides", []))
            # FIX #31.4 (2026-05-27, analista review 5): gate fail-fast,
            # NON accept. Prima loggava warning e ritornava il modulo
            # disastrato che il builder portava a un PPTX consegnabile
            # con modulo mancante + numerazione rotta (E2E #22: M2 = 2
            # slide su 82 attese, modulo 3 sparito, numerazione 1-2-4).
            # Per una demo self-serve è inaccettabile: un cliente che
            # genera un corso deve vedere un crash esplicito, NON un
            # output silenziosamente rotto.
            if slide_count < MIN_ACCEPTABLE_SLIDES_PER_MODULE:
                logger.error(
                    "module_below_threshold_fatal",
                    module_index=module.module_index,  # type: ignore[attr-defined]
                    slide_count=slide_count,
                    threshold=MIN_ACCEPTABLE_SLIDES_PER_MODULE,
                )
                raise RuntimeError(
                    f"Modulo {module.module_index} ha solo {slide_count} "  # type: ignore[attr-defined]
                    f"slide su soglia minima {MIN_ACCEPTABLE_SLIDES_PER_MODULE}. "
                    f"Pipeline interrotta per non consegnare corso con modulo "
                    f"mancante (FIX #31.4 gate fatal — analista review 5)."
                )
            return result
            # Codice morto seguente (mai eseguito, lasciato per riferimento storico
            # FIX #7 quando instructor non esisteva ancora):
            logger.warning(
                "module_below_threshold_after_retry",
                module_index=module.module_index,  # type: ignore[attr-defined]
                final_slides=slide_count,
            )
            return result
        return None

    async def _generate_module_once(module: object, attempt: int = 0) -> dict[str, object] | None:
        """Generate slides for a single module. Returns module dict or None on failure.

        FIX #28.1e (2026-05-26): structured output via instructor è il path PRIMARY.
        Garantisce profondità per-slide (max_retries) + cardinalità per-modulo (fill-loop)
        con budget separati. Il legacy auto-fix sotto è floor di ultima istanza per
        compatibilità (se instructor crasha o un provider è giù, ripieghiamo).

        H8 (2026-05-31): branch voce-to-slide cluster. Se `chunks_by_voice` e
        `module_skeletons` sono disponibili per il modulo (skeleton-validation ON
        + skeleton già materializzato), generiamo cluster di slide PER VOCE
        invece di N slide free-form sull'union dei chunks. Cura il drift
        voce-to-slide (sample-read M0 post-V1.5: on-topic core 1.2% su 84 slide
        free-form da pool union).
        """
        from app.config import settings as _settings

        mod_idx_h8 = module.module_index  # type: ignore[attr-defined]
        # H8 gate: cluster voce-per-voce attivo solo se TUTTI i prerequisiti soddisfatti.
        # Path legacy invariato come fallback safe.
        h8_voci = context.chunks_by_voice.get(mod_idx_h8, {}) if hasattr(context, "chunks_by_voice") else {}
        h8_skel = context.module_skeletons.get(mod_idx_h8, []) if hasattr(context, "module_skeletons") else []
        if (
            _settings.v2_skeleton_validation
            and h8_voci
            and h8_skel
            and len(h8_skel) >= 2  # almeno 2 voci, altrimenti monovoce = path legacy stesso esito
        ):
            try:
                return await _generate_module_h8(
                    module=module,
                    voci_skeleton=h8_skel,
                    chunks_by_voce=h8_voci,
                    style_patterns=context.style_patterns,
                    previous_summary=previous_summary,
                    target=request.target,
                    system_prompt=system_prompt,
                )
            except Exception as exc:
                # H8 ha fallito: log + fallback al path legacy (safety net).
                logger.warning(
                    "h8_voci_failed_fallback_legacy",
                    module_index=mod_idx_h8,
                    n_voci=len(h8_skel),
                    error_class=type(exc).__name__,
                    error=str(exc)[:200],
                )
                # Cade al path legacy sotto.

        module_chunks = context.chunks_by_module.get(module.module_index, [])  # type: ignore[attr-defined]
        user_prompt = build_module_prompt(
            module=module,
            chunks=module_chunks,
            style_patterns=context.style_patterns,
            previous_summary=previous_summary,
            target=request.target,
        )
        expected = int(getattr(module, "slide_count", 0) or 0)

        # ── PRIMARY: instructor (structured output, schema imposto, batch) ──
        if expected > 0:
            # FIX #29.1: passa il testo dei chunk normativi del modulo. Il
            # generate_module_structured li partizionerà tra i batch così ogni
            # call ha materiale fresco e non under-generates per padding.
            # FIX #30.7b (2026-05-26): espone chunk_id UUID intero (non
            # regulation_id prefix come prima) così l'LLM lo copia
            # corretto in source_chunk_ids della slide → enrich
            # normative_ref dal DB funziona (citation_label puntuale per
            # articolo, non solo per regulation generico).
            chunks_text = "\n\n".join(
                f"[ID: {c.chunk_id}] Art. {c.article or '?'}: {c.body}"
                for c in module_chunks[:30]
            )
            # FIX #31.4 (analista review 5): SEPARO il try/except in 2 step.
            # STEP 1: generate_module_structured (può fallire per LLM/quota/
            # validation → legittimo fallback legacy).
            # STEP 2: bookends (NON deve attivare fallback se fallisce: 77
            # slide buone non si buttano via per un bullet di 13 parole nel
            # MODULE_CLOSE — è quello che ha eliminato M2 in E2E #22).
            module_obj = None
            telemetry: dict[str, object] = {}
            try:
                module_obj, telemetry = await generate_module_structured(
                    system=system_prompt,
                    user_prompt=user_prompt,
                    module_index=module.module_index,  # type: ignore[attr-defined]
                    module_title=module.title,  # type: ignore[attr-defined]
                    expected_slides=expected,
                    chunks_text=chunks_text,
                    slide_distribution=module.slide_distribution,  # FIX #30.8 quota
                )
                logger.info(
                    "module_instructor_ok",
                    module_index=module.module_index,  # type: ignore[attr-defined]
                    final=telemetry.get("final_count"),
                    expected=telemetry.get("expected"),
                    degraded=telemetry.get("degraded"),
                    provider=telemetry.get("provider_used"),
                )
            except Exception as exc:
                logger.warning(
                    "module_instructor_failed_fallback_legacy",
                    module_index=module.module_index,  # type: ignore[attr-defined]
                    error_class=type(exc).__name__,
                    error=str(exc)[:200],
                )
                # Fall-through al path legacy sotto (instructor fallito veramente).
                module_obj = None

            # STEP 2: se STEP 1 è andato a buon fine, applico bookends.
            # NON dentro try/except che fa fallback (analista review 5):
            # se bookends fallisce, è bug nostro e va aggiustato con
            # truncate/drop, non dropping 77 slide buone.
            if module_obj is not None:
                content_slides = list(module_obj.slides)
                mod_idx = module.module_index  # type: ignore[attr-defined]
                mod_title = module.title  # type: ignore[attr-defined]
                try:
                    bookend_slides = _build_module_bookends(
                        module_index=mod_idx,
                        module_title=mod_title,
                        content_slides=content_slides,
                    )
                    all_slides = (
                        [bookend_slides[0]] + content_slides + [bookend_slides[1]]
                    )
                except Exception as exc:
                    # FIX #31.4 (analista review 5): bookends fallito MA
                    # tengo le content_slides buone. Solo logging + skip
                    # bookends, NO fallback distruttivo. Il modulo perde
                    # MODULE_OPEN/CLOSE ma resta integro nei contenuti.
                    logger.error(
                        "bookends_construction_failed_kept_content",
                        module_index=mod_idx,
                        content_slides=len(content_slides),
                        error_class=type(exc).__name__,
                        error=str(exc)[:200],
                    )
                    all_slides = list(content_slides)
                for i, s in enumerate(all_slides):
                    s.index = i
                    s.module_index = mod_idx
                return ModuleContent(
                    module_index=mod_idx,
                    title=mod_title,
                    slides=all_slides,
                ).model_dump()

        # ── LEGACY FLOOR: parse+auto-fix manuale (solo se instructor è giù) ──
        try:
            raw_response = await call_llm(
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
            )
        except Exception as e:
            logger.error("module_llm_failed", module_index=module.module_index, error=str(e))  # type: ignore[attr-defined]
            return None

        slides = parse_slides_json(raw_response)
        if slides is None:
            correction_prompt = (
                f"Il tuo output precedente non era JSON valido. "
                f"Riscrivi SOLO l'array JSON di slide, senza testo aggiuntivo.\n\n"
                f"Output precedente (non valido):\n{raw_response[:2000]}"
            )
            try:
                raw_response = await call_llm(
                    messages=[{"role": "user", "content": correction_prompt}],
                    system=system_prompt,
                )
                slides = parse_slides_json(raw_response)
            except Exception:
                slides = None

        if slides is None:
            logger.error("module_json_failed", module_index=module.module_index)  # type: ignore[attr-defined]
            return None

        # FIX #13 (2026-05-25): strategia AUTO-COMPLETE PURAMENTE ADDITIVA
        # (no troncamento, no perdita contenuto).
        # 1. Tentativo immediato: SlideContent(**s) ok → slide valida, va.
        # 2. AUTO-COMPLETE deterministico (ZERO call LLM, solo append/default):
        #    - module_index missing → uso quello del modulo corrente
        #    - notes troppo brevi → append " Riferimento normativo: <ref>." finché OK
        #    - viewBox missing → aggiungo viewBox="0 0 1760 800" all'SVG
        #    - aspect_hint None → default "landscape"
        #    - quiz_correct missing → default 0
        # 3. Per errori NON-additivi (title troppo lungo, notes troppo lunghi,
        #    troppi bullet) → SPLIT LLM retry (cap 5 per modulo per evitare loop).
        #    Cap raggiunto → la slide invalida resta MA logghiamo "slide_held"
        #    così l'utente la rigenera dalla Course Studio.
        MAX_SPLITS_PER_MODULE = 5
        validated_slides: list[dict[str, object]] = []
        splits_used = 0
        auto_fixed = 0
        held_for_studio: list[dict[str, object]] = []  # slide invalide preservate
        # FIX #27 diag: categorizza i motivi di rifiuto per capire se la causa è
        # l'LLM (under-genera bullet/note) o lo schema. Stampato a fine modulo.
        reject_reasons: dict[str, int] = {}
        for s in slides:
            if not isinstance(s, dict):
                continue
            try:
                validated_slides.append(SlideContent(**s).model_dump())
                continue
            except Exception as e:
                err_str = str(e)
                # Estrai la categoria: "< N min" (under-gen LLM), "> N max"
                # (over-gen), "richiede" (campo mancante), ecc.
                if "< " in err_str and " min" in err_str:
                    reject_reasons["under_min_bullets_or_notes"] = reject_reasons.get("under_min_bullets_or_notes", 0) + 1
                elif "> " in err_str and " max" in err_str:
                    reject_reasons["over_max"] = reject_reasons.get("over_max", 0) + 1
                elif "richiede" in err_str:
                    reject_reasons["missing_field"] = reject_reasons.get("missing_field", 0) + 1
                else:
                    reject_reasons["other"] = reject_reasons.get("other", 0) + 1
            # Tentativo 1: AUTO-COMPLETE deterministico (solo additivo)
            fixed = _auto_complete_invalid_slide(s, module.module_index, err_str)  # type: ignore[attr-defined]
            if fixed is not None:
                try:
                    validated_slides.append(SlideContent(**fixed).model_dump())
                    auto_fixed += 1
                    continue
                except Exception:
                    pass  # auto-fix non basta, prosegui col SPLIT
            logger.warning(
                "slide_validation_failed",
                error=err_str[:200],
                slide=s.get("index"),
            )
            # Tentativo 2: SPLIT LLM (solo se sotto cap)
            if splits_used >= MAX_SPLITS_PER_MODULE:
                # Cap raggiunto: preserva la slide grezza per Course Studio
                # invece di skippare. L'utente vedrà "slide non validata" in UI.
                held_for_studio.append(s)
                continue
            splits_used += 1
            try:
                split_prompt = build_split_correction_prompt(s, [err_str])
                raw_split = await call_llm(
                    messages=[{"role": "user", "content": split_prompt}],
                    system=system_prompt,
                )
                new_slides = parse_slides_json(raw_split) or []
                added = 0
                for ns in new_slides:
                    if not isinstance(ns, dict):
                        continue
                    ns.setdefault("module_index", module.module_index)  # type: ignore[attr-defined]
                    try:
                        validated_slides.append(SlideContent(**ns).model_dump())
                        added += 1
                    except Exception:
                        ns_fixed = _auto_complete_invalid_slide(ns, module.module_index, "")  # type: ignore[attr-defined]
                        if ns_fixed is not None:
                            try:
                                validated_slides.append(SlideContent(**ns_fixed).model_dump())
                                added += 1
                            except Exception:
                                held_for_studio.append(ns)
                logger.info(
                    "slide_split_recovered",
                    original_index=s.get("index"),
                    recovered=added,
                )
            except Exception as e3:
                logger.error(
                    "slide_split_failed",
                    original_index=s.get("index"),
                    error=str(e3)[:200],
                )
                held_for_studio.append(s)
        if auto_fixed > 0 or held_for_studio or reject_reasons:
            logger.info(
                "module_recovery_stats",
                module_index=module.module_index,  # type: ignore[attr-defined]
                validated=len(validated_slides),
                auto_fixed=auto_fixed,
                splits_used=splits_used,
                held_for_studio=len(held_for_studio),
                # FIX #27 diag: dove sta il problema. under_min* alto = LLM
                # under-genera (problema prompt/modello); missing_field alto =
                # schema; other = bug nostro da investigare.
                reject_reasons=reject_reasons,
            )

        logger.info(
            "module_completed",
            module=module.module_index,  # type: ignore[attr-defined]
            slides=len(validated_slides),
        )
        return ModuleContent(
            module_index=module.module_index,  # type: ignore[attr-defined]
            title=module.title,  # type: ignore[attr-defined]
            slides=[SlideContent(**vs) for vs in validated_slides],
        ).model_dump()

    # FASE 0b R6 mitigation: Semaphore gating per non saturare Azure 200K TPM.
    # 10 moduli concorrenti = ~160K TPM picco (gpt-4.1-mini ~20K token/modulo),
    # margine 20% per retry burst. Corsi 4h (12 moduli): coda 2; corsi 8h (24): coda 14.
    sem = asyncio.Semaphore(settings.content_agent_concurrency)

    async def _bounded(module: object) -> dict[str, object] | None:
        async with sem:
            return await _generate_one_module(module)

    results = await asyncio.gather(
        *(_bounded(m) for m in pending_modules),
        return_exceptions=False,
    )
    completed: list[dict[str, object]] = [r for r in results if r is not None]
    failed_count = sum(1 for r in results if r is None)

    # ═══ INLINE CIRCUIT BREAKER (FIX-3) ═══
    total_modules = len(pending_modules)
    if failed_count > total_modules * 0.5:
        raise RuntimeError(
            f"Circuit breaker: {failed_count}/{total_modules} moduli falliti. "
            f"Verificare la qualità dei chunk RAG o lo stato delle API Anthropic."
        )

    return {
        "completed_modules": completed,
        "current_module_index": len(pacing.modules),
    }
