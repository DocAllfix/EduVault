"""Tests for KnowledgeRepository (PHASE 2.5).

The pool is stubbed with AsyncMock — same pattern as test_auth/test_seed
(pytest runs against mocks, never a live DB; HANDOFF gotcha #4). Live DB
exercise of the vector query happens in the E2E smoke tests (2.6 / FASE 5).

Covered:
- resolve_slugs_to_ids: returns UUIDs / raises ValueError on missing slug
- search_chunks: builds NormativeChunk list, embedding serialized to pgvector
  literal, regional JOIN present in SQL
- get_style_patterns: ORDER BY certified_at DESC LIMIT 5, JSON decoded
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from app.models.core import ChunkType
from app.models.knowledge import NormativeChunk, StylePattern
from app.services.knowledge_repo import KnowledgeRepository, _to_pgvector

REG_UUID = "11111111-1111-1111-1111-111111111111"
CHUNK_UUID = "22222222-2222-2222-2222-222222222222"


# ─────────── _to_pgvector ───────────


def test_to_pgvector_formats_literal() -> None:
    assert _to_pgvector([0.1, 0.2, 0.3]) == "[0.1,0.2,0.3]"


def test_to_pgvector_empty() -> None:
    assert _to_pgvector([]) == "[]"


# ─────────── resolve_slugs_to_ids ───────────


async def test_resolve_slugs_returns_ids() -> None:
    pool = AsyncMock()
    pool.fetch = AsyncMock(
        return_value=[
            {"id": REG_UUID, "slug": "dm_388_2003"},
            {"id": "33333333-3333-3333-3333-333333333333", "slug": "dlgs_81_08"},
        ]
    )
    repo = KnowledgeRepository(pool)

    ids = await repo.resolve_slugs_to_ids(["dm_388_2003", "dlgs_81_08"])

    assert ids == [REG_UUID, "33333333-3333-3333-3333-333333333333"]


async def test_resolve_slugs_raises_on_missing() -> None:
    pool = AsyncMock()
    # DB returns only one of the two requested slugs.
    pool.fetch = AsyncMock(return_value=[{"id": REG_UUID, "slug": "dm_388_2003"}])
    repo = KnowledgeRepository(pool)

    with pytest.raises(ValueError) as excinfo:
        await repo.resolve_slugs_to_ids(["dm_388_2003", "slug_inesistente"])

    assert "slug_inesistente" in str(excinfo.value)


# ─────────── search_chunks ───────────


def _chunk_row(score: float) -> dict[str, object]:
    return {
        "id": CHUNK_UUID,
        "regulation_id": REG_UUID,
        "article": "Art. 1",
        "paragraph": "Comma 1",
        "hierarchy_path": "Art. 1 > Comma 1",
        "body": "Le aziende sono classificate in tre gruppi.",
        "chunk_type": "GENERALE",
        "tags": ["primo_soccorso"],
        "relevance_score": score,
    }


async def test_search_chunks_maps_to_normative_chunk() -> None:
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[_chunk_row(0.87)])
    repo = KnowledgeRepository(pool)

    chunks = await repo.search_chunks([0.1] * 1024, [REG_UUID], "NAZIONALE", top_k=30)

    assert len(chunks) == 1
    c = chunks[0]
    assert isinstance(c, NormativeChunk)
    assert c.chunk_id == CHUNK_UUID
    assert c.chunk_type == ChunkType.GENERALE
    assert c.relevance_score == pytest.approx(0.87)
    assert c.tags == ["primo_soccorso"]


async def test_search_chunks_passes_pgvector_literal_and_regional_join() -> None:
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    repo = KnowledgeRepository(pool)

    await repo.search_chunks([0.5, 0.6], [REG_UUID], "CAMPANIA", top_k=10)

    # Inspect the SQL and bound params asyncpg received.
    args = pool.fetch.await_args.args
    sql, embedding_param, ids_param, region_param, top_k_param = args
    assert "JOIN regulations r" in sql
    # D-168 (2026-05-30): NAZIONALE + EUROPEA always pass; region-specific
    # only when matching. Pre-fix was `r.region = 'NAZIONALE' OR ...`.
    assert "r.region IN ('NAZIONALE', 'EUROPEA')" in sql
    assert "<=> $1::vector" in sql
    assert embedding_param == "[0.5,0.6]"  # serialized, not raw list
    assert region_param == "CAMPANIA"
    assert top_k_param == 10


async def test_search_chunks_unknown_region_does_not_raise() -> None:
    """Documents the contract: unknown region is NOT validated here.

    The query passes through; only NAZIONALE chunks would match in a real
    DB. Hard validation of "regional course + non-regional region" lives
    in research_agent (BP §05.4, FASE 3.3), not in this repository.
    """
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    repo = KnowledgeRepository(pool)

    # Must NOT raise on a region that does not exist in the DB.
    chunks = await repo.search_chunks([0.1], [REG_UUID], "ATLANTIDE")
    assert chunks == []
    region_arg = pool.fetch.await_args.args[3]
    assert region_arg == "ATLANTIDE"  # passed through verbatim, not sanitized


async def test_search_chunks_handles_null_tags() -> None:
    row = _chunk_row(0.5)
    row["tags"] = None  # asyncpg may return NULL array as None
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[row])
    repo = KnowledgeRepository(pool)

    chunks = await repo.search_chunks([0.1], [REG_UUID], "NAZIONALE")

    assert chunks[0].tags == []


# ─────────── get_style_patterns ───────────


async def test_get_style_patterns_decodes_json_ordered() -> None:
    pattern = {
        "avg_words_per_slide": 70,
        "preferred_slide_sequence": ["CONTENT_TEXT", "QUIZ", "RECAP"],
        "tone_register": "tecnico-divulgativo",
        "recurring_section_titles": ["Introduzione", "Riepilogo"],
        "avg_quiz_per_module": 1.5,
        "preferred_image_ratio": 0.2,
    }
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[{"style_pattern": json.dumps(pattern)}])
    repo = KnowledgeRepository(pool)

    patterns = await repo.get_style_patterns("primo_soccorso_gruppo_b_c", "discente")

    assert len(patterns) == 1
    assert isinstance(patterns[0], StylePattern)
    assert patterns[0].avg_words_per_slide == 70
    # Verify the query enforces recency ordering + cap.
    sql = pool.fetch.await_args.args[0]
    assert "ORDER BY certified_at DESC" in sql
    assert "LIMIT 5" in sql


async def test_get_style_patterns_empty() -> None:
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    repo = KnowledgeRepository(pool)

    patterns = await repo.get_style_patterns("preposti", "formatore")

    assert patterns == []
