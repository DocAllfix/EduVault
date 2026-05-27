"""FIX #31.6D (2026-05-27) — Test drop-list per Segnaletica modulo.

In E2E #24 M3 "Segnaletica" aveva 13 slide off-topic su 84 (15%) per
adiacenza-corpus: il D.Lgs. 81/08 ha cosine alto fra "segnaletica" e
sanzioni/medico/inidoneità/RSPP (parti del Testo Unico semanticamente
vicine).

Il drop-list applicato SOLO al modulo Segnaletica (NON ad altri moduli,
perché "RSPP" è legittimo in M0 Rischi specifici) filtra chunks il cui
body matcha pattern off-topic post-dedup.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.research_agent import retrieve_chunks_per_module
from app.models.core import ChunkType
from app.models.knowledge import NormativeChunk
from app.models.pipeline import ModuleSpec, PacingPlan


def _chunk(cid: str, body: str, score: float = 0.7) -> NormativeChunk:
    return NormativeChunk(
        chunk_id=cid,
        regulation_id="reg-test",
        article="42",
        paragraph="1",
        hierarchy_path="art. 42",
        body=body,
        chunk_type=ChunkType.OBBLIGO,
        tags=[],
        relevance_score=score,
    )


def _pacing_plan(*titles: str) -> PacingPlan:
    modules = [
        ModuleSpec(
            module_index=i,
            title=t,
            slide_count=80,
            slide_distribution={"CONTENT_TEXT": 80},
        )
        for i, t in enumerate(titles)
    ]
    return PacingPlan(total_slides=sum(m.slide_count for m in modules), modules=modules)


def _mock_repo(chunks_per_query: list[list[NormativeChunk]]) -> Any:
    """Repo che ritorna chunks_per_query[i] alla i-esima chiamata search_chunks."""
    repo = MagicMock()
    calls = []

    async def _search(*, query_embedding, regulation_ids, region, top_k):
        idx = len(calls)
        calls.append({"top_k": top_k})
        return list(chunks_per_query[idx]) if idx < len(chunks_per_query) else []

    repo.search_chunks = _search
    repo._calls = calls
    return repo


@pytest.mark.asyncio
async def test_segnaletica_drops_sanzioni_chunks() -> None:
    """Modulo Segnaletica: chunk con body contenente 'sanzioni' viene
    droppato dal pool M3."""
    plan = _pacing_plan("Segnaletica")
    repo = _mock_repo(
        [
            [
                _chunk("c1", "Cartelli di divieto e segnaletica antincendio"),
                _chunk("c2", "Le sanzioni amministrative per mancata segnaletica"),
                _chunk("c3", "Pittogrammi ISO 7010 per emergenza"),
                _chunk("c4", "Sanzioni penali ai sensi dell'art. 56"),
            ]
        ]
    )

    with patch(
        "app.services.ingestion_service.embed_query",
        new=AsyncMock(return_value=[0.1] * 1024),
    ):
        result = await retrieve_chunks_per_module(
            pacing_plan=plan,
            regulation_ids=["reg-test"],
            region="NAZIONALE",
            knowledge_repo=repo,
            top_k_per_module=10,
            min_relevance=0.0,
        )

    m_seg = result[0]
    body_texts = [c.body for c in m_seg]
    # I 2 chunk on-topic restano
    assert any("Cartelli di divieto" in b for b in body_texts)
    assert any("Pittogrammi ISO" in b for b in body_texts)
    # I 2 chunk sanzioni sono droppati
    assert not any("sanzioni amministrative" in b.lower() for b in body_texts)
    assert not any("sanzioni penali" in b.lower() for b in body_texts)
    assert len(m_seg) == 2


@pytest.mark.asyncio
async def test_segnaletica_drops_medico_competente() -> None:
    """Body con 'medico competente' / 'inidoneità' / 'giudizio medico'
    droppato da M3 Segnaletica."""
    plan = _pacing_plan("Segnaletica")
    repo = _mock_repo(
        [
            [
                _chunk("c1", "Colori di sicurezza per cartelli ISO"),
                _chunk("c2", "Il medico competente esprime giudizio di idoneità"),
                _chunk("c3", "Misure in caso di inidoneità del lavoratore"),
                _chunk("c4", "Sorveglianza sanitaria annuale"),
                _chunk("c5", "Segnali gestuali per movimentazione carichi"),
            ]
        ]
    )

    with patch(
        "app.services.ingestion_service.embed_query",
        new=AsyncMock(return_value=[0.1] * 1024),
    ):
        result = await retrieve_chunks_per_module(
            pacing_plan=plan,
            regulation_ids=["reg-test"],
            region="NAZIONALE",
            knowledge_repo=repo,
            top_k_per_module=10,
            min_relevance=0.0,
        )

    m_seg = result[0]
    body_texts = [c.body for c in m_seg]
    # On-topic restano
    assert any("Colori di sicurezza" in b for b in body_texts)
    assert any("Segnali gestuali" in b for b in body_texts)
    # Off-topic droppati: medico competente, inidoneità, sorveglianza sanitaria
    assert not any("medico competent" in b.lower() for b in body_texts)
    assert not any("inidoneità" in b.lower() for b in body_texts)
    assert not any("sorveglianza sanitaria" in b.lower() for b in body_texts)


@pytest.mark.asyncio
async def test_drop_list_NOT_applied_to_other_modules() -> None:
    """Il drop-list NON tocca M0 "Rischi specifici": RSPP/sanzioni
    sono legittimi in quel modulo."""
    plan = _pacing_plan("Rischi specifici", "Segnaletica")
    rischi_chunks = [
        _chunk("r1", "RSPP ha compiti di valutazione rischi"),
        _chunk("r2", "Sanzioni per omessa valutazione del rischio"),
    ]
    seg_chunks = [
        _chunk("s1", "Cartelli antincendio"),
        _chunk("s2", "Sanzioni amministrative segnaletica"),
    ]
    repo = _mock_repo([rischi_chunks, seg_chunks])

    with patch(
        "app.services.ingestion_service.embed_query",
        new=AsyncMock(return_value=[0.1] * 1024),
    ):
        result = await retrieve_chunks_per_module(
            pacing_plan=plan,
            regulation_ids=["reg-test"],
            region="NAZIONALE",
            knowledge_repo=repo,
            top_k_per_module=10,
            min_relevance=0.0,
        )

    # M0 Rischi specifici NON ha drop-list applicato → tutti chunk intatti
    m_rischi = result[0]
    assert len(m_rischi) == 2
    assert any("RSPP" in c.body for c in m_rischi)
    assert any("Sanzioni" in c.body for c in m_rischi)

    # M1 Segnaletica HA drop-list → "Sanzioni amministrative" droppato
    m_seg = result[1]
    assert len(m_seg) == 1
    assert m_seg[0].body == "Cartelli antincendio"


@pytest.mark.asyncio
async def test_drop_list_skipped_when_no_segnaletica_module() -> None:
    """Se pacing_plan non ha modulo 'Segnaletica', drop-list non viene
    applicato a nessuno (no errori)."""
    plan = _pacing_plan("Rischi specifici", "DPI")
    repo = _mock_repo(
        [
            [_chunk("r1", "Rischi e sanzioni del datore")],
            [_chunk("d1", "DPI obbligatori secondo Allegato VIII")],
        ]
    )

    with patch(
        "app.services.ingestion_service.embed_query",
        new=AsyncMock(return_value=[0.1] * 1024),
    ):
        result = await retrieve_chunks_per_module(
            pacing_plan=plan,
            regulation_ids=["reg-test"],
            region="NAZIONALE",
            knowledge_repo=repo,
            top_k_per_module=10,
            min_relevance=0.0,
        )

    # Tutti i chunk preservati: drop-list non si applica
    assert len(result[0]) == 1
    assert len(result[1]) == 1
