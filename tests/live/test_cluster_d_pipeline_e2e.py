"""Cluster D — Live pipeline E2E test.

NO MOCKS. Full chain:
 1. CourseRequest → research_agent (Voyage embed + pgvector search + chunk distribution)
 2. → content_agent (Sonnet 4.6 slide generation, 1 LLM call per modulo)
 3. → LangGraph checkpointer Postgres (state persistence between nodes)
 4. → result has completed_modules with slides anchored to real chunks

Prerequisiti:
 - Cluster A/B/C verdi (DB, Voyage, Anthropic working)
 - DM 388/2003 ingerito (slug='dm_388_2003')
 - D.Lgs 81/2008 ingerito (slug='dlgs_81_08')
 - LangGraph checkpoint tables setup (#R11)

Costo stimato: ~$0.50-1.00 (12 chiamate Sonnet 4.6 per un corso 12h primo_soccorso).

NOTA tempo: 5-15 minuti reali. NON è un test rapido.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio
import voyageai

from app.agents.pipeline import create_pipeline
from app.config import settings
from app.services.dependencies import set_pool, set_voyage_client

pytestmark = pytest.mark.live


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    p = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    set_pool(p)
    set_voyage_client(voyageai.AsyncClient(api_key=settings.voyage_api_key))
    try:
        yield p
    finally:
        await p.close()


async def test_d01_pipeline_e2e_dm388_only_real(
    pool: asyncpg.Pool,
) -> None:
    """End-to-end pipeline: research + content + checkpoint persistence,
    contro Voyage + Anthropic + Postgres + chunks REALI di DM 388/2003.

    Course: primo_soccorso_test_dm388_only (1h → 120 slide → 3 moduli ~40 slide cad.).
    Tempo atteso: 3-8 minuti reali. Costo: ~$0.10-0.30.

    Test minimo per chiudere Cluster D senza richiedere ingest D.Lgs 81 (581 pp).
    Per il test pipeline completo con corso reale (12h primo_soccorso_gruppo_b_c)
    serve prima ingerire D.Lgs 81 — task FASE 7.
    """
    # Pre-flight: verifica DM 388 ingerito
    reg_count = await pool.fetchval(
        "SELECT COUNT(*) FROM regulations WHERE slug = 'dm_388_2003'"
    )
    if reg_count == 0:
        pytest.skip("dm_388_2003 non ingerito.")

    chunk_count = await pool.fetchval(
        "SELECT COUNT(*) FROM regulation_chunks rc "
        "JOIN regulations r ON rc.regulation_id = r.id "
        "WHERE r.slug = 'dm_388_2003'"
    )
    assert chunk_count >= 10, f"DM 388 ingerito ma solo {chunk_count} chunks"

    course_request: dict[str, object] = {
        "course_type": "primo_soccorso_test_dm388_only",
        "target": "discente",
        "duration_hours": 1.0,
        "region": "NAZIONALE",
        "brand_preset_id": str(uuid.uuid4()),
        "slide_density": "standard",
        "outputs": ["pptx"],
    }
    initial_state: dict[str, object] = {
        "course_request": course_request,
        "course_id": str(uuid.uuid4()),
        "completed_modules": [],
        "errors": [],
    }

    async with create_pipeline(settings.database_url) as graph:
        result = await asyncio.wait_for(
            graph.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": initial_state["course_id"]}},
            ),
            timeout=900,  # 15 min max — parallelizzato con asyncio.gather attesi 3-6 min
        )

    assert "errors" in result
    errors = result["errors"]
    assert not errors, f"pipeline errors: {errors}"

    assert "completed_modules" in result
    modules = result["completed_modules"]
    assert len(modules) >= 2, f"expected >=2 moduli, got {len(modules)}"

    total_slides = 0
    for mod in modules:
        assert "slides" in mod
        assert len(mod["slides"]) > 0, f"module {mod.get('module_index')} vuoto"
        total_slides += len(mod["slides"])

        for slide in mod["slides"]:
            assert slide.get("title"), f"slide senza title: {slide}"
            assert slide.get("body"), f"slide senza body: {slide}"
            assert slide.get("normative_ref"), (
                f"slide senza normative_ref (anti-hallucination violato): {slide}"
            )

    print(
        f"\nPIPELINE E2E COMPLETED: {len(modules)} moduli, "
        f"{total_slides} slide totali"
    )
