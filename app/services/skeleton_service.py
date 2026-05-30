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
) -> tuple[dict[int, list[NormativeChunk]], list[NormativeChunk]]:
    """Per-sub-topic retrieval → (per-voce dict, modulo-deduped list).

    H8 (2026-05-31): return cambiato da ``list[NormativeChunk]`` a tuple
    ``(dict_per_voce, list_deduped)`` per supportare il vincolo voce-to-slide
    nel content_agent. Sample-read M0 post-V1.5 ha confermato per la terza
    volta che il drift voce-to-slide e' patologia strutturale: 1.2% on-topic
    core su 84 slide. Cura: ogni voce dello skeleton diventa cluster di slide.

    Return structure:
      - ``chunks_by_voice: dict[int, list[NormativeChunk]]``: key = item.ordinal
        (1-based), value = chunks per quella voce nel pool ranked. H8 content_agent
        itera questo dict per generare cluster di slide per voce.
      - ``chunks_module_dedup: list[NormativeChunk]``: union dedup di tutti i pool
        (legacy format, preservato per popolare ``CourseContext.chunks_by_module``
        ai fini telemetria/audit e per fallback path non-H8).

    For each ``SkeletonItem`` we call ``retrieval_v2.retrieve_for_subtopic``
    passing ``item.retrieval_query`` directly: that query is *already* a
    semantic module-query written by instructor structured in the context of
    the specific sub-topic, so we MUST NOT re-formulate it via autogen LLM
    (D-170 lesson 2026-05-30: re-formulating an LLM-written query through a
    second LLM is double LLM, no informational gain, stochasticity injected
    into a path that should be deterministic).

    F2.12 B2 path (flag v2_b2_cosine_selector_enabled):
      Quando il flag e' on, sostituisce Cohere rerank con cosine_voyage diretto
      come selettore di pool top-K. Post-D-171-bis closure (analista
      2026-05-30): cosine_voyage e' selettore di pool affidabile (ratio
      A1_useful/B_useful >= 2.3x sui 5 moduli classify ciecamente disciplinati),
      Cohere downgrade a topical-affinity telemetry.

    Results are concatenated preserving rank order, first-wins on duplicate
    ``chunk_id`` per il modulo-dedup. Il dict per-voce mantiene chunks
    completi (non dedup cross-voce: i duplicati cross-voce sono semanticamente
    legittimi e il content_agent li gestisce a livello cluster).
    """
    from app.config import settings

    # Branch su flag B2/B3/B4. Lazy import per non aumentare il footprint quando OFF.
    # Ordine architetturale (analista H7 2026-05-30): B2 selettore + B3 decay +
    # B4 corpus-thin SEMPRE in serie, mai stadi successivi da soli (richiedono
    # output dello stadio precedente).
    # F2.14 B4 (analista 2026-05-30 (c) Caso 1): wrapper b2_b3_b4 ritorna tuple
    # (chunks, b4_decisions); per uniformare la firma del retriever con i path
    # legacy, qui usiamo un closure adapter che scarta il secondo elemento.
    from typing import Awaitable, Callable
    from app.services.retrieval_v2 import ScoredChunk as _ScoredChunk

    _Retriever = Callable[..., Awaitable[list[_ScoredChunk]]]

    if (
        settings.v2_b4_corpus_thin_enabled
        and settings.v2_b3_cross_title_decay_enabled
        and settings.v2_b2_cosine_selector_enabled
    ):
        from app.services.retrieval_v2 import retrieve_for_subtopic_b2_b3_b4 as _retriever_b4

        async def _retriever(**kwargs: object) -> list[_ScoredChunk]:
            # Estrae voice_idx dai kwargs per propagarlo a B4
            survivors, _b4_decisions = await _retriever_b4(**kwargs)  # type: ignore[arg-type]
            return survivors
    elif settings.v2_b3_cross_title_decay_enabled and settings.v2_b2_cosine_selector_enabled:
        from app.services.retrieval_v2 import retrieve_for_subtopic_b2_b3 as _retriever  # type: ignore[assignment]
    elif settings.v2_b2_cosine_selector_enabled:
        from app.services.retrieval_v2 import retrieve_for_subtopic_b2 as _retriever  # type: ignore[assignment]
    else:
        from app.services.retrieval_v2 import retrieve_for_subtopic as _retriever  # type: ignore[assignment]

    seen: set[str] = set()
    out: list[NormativeChunk] = []
    chunks_by_voice: dict[int, list[NormativeChunk]] = {}

    with timed(
        PipelinePhase.SKELETON_GENERATE,
        course_id=course_id,
        module_idx=skeleton.module_index,
        module_title=skeleton.title,
        source=(
            "materialize_by_subtopic_b2"
            if settings.v2_b2_cosine_selector_enabled
            else "materialize_by_subtopic"
        ),
    ) as ev:
        for item in skeleton.items:
            # F2.14 B4: passa voice_idx per log strutturato per voce.
            # I retriever B2/B3 ignorano voice_idx (kwargs extra), il
            # wrapper b2_b3_b4 lo usa per la telemetria B4.
            scored = await _retriever(
                retrieval_query=item.retrieval_query,
                regulation_ids=regulation_ids,
                region=region,
                repo=repo,
                course_id=course_id,
                module_idx=skeleton.module_index,
                voice_idx=item.ordinal,
            ) if settings.v2_b4_corpus_thin_enabled and settings.v2_b3_cross_title_decay_enabled and settings.v2_b2_cosine_selector_enabled else await _retriever(
                retrieval_query=item.retrieval_query,
                regulation_ids=regulation_ids,
                region=region,
                repo=repo,
                course_id=course_id,
                module_idx=skeleton.module_index,
            )
            # H8: cattura chunks per voce (NON dedup cross-voce: contesto cluster
            # per content_agent). relevance_score impostato su tutti per audit
            # downstream coerente col path legacy.
            voce_chunks: list[NormativeChunk] = []
            for sc in scored:
                sc.chunk.relevance_score = sc.score
                voce_chunks.append(sc.chunk)
                # Dedup module-level (first-wins su chunk_id) per il list legacy
                if sc.chunk.chunk_id not in seen:
                    seen.add(sc.chunk.chunk_id)
                    out.append(sc.chunk)
            chunks_by_voice[item.ordinal] = voce_chunks
        ev["subtopics"] = len(skeleton.items)
        ev["chunks_materialized"] = len(out)
        ev["chunks_by_voice_voices"] = len(chunks_by_voice)
        ev["chunks_by_voice_total"] = sum(len(v) for v in chunks_by_voice.values())
    return chunks_by_voice, out
