"""Cluster B — Live tests against real Voyage AI + Postgres + pgvector.

NO MOCKS. Calls https://api.voyageai.com with the real key from
settings.voyage_api_key. Then writes the resulting 1024-dim vectors into
the live regulation_chunks table and verifies they're queryable via the
pgvector ``<=>`` operator.

Skipped by default in CI (``addopts = -m 'not live'`` in pyproject).

Prerequisiti: Cluster A passed + VOYAGE_API_KEY valida in .env.

Costo stimato: ~$0.01 totale (4 testi + qualche embed singoli).
"""

from __future__ import annotations

import os
import uuid
from typing import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from app.config import settings
from app.services.dependencies import get_voyage_client, set_voyage_client
from app.services.ingestion_service import (
    embed_batch,
    voyage_embed_with_retry,
    index_chunks,
)
from app.services.knowledge_repo import KnowledgeRepository, _to_pgvector

pytestmark = pytest.mark.live


# Init voyageai client (di solito fatto da app startup; qui lo facciamo
# manuale dato che pytest non lancia l'app FastAPI).
def _ensure_voyage_initialized() -> None:
    try:
        get_voyage_client()
    except RuntimeError:
        import voyageai
        set_voyage_client(voyageai.AsyncClient(api_key=settings.voyage_api_key))


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    p = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=4)
    assert p is not None
    try:
        yield p
    finally:
        await p.close()


# ──────────────────────── Test B1: voyage key present ────────────────────────


async def test_b01_voyage_key_is_real() -> None:
    """Sanity: settings.voyage_api_key must be set and NOT a placeholder."""
    assert settings.voyage_api_key, "VOYAGE_API_KEY not set"
    assert not settings.voyage_api_key.startswith(
        "PLACEHOLDER"
    ), "VOYAGE_API_KEY is still a placeholder"


# ──────────────────────── Test B2-3: embed single + batch ────────────────────────


async def test_b02_embed_batch_returns_one_vector_per_text() -> None:
    """voyage-3 must return exactly one 1024-dim vector per input text."""
    _ensure_voyage_initialized()
    texts = [
        "Il datore di lavoro deve valutare tutti i rischi.",
        "I DPI sono dispositivi di protezione individuale.",
        "L'RSPP coordina il servizio prevenzione e protezione.",
    ]
    vectors = await embed_batch(texts)
    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == 1024
        assert all(isinstance(x, float) for x in v)


async def test_b03_voyage_embed_with_retry_returns_single_vector() -> None:
    """voyage_embed_with_retry wraps embed_batch for the single-query case."""
    _ensure_voyage_initialized()
    vec = await voyage_embed_with_retry("primo soccorso aziendale")
    assert len(vec) == 1024
    assert all(isinstance(x, float) for x in vec)


# ──────────────────────── Test B4: semantic similarity sanity ────────────────────────


async def test_b04_embeddings_capture_semantic_similarity() -> None:
    """Vectors for related concepts must be closer than vectors for
    unrelated concepts (basic sanity that the embedder works)."""
    _ensure_voyage_initialized()
    vecs = await embed_batch([
        "primo soccorso e cassetta medicazioni",   # 0: medical
        "defibrillatore e arresto cardiaco",       # 1: medical (related to 0)
        "impianto elettrico e cavi alta tensione",  # 2: electrical (far from 0/1)
    ])
    import math

    def cos(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb)

    sim_01 = cos(vecs[0], vecs[1])  # medical-medical
    sim_02 = cos(vecs[0], vecs[2])  # medical-electrical
    assert sim_01 > sim_02, (
        f"semantic similarity broken: sim(medical, medical)={sim_01:.3f} "
        f"vs sim(medical, electrical)={sim_02:.3f}"
    )


# ──────────────────────── Test B5: index_chunks against real DB + Voyage ────────────────────────


