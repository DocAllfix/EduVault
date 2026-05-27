"""Cluster A — Live tests against real Postgres + pgvector.

NO MOCKS. Every test in this file connects to the running Postgres
instance via ``asyncpg.create_pool(settings.database_url)`` and exercises
real SQL — including the pgvector ``<=>`` cosine-distance operator on the
HNSW index, the partial unique index on ``content_hash WHERE is_current``,
the ``regulations`` slug lookup, and the ``audit_log`` append-only
trigger.

Skipped by default in CI (``addopts = -m 'not live'`` in pyproject).
Run explicitly inside the backend container:

    docker exec eduvault-backend-1 python -m pytest \
        -m live tests/live/test_cluster_a_db.py -v

Prerequisiti:
- ``docker compose up -d postgres`` (eduvault-postgres-1 healthy)
- ``DATABASE_URL`` env var puntando al pool ``nexus_app`` reale
- migrations applicate (001_initial.sql + setup_roles.sql)
- seed.py eseguito almeno una volta (per il default brand preset)

Ogni test pulisce ciò che inserisce (no cross-contamination tra test).
"""

from __future__ import annotations

import uuid
from typing import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from app.config import settings
from app.services.knowledge_repo import KnowledgeRepository

pytestmark = pytest.mark.live


# ──────────────────────── Helpers ────────────────────────


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    """Real asyncpg pool to the live Postgres instance.

    Closed cleanly at the end of each test.
    """
    p = await asyncpg.create_pool(
        settings.database_url, min_size=1, max_size=4
    )
    assert p is not None
    try:
        yield p
    finally:
        await p.close()


def _random_vector(dim: int = 1024) -> list[float]:
    """Deterministic-enough vector for tests (not a real embedding)."""
    import random
    rng = random.Random(42)
    return [rng.uniform(-1.0, 1.0) for _ in range(dim)]


def _to_pgvector(vec: list[float]) -> str:
    """Mirror of knowledge_repo._to_pgvector — the literal format pgvector
    accepts for explicit ``::vector`` casts."""
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


# ──────────────────────── Test 1: pool connect + SELECT 1 ────────────────────────


async def test_a01_pool_connect_and_select_one(pool: asyncpg.Pool) -> None:
    """Sanity check: pool can connect, basic SELECT works."""
    result = await pool.fetchval("SELECT 1")
    assert result == 1


async def test_a02_pool_uses_nexus_app_role(pool: asyncpg.Pool) -> None:
    """Verify we connect as the restricted nexus_app role (not admin)."""
    role = await pool.fetchval("SELECT current_user")
    assert role == "nexus_app", f"expected nexus_app, got {role}"


# ──────────────────────── Test 3: pgvector extension present ────────────────────────


async def test_a03_pgvector_extension_installed(pool: asyncpg.Pool) -> None:
    """pgvector must be installed; otherwise embeddings ::vector cast fails."""
    ext = await pool.fetchval(
        "SELECT extname FROM pg_extension WHERE extname = 'vector'"
    )
    assert ext == "vector", "pgvector extension not installed"


# ──────────────────────── Test 4: schema enforcement ────────────────────────


async def test_a04_regulation_chunks_schema_matches_pydantic(
    pool: asyncpg.Pool,
) -> None:
    """The 5 chunk_type values must match the Pydantic enum exactly."""
    rows = await pool.fetch(
        """
        SELECT pg_get_constraintdef(c.oid) AS def
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        WHERE t.relname = 'regulation_chunks'
          AND c.conname LIKE '%chunk_type%'
        """
    )
    assert rows, "chunk_type CHECK constraint not found"
    cdef = rows[0]["def"]
    for expected in ("OBBLIGO", "SANZIONE", "DEFINIZIONE", "PROCEDURA", "GENERALE"):
        assert expected in cdef, f"missing {expected} in CHECK constraint"


async def test_a05_embedding_column_dim_is_1024(pool: asyncpg.Pool) -> None:
    """Voyage voyage-3 produces 1024-dim vectors; the column must match."""
    type_str = await pool.fetchval(
        """
        SELECT format_type(a.atttypid, a.atttypmod)
        FROM pg_attribute a
        JOIN pg_class t ON a.attrelid = t.oid
        WHERE t.relname = 'regulation_chunks' AND a.attname = 'embedding'
        """
    )
    assert type_str == "vector(1024)", f"got {type_str}"


