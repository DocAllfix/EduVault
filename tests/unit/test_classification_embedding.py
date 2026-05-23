"""Unit tests for ingestion Stage 3 + Stage 4 (PHASE 2.3).

LLM and Voyage are mocked — no network. Covers:
- classify_chunk: JSON parse + SANZIONE rule-based downgrade
- embed_batch / voyage_embed_with_retry via mocked Voyage client
- index_chunks: batch INSERT + content_hash dedup skip
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from app.services import ingestion_service as ing

REG_ID = "00000000-0000-0000-0000-000000000001"


# ─────────── classify_chunk ───────────


async def test_classify_chunk_parses_json() -> None:
    payload = json.dumps({"type": "OBBLIGO", "tags": ["datore_lavoro", "formazione"]})
    with patch.object(ing, "call_llm", AsyncMock(return_value=payload)):
        result = await ing.classify_chunk("Il datore di lavoro deve garantire la formazione.")
    assert result["type"] == "OBBLIGO"
    assert result["tags"] == ["datore_lavoro", "formazione"]


async def test_classify_chunk_downgrades_false_sanzione() -> None:
    # LLM says SANZIONE but the body has no penalty keyword → downgrade.
    payload = json.dumps({"type": "SANZIONE", "tags": ["lavoratori"]})
    body = "Il lavoratore partecipa ai programmi di formazione organizzati dal datore."
    with patch.object(ing, "call_llm", AsyncMock(return_value=payload)):
        result = await ing.classify_chunk(body)
    assert result["type"] == "GENERALE"


async def test_classify_chunk_keeps_true_sanzione() -> None:
    payload = json.dumps({"type": "SANZIONE", "tags": ["datore_lavoro"]})
    body = "Il datore di lavoro è punito con l'arresto o con l'ammenda fino a 6400 euro."
    with patch.object(ing, "call_llm", AsyncMock(return_value=payload)):
        result = await ing.classify_chunk(body)
    assert result["type"] == "SANZIONE"


# ─────────── embed_batch / voyage_embed_with_retry ───────────


def _voyage_stub(dim: int = 1024) -> AsyncMock:
    """Voyage client whose embed() returns one vector per input text."""
    client = AsyncMock()

    async def _embed(texts: list[str], model: str) -> object:
        resp = AsyncMock()
        resp.embeddings = [[0.1] * dim for _ in texts]
        return resp

    client.embed = _embed
    return client


async def test_embed_batch_returns_one_vector_per_text() -> None:
    with patch.object(ing, "get_voyage_client", return_value=_voyage_stub()):
        vectors = await ing.embed_batch(["alpha", "beta", "gamma"])
    assert len(vectors) == 3
    assert all(len(v) == 1024 for v in vectors)


async def test_voyage_embed_with_retry_returns_single_vector() -> None:
    with patch.object(ing, "get_voyage_client", return_value=_voyage_stub()):
        vector = await ing.voyage_embed_with_retry("una query semantica")
    assert len(vector) == 1024


# ─────────── index_chunks ───────────


def _classified_chunk(body: str) -> dict[str, object]:
    return {
        "regulation_id": REG_ID,
        "article": "Art. 1",
        "paragraph": None,
        "hierarchy_path": "Art. 1",
        "body": body,
        "classification": {"type": "OBBLIGO", "tags": ["formazione"]},
    }


async def test_index_chunks_inserts_new_chunks() -> None:
    chunks = [_classified_chunk("corpo primo"), _classified_chunk("corpo secondo")]
    pool = AsyncMock()
    pool.fetchval = AsyncMock(return_value=None)  # nothing exists → all new
    pool.execute = AsyncMock(return_value="INSERT 0 1")

    with patch.object(ing, "get_voyage_client", return_value=_voyage_stub()):
        await ing.index_chunks(chunks, pool)

    assert pool.execute.await_count == 2  # one INSERT per chunk


async def test_index_chunks_skips_duplicates() -> None:
    chunks = [_classified_chunk("corpo identico"), _classified_chunk("corpo nuovo")]
    pool = AsyncMock()
    # First chunk already exists, second does not.
    pool.fetchval = AsyncMock(side_effect=["existing-uuid", None])
    pool.execute = AsyncMock(return_value="INSERT 0 1")

    with patch.object(ing, "get_voyage_client", return_value=_voyage_stub()):
        await ing.index_chunks(chunks, pool)

    assert pool.execute.await_count == 1  # only the non-duplicate inserted


async def test_index_chunks_empty_is_noop() -> None:
    pool = AsyncMock()
    with patch.object(ing, "get_voyage_client", return_value=_voyage_stub()):
        await ing.index_chunks([], pool)
    pool.execute.assert_not_awaited()
    pool.fetchval.assert_not_awaited()