async def test_b05_index_chunks_writes_real_embeddings_to_pgvector(
    pool: asyncpg.Pool,
) -> None:
    """index_chunks() must embed via real Voyage, dedup via content_hash,
    insert with pgvector cast. Verify retrievability."""
    _ensure_voyage_initialized()
    # Setup: regulation
    slug = f"index_{uuid.uuid4().hex[:8]}"
    reg_id = await pool.fetchval(
        "INSERT INTO regulations (slug, title, type, region, status) "
        "VALUES ($1, 'Cluster B', 'DECRETO', 'NAZIONALE', 'VIGENTE') "
        "RETURNING id",
        slug,
    )
    try:
        # 3 chunk pre-classified (manualmente, perché classification è
        # Cluster C). Lo schema input di index_chunks: dict con keys
        # regulation_id, hierarchy_path, body, chunk_type, tags, content_hash
        import hashlib
        chunks_input = []
        for i, body in enumerate([
            "Il datore di lavoro nomina il medico competente.",
            "Le visite mediche sono effettuate periodicamente.",
            "Il medico esprime giudizio di idoneità.",
        ]):
            chunks_input.append({
                "regulation_id": str(reg_id),
                "article": f"Art. {41 + i}",
                "paragraph": "1",
                "hierarchy_path": f"Art. {41 + i}, comma 1",
                "body": body,
                "content_hash": hashlib.sha256(body.encode()).hexdigest(),
                "classification": {
                    "type": "OBBLIGO",
                    "tags": ["medico", "sorveglianza_sanitaria"],
                },
            })

        # Esegui ingestione reale (embedding + insert)
        await index_chunks(chunks_input, pool)

        # Verifica: 3 chunk in DB con embedding non-NULL
        rows = await pool.fetch(
            "SELECT id, body, embedding IS NOT NULL AS has_emb, tags "
            "FROM regulation_chunks WHERE regulation_id = $1",
            reg_id,
        )
        assert len(rows) == 3, f"expected 3, got {len(rows)}"
        for r in rows:
            assert r["has_emb"], f"chunk {r['id']} has NULL embedding"
            assert "medico" in r["tags"]

        # Vector search reale: query "sorveglianza sanitaria del lavoratore"
        # → uno dei 3 chunks deve emergere primo (semantic match)
        repo = KnowledgeRepository(pool)
        query_vec = await voyage_embed_with_retry(
            "sorveglianza sanitaria e visita medica"
        )
        retrieved = await repo.search_chunks(
            query_embedding=query_vec,
            regulation_ids=[str(reg_id)],
            region="NAZIONALE",
            top_k=3,
        )
        assert len(retrieved) == 3
        # Il chunk top deve avere relevance_score > 0.5 (cosine match decente)
        assert retrieved[0].relevance_score > 0.5, (
            f"top match score too low: {retrieved[0].relevance_score}"
        )
    finally:
        await pool.execute("DELETE FROM regulations WHERE id = $1", reg_id)


# ──────────────────────── Test B6: dedup via content_hash ────────────────────────


async def test_b06_index_chunks_skips_duplicates(pool: asyncpg.Pool) -> None:
    """Re-indexing identical body must skip (dedup via content_hash)."""
    _ensure_voyage_initialized()
    slug = f"dedup_b_{uuid.uuid4().hex[:8]}"
    reg_id = await pool.fetchval(
        "INSERT INTO regulations (slug, title, type, region, status) "
        "VALUES ($1, 'Dedup B', 'DECRETO', 'NAZIONALE', 'VIGENTE') "
        "RETURNING id",
        slug,
    )
    try:
        import hashlib
        body = "Chunk duplicato test B6"
        h = hashlib.sha256(body.encode()).hexdigest()
        chunk = {
            "regulation_id": str(reg_id),
            "article": "Art. 1",
            "paragraph": "1",
            "hierarchy_path": "Art. 1",
            "body": body,
            "content_hash": h,
            "classification": {"type": "GENERALE", "tags": []},
        }
        # Prima ingestione: OK
        await index_chunks([chunk], pool)
        count1 = await pool.fetchval(
            "SELECT COUNT(*) FROM regulation_chunks WHERE regulation_id = $1",
            reg_id,
        )
        assert count1 == 1
        # Seconda ingestione stesso chunk: deve essere dedupato
        await index_chunks([chunk], pool)
        count2 = await pool.fetchval(
            "SELECT COUNT(*) FROM regulation_chunks WHERE regulation_id = $1",
            reg_id,
        )
        assert count2 == 1, f"dedup failed: {count2} rows for same hash"
    finally:
        await pool.execute("DELETE FROM regulations WHERE id = $1", reg_id)