# ──────────────────────── Test 6-7: indexes ────────────────────────


async def test_a06_hnsw_index_on_embedding(pool: asyncpg.Pool) -> None:
    """The HNSW index must exist with cosine ops, else search degrades to seq scan."""
    idx_def = await pool.fetchval(
        """
        SELECT indexdef FROM pg_indexes
        WHERE indexname = 'idx_chunks_embedding'
        """
    )
    assert idx_def is not None, "idx_chunks_embedding not found"
    assert "hnsw" in idx_def.lower(), f"not HNSW: {idx_def}"
    assert "vector_cosine_ops" in idx_def, f"not cosine: {idx_def}"


async def test_a07_partial_unique_on_content_hash(pool: asyncpg.Pool) -> None:
    """Partial UNIQUE index on content_hash WHERE is_current=true must exist."""
    idx_def = await pool.fetchval(
        """
        SELECT indexdef FROM pg_indexes
        WHERE indexname = 'idx_chunks_content_hash'
        """
    )
    assert idx_def is not None, "idx_chunks_content_hash not found"
    assert "UNIQUE" in idx_def, f"not UNIQUE: {idx_def}"
    assert "is_current" in idx_def, f"not partial on is_current: {idx_def}"


# ──────────────────────── Test 8: knowledge_repo.resolve_slugs ────────────────────────


async def test_a08_resolve_slugs_returns_real_ids(pool: asyncpg.Pool) -> None:
    """Insert 2 regolamenti, resolve_slugs_to_ids must return their UUIDs."""
    slug_a = f"test_a_{uuid.uuid4().hex[:8]}"
    slug_b = f"test_b_{uuid.uuid4().hex[:8]}"
    id_a = await pool.fetchval(
        "INSERT INTO regulations (slug, title, type, region, status) "
        "VALUES ($1, $2, 'DECRETO', 'NAZIONALE', 'VIGENTE') RETURNING id",
        slug_a, "Test reg A",
    )
    id_b = await pool.fetchval(
        "INSERT INTO regulations (slug, title, type, region, status) "
        "VALUES ($1, $2, 'DECRETO', 'NAZIONALE', 'VIGENTE') RETURNING id",
        slug_b, "Test reg B",
    )
    try:
        repo = KnowledgeRepository(pool)
        resolved = await repo.resolve_slugs_to_ids([slug_a, slug_b])
        # returns list[str] of UUIDs
        assert len(resolved) == 2
        resolved_uuids = {uuid.UUID(s) for s in resolved}
        assert {id_a, id_b} == resolved_uuids
    finally:
        await pool.execute(
            "DELETE FROM regulations WHERE id = ANY($1::uuid[])", [id_a, id_b]
        )


async def test_a09_resolve_slugs_raises_on_missing(pool: asyncpg.Pool) -> None:
    """An unknown slug must raise (research_agent relies on this guard)."""
    repo = KnowledgeRepository(pool)
    with pytest.raises(ValueError, match="non trovati"):
        await repo.resolve_slugs_to_ids(
            [f"never_exists_{uuid.uuid4().hex[:8]}"]
        )


# ──────────────────────── Test 10-11: search_chunks pgvector ────────────────────────


