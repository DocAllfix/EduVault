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

import structlog

from app.agents.pipeline import NexusPipelineState
from app.models.core import LAYOUT_CONSTRAINTS, SlideType


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

    Note speaker brevi pre-composte per entrambi (non dipendono da LLM, audio
    TTS pulito it-IT-DiegoNeural).
    """
    from app.models.core import SlideType

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

    close_slide = SlideContent(
        index=len(content_slides) + 1,
        module_index=module_index,
        slide_type=SlideType.MODULE_CLOSE,
        title=module_title,
        bullets=top5,
        speaker_notes=(
            f"Riepilogo del modulo {n_module}. Abbiamo trattato i punti chiave "
            f"qui sintetizzati. Nel modulo successivo continueremo il percorso "
            f"formativo con altri temi normativi e applicazioni pratiche."
        ),
    )

    return open_slide, close_slide


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
            # Accetta il risultato: instructor (o legacy) ha già fatto il suo
            # massimo. Sotto-cardinalità è loggata via degraded=True dentro
            # generate_module_structured, non rigeneriamo da zero.
            if slide_count < MIN_ACCEPTABLE_SLIDES_PER_MODULE:
                logger.warning(
                    "module_below_threshold_accepted",
                    module_index=module.module_index,  # type: ignore[attr-defined]
                    slide_count=slide_count,
                    threshold=MIN_ACCEPTABLE_SLIDES_PER_MODULE,
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
        """
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
                # FIX #30.2 (2026-05-26): bookends MODULE_OPEN + MODULE_CLOSE
                # come slot fissi (NON via LLM separato). MODULE_OPEN apre con
                # "MODULO N" + titolo modulo; MODULE_CLOSE chiude con 5 top
                # bullet derivati dai title delle slide di contenuto.
                content_slides = list(module_obj.slides)
                mod_idx = module.module_index  # type: ignore[attr-defined]
                mod_title = module.title  # type: ignore[attr-defined]
                bookend_slides = _build_module_bookends(
                    module_index=mod_idx,
                    module_title=mod_title,
                    content_slides=content_slides,
                )
                # Open + content + close, indici riassegnati contigui per modulo
                all_slides = [bookend_slides[0]] + content_slides + [bookend_slides[1]]
                for i, s in enumerate(all_slides):
                    s.index = i
                    s.module_index = mod_idx
                return ModuleContent(
                    module_index=mod_idx,
                    title=mod_title,
                    slides=all_slides,
                ).model_dump()
            except Exception as exc:
                logger.warning(
                    "module_instructor_failed_fallback_legacy",
                    module_index=module.module_index,  # type: ignore[attr-defined]
                    error_class=type(exc).__name__,
                    error=str(exc)[:200],
                )
                # Fall-through al path legacy sotto.

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
