"""KnowledgeRepository — RAG retrieval over the normative corpus (BLUEPRINT §06.3).

Hybrid retrieval pattern (semantic vector search + scalar regional filter)
implemented directly on pgvector + asyncpg — NOT via a LangChain retriever
abstraction. The langchain-rag skill informs the approach (consistent
embedding model across index/query = voyage-3/1024, vector+scalar filter),
but the store is our own PostgreSQL HNSW index.
"""

from __future__ import annotations

import json

import asyncpg

from app.models.knowledge import NormativeChunk, StylePattern


def _to_pgvector(embedding: list[float]) -> str:
    """Serialize a float list to the pgvector text literal ``[a,b,c]``.

    asyncpg has no native codec for the ``vector`` type, so the embedding
    is passed as a string and cast with ``$N::vector`` in SQL. This is the
    standard pgvector + asyncpg interop (see REI-16 note in 2.5).
    """
    return "[" + ",".join(str(x) for x in embedding) + "]"


class KnowledgeRepository:
    """Read-side access to regulations, chunks and Level-2 style patterns."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def resolve_slugs_to_ids(
        self,
        slugs: list[str],
        *,
        include_abrogated: bool = False,
    ) -> list[str]:
        """Resolve slugs -> UUIDs with VALIDATION: raise if a slug is missing.

        Without this validation a typo in COURSE_CATALOG would silently
        produce incomplete courses (BP §06.3).

        D-161 (2026-05-30): filtra anche per ``effective_until`` (regulation
        abrogata da normativa successiva). Default ``include_abrogated=False``:
        accordo_stato_regioni_2011 (effective_until 2026-05-24, abrogato da
        Accordo SR 2025 GU n. 119/2025) viene escluso dal pool retrieval.
        Override esplicito per corsi "evoluzione normativa" che vogliono
        l'abrogata come materiale didattico.
        """
        sql = (
            "SELECT id, slug FROM regulations "
            "WHERE slug = ANY($1::text[]) AND status = 'VIGENTE' "
            "AND ($2::bool OR effective_until IS NULL OR effective_until > now())"
        )
        rows = await self.pool.fetch(sql, slugs, include_abrogated)
        found_slugs = {row["slug"] for row in rows}
        missing = set(slugs) - found_slugs
        if missing:
            raise ValueError(
                f"Slug normativi non trovati nel database: {missing}. "
                f"Verificare COURSE_CATALOG e tabella regulations."
            )
        return [str(row["id"]) for row in rows]

    async def search_chunks(
        self,
        query_embedding: list[float],
        regulation_ids: list[str],
        region: str,
        top_k: int = 30,
        *,
        include_abrogated: bool = False,
    ) -> list[NormativeChunk]:
        """Vector search filtered by regulation and region.

        The regional filter uses regulations.region (reliable JOIN), NOT
        chunk tags (which carry no regional info). NULL-safe.

        Region semantics (D-168, 2026-05-30):
          - 'NAZIONALE' regulations always pass (legge italiana applicabile
            ovunque sul territorio).
          - 'EUROPEA' regulations always pass: regolamenti UE (Reg. CE/UE)
            sono fonti direttamente applicabili nel diritto italiano senza
            recepimento, efficaci su tutto il territorio nazionale a
            prescindere dalla region del corso. Esempi: Reg. CE 852/2004
            (HACCP), Reg. CE 1272/2008 (CLP). Pre-D-168 il filtro li
            scartava silenziosamente → cosine_size=0 sistematico → BM25
            compensava in recall_hybrid ma con degrado retrieval invisibile.
          - Region-specific regulations (LOMBARDIA, LAZIO, ...) passano solo
            quando ``region`` corrisponde.

        Behaviour on unknown ``region``: this method does NOT validate the
        region string. An unrecognised value (e.g. "ATLANTIDE") simply
        matches no region-specific row — the query still returns NAZIONALE
        + EUROPEA chunks. Hard validation of "regional course + non-regional
        region" lives in the research_agent (BP §05.4, FASE 3.3) which
        raises ValueError before reaching this method.

        D-161 (2026-05-30): ``include_abrogated`` filtra regulations con
        ``effective_until`` non-null e nel passato. Default False (default
        sicuro: principio "mai mostrare abrogata se non esplicitato").
        Override via ``courses.include_abrogated_for_pedagogy`` per corsi
        evolutivi (es. confronto Accordo 2011 vs 2025). Lezione D-168:
        filtro applicato al join SQL, NON in-Python post-fetch (i filtri
        Python compensano silenziosamente i bug del filtro SQL e li
        nascondono — vedi cosine_size=0 pre-D-168).
        """
        sql = """
            SELECT rc.id, rc.regulation_id, rc.article, rc.paragraph, rc.hierarchy_path,
                   rc.body, rc.chunk_type, rc.tags,
                   1 - (rc.embedding <=> $1::vector) AS relevance_score
            FROM regulation_chunks rc
            JOIN regulations r ON rc.regulation_id = r.id
            WHERE rc.regulation_id = ANY($2::uuid[])
              AND rc.is_current = true
              AND (r.region IN ('NAZIONALE', 'EUROPEA')
                   OR ($3::text IS NOT NULL AND r.region = $3::text))
              AND ($5::bool OR r.effective_until IS NULL OR r.effective_until > now())
            ORDER BY rc.embedding <=> $1::vector
            LIMIT $4
        """
        rows = await self.pool.fetch(
            sql,
            _to_pgvector(query_embedding),
            regulation_ids,
            region,
            top_k,
            include_abrogated,
        )
        return [
            NormativeChunk(
                chunk_id=str(row["id"]),
                regulation_id=str(row["regulation_id"]),
                article=row["article"],
                paragraph=row["paragraph"],
                hierarchy_path=row["hierarchy_path"],
                body=row["body"],
                chunk_type=row["chunk_type"],
                tags=row["tags"] or [],
                relevance_score=float(row["relevance_score"]),
            )
            for row in rows
        ]

    async def get_style_patterns(self, course_type: str, target: str) -> list[StylePattern]:
        """Retrieve Level-2 style patterns, most recent first (BP §06.2/§06.3)."""
        rows = await self.pool.fetch(
            "SELECT style_pattern FROM approved_courses "
            "WHERE course_type = $1 AND target = $2 "
            "ORDER BY certified_at DESC LIMIT 5",
            course_type,
            target,
        )
        return [StylePattern(**json.loads(row["style_pattern"])) for row in rows]
