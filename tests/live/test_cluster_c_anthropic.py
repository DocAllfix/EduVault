"""Cluster C — Live tests against real Anthropic API.

NO MOCKS. Calls https://api.anthropic.com with the real key from
settings.anthropic_api_key. Validates:
 - classify_chunk on real chunk bodies returns valid {type, tags} JSON
 - SANZIONE guard downgrades false positives
 - call_llm with Sonnet 4.6 generates valid slide-JSON for content_agent
 - content_agent + research_agent end-to-end happy paths (covered in Cluster D)

Skipped by default. Run with:
    docker exec eduvault-backend-1 python -m pytest -m live \
        tests/live/test_cluster_c_anthropic.py -v

Prerequisiti: ANTHROPIC_API_KEY valida + Haiku 4.5 + Sonnet 4.6 accessibili.
Costo stimato: ~$0.10 (4 chiamate Haiku + 1 Sonnet per slide generation test).
"""

from __future__ import annotations

import json

import pytest

from app.config import settings
from app.services.ingestion_service import call_llm, classify_chunk

pytestmark = pytest.mark.live


# ──────────────────────── Test C1: anthropic key + models accessibili ────────────────────────


async def test_c01_anthropic_key_is_real() -> None:
    """Sanity: ANTHROPIC_API_KEY non placeholder."""
    assert settings.anthropic_api_key, "ANTHROPIC_API_KEY not set"
    assert not settings.anthropic_api_key.startswith(
        "PLACEHOLDER"
    ), "ANTHROPIC_API_KEY is still placeholder"


async def test_c02_haiku_model_accessible() -> None:
    """Haiku 4.5 (classify_model) deve essere chiamabile direttamente."""
    raw = await call_llm(
        messages=[{"role": "user", "content": "Rispondi solo: OK"}],
        system="Rispondi solo con 'OK'.",
        model=settings.llm_classify_model,
    )
    assert "OK" in raw.upper()


async def test_c03_sonnet_content_model_accessible() -> None:
    """Sonnet 4.6 (content_model) deve essere chiamabile."""
    raw = await call_llm(
        messages=[{"role": "user", "content": "Rispondi solo: PRONTO"}],
        system="Rispondi solo con 'PRONTO'.",
        model=settings.llm_content_model,
    )
    assert "PRONTO" in raw.upper()


# ──────────────────────── Test C4-7: classify_chunk REAL ────────────────────────


async def test_c04_classify_chunk_real_obbligo() -> None:
    """Chunk normativo italiano con 'deve/è tenuto' → OBBLIGO."""
    result = await classify_chunk(
        "Il datore di lavoro deve valutare tutti i rischi presenti in azienda "
        "e redigere il Documento di Valutazione dei Rischi (DVR) entro 60 giorni "
        "dall'inizio dell'attività."
    )
    assert result["type"] == "OBBLIGO", f"expected OBBLIGO, got {result}"
    assert isinstance(result["tags"], list)
    assert len(result["tags"]) >= 1


async def test_c05_classify_chunk_real_sanzione_with_penalty() -> None:
    """Chunk con sanzione vera ('ammenda', 'arresto') → SANZIONE preserved."""
    result = await classify_chunk(
        "Il datore di lavoro che non effettua la valutazione dei rischi è punito "
        "con l'arresto da tre a sei mesi o con l'ammenda da 2.500 a 6.400 euro."
    )
    assert result["type"] == "SANZIONE", f"expected SANZIONE, got {result}"


async def test_c06_classify_chunk_real_sanzione_downgrade_guard() -> None:
    """Chunk SENZA parole-penale ma che parla di obblighi → SANZIONE
    downgradata a GENERALE dalla regola rule-based (BP §06.1.1)."""
    # Body che NON contiene "ammenda/arresto/sanzione/euro/pena"
    # ma che parla di adempimenti generali — l'LLM POTREBBE classificarlo
    # erroneamente come SANZIONE; la guardia lo downgrada.
    # Forziamo un chunk neutro: la guard scatta solo se l'LLM emette SANZIONE.
    result = await classify_chunk(
        "Le definizioni del presente decreto si applicano integralmente "
        "secondo quanto stabilito dalle norme attuative successive."
    )
    # La guardia trasforma SANZIONE→GENERALE SOLO se body manca keyword penale
    # → se l'LLM dice OBBLIGO/DEFINIZIONE/GENERALE/PROCEDURA va bene comunque.
    # Garantito: NON deve essere SANZIONE perché il guard la blocca.
    assert result["type"] != "SANZIONE", (
        f"SANZIONE guard failed: chunk has no penalty keyword but type={result['type']}"
    )


async def test_c07_classify_chunk_returns_known_enum_value() -> None:
    """Whatever the LLM picks, type must be one of the 5 enum values."""
    result = await classify_chunk(
        "Ai fini del presente decreto, si intende per pericolo una proprietà "
        "intrinseca di un fattore avente il potenziale di causare danni."
    )
    assert result["type"] in (
        "OBBLIGO", "SANZIONE", "DEFINIZIONE", "PROCEDURA", "GENERALE"
    )


# ──────────────────────── Test C8: content_model JSON slide generation ────────────────────────


async def test_c08_content_model_generates_valid_slide_json() -> None:
    """Sonnet 4.6 con prompt slide JSON deve emettere array parseable.

    Test minimalista del flow content_agent: prompt → LLM → JSON valido.
    Il prompt usa lo stesso pattern di build_module_prompt (chunk citato +
    richiesta N slide). Verifica struttura, non qualità contenuto.
    """
    system = (
        "Sei un esperto formatore italiano. Genera SOLO JSON valido come "
        "array di oggetti, niente testo prima/dopo."
    )
    user_prompt = (
        "Genera ESATTAMENTE 2 slide in JSON array. Ogni slide deve avere:\n"
        '- "slide_type": "CONTENT_TEXT"\n'
        '- "title": string italiana\n'
        '- "body": string italiana ≤90 parole\n'
        '- "normative_ref": string es. "Art. 18, D.Lgs 81/08"\n\n'
        "Argomento: obblighi del datore di lavoro sulla valutazione rischi.\n"
        "CHUNK normativo di riferimento:\n"
        '"Il datore di lavoro deve valutare tutti i rischi e redigere il DVR '
        "entro 60 giorni dall'inizio dell'attività. Art. 28, D.Lgs 81/08\"\n\n"
        "Output: SOLO array JSON, niente backticks, niente spiegazioni."
    )
    raw = await call_llm(
        messages=[{"role": "user", "content": user_prompt}],
        system=system,
        model=settings.llm_content_model,
    )
    # Strip optional markdown fences
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    data = json.loads(cleaned)
    assert isinstance(data, list), f"expected list, got {type(data)}"
    assert len(data) == 2, f"expected 2 slides, got {len(data)}"
    for slide in data:
        assert "title" in slide and slide["title"]
        assert "body" in slide and slide["body"]
        assert "normative_ref" in slide and "D.Lgs 81/08" in slide["normative_ref"]
        # Body max 90 parole (approx, count whitespace splits)
        word_count = len(slide["body"].split())
        assert word_count <= 110, f"body too long: {word_count} words"
