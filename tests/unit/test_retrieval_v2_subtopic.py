"""Unit tests per retrieve_for_subtopic (D3 path, D-170 fix).

L'analista 2026-05-30: la disciplina "stesso input -> stesso output entro
epsilon Cohere" e' la spina dorsale della calibrazione B2. Questi test
verificano la proprieta' architetturale (autogen NON viene invocato sul
path D3) — la ripetibilita' al jitter Cohere si verifica in E2E successivo,
non qui (no rete in unit test).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.models.core import ChunkType
from app.models.knowledge import NormativeChunk
from app.services.retrieval_v2 import ScoredChunk, retrieve_for_subtopic


def _make_chunk(idx: int) -> NormativeChunk:
    return NormativeChunk(
        chunk_id=f"00000000-0000-0000-0000-{idx:012d}",
        regulation_id="11111111-1111-1111-1111-111111111111",
        article=f"Art. {idx}",
        paragraph="",
        hierarchy_path=f"art{idx}",
        body=f"body chunk {idx}",
        chunk_type=ChunkType.GENERALE,
        tags=[],
        relevance_score=0.0,
    )


@pytest.mark.asyncio
async def test_retrieve_for_subtopic_does_not_call_autogen() -> None:
    """D-170 property: il path D3 NON deve invocare autogen LLM.

    La retrieval_query e' gia' una module-query semantica scritta da instructor
    structured, riformularla via LLM e' doppio LLM senza guadagno informativo
    e introduce stocasticita' (top_score osservato da 0.339 a 0.642 su HACCP
    M3 voce 1 fra due run con stessa query in input).
    """
    repo = AsyncMock()
    fake_chunks = [_make_chunk(i) for i in range(3)]
    fake_scored = [
        ScoredChunk(chunk=c, score=0.9 - i * 0.1, source="rerank_cohere")
        for i, c in enumerate(fake_chunks)
    ]

    with (
        patch(
            "app.services.retrieval_v2.autogen_module_query",
            new=AsyncMock(return_value="NEVER_CALLED"),
        ) as autogen_mock,
        patch(
            "app.services.retrieval_v2.recall_hybrid",
            new=AsyncMock(return_value=fake_chunks),
        ) as recall_mock,
        patch(
            "app.services.retrieval_v2.rerank_chunks",
            new=AsyncMock(return_value=fake_scored),
        ) as rerank_mock,
    ):
        result = await retrieve_for_subtopic(
            retrieval_query="query semantica gia' scritta da instructor",
            regulation_ids=["11111111-1111-1111-1111-111111111111"],
            region="NAZIONALE",
            repo=repo,
        )

    autogen_mock.assert_not_awaited()
    assert recall_mock.await_count == 1
    assert rerank_mock.await_count == 1
    # La query passata a recall_hybrid DEVE essere quella in input, NON una
    # riformulazione.
    assert recall_mock.await_args.kwargs["query"] == (
        "query semantica gia' scritta da instructor"
    )
    assert rerank_mock.await_args.kwargs["query"] == (
        "query semantica gia' scritta da instructor"
    )
    assert len(result) == 3
    assert all(sc.source == "rerank_cohere" for sc in result)


@pytest.mark.asyncio
async def test_retrieve_for_module_still_calls_autogen() -> None:
    """Regression: il path V2 by-title legacy continua a fare autogen.

    Garantisce che il refactor D-170 non abbia rotto il path non-D3 (usato dal
    research_agent quando il flag skeleton_validation e' OFF).
    """
    from app.services.retrieval_v2 import retrieve_for_module

    repo = AsyncMock()
    fake_chunks = [_make_chunk(i) for i in range(2)]
    fake_scored = [
        ScoredChunk(chunk=c, score=0.8 - i * 0.1, source="rerank_cohere")
        for i, c in enumerate(fake_chunks)
    ]

    with (
        patch(
            "app.services.retrieval_v2.autogen_module_query",
            new=AsyncMock(return_value="query autogen-riformulata dal LLM"),
        ) as autogen_mock,
        patch(
            "app.services.retrieval_v2.recall_hybrid",
            new=AsyncMock(return_value=fake_chunks),
        ) as recall_mock,
        patch(
            "app.services.retrieval_v2.rerank_chunks",
            new=AsyncMock(return_value=fake_scored),
        ),
    ):
        await retrieve_for_module(
            module_title="Prevenzione e protezione",
            course_target="discente",
            normative_slug="dlgs_81_08",
            regulation_ids=["11111111-1111-1111-1111-111111111111"],
            region="NAZIONALE",
            repo=repo,
        )

    autogen_mock.assert_awaited_once()
    # La query passata a recall_hybrid DEVE essere l'output autogen, NON il
    # module_title grezzo.
    assert recall_mock.await_args.kwargs["query"] == (
        "query autogen-riformulata dal LLM"
    )
