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

import json

import structlog

from app.agents.pipeline import NexusPipelineState
from app.agents.prompts import (
    build_content_system_prompt,
    build_module_prompt,
    build_previous_summary,
)
from app.models.pipeline import (
    CourseContext,
    ModuleContent,
    PacingPlan,
    SlideContent,
)
from app.models.requests import CourseRequest
from app.services.ingestion_service import call_llm

logger = structlog.get_logger()


def parse_slides_json(raw: str) -> list[dict[str, object]] | None:
    """Robust JSON parsing with markdown-fence cleanup (BP §05.5).

    Strips a leading ``\\`\\`\\`json ... \\`\\`\\``` wrapper if present, then
    json.loads. Returns ``None`` on parse failure so the caller can drive a
    corrective retry.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        return None
    except json.JSONDecodeError:
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

    completed: list[dict[str, object]] = []
    failed_count = 0  # ← FIX-3: INLINE counter, no class.
    start_index = state.get("current_module_index", 0)

    for module in pacing.modules[start_index:]:
        # Chunks already grouped by the Research Agent
        module_chunks = context.chunks_by_module.get(module.module_index, [])

        # Recap of prior modules (titles + key points, not full text)
        previous_summary = build_previous_summary(
            list(state.get("completed_modules", [])) + completed
        )

        # Prompt selection by target
        system_prompt = build_content_system_prompt(request.target)
        user_prompt = build_module_prompt(
            module=module,
            chunks=module_chunks,
            style_patterns=context.style_patterns,
            previous_summary=previous_summary,
            target=request.target,
        )

        # LLM call with tenacity retry (3 attempts on 429/500/529 — applied
        # in app.services.ingestion_service.call_llm).
        try:
            raw_response = await call_llm(
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
            )
        except Exception as e:
            logger.error("module_llm_failed", module_index=module.module_index, error=str(e))
            failed_count += 1
            continue

        # JSON parsing with one corrective retry (BP §05.5)
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
            logger.error("module_json_failed", module_index=module.module_index)
            failed_count += 1
            continue

        # ═══ OUTPUT VALIDATION (per-slide) ═══
        validated_slides: list[dict[str, object]] = []
        for s in slides:
            try:
                validated_slides.append(SlideContent(**s).model_dump())
            except Exception as e:
                logger.warning(
                    "slide_validation_failed",
                    error=str(e),
                    slide=s.get("index") if isinstance(s, dict) else None,
                )

        completed.append(
            ModuleContent(
                module_index=module.module_index,
                title=module.title,
                slides=[SlideContent(**vs) for vs in validated_slides],
            ).model_dump()
        )

        logger.info(
            "module_completed",
            module=module.module_index,
            slides=len(validated_slides),
        )

    # ═══ INLINE CIRCUIT BREAKER (FIX-3) ═══
    total_modules = len(pacing.modules[start_index:])
    if failed_count > total_modules * 0.5:
        raise RuntimeError(
            f"Circuit breaker: {failed_count}/{total_modules} moduli falliti. "
            f"Verificare la qualità dei chunk RAG o lo stato delle API Anthropic."
        )

    return {
        "completed_modules": completed,
        "current_module_index": len(pacing.modules),
    }
