"""FIX #32 (2026-05-27, analista review 12) — test drop-list M1
"Prevenzione e protezione" del corso GENERALE 4h.

Demo #2 v2 ha mostrato che M1 era al 46% off-topic (medico/sorveglianza/
agenti biologici / cartella sanitaria / vaccinazioni). La leva C dedup
quota-aware #31.8 ha bilanciato i numeri ma il contenuto recuperato
era ancora dominato da temi adiacenti perché "Prevenzione" e
"Sorveglianza sanitaria" sono cosine-vicinissimi nel corpus D.Lgs 81/08.

Il drop-list applicato SOLO al modulo "Prevenzione e protezione"
(NON globalmente: in altri moduli del catalog medico/biologico
possono essere on-topic) filtra chunks post-dedup come fatto per
Segnaletica in #31.6D.
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
    """Repo che ritorna chunks_per_query[i] alla i-esima chiamata search_chunks."""
    repo = MagicMock()
    calls: list[dict[str, Any]] = []

    async def _search(*, query_embedding, regulation_ids, region, top_k):
        idx = len(calls)
        calls.append({"top_k": top_k})
        return list(chunks_per_query[idx]) if idx < len(chunks_per_query) else []

    repo.search_chunks = _search
    repo._calls = calls
    return repo


# ─────────────── M1 Prevenzione drop-list tests ───────────────


@pytest.mark.asyncio
async def test_m1_prevenzione_drops_medico_competente() -> None:
    """Modulo "Prevenzione e protezione": chunk con body contenente
    "medico competente" / "sorveglianza sanitaria" viene droppato."""
    plan = _pacing_plan("Prevenzione e protezione")
    repo = _mock_repo(
        [
            [
                _chunk("c1", "Misure tecniche di prevenzione: parapetti, schermi"),
                _chunk(
                    "c2",
                    "Il medico competente esprime giudizio di idoneità annuale",
                ),
                _chunk("c3", "DPI obbligatori per rischio elettrico"),
                _chunk(
                    "c4",
                    "Sorveglianza sanitaria periodica art. 41 D.Lgs 81/08",
                ),
                _chunk("c5", "Procedure operative di sicurezza in cantiere"),
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

    m_prev = result[0]
    body_texts = [c.body for c in m_prev]
    # I 3 chunk on-topic restano
    assert any("Misure tecniche" in b for b in body_texts)
    assert any("DPI obbligatori" in b for b in body_texts)
    assert any("Procedure operative" in b for b in body_texts)
    # I 2 chunk medico/sorveglianza sono droppati
    assert not any("medico competente" in b.lower() for b in body_texts)
    assert not any("sorveglianza sanitaria" in b.lower() for b in body_texts)
    assert len(m_prev) == 3


@pytest.mark.asyncio
async def test_m1_prevenzione_drops_agenti_biologici_e_cartella() -> None:
    """Body con "agenti biologici" / "cartella sanitaria" / "vaccinazione"
    droppato da M1 Prevenzione."""
    plan = _pacing_plan("Prevenzione e protezione")
    repo = _mock_repo(
        [
            [
                _chunk("c1", "Schermature per rischi meccanici"),
                _chunk("c2", "Registro esposizione agenti biologici"),
                _chunk("c3", "Cartella sanitaria del lavoratore esposto"),
                _chunk("c4", "Vaccinazioni obbligatorie per lavoratori sanitari"),
                _chunk(
                    "c5",
                    "Misure cancerogeni e mutageni: sostituzione e contenimento",
                ),
                _chunk("c6", "Interlock di sicurezza su macchine pericolose"),
                _chunk("c7", "Visita medica preventiva e periodica"),
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

    m_prev = result[0]
    body_texts = [c.body for c in m_prev]
    # On-topic restano
    assert any("Schermature" in b for b in body_texts)
    assert any("Interlock" in b for b in body_texts)
    # Off-topic droppati: agenti biologici / cartella sanitaria /
    # vaccinazione / cancerogeni / visita medica
    assert not any("agenti biologici" in b.lower() for b in body_texts)
    assert not any("cartella sanitaria" in b.lower() for b in body_texts)
    assert not any("vaccinazion" in b.lower() for b in body_texts)
    assert not any("cancerogeni e mutageni" in b.lower() for b in body_texts)
    assert not any("visita medica" in b.lower() for b in body_texts)


@pytest.mark.asyncio
async def test_m1_drop_list_NOT_applied_to_other_modules() -> None:
    """Il drop-list NON tocca M0 "Concetti di rischio" o
    M2 "Organizzazione della prevenzione" del corso Generale:
    medico/sorveglianza/biologico sono legittimi in quei moduli."""
    plan = _pacing_plan(
        "Concetti di rischio", "Prevenzione e protezione", "Organizzazione della prevenzione"
    )
    concetti_chunks = [
        _chunk("c1", "Rischio biologico: definizione e classificazione"),
        _chunk("c2", "Sorveglianza sanitaria come parte valutazione rischio"),
    ]
    prev_chunks = [
        _chunk("p1", "Schermi e parapetti per rischio caduta"),
        _chunk("p2", "Sorveglianza sanitaria del lavoratore"),
    ]
    org_chunks = [
        _chunk("o1", "Medico competente: nomina e ruolo nel SPP"),
        _chunk("o2", "RSPP designazione e funzioni"),
    ]
    repo = _mock_repo([concetti_chunks, prev_chunks, org_chunks])

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

    # M0 "Concetti di rischio" NON ha drop-list M1 applicato
    m_concetti = result[0]
    assert len(m_concetti) == 2
    assert any("biologico" in c.body.lower() for c in m_concetti)
    assert any("sorveglianza sanitaria" in c.body.lower() for c in m_concetti)

    # M1 "Prevenzione e protezione" HA drop-list → "sorveglianza" droppato
    m_prev = result[1]
    assert len(m_prev) == 1
    assert m_prev[0].body == "Schermi e parapetti per rischio caduta"

    # M2 "Organizzazione della prevenzione" NON ha drop-list M1 applicato
    m_org = result[2]
    assert len(m_org) == 2
    assert any("Medico competente" in c.body for c in m_org)
    assert any("RSPP" in c.body for c in m_org)


@pytest.mark.asyncio
async def test_m1_drop_list_skipped_when_no_prevenzione_module() -> None:
    """Se pacing_plan non ha modulo 'Prevenzione e protezione',
    drop-list M1 non viene applicato (no errori)."""
    plan = _pacing_plan("Rischi specifici", "DPI", "Segnaletica")
    repo = _mock_repo(
        [
            [_chunk("r1", "Rischi e medico competente")],
            [_chunk("d1", "DPI obbligatori per sorveglianza sanitaria")],
            [_chunk("s1", "Cartelli segnaletica antincendio")],
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

    # M0 "Rischi specifici" non droppato dal pattern M1
    assert len(result[0]) == 1
    assert any("medico" in c.body.lower() for c in result[0])
    # M1 "DPI": qui contiene "sorveglianza sanitaria" ma NON è il modulo
    # M1 di Generale ("Prevenzione e protezione"), quindi drop-list non
    # si applica. NB: il drop-list Segnaletica SÌ si applica al modulo
    # "Segnaletica" (modulo M2 di questo plan, indice 2), ma il chunk
    # s1 "Cartelli segnaletica antincendio" non matcha il pattern
    # Segnaletica (non ha sanzioni/medico/RSPP/etc), quindi resta.
    assert len(result[1]) == 1
    # M2 "Segnaletica" preserva i chunk on-topic
    assert len(result[2]) == 1
