"""D3 — Narrative skeleton service (vast-hopping-sketch, post-review-17).

Two responsibilities:

1. ``generate_module_skeleton`` — 1 instructor structured call producing a
   ``ModuleSkeleton`` (6-10 ordered sub-topics) for a module. The skeleton is a
   TAXONOMIC map of the module, generated from the domain + the module's place
   in the course — NOT from corpus chunks. This is the analyst's grounding
   decision (a): "the skeleton is a taxonomy, not a corpus extraction". Feeding
   by-title chunks as grounding would re-inject the cross-course contamination
   that D3 exists to remove (the LLM would see a "Modulo A RSPP" chunk in the
   grounding and propose an RSPP sub-topic for Preposti M3). The corpus only
   enters at retrieval time, per sub-topic.

2. ``materialize_module_from_skeleton`` — for each approved sub-topic, run a
   DEDICATED retrieval via ``retrieval_v2.retrieve_for_subtopic`` passing
   ``item.retrieval_query`` directly (D-170 fix: NO autogen re-formulation,
   the query is already semantic, written by instructor structured). Dedup
   into the same ``dict[int, list[NormativeChunk]]`` contract that
   ``content_agent`` already consumes — so content_agent is unchanged.

Provider: Azure ``gpt-4.1-mini`` (the content/structured chain), NOT DeepSeek —
DeepSeek rejects forced ``tool_choice`` and instructor Mode.TOOLS fails on it
(see ingestion_service `_FALLBACK_CHAIN_CONTENT` and the note at its definition).

Everything behind ``settings.v2_features['skeleton_validation']`` at the call
sites (generation_service); this module is pure logic with no flag check of its
own.
"""

from __future__ import annotations

import structlog

from app.config import settings
from app.models.knowledge import NormativeChunk
from app.models.pipeline import ModuleSkeleton
from app.services.ingestion_service import (
    _FALLBACK_CHAIN_CONTENT,
    _INSTRUCTOR_DEPTH_RETRIES,
    _instructor_client_for,
)
from app.services.knowledge_repo import KnowledgeRepository
from app.services.pipeline_telemetry import PipelinePhase, timed

logger = structlog.get_logger(__name__)


# Number of sub-topics we ask the LLM to produce. The Pydantic model enforces
# 6-10; we nudge toward the middle in the prompt so a module rarely hits the
# 6-floor (too coarse) or the 10-ceiling (too granular for slide pacing).
_SKELETON_TARGET_ITEMS = "6-10"


_SKELETON_SYSTEM = (
    "Sei un progettista esperto di corsi di formazione sulla sicurezza sul "
    "lavoro in Italia (D.Lgs 81/08, Accordi Stato-Regioni, decreti antincendio, "
    "primo soccorso, HACCP). Il tuo compito e' definire la STRUTTURA NARRATIVA "
    "di un modulo: la sequenza ordinata di sotto-temi che un docente esperto "
    "tratterebbe, nell'ordine in cui li tratterebbe. "
    "NON elenchi slide, NON scrivi contenuti: definisci la tassonomia del modulo. "
    "Ogni sotto-tema deve appartenere al PERIMETRO del modulo e del corso indicato: "
    "non sconfinare in argomenti che appartengono ad ALTRI corsi o ad altri moduli "
    "dello stesso corso. Rispetta la progressione didattica (dai concetti generali "
    "ai casi applicativi)."
)


def _build_skeleton_prompt(
    *,
    module_title: str,
    course_type_slug: str,
    course_title: str,
    sibling_module_titles: list[str],
) -> str:
    """Grounding (a): module title + course + sibling module titles. NO chunks.

    The sibling module titles give the LLM the INTER-module boundaries so it
    does not propose a sub-topic that belongs to a different module of the same
    course (e.g. it should not put "Comunicazione con i dirigenti" — which lives
    in another Preposti module — inside "Valutazione dei rischi").
    """
    siblings = "\n".join(f"  - {t}" for t in sibling_module_titles if t != module_title)
    return (
        f"CORSO: {course_title} (slug: {course_type_slug})\n"
        f"MODULO DA STRUTTURARE: {module_title}\n\n"
        f"Altri moduli dello STESSO corso (NON invadere il loro perimetro):\n"
        f"{siblings or '  (nessun altro modulo)'}\n\n"
        f"Genera {_SKELETON_TARGET_ITEMS} sotto-temi ordinati narrativamente per il "
        f"modulo '{module_title}'. Per ogni sotto-tema fornisci:\n"
        f"  - sub_topic: il titolo del sotto-tema (conciso, max 160 caratteri)\n"
        f"  - retrieval_query: una frase di 15-30 parole in italiano che cattura il "
        f"contenuto normativo/tecnico di QUEL sotto-tema, da usare per recuperare i "
        f"passaggi normativi pertinenti (specifica, non generica).\n"
        f"  - ordinal: la posizione 1..N nella sequenza.\n\n"
        f"I sotto-temi devono coprire il modulo in modo completo e non sovrapposto, "
        f"restando dentro il perimetro del corso e del modulo."
    )