async def test_a10_search_chunks_uses_pgvector_distance(
    pool: asyncpg.Pool,
) -> None:
    """Insert 3 chunk with vectors, query with cosine distance, verify
    the closest comes back first."""
    slug = f"search_test_{uuid.uuid4().hex[:8]}"
    reg_id = await pool.fetchval(
        "INSERT INTO regulations (slug, title, type, region, status) "
        "VALUES ($1, 'Search test', 'DECRETO', 'NAZIONALE', 'VIGENTE') "
        "RETURNING id",
        slug,
    )
    try:
        # 3 chunk con vettori distinti
        v1 = [1.0] + [0.0] * 1023  # vector "1"
        v2 = [0.0, 1.0] + [0.0] * 1022  # ortogonale a v1
        v3 = [0.9, 0.1] + [0.0] * 1022  # vicino a v1, lontano da v2

        ids = []
        for body, vec in [("A", v1), ("B", v2), ("C", v3)]:
            cid = await pool.fetchval(
                """
                INSERT INTO regulation_chunks
                    (regulation_id, hierarchy_path, body, chunk_type, embedding, content_hash)
                VALUES ($1, $2, $3, 'GENERALE', $4::vector, $5)
                RETURNING id
                """,
                reg_id, f"Art. {body}", body, _to_pgvector(vec),
                f"hash_{uuid.uuid4().hex}",
            )
            ids.append(cid)

        # Query con vector molto vicino a v1 → ranking atteso: A, C, B
        query_vec = [0.95, 0.05] + [0.0] * 1022
        rows = await pool.fetch(
            """
            SELECT body FROM regulation_chunks
            WHERE regulation_id = $1
            ORDER BY embedding <=> $2::vector
            LIMIT 3
            """,
            reg_id, _to_pgvector(query_vec),
        )
        order = [r["body"] for r in rows]
        assert order[0] == "A", f"expected A first, got {order}"
        # B (ortogonale) deve essere ultimo
        assert order[-1] == "B", f"expected B last, got {order}"
    finally:
        await pool.execute("DELETE FROM regulations WHERE id = $1", reg_id)


async def test_a11_search_chunks_via_knowledge_repo_function(
    pool: asyncpg.Pool,
) -> None:
    """The high-level search_chunks() function must work against real DB +
    return NormativeChunk dataclass instances."""
    slug = f"krepo_{uuid.uuid4().hex[:8]}"
    reg_id = await pool.fetchval(
        "INSERT INTO regulations (slug, title, type, region, status) "
        "VALUES ($1, 'KRepo test', 'DECRETO', 'NAZIONALE', 'VIGENTE') "
        "RETURNING id",
        slug,
    )
    try:
        cid = await pool.fetchval(
            """
            INSERT INTO regulation_chunks
                (regulation_id, hierarchy_path, body, chunk_type, tags,
                 embedding, content_hash)
            VALUES ($1, 'Art. 1', 'Testo articolo 1', 'OBBLIGO',
                    ARRAY['formazione', 'lavoratori']::text[],
                    $2::vector, $3)
            RETURNING id
            """,
            reg_id,
            _to_pgvector(_random_vector()),
            f"hash_{uuid.uuid4().hex}",
        )

        query_vec = _random_vector()
        repo = KnowledgeRepository(pool)
        chunks = await repo.search_chunks(
            query_embedding=query_vec,
            regulation_ids=[str(reg_id)],
            region="NAZIONALE",
            top_k=5,
        )
        # _ = chunks  # touch
        assert len(chunks) >= 1
        # Verifica mapping a NormativeChunk
        found = next((c for c in chunks if str(c.chunk_id) == str(cid)), None)
        assert found is not None, "inserted chunk not returned"
        assert found.hierarchy_path == "Art. 1"
        assert found.body == "Testo articolo 1"
        assert found.chunk_type == "OBBLIGO"
        assert "formazione" in found.tags
    finally:
        await pool.execute("DELETE FROM regulations WHERE id = $1", reg_id)


# ──────────────────────── Test 12: partial unique dedup ────────────────────────


