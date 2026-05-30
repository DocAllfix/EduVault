"""Unit tests per D-161 effective_until filter in knowledge_repo.

Architettura D-161 (analista sign-off 2026-05-30):
  - regulations.effective_until DATE NULL: data fino a cui regulation
    applicabile. NULL = vigente indefinito.
  - Filtro retrieval default: ``effective_until IS NULL OR > now()``.
  - Override via param ``include_abrogated=True`` per corsi pedagogici.
  - Lezione D-168: filtro al join SQL, NON in-Python post-fetch.

Test verificano:
  - resolve_slugs_to_ids passa include_abrogated come param SQL $2.
  - resolve_slugs_to_ids default include_abrogated=False.
  - search_chunks passa include_abrogated come param SQL $5.
  - search_chunks default include_abrogated=False.
  - SQL emesso contiene clause effective_until su entrambi i path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.knowledge_repo import KnowledgeRepository


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    return pool


@pytest.mark.asyncio
async def test_resolve_slugs_default_excludes_abrogated(mock_pool: AsyncMock) -> None:
    """Default ``include_abrogated=False`` deve passare False come $2 SQL."""
    repo = KnowledgeRepository(mock_pool)
    with pytest.raises(ValueError):
        # slug list non vuota ma fetch ritorna [] -> missing slugs -> raise
        await repo.resolve_slugs_to_ids(["accordo_stato_regioni_2011"])

    args = mock_pool.fetch.call_args
    sql = args.args[0]
    assert "effective_until" in sql
    assert "$2::bool" in sql
    # Param $2 = include_abrogated default False
    assert args.args[2] is False


@pytest.mark.asyncio
async def test_resolve_slugs_include_abrogated_true(mock_pool: AsyncMock) -> None:
    """include_abrogated=True deve passare True come $2 SQL."""
    repo = KnowledgeRepository(mock_pool)
    with pytest.raises(ValueError):
        await repo.resolve_slugs_to_ids(
            ["accordo_stato_regioni_2011"],
            include_abrogated=True,
        )

    args = mock_pool.fetch.call_args
    assert args.args[2] is True


@pytest.mark.asyncio
async def test_search_chunks_default_excludes_abrogated(mock_pool: AsyncMock) -> None:
    """Default ``include_abrogated=False`` deve passare False come $5 SQL."""
    repo = KnowledgeRepository(mock_pool)
    await repo.search_chunks(
        query_embedding=[0.1] * 1024,
        regulation_ids=["00000000-0000-0000-0000-000000000001"],
        region="NAZIONALE",
        top_k=10,
    )

    args = mock_pool.fetch.call_args
    sql = args.args[0]
    assert "effective_until" in sql
    assert "$5::bool" in sql
    # Args: ($1=embedding_str, $2=regulation_ids, $3=region, $4=top_k, $5=include_abrogated)
    assert args.args[5] is False


@pytest.mark.asyncio
async def test_search_chunks_include_abrogated_true(mock_pool: AsyncMock) -> None:
    """include_abrogated=True deve passare True come $5 SQL."""
    repo = KnowledgeRepository(mock_pool)
    await repo.search_chunks(
        query_embedding=[0.1] * 1024,
        regulation_ids=["00000000-0000-0000-0000-000000000001"],
        region="NAZIONALE",
        top_k=10,
        include_abrogated=True,
    )

    args = mock_pool.fetch.call_args
    assert args.args[5] is True


@pytest.mark.asyncio
async def test_search_chunks_sql_clause_format(mock_pool: AsyncMock) -> None:
    """SQL emesso contiene la clause completa effective_until al join SQL."""
    repo = KnowledgeRepository(mock_pool)
    await repo.search_chunks(
        query_embedding=[0.1] * 1024,
        regulation_ids=["00000000-0000-0000-0000-000000000001"],
        region="NAZIONALE",
        top_k=10,
    )

    sql = mock_pool.fetch.call_args.args[0]
    # Lezione D-168: filtro al join SQL, mai in-Python post-fetch.
    assert "r.effective_until IS NULL OR r.effective_until > now()" in sql
