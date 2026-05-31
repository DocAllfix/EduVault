"""Course generation pipeline wrapper (BLUEPRINT §09).

Implementa BP §09.1 verbatim con tre adattamenti REI/OPT (segnalati come
discrepanze):

- ``PIPELINE_TIMEOUT_SECONDS`` da ``settings.pipeline_timeout`` (OPT-2).
- ``settings.database_url`` invece di ``from app.config import DATABASE_URL``.
- ``create_pipeline`` è ``@asynccontextmanager`` (D18 storica) → ``async with``.

REI-3 / FIX-7 v2.0: ``_job_semaphore = asyncio.Semaphore(1)`` vive QUI,
non in ``services/dependencies.py``. È un vincolo architetturale
(python-pptx + lxml non thread-safe) — NON alzare a 2+ senza convertire
a process pool o Celery.

D-18: shutdown event LETTO da ``dependencies.get_shutdown_event()``.
Nessun ``asyncio.Event()`` locale in questo modulo.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Literal, cast

import asyncpg
import structlog

from app.agents.pipeline import NexusPipelineState, create_pipeline
from app.builders.production_builder import ProductionBuilder
from app.config import settings
from app.models.pipeline import SlideContent
from app.services.dependencies import get_pool, get_shutdown_event
from app.services.image_service import prefetch_images

logger = structlog.get_logger()

# ═══ SEMAFORO DI CONCORRENZA (REI-3 / FIX-7 v2.0) ═══
# VINCOLO ARCHITETTURALE: python-pptx + lxml NON sono thread-safe.
# NON alzare MAI a Semaphore(2+) senza passare a process pool o Celery.
MAX_CONCURRENT_JOBS = 1
_job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

# ═══ TIMEOUT GLOBALE PIPELINE (OPT-2 — settings.pipeline_timeout) ═══
PIPELINE_TIMEOUT_SECONDS = settings.pipeline_timeout

# ═══ BACKGROUND TASKS REGISTRY (FIX #31 MOSSA 3) ═══
# Set di riferimenti forti per i task spawnati con asyncio.create_task DOPO
# che la pipeline ha settato status=completed (audio TTS in background).
# Senza questo set, il GC porta via i task perché nessuno tiene un
# riferimento forte → audio non parte mai → audio_manifest_path=NULL per
# sempre. Gotcha asyncio documentato. Il done_callback rimuove il task
# alla fine (vedi _bg_audio in _run_pipeline_inner), così il set non
# cresce indefinitamente in batch notturno.
# REI-3 NON violato: edge-tts è I/O HTTP, non tocca python-pptx.
_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


async def send_ws_progress(job_id: str, percent: int, step: str) -> None:
    """Update job progress in the DB. The WebSocket reads it via
    ``get_job_progress()``. Decoupling pipeline from WS: pipeline writes,
    WS polls the DB."""
    db = get_pool()
    await db.execute(
        "UPDATE generation_jobs SET progress_percent=$1, current_step=$2 WHERE id=$3",
        percent,
        step,
        job_id,
    )


def build_normative_fingerprint(slides: list[dict[str, Any]]) -> dict[str, Any]:
    """Compose a normative fingerprint for the future Delta-Update.

    Shape: ``{refs: [unique normative_ref strings], chunk_count: int,
    generated_at: ISO 8601}``.
    """
    refs: list[str] = []
    seen_refs: set[str] = set()
    all_chunk_ids: set[str] = set()
    for slide in slides:
        # Difensivo: a volte LangGraph reducer può restituire str invece di dict
        # se la pipeline ha avuto recovery parziale. Skippiamo silenziosamente.
        if not isinstance(slide, dict):
            continue
        ref = slide.get("normative_ref", "") or ""
        if ref and ref not in seen_refs:
            refs.append(ref)
            seen_refs.add(ref)
        for cid in slide.get("source_chunk_ids", []) or []:
            all_chunk_ids.add(cid)
    return {
        "refs": refs,
        "chunk_count": len(all_chunk_ids),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def run_pipeline(
    job_id: str, course_id: str, phase: Literal["research", "content"] = "research"
) -> None:
    """Main wrapper: acquires the semaphore and wraps the pipeline in a
    global timeout. A stuck job must never monopolise the instance.

    Maps every failure mode to a terminal ``generation_jobs.status`` so the
    UI / WS layer can stop polling.

    ``phase`` (D3, vast-hopping-sketch): ``"research"`` (default) runs the full
    pipeline today; with ``v2_features['skeleton_validation']`` it stops after
    research at ``skeleton_pending``. ``"content"`` is invoked by the skeleton
    approve endpoint to resume from the (edited) skeleton and build outputs.
    """
    async with _job_semaphore:
        try:
            await asyncio.wait_for(
                _run_pipeline_inner(job_id, course_id, phase=phase),
                timeout=PIPELINE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.error(
                "pipeline_timeout",
                job_id=job_id,
                timeout=PIPELINE_TIMEOUT_SECONDS,
            )
            db = get_pool()
            await db.execute(
                "UPDATE generation_jobs SET status='failed', "
                "error_message='Pipeline timeout dopo 30 minuti' WHERE id=$1",
                job_id,
            )
        except asyncio.CancelledError:
            db = get_pool()
            await db.execute(
                "UPDATE generation_jobs SET status='cancelled' WHERE id=$1",
                job_id,
            )
            raise
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error("pipeline_failed", job_id=job_id, error=str(e), traceback=tb[-2000:])
            db = get_pool()
            await db.execute(
                "UPDATE generation_jobs SET status='failed', "
                "error_message=$1 WHERE id=$2",
                (str(e) + " | " + tb[-300:])[:500],
                job_id,
            )


async def _run_research_and_skeleton(
    *,
    job_id: str,
    course_id: str,
    initial_state: dict[str, Any],
    pipeline_config: Any,
    db: Any,
) -> None:
    """D3 research phase: run research, generate skeletons, stop at gate.

    The graph is compiled with ``stop_before_content=True`` so ``ainvoke``
    returns right after research (``interrupt_before=["content"]``). We read the
    resulting ``pacing_plan`` from the checkpoint state, generate one
    ``ModuleSkeleton`` per module (grounding (a): title + course_type + sibling
    titles, NO chunks), persist them to ``courses.module_skeletons_json``, and
    set status ``skeleton_pending``. No content, no build.
    """
    import json as _json
    import uuid as _uuid

    from app.models.pipeline import PacingPlan
    from app.services.skeleton_service import generate_module_skeleton

    await db.execute(
        "UPDATE generation_jobs SET status='research' WHERE id=$1", job_id
    )

    async with create_pipeline(
        settings.database_url, stop_before_content=True
    ) as pipeline:
        await pipeline.ainvoke(
            cast(NexusPipelineState, initial_state), config=pipeline_config
        )
        snapshot = await pipeline.aget_state(pipeline_config)

    state_values = snapshot.values
    course_context = state_values.get("course_context")
    if course_context is None:
        raise ValueError("research produced no course_context (skeleton phase)")
    # course_context may be a CourseContext model or a dict (LangGraph serializes
    # state); normalize access to the pacing_plan + modules.
    pacing_raw = (
        course_context.get("pacing_plan")
        if isinstance(course_context, dict)
        else getattr(course_context, "pacing_plan", None)
    )
    pacing = PacingPlan.model_validate(pacing_raw) if pacing_raw is not None else None
    if pacing is None or not pacing.modules:
        raise ValueError("research produced no pacing_plan modules (skeleton phase)")

    course_row = await db.fetchrow(
        "SELECT course_type, title FROM courses WHERE id=$1", _uuid.UUID(course_id)
    )
    course_type_slug = course_row["course_type"]
    course_title = course_row["title"] or course_type_slug
    all_titles = [m.title for m in pacing.modules]

    # Generate skeletons (bounded concurrency, mirrors content_agent).
    sem = asyncio.Semaphore(4)

    async def _one(m: Any) -> dict[str, Any]:
        async with sem:
            sk = await generate_module_skeleton(
                module_index=m.module_index,
                module_title=m.title,
                course_type_slug=course_type_slug,
                course_title=course_title,
                sibling_module_titles=all_titles,
                course_id=course_id,
            )
            return sk.model_dump()

    skeletons = await asyncio.gather(*(_one(m) for m in pacing.modules))
    skeletons_sorted = sorted(skeletons, key=lambda s: int(s["module_index"]))

    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "modules": skeletons_sorted,
    }
    await db.execute(
        "UPDATE courses SET module_skeletons_json=$1, status='skeleton_pending' "
        "WHERE id=$2",
        _json.dumps(payload),
        _uuid.UUID(course_id),
    )
    await db.execute(
        "UPDATE generation_jobs SET status='skeleton_pending' WHERE id=$1", job_id
    )
    logger.info(
        "skeleton_pending_ready",
        course_id=course_id,
        job_id=job_id,
        modules=len(skeletons_sorted),
    )


async def _resume_content_from_skeleton(
    *,
    job_id: str,
    course_id: str,
    initial_state: dict[str, Any],
    pipeline_config: Any,
    db: Any,
) -> dict[str, Any]:
    """D3 content phase: materialize edited skeleton → resume content.

    Reads the (operator-edited) skeleton from ``courses.module_skeletons_json``,
    runs per-sub-topic retrieval to build ``chunks_by_module``, rebuilds the
    ``CourseContext`` with those chunks, then resumes the graph from the
    ``content`` node via ``aupdate_state(..., as_node="research")`` +
    ``ainvoke(None)`` — so content sees the by-sub-topic chunks, not the stale
    by-title ones from the research checkpoint.
    """
    import json as _json
    import uuid as _uuid

    from app.models.pipeline import CourseContext, ModuleSkeleton
    from app.services.knowledge_repo import KnowledgeRepository
    from app.services.skeleton_service import materialize_module_from_skeleton

    await db.execute(
        "UPDATE generation_jobs SET status='content' WHERE id=$1", job_id
    )

    row = await db.fetchrow(
        "SELECT module_skeletons_json, course_type, region FROM courses WHERE id=$1",
        _uuid.UUID(course_id),
    )
    raw = row["module_skeletons_json"]
    if raw is None:
        raise ValueError("content phase: no module_skeletons_json to materialize")
    payload = _json.loads(raw) if isinstance(raw, str) else raw
    skeletons = [ModuleSkeleton.model_validate(m) for m in payload["modules"]]

    # Resolve regulation_ids for the course (same as research_agent).
    from config.catalog_config import COURSE_CATALOG

    catalog_entry = COURSE_CATALOG.get(row["course_type"], {})
    reg_slugs_raw = catalog_entry.get("regs") if catalog_entry else None
    reg_slugs = reg_slugs_raw if isinstance(reg_slugs_raw, list) else ["dlgs_81_08"]
    repo = KnowledgeRepository(db)
    reg_ids = await repo.resolve_slugs_to_ids([str(s) for s in reg_slugs])
    region = row["region"] or "NAZIONALE"

    # H8 (2026-05-31): materialize_module_from_skeleton ora ritorna
    # (chunks_by_voice, chunks_module_dedup). Popola chunks_by_voice nuovo
    # campo CourseContext + chunks_by_module legacy retro-compat.
    # Inoltre popola module_skeletons (subset serializzato dei ModuleSkeleton)
    # per il content_agent che itera voce per voce.
    chunks_by_module: dict[int, list[Any]] = {}
    chunks_by_voice: dict[int, dict[int, list[Any]]] = {}
    module_skeletons: dict[int, list[dict[str, object]]] = {}
    all_chunks: list[Any] = []
    seen_global: set[str] = set()
    for sk in skeletons:
        module_chunks_by_voice, module_chunks_dedup = await materialize_module_from_skeleton(
            skeleton=sk,
            regulation_ids=reg_ids,
            region=region,
            repo=repo,
            course_id=course_id,
        )
        chunks_by_module[sk.module_index] = module_chunks_dedup
        chunks_by_voice[sk.module_index] = module_chunks_by_voice
        module_skeletons[sk.module_index] = [
            {
                "ordinal": item.ordinal,
                "sub_topic": item.sub_topic,
                "retrieval_query": item.retrieval_query,
            }
            for item in sk.items
        ]
        for c in module_chunks_dedup:
            if c.chunk_id not in seen_global:
                seen_global.add(c.chunk_id)
                all_chunks.append(c)

    async with create_pipeline(
        settings.database_url, stop_before_content=True
    ) as pipeline:
        snapshot = await pipeline.aget_state(pipeline_config)
        cc_raw = snapshot.values.get("course_context")
        # Rebuild CourseContext keeping pacing_plan + style_patterns, swapping in
        # the by-sub-topic chunks. H8: aggiunto chunks_by_voice.
        cc = (
            CourseContext.model_validate(cc_raw)
            if not isinstance(cc_raw, CourseContext)
            else cc_raw
        )
        new_cc = cc.model_copy(
            update={
                "chunks": all_chunks,
                "chunks_by_module": chunks_by_module,
                "chunks_by_voice": chunks_by_voice,
                "module_skeletons": module_skeletons,
            }
        )
        await pipeline.aupdate_state(
            pipeline_config,
            {"course_context": new_cc.model_dump()},
            as_node="research",
        )
        result = await pipeline.ainvoke(None, config=pipeline_config)
    return cast(dict[str, Any], result)


async def _run_pipeline_inner(
    job_id: str, course_id: str, phase: Literal["research", "content"] = "research"
) -> None:
    """Inner pipeline logic, isolated for clean timeout/cancel propagation.

    D3: ``phase`` gates the skeleton split when
    ``v2_features['skeleton_validation']`` is on:
      - ``research``: run research, stop at ``interrupt_before=["content"]``,
        generate per-module skeletons, persist them, set ``skeleton_pending``,
        and RETURN (no content, no build).
      - ``content``: read the (edited) skeleton from the DB, materialize chunks
        per sub-topic, resume the graph from ``content`` via aupdate_state, then
        run the existing build block.
    With the flag off, ``phase`` is ignored and the pipeline runs end-to-end as
    today.
    """
    db = get_pool()
    start_time = time.time()

    if get_shutdown_event().is_set():
        raise asyncio.CancelledError("Server in shutdown")

    # ═══ DB LOAD ═══
    course_row = await db.fetchrow("SELECT * FROM courses WHERE id = $1", course_id)
    if course_row is None:
        raise ValueError(f"Course {course_id} not found")
    course = dict(course_row)

    brand_row = await db.fetchrow(
        "SELECT * FROM brand_presets WHERE id = $1", course["brand_preset_id"]
    )
    if brand_row is None:
        raise ValueError(f"Brand preset {course['brand_preset_id']} not found")
    brand = dict(brand_row)

    # FIX 2026-05-25: asyncpg deserializza UUID columns come uuid.UUID native,
    # ma Pydantic CourseRequest vuole brand_preset_id come str. Coercione esplicita
    # qui evita "Input should be a valid string" sul rebuild in research/content agent.
    import uuid as _uuid_mod
    course_request_dict = {
        k: (str(v) if isinstance(v, _uuid_mod.UUID) else v)
        for k, v in course.items()
    }

    # ═══ LANGGRAPH INITIAL STATE (BP §05.2 — 8 fields, no extras) ═══
    initial_state: dict[str, Any] = {
        "course_request": course_request_dict,
        "brand_config": brand,
        "course_context": None,
        "pacing_plan": None,
        "completed_modules": [],
        "current_module_index": 0,
        "job_id": job_id,
        "errors": [],
    }

    await db.execute(
        "UPDATE generation_jobs SET status='research', started_at=NOW() WHERE id=$1",
        job_id,
    )

    # ═══ LANGGRAPH PIPELINE (D18: create_pipeline è @asynccontextmanager) ═══
    # cast() needed because RunnableConfig + NexusPipelineState are TypedDicts
    # and mypy strict rejects the literal-dict overload, even though
    # `{"configurable": {"thread_id": ...}}` is the canonical LangGraph idiom
    # (BP §05.3) and our initial_state already matches the 8-field shape.
    from langchain_core.runnables import RunnableConfig

    # D3: the LangGraph checkpoint thread_id must be STABLE across the research
    # and content phases (they are two separate generation_jobs but ONE course
    # pipeline). Keying on course_id lets the content phase aget_state/
    # aupdate_state the checkpoint that the research phase produced. The legacy
    # single-invoke path is unaffected (one job, one course, same value either
    # way).
    thread_id = course_id
    pipeline_config = cast(
        RunnableConfig, {"configurable": {"thread_id": thread_id}}
    )
    skeleton_on = bool(settings.v2_features.get("skeleton_validation"))

    if skeleton_on and phase == "research":
        # ═══ D3 RESEARCH PHASE: stop at skeleton_pending ═══
        await _run_research_and_skeleton(
            job_id=job_id,
            course_id=course_id,
            initial_state=initial_state,
            pipeline_config=pipeline_config,
            db=db,
        )
        return  # gate: no content, no build until the operator approves

    if skeleton_on and phase == "content":
        # ═══ D3 CONTENT PHASE: resume from edited skeleton ═══
        result = await _resume_content_from_skeleton(
            job_id=job_id,
            course_id=course_id,
            initial_state=initial_state,
            pipeline_config=pipeline_config,
            db=db,
        )
    else:
        # ═══ LEGACY PATH (flag off): full pipeline in one invoke ═══
        async with create_pipeline(settings.database_url) as pipeline:
            result = await pipeline.ainvoke(
                cast(NexusPipelineState, initial_state), config=pipeline_config
            )

    # FIX #27.1 (2026-05-26): modules are produced in PARALLEL (asyncio.gather in
    # content_agent) and arrive in COMPLETION order, not module order. Without
    # sorting, "Modulo N" labels and the global page_num (enumerate position in
    # the builder) get scrambled — a Module 5 slide can appear before Module 2.
    # Sort by module_index, then each module's slides by their local index, so
    # the assembled deck is strictly module→slide ordered.
    modules_sorted = sorted(
        result["completed_modules"], key=lambda m: m["module_index"]
    )
    all_slides = [
        s
        for m in modules_sorted
        for s in sorted(m["slides"], key=lambda sl: sl["index"])
    ]

    # FIX #30.5b (2026-05-26): post-process normative_ref ricostruito dal DB
    # tramite citation_label denormalizzato. L'LLM ha scritto un valore
    # nel campo (vecchio prompt) ma lo sovrascriviamo deterministicamente
    # dai source_chunk_ids → niente più allucinazioni "Pag. X-Y" né format
    # incoerenti. Lavora su dict (all_slides è list[dict]) per evitare il
    # round-trip Pydantic.
    try:
        import re as _re
        _UUID_RE = _re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            _re.IGNORECASE,
        )
        # FIX #30.6 (2026-05-26): l'LLM usa source_chunk_ids in 2 modi diversi:
        #   (a) UUID intero (corretto): "a428644f-2a0f-48c5-a5ab-45aa98f08cac"
        #   (b) regulation_id prefisso 8 char (preso dal prompt che mostra
        #       "Art. X (PREFISSO): body") → es. "237e0712"
        # Strategia: accumuliamo entrambi i tipi e facciamo 2 query separate
        # (uuid match esatto + prefix match su regulation_id). La prefix dà
        # citation a granularità reg-only (perdiamo art. specifico) ma è meglio
        # di niente. Il prompt-fix vero (chiedere chunk_id intero) va in #30.7.
        all_uuid_ids: set[str] = set()
        all_prefix_ids: set[str] = set()
        for s in all_slides:
            ids = s.get("source_chunk_ids") or []
            for cid in ids:
                sc = str(cid)
                if _UUID_RE.match(sc):
                    all_uuid_ids.add(sc)
                elif len(sc) == 8 and all(c in "0123456789abcdef" for c in sc.lower()):
                    all_prefix_ids.add(sc.lower())

        id_to_label: dict[str, str] = {}
        if all_uuid_ids:
            rows = await db.fetch(
                "SELECT id::text AS id, citation_label "
                "FROM regulation_chunks WHERE id = ANY($1::uuid[])",
                list(all_uuid_ids),
            )
            for r in rows:
                if r["citation_label"]:
                    id_to_label[r["id"]] = r["citation_label"]
        if all_prefix_ids:
            # Lookup via regulation_id prefix: prendiamo 1 chunk per reg come
            # rappresentativo (la citation viene dal regulation, non dall'art.)
            rows = await db.fetch(
                "SELECT DISTINCT ON (regulation_id) regulation_id::text AS rid, "
                "citation_label FROM regulation_chunks "
                "WHERE SUBSTRING(regulation_id::text, 1, 8) = ANY($1::text[])",
                list(all_prefix_ids),
            )
            for r in rows:
                if r["citation_label"]:
                    # Mappiamo la prefix al label (e anche l'uppercase variant)
                    short = r["rid"][:8]
                    # estrai solo "D.Lgs. 81/08" senza "art. X" parte
                    base = r["citation_label"].split(",")[0]
                    id_to_label[short] = base
                    id_to_label[short.upper()] = base

        if not id_to_label:
            return  # niente da enrichire

        n_enriched = 0
        for s in all_slides:
            ids = s.get("source_chunk_ids") or []
            if not ids:
                continue
            labels = []
            for cid in ids:
                sc = str(cid)
                lbl = id_to_label.get(sc) or id_to_label.get(sc.lower())
                if lbl:
                    labels.append(lbl)
            if not labels:
                continue
            seen: set[str] = set()
            unique = []
            for l in labels:
                if l not in seen:
                    seen.add(l)
                    unique.append(l)
            new_ref = "; ".join(unique[:3])[:200]
            s["normative_ref"] = new_ref
            n_enriched += 1
        logger.info(
            "normative_refs_enriched",
            enriched=n_enriched,
            total=len(all_slides),
            unique_uuid_lookup=len(all_uuid_ids),
            unique_prefix_lookup=len(all_prefix_ids),
        )
    except Exception as exc:
        logger.warning("normative_ref_enrich_failed", error=str(exc))

    # FIX #29.4 (2026-05-26): gate "partial" per corsi con troppi moduli degradati.
    # Un modulo è degradato quando ha meno slide del previsto (batch falliti o
    # under-cardinalità). Se > 30% dei moduli è degradato il corso NON è
    # `completed` ma `partial` — l'RSPP deve sapere che va revisionato a fondo.
    total_modules = len(modules_sorted)
    degraded_modules = 0
    for m in modules_sorted:
        # Stima: un modulo è degradato se ha < 80% delle slide attese (~21/27 a 45s).
        # Soglia conservativa — meglio un partial in più che un completed mascherato.
        n_slides = len(m.get("slides", []))
        expected = m.get("expected_slides") or 27
        if n_slides < int(expected * 0.8):
            degraded_modules += 1
    degraded_ratio = degraded_modules / max(total_modules, 1)
    course_final_status = "partial" if degraded_ratio > 0.30 else "completed"
    logger.info(
        "course_quality_gate",
        course_id=str(course_id),
        total_modules=total_modules,
        degraded_modules=degraded_modules,
        degraded_ratio=round(degraded_ratio, 2),
        final_status=course_final_status,
    )

    # ═══ CRASH-SAFE SAVE (slides JSON + fingerprint BEFORE the build) ═══
    await db.execute(
        "UPDATE courses SET slide_contents_json = $1 WHERE id = $2",
        json.dumps(all_slides),
        course_id,
    )

    fingerprint = build_normative_fingerprint(all_slides)
    chunk_ids = sorted(
        {
            cid
            for s in all_slides
            if isinstance(s, dict)
            for cid in (s.get("source_chunk_ids") or [])
        }
    )
    await db.execute(
        "UPDATE courses SET normative_fingerprint=$1, source_chunk_ids=$2 WHERE id=$3",
        json.dumps(fingerprint),
        chunk_ids,
        course_id,
    )

    await db.execute(
        "UPDATE generation_jobs SET status='building' WHERE id=$1", job_id
    )

    # ═══ IMAGE PRE-FETCH (BP §07.0) ═══
    slide_models = [SlideContent(**s) for s in all_slides]
    image_map = await prefetch_images(slide_models, db)

    # FIX 2026-05-31: prefetch_images muta slide_models[i].image.query_url
    # (tier-0 library hit / tier-1 web URL). all_slides salvato a riga 600 ha
    # query_url=null per TUTTE le slide perche' il save e' PRIMA del prefetch
    # (necessario per crash-safety: se prefetch crash, le slide sono almeno
    # salvate). Risincronizziamo all_slides DOPO prefetch cosi' l'UI Studio
    # mostra image.url popolato + image_picker Library tab puo' detect hit.
    all_slides = [s.model_dump() for s in slide_models]
    await db.execute(
        "UPDATE courses SET slide_contents_json = $1 WHERE id = $2",
        json.dumps(all_slides),
        course_id,
    )

    # ═══ PRODUCTION BUILD (PPTX + PDF — audio spostato in background, FIX #31 MOSSA 3) ═══
    builder = ProductionBuilder(brand_config=brand)
    pptx_path, pdf_path, _report = await builder.build(
        slides=slide_models,
        course=course,
        job_id=job_id,
        ws_callback=send_ws_progress,
        image_map=image_map,
        db=db,
    )

    elapsed = time.time() - start_time

    # ═══ FINAL DB STATE per PPTX/PDF — utente può scaricare SUBITO ═══
    # (FIX #29.4: status può essere 'completed' o 'partial'; FIX #31 MOSSA 3:
    #  l'audio non è più nel percorso critico, parte come task background dopo)
    await db.execute(
        "UPDATE courses SET pptx_path=$1, pdf_path=$2, status=$4 WHERE id=$3",
        str(pptx_path),
        str(pdf_path),
        course_id,
        course_final_status,
    )
    await db.execute(
        "UPDATE generation_jobs SET status='completed', completed_at=NOW(), "
        "progress_percent=100 WHERE id=$1",
        job_id,
    )

    # ═══ TELEMETRY → audit_log ═══
    audio_requested = "audio" in course.get("outputs", [])
    await db.execute(
        "INSERT INTO audit_log (action, entity_type, entity_id, details) "
        "VALUES ('pipeline_metrics', 'course', $1, $2)",
        course_id,
        json.dumps(
            {
                "elapsed_seconds": round(elapsed, 1),  # SOLO PPTX+PDF, audio escluso
                "total_slides": len(all_slides),
                "images_resolved": len(image_map),
                "audio_in_background": audio_requested,
            }
        ),
    )

    logger.info(
        "pipeline_completed",
        job_id=job_id,
        slides=len(all_slides),
        elapsed_seconds=round(elapsed, 1),
        audio_in_background=audio_requested,
    )

    # ═══ AUDIO BACKGROUND TASK (FIX #31 MOSSA 3) ═══
    # L'utente ora vede PPTX/PDF immediatamente. audio_manifest_path resta
    # NULL fino al completamento (front-end polla ogni 5s, timeout 5 min).
    # Eccezioni dentro la task NON propagano: vengono loggate con course_id
    # e classe errore, è l'UNICA osservabilità su NULL=fallito (limite
    # accettato analista — vedi #R-audio-bg-no-recovery in VERIFICATION_DEBT).
    # Strong-ref tramite _BACKGROUND_TASKS set + done_callback per prevenire
    # GC silent-death del task.
    if audio_requested:
        from app.services.audio_service import AudioService

        audio_service = AudioService(voice=settings.tts_voice)

        async def _bg_audio() -> None:
            bg_start = time.time()
            try:
                logger.info(
                    "audio_bg_started",
                    course_id=str(course_id),
                    slides=len(slide_models),
                )
                await audio_service.generate_narrations(
                    slide_models, str(course_id), db
                )
                logger.info(
                    "audio_bg_completed",
                    course_id=str(course_id),
                    elapsed_seconds=round(time.time() - bg_start, 1),
                )
            except Exception as exc:
                logger.error(
                    "audio_bg_failed",
                    course_id=str(course_id),
                    error_class=type(exc).__name__,
                    error_msg=str(exc)[:300],
                    elapsed_before_failure=round(time.time() - bg_start, 1),
                )
                # audio_manifest_path resta NULL → FE timeout 5 min mostrerà
                # "audio non disponibile". Il log qui è l'unica fonte per
                # capire COSA è fallito.

        task = asyncio.create_task(_bg_audio(), name=f"audio_bg_{course_id}")
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)


async def recover_interrupted_jobs(pool: asyncpg.Pool) -> None:
    """v1.0: reset every job stuck mid-flight to 'failed' + sync course status.

    Prima del fix 2026-05-31: solo generation_jobs aggiornato. Bug rilevato:
    se backend restart durante content/building, courses.status restava su
    'content' forever -> UI mostrava status fake "in corso" pero' il job
    era failed da ore. Adesso anche courses.status sincronizzata a 'failed'
    cosi' utente vede il vero stato e puo' archiviare/riprovare.

    La smarter LangGraph-checkpoint resume lands in v1.1 (BP §09.2)."""
    # 1. Trova jobs orfani prima di marcarli failed (per loggare corso owner)
    orphan_courses = await pool.fetch(
        "SELECT DISTINCT course_id FROM generation_jobs "
        "WHERE status IN ('research', 'content', 'building')"
    )
    # 2. Marca jobs failed
    result_jobs = await pool.execute(
        "UPDATE generation_jobs SET status='failed', "
        "error_message='Interrotto da restart server' "
        "WHERE status IN ('research', 'content', 'building')"
    )
    # 3. Sync courses.status: solo i courses con job failed
    # (NON archiviati / NON completed). Status 'failed' fa apparire l'icona
    # rossa nel CourseDetail + abilita "Rigenera" CTA.
    if orphan_courses:
        course_ids = [r["course_id"] for r in orphan_courses]
        result_courses = await pool.execute(
            "UPDATE courses SET status='failed' "
            "WHERE id = ANY($1::uuid[]) "
            "AND status IN ('research', 'content', 'building', 'skeleton_pending')",
            course_ids,
        )
        if result_jobs != "UPDATE 0" or result_courses != "UPDATE 0":
            logger.warning(
                "jobs_recovered_to_failed",
                jobs_result=result_jobs,
                courses_result=result_courses,
                n_orphan_courses=len(orphan_courses),
            )


__all__ = [
    "MAX_CONCURRENT_JOBS",
    "PIPELINE_TIMEOUT_SECONDS",
    "build_normative_fingerprint",
    "recover_interrupted_jobs",
    "run_pipeline",
    "send_ws_progress",
]