async def test_a12_partial_unique_blocks_duplicate_content_hash(
    pool: asyncpg.Pool,
) -> None:
    """Inserting two chunks with same content_hash + is_current=true must
    raise. Inserting one with is_current=false bypasses the unique."""
    slug = f"dedup_{uuid.uuid4().hex[:8]}"
    reg_id = await pool.fetchval(
        "INSERT INTO regulations (slug, title, type, region, status) "
        "VALUES ($1, 'Dedup test', 'DECRETO', 'NAZIONALE', 'VIGENTE') "
        "RETURNING id",
        slug,
    )
    try:
        hash_v = f"hash_{uuid.uuid4().hex}"
        vec = _to_pgvector(_random_vector())
        # First insert is_current=true OK
        await pool.execute(
            """
            INSERT INTO regulation_chunks
                (regulation_id, body, chunk_type, embedding, content_hash, is_current)
            VALUES ($1, 'first', 'GENERALE', $2::vector, $3, true)
            """,
            reg_id, vec, hash_v,
        )
        # Second insert with same hash + is_current=true MUST FAIL
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await pool.execute(
                """
                INSERT INTO regulation_chunks
                    (regulation_id, body, chunk_type, embedding, content_hash, is_current)
                VALUES ($1, 'second', 'GENERALE', $2::vector, $3, true)
                """,
                reg_id, vec, hash_v,
            )
        # Third insert with is_current=false is allowed (partial index)
        await pool.execute(
            """
            INSERT INTO regulation_chunks
                (regulation_id, body, chunk_type, embedding, content_hash, is_current)
            VALUES ($1, 'third superseded', 'GENERALE', $2::vector, $3, false)
            """,
            reg_id, vec, hash_v,
        )
    finally:
        await pool.execute("DELETE FROM regulations WHERE id = $1", reg_id)


# ──────────────────────── Test 13: audit_log append-only ────────────────────────


async def test_a13_audit_log_blocks_update_and_delete(
    pool: asyncpg.Pool,
) -> None:
    """audit_log must be append-only for nexus_app role (UPDATE/DELETE/
    TRUNCATE must fail with permission denied). BP §16 audit-first.

    Schema reale (001_initial.sql): user_id uuid nullable, action varchar,
    details jsonb. NO ``actor`` column.
    """
    # INSERT OK (user_id NULL allowed)
    audit_id = await pool.fetchval(
        """
        INSERT INTO audit_log (user_id, action, details)
        VALUES (NULL, 'cluster_a_test', '{"k":"v"}'::jsonb)
        RETURNING id
        """
    )
    assert audit_id is not None
    # UPDATE must be denied
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        await pool.execute(
            "UPDATE audit_log SET action = 'tampered' WHERE id = $1",
            audit_id,
        )
    # DELETE must be denied
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        await pool.execute(
            "DELETE FROM audit_log WHERE id = $1", audit_id
        )
    # TRUNCATE must be denied
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        await pool.execute("TRUNCATE audit_log")
    # We can't DELETE as nexus_app — leave the row (small + test-tagged).


# ──────────────────────── Test 14: trigger updated_at ────────────────────────


async def test_a14_regulations_trigger_updates_updated_at(
    pool: asyncpg.Pool,
) -> None:
    """The trg_regulations_updated trigger must bump updated_at on UPDATE."""
    slug = f"trg_{uuid.uuid4().hex[:8]}"
    reg_id = await pool.fetchval(
        "INSERT INTO regulations (slug, title, type, region, status) "
        "VALUES ($1, 'Trg test', 'DECRETO', 'NAZIONALE', 'VIGENTE') "
        "RETURNING id",
        slug,
    )
    try:
        row = await pool.fetchrow(
            "SELECT created_at, updated_at FROM regulations WHERE id = $1",
            reg_id,
        )
        original_updated = row["updated_at"]
        # Sleep brief + UPDATE
        import asyncio
        await asyncio.sleep(0.01)
        await pool.execute(
            "UPDATE regulations SET title = 'updated' WHERE id = $1", reg_id
        )
        new_updated = await pool.fetchval(
            "SELECT updated_at FROM regulations WHERE id = $1", reg_id
        )
        assert new_updated > original_updated, (
            f"trigger did not bump updated_at: {original_updated} -> {new_updated}"
        )
    finally:
        await pool.execute("DELETE FROM regulations WHERE id = $1", reg_id)


# ──────────────────────── Test 15: bootstrap admin user exists ────────────────────────


async def test_a15_bootstrap_admin_user_exists(pool: asyncpg.Pool) -> None:
    """seed.py should have created the admin user; this test ensures the
    project's auth flow has at least one valid user to log in with."""
    row = await pool.fetchrow(
        "SELECT email, role, is_active FROM users WHERE role = 'admin' LIMIT 1"
    )
    assert row is not None, "no admin user seeded"
    assert row["is_active"] is True
    assert row["role"] == "admin"
