"""FIX #32 LEVA 2 (2026-05-27, analista review 14) — test drop-list
M3 "Incidenti e infortuni mancati" del corso PREPOSTI 8h.

Demo #3 v2 ha mostrato M3 al 47% off-topic (analista classificazione:
ATEX 4 slide, registri tumori cancerogeni 7, attrezzature singole 11,
sostanze cancerogene 5, sorveglianza 7, istituzioni 2). Leva 1 (query
refinement con anchor art. 18/19/29/35/53 D.Lgs) spinge cosine su
contenuto preposto-incident-management, ma il residuo dei 6 cluster
sparsi resta — drop-list mira chirurgicamente i pattern noti.

Applicato SOLO al modulo "Incidenti e infortuni mancati" (NON
globalmente: ATEX/cancerogeni sono on-topic in altri corsi).
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
    return PacingPlan(
        total_slides=sum(m.slide_count for m in modules), modules=modules
    )


def _mock_repo(chunks_per_query: list[list[NormativeChunk]]) -> Any:
    repo = MagicMock()
    calls: list[dict[str, Any]] = []

    async def _search(*, query_embedding, regulation_ids, region, top_k):
        idx = len(calls)
        calls.append({"top_k": top_k})
        return list(chunks_per_query[idx]) if idx < len(chunks_per_query) else []

    repo.search_chunks = _search
    repo._calls = calls
    return repo


# ─────────────── M3 Incidenti drop-list tests ───────────────


@pytest.mark.asyncio
async def test_m3_incidenti_drops_atex_e_cancerogeni() -> None:
    """Modulo M3 "Incidenti e infortuni mancati": chunk con body
    contenente ATEX/atmosfere esplosive/cancerogeni viene droppato."""
    plan = _pacing_plan("Incidenti e infortuni mancati")
    repo = _mock_repo(
        [
            [
                _chunk("c1", "Segnalazione tempestiva del preposto delle deficienze"),
                _chunk("c2", "Zona ATEX classificazione aree pericolose"),
                _chunk("c3", "Riunione periodica andamento infortunistico annuale"),
                _chunk("c4", "Registro tumori professionali aggiornamento"),
                _chunk("c5", "Agenti cancerogeni e mutageni esposizione"),
                _chunk("c6", "Denuncia INAIL infortunio superiore tre giorni"),
                _chunk("c7", "Atmosfere esplosive prevenzione rischio"),
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

    m_inc = result[0]
    body_texts = [c.body for c in m_inc]
    # I 3 chunk on-topic restano
    assert any("Segnalazione tempestiva del preposto" in b for b in body_texts)
    assert any("Riunione periodica andamento" in b for b in body_texts)
    assert any("Denuncia INAIL infortunio" in b for b in body_texts)
    # I 4 chunk ATEX/cancerogeni/tumori sono droppati
    assert not any("ATEX" in b for b in body_texts)
    assert not any("atmosfere esplosive" in b.lower() for b in body_texts)
    assert not any("cancerogeni" in b.lower() for b in body_texts)
    assert not any("registro tumori" in b.lower() for b in body_texts)
    assert len(m_inc) == 3


@pytest.mark.asyncio
async def test_m3_incidenti_drops_medico_cartella_porte() -> None:
    """Body con "medico competente" / "cartella sanitaria" / "porte
    meccaniche" droppato da M3 Incidenti (review 14 aggiunta)."""
    plan = _pacing_plan("Incidenti e infortuni mancati")
    repo = _mock_repo(
        [
            [
                _chunk("c1", "Vigilanza preposto su uso DPI lavoratori"),
                _chunk("c2", "Il medico competente esprime giudizio idoneità"),
                _chunk("c3", "Cartella sanitaria del lavoratore esposto"),
                _chunk("c4", "Porte meccaniche con sistema di blocco"),
                _chunk("c5", "Sorveglianza sanitaria periodica annuale"),
                _chunk("c6", "Aggiornamento DVR a seguito infortunio significativo"),
                _chunk("c7", "Sostanze tossiche valutazione esposizione lavoratori"),
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

    m_inc = result[0]
    body_texts = [c.body for c in m_inc]
    # On-topic restano
    assert any("Vigilanza preposto" in b for b in body_texts)
    assert any("Aggiornamento DVR" in b for b in body_texts)
    # Off-topic droppati: medico/cartella/porte/sorveglianza/sostanze
    assert not any("medico competente" in b.lower() for b in body_texts)
    assert not any("cartella sanitaria" in b.lower() for b in body_texts)
    assert not any("porte meccaniche" in b.lower() for b in body_texts)
    assert not any("sorveglianza sanitaria" in b.lower() for b in body_texts)
    assert not any("sostanze tossiche" in b.lower() for b in body_texts)


@pytest.mark.asyncio
async def test_m3_incidenti_drop_NOT_applied_to_other_modules() -> None:
    """Il drop-list NON tocca altri moduli di Preposti (M0 "Principali
    soggetti", M2 "Fattori di rischio") dove medico/ATEX/cancerogeni
    sono legittimi."""
    plan = _pacing_plan(
        "Principali soggetti del sistema di prevenzione",
        "Definizione e individuazione dei fattori di rischio",
        "Incidenti e infortuni mancati",
    )
    soggetti_chunks = [
        _chunk("s1", "RSPP nomina e funzioni nel servizio prevenzione"),
        _chunk("s2", "Medico competente come soggetto della prevenzione"),
    ]
    fattori_chunks = [
        _chunk("f1", "Atmosfere esplosive come fattore di rischio specifico"),
        _chunk("f2", "Agenti cancerogeni esposizione cronica lavoratori"),
    ]
    incidenti_chunks = [
        _chunk("i1", "Registro infortuni denuncia INAIL obbligatoria"),
        _chunk("i2", "Atmosfere esplosive registro incidenti"),
    ]
    repo = _mock_repo([soggetti_chunks, fattori_chunks, incidenti_chunks])

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

    # M0 "Soggetti" NON ha drop-list applicato → medico competente resta
    m_soggetti = result[0]
    assert len(m_soggetti) == 2
    assert any("Medico competente" in c.body for c in m_soggetti)

    # M1 "Fattori di rischio" NON ha drop-list applicato → ATEX/cancerogeni restano
    m_fattori = result[1]
    assert len(m_fattori) == 2
    assert any("Atmosfere esplosive" in c.body for c in m_fattori)
    assert any("cancerogeni" in c.body.lower() for c in m_fattori)

    # M2 "Incidenti e infortuni mancati" HA drop-list → ATEX droppato
    m_inc = result[2]
    assert len(m_inc) == 1
    assert m_inc[0].body == "Registro infortuni denuncia INAIL obbligatoria"


@pytest.mark.asyncio
async def test_m3_drop_list_skipped_when_no_incidenti_module() -> None:
    """Se pacing_plan non ha modulo 'Incidenti e infortuni mancati',
    drop-list M3 non viene applicato (no errori)."""
    plan = _pacing_plan("Rischi specifici", "DPI", "Procedure di emergenza", "Segnaletica")
    repo = _mock_repo(
        [
            [_chunk("r1", "Rischi ATEX in atmosfere esplosive")],
            [_chunk("d1", "DPI per agenti cancerogeni")],
            [_chunk("e1", "Procedure emergenza zona ATEX")],
            [_chunk("s1", "Cartelli antincendio segnaletica")],
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

    # Nessun modulo "Incidenti e infortuni mancati" → drop-list non scatta
    # Tutti chunk preservati nei moduli specifici (incluso ATEX/cancerogeni
    # che sono on-topic per Rischi specifici / DPI / Emergenza)
    assert any("ATEX" in c.body for c in result[0])
    assert any("cancerogeni" in c.body for c in result[1])
    assert any("ATEX" in c.body for c in result[2])