async def generate_module_skeleton(
    *,
    module_index: int,
    module_title: str,
    course_type_slug: str,
    course_title: str,
    sibling_module_titles: list[str],
    course_id: str | None = None,
) -> ModuleSkeleton:
    """Generate the narrative skeleton for one module (1 LLM structured call).

    Grounding (a) pura: NO corpus chunks. Walks the content fallback chain
    (Azure mini → OpenAI → Anthropic) so a single provider outage does not block
    skeleton generation. Returns a validated ``ModuleSkeleton`` (6-10 items,
    ordinals normalized 1..N, ``approved=False``).
    """
    prompt = _build_skeleton_prompt(
        module_title=module_title,
        course_type_slug=course_type_slug,
        course_title=course_title,
        sibling_module_titles=sibling_module_titles,
    )

    with timed(
        PipelinePhase.SKELETON_GENERATE,
        course_id=course_id,
        module_idx=module_index,
        module_title=module_title,
        source="llm_content_chain",
    ) as ev:
        last_exc: Exception | None = None
        for provider, deployment_key, level_name in _FALLBACK_CHAIN_CONTENT:
            model_id = getattr(settings, deployment_key, None)
            if not model_id:
                continue
            try:
                client, eff_model, _reask = _instructor_client_for(provider, model_id)
                skeleton: ModuleSkeleton = await client.chat.completions.create(
                    model=eff_model,
                    response_model=ModuleSkeleton,
                    max_retries=_INSTRUCTOR_DEPTH_RETRIES,
                    messages=[
                        {"role": "system", "content": _SKELETON_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                )
                # Force the authoritative module_index/title (the LLM may echo
                # something slightly off); ordinals are already normalized by
                # the model_validator.
                skeleton.module_index = module_index
                skeleton.title = module_title
                ev["provider_used"] = level_name
                ev["items_count"] = len(skeleton.items)
                return skeleton
            except Exception as exc:  # noqa: BLE001 — walk the chain on any failure
                last_exc = exc
                logger.warning(
                    "skeleton_provider_failed",
                    module_index=module_index,
                    provider=level_name,
                    error_class=type(exc).__name__,
                    error_msg=str(exc)[:200],
                )
                continue
        # All providers failed.
        raise RuntimeError(
            f"skeleton generation failed for module {module_index} "
            f"('{module_title}') on all providers"
        ) from last_exc


async def materialize_module_from_skeleton(
    *,
    skeleton: ModuleSkeleton,
    regulation_ids: list[str],
    region: str,
    repo: KnowledgeRepository,
    course_id: str | None = None,
) -> list[NormativeChunk]:
    """Per-sub-topic retrieval → one deduplicated chunk list for the module.

    For each ``SkeletonItem`` we call ``retrieval_v2.retrieve_for_subtopic``
    passing ``item.retrieval_query`` directly: that query is *already* a
    semantic module-query written by instructor structured in the context of
    the specific sub-topic, so we MUST NOT re-formulate it via autogen LLM
    (D-170 lesson 2026-05-30: re-formulating an LLM-written query through a
    second LLM is double LLM, no informational gain, stochasticity injected
    into a path that should be deterministic).

    Results are concatenated preserving rerank order, first-wins on duplicate
    ``chunk_id``. ``relevance_score`` is set from the rerank score so
    downstream audit/quality checks read the same field as the legacy path.

    Returns ``list[NormativeChunk]`` for ONE module (the caller assembles the
    ``dict[int, list[NormativeChunk]]`` across modules).
    """
    # Lazy import to avoid a heavy import at module load when the flag is off.
    from app.services.retrieval_v2 import retrieve_for_subtopic

    seen: set[str] = set()
    out: list[NormativeChunk] = []

    with timed(
        PipelinePhase.SKELETON_GENERATE,
        course_id=course_id,
        module_idx=skeleton.module_index,
        module_title=skeleton.title,
        source="materialize_by_subtopic",
    ) as ev:
        for item in skeleton.items:
            scored = await retrieve_for_subtopic(
                retrieval_query=item.retrieval_query,
                regulation_ids=regulation_ids,
                region=region,
                repo=repo,
                course_id=course_id,
                module_idx=skeleton.module_index,
            )
            for sc in scored:
                if sc.chunk.chunk_id in seen:
                    continue
                seen.add(sc.chunk.chunk_id)
                sc.chunk.relevance_score = sc.score
                out.append(sc.chunk)
        ev["subtopics"] = len(skeleton.items)
        ev["chunks_materialized"] = len(out)
    return out
