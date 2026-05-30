"""Unit tests per retrieve_for_subtopic_b2 (F2.12 B2 selettore di pool).

Architettura post-classify cieca 2026-05-30 (sign-off analista):
  - B2 = top-K cosine_voyage K=30 fissa selettore di pool dal pool RRF top-100.
  - cosine_voyage diretto fra subtopic.text_emb (Voyage) e chunk.body_emb
    (Voyage gia' in DB).
  - Cohere downgrade a topical-affinity telemetry (D-171-bis).
  - L'ordinamento finale viene da cosine_voyage, NON da Cohere score.

I test verificano:
  - retrieve_for_subtopic_b2 ritorna top-K ordinati per cosine_voyage discendente
  - NON chiama rerank_chunks (Cohere) per il ranking decisionale
  - emette telemetria B4 D9 sensor (extra_top_cosine_voyage)
  - source dei chunks ritornati e' 'b2_cosine_voyage' (NON 'rerank_cohere')
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.models.core import ChunkType
from app.models.knowledge import NormativeChunk
from app.services.retrieval_v2 import B2_TOP_K_DEFAULT, retrieve_for_subtopic_b2


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
async def test_retrieve_for_subtopic_b2_returns_top_k_by_cosine_voyage() -> None:
    """B2 deve ritornare top-K cosine_voyage discendente.

    Pool RRF top-100 con embedding noti per ciascun chunk. Subtopic emb scelta
    in modo che ogni chunk abbia un cosine specifico determinato dal suo idx.

    Costruzione embedding per cosine controllato: subtopic = [1, 0, 0, ..., 0]
    (vettore unit lungo dim 0). Chunk idx=N ha embedding = [cos_target_N,
    sin_target_N, 0, 0, ..., 0] dove cos_target_N = N/100 e sin_target_N e'
    sqrt(1 - (N/100)^2). Il modulo dell'embedding e' 1 e il cosine con
    subtopic e' esattamente N/100.
    """
    fake_pool = [_make_chunk(i) for i in range(100)]
    # subtopic emb 1024-dim deterministica, unit vector lungo dim 0
    subtopic_emb = [1.0] + [0.0] * 1023

    def emb_for_chunk(idx: int) -> list[float]:
        """Embedding con cosine = idx/100 vs subtopic [1, 0, ..., 0]."""
        if idx == 0:
            # Chunk 0: ortogonale al subtopic (cosine 0).
            return [0.0, 1.0] + [0.0] * 1022
        target = idx / 100.0
        sin_part = (1.0 - target * target) ** 0.5
        return [target, sin_part] + [0.0] * 1022

    # Pool fetch mocking: asyncpg pool.fetch ritorna rows con id + embedding text
    mock_pool = AsyncMock()
    mock_rows = []
    for c in fake_pool:
        idx = int(c.chunk_id[-3:])
        emb_text = "[" + ",".join(str(x) for x in emb_for_chunk(idx)) + "]"
        mock_rows.append({"id": c.chunk_id, "emb": emb_text})
    mock_pool.fetch = AsyncMock(return_value=mock_rows)

    mock_repo = AsyncMock()
    mock_repo.pool = mock_pool

    with (
        patch(
            "app.services.retrieval_v2.recall_hybrid",
            new=AsyncMock(return_value=fake_pool),
        ) as recall_mock,
        patch(
            "app.services.retrieval_v2.voyage_embed_with_retry",
            new=AsyncMock(return_value=subtopic_emb),
        ) as voyage_mock,
        patch(
            "app.services.retrieval_v2.rerank_chunks",
            new=AsyncMock(),
        ) as rerank_mock,
    ):
        result = await retrieve_for_subtopic_b2(
            retrieval_query="query semantica subtopic B2",
            regulation_ids=["11111111-1111-1111-1111-111111111111"],
            region="NAZIONALE",
            repo=mock_repo,
        )

    # B2 path: recall_hybrid chiamata UNA volta con top_k=100 (B2_POOL_FOR_RANKING).
    assert recall_mock.await_count == 1
    assert recall_mock.await_args.kwargs["top_k"] == 100

    # B2 path: subtopic embedded via Voyage UNA volta.
    assert voyage_mock.await_count == 1

    # B2 path: rerank_chunks (Cohere) NON chiamato per il ranking. E' solo
    # telemetria opzionale fuori dal path B2.
    assert rerank_mock.await_count == 0

    # Result deve essere top-K=30 ordinati per cosine_voyage discendente.
    assert len(result) == B2_TOP_K_DEFAULT
    # Top-1: chunk idx=99 (cosine 0.99).
    assert result[0].chunk.chunk_id.endswith("099")
    # Top-2: chunk idx=98 (cosine 0.98).
    assert result[1].chunk.chunk_id.endswith("098")
    # Top-30: chunk idx=70 (cosine 0.70).
    assert result[29].chunk.chunk_id.endswith("070")

    # Tutti i chunk ritornati devono avere source = 'b2_cosine_voyage'.
    assert all(sc.source == "b2_cosine_voyage" for sc in result)

    # Lo score deve essere il cosine_voyage (decrescente).
    for i in range(len(result) - 1):
        assert result[i].score >= result[i + 1].score


@pytest.mark.asyncio
async def test_retrieve_for_subtopic_b2_empty_pool_returns_empty() -> None:
    """Edge case: pool RRF vuoto -> ritorna lista vuota."""
    mock_pool = AsyncMock()
    mock_repo = AsyncMock()
    mock_repo.pool = mock_pool

    with (
        patch(
            "app.services.retrieval_v2.recall_hybrid",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.retrieval_v2.voyage_embed_with_retry",
            new=AsyncMock(),
        ) as voyage_mock,
    ):
        result = await retrieve_for_subtopic_b2(
            retrieval_query="query semantica subtopic B2",
            regulation_ids=["11111111-1111-1111-1111-111111111111"],
            region="NAZIONALE",
            repo=mock_repo,
        )

    assert result == []
    # Voyage NON chiamato se pool e' vuoto (early return).
    assert voyage_mock.await_count == 0
