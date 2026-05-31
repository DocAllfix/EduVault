"""F5.2 — Image library semantic search service (vast-hopping §F5.2).

Riusa ``embed_text_for_image_query`` (voyage-multimodal-3) per embeddare la
query, poi k-NN cosine su ``image_library.embedding`` (HNSW vector_cosine_ops,
migration 005). Fallback su GIN tag overlap se embedding query fallisce o
ritorna nessun hit sopra threshold.

Pattern allineato a ``knowledge_repo.search_chunks``:
  - usa ``_to_pgvector`` per literal `[...]::vector`
  - ritorna relevance_score = 1 - cosine_distance (compatibile con MIN_RERANK_SCORE_ALERT)
  - threshold conservativo 0.30 (calibrato come MIN_RERANK_SCORE_ALERT)

VAA-b provenance: ogni hit include ``source`` + ``license`` + ``attribution``
per UI badge license chip (REI-10 sicurezza). Tracciato ``usage_count++``
quando un hit viene effettivamente scelto dall'utente (incremento atomico,
sample read di telemetria utilizzo per F5.5).
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel

from app.services.embeddings import embed_text_for_image_query
from app.services.knowledge_repo import _to_pgvector

logger = structlog.get_logger(__name__)

# Threshold cosine_similarity per accettare hit library (sotto questo,
# tier-1 fallisce e la cascata passa a Pexels). 0.30 calibrato come
# MIN_RERANK_SCORE_ALERT (vedi config.py).
SEARCH_THRESHOLD = 0.30

# k default per UI grid 2x4 = 8 hit
DEFAULT_K = 8


class LibraryHit(BaseModel):
    """Single image_library row exposed to caller (UI + cascade)."""

    id: str
    file_path: str
    tags: list[str]
    source: str
    license: str | None
    attribution: str | None
    source_url: str | None
    width: int | None
    height: int | None
    usage_count: int
    score: float


async def search(
    query: str,
    pool: Any,
    *,
    k: int = DEFAULT_K,
    threshold: float = SEARCH_THRESHOLD,
) -> list[LibraryHit]:
    """k-NN cosine sul library + fallback GIN tag.

    Args:
        query: testo libero (es. "estintore officina")
        pool: asyncpg pool
        k: numero massimo hit (default 8 per UI grid 2x4)
        threshold: cosine_similarity minima (default 0.30)

    Returns:
        Lista LibraryHit ordinate per score desc. Vuota se nessun match
        sopra threshold (caller cade su Pexels via image_search.cascade).
    """
    q = (query or "").strip()
    if not q:
        return []

    # Tier 1A: vector search via voyage multimodal text-query embedding
    try:
        emb = await embed_text_for_image_query(q)
    except Exception as exc:  # noqa: BLE001 — voyage outage → tag fallback
        logger.warning("library_query_embed_failed", query=q, error=str(exc))
        emb = None

    if emb is not None:
        rows = await pool.fetch(
            """
            SELECT id, file_path, tags, source, license, attribution,
                   source_url, width, height, usage_count,
                   1 - (embedding <=> $1::vector) AS score
            FROM image_library
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            _to_pgvector(emb),
            k,
        )
        hits = [
            LibraryHit(
                id=str(r["id"]),
                file_path=r["file_path"],
                tags=list(r["tags"] or []),
                source=r["source"],
                license=r["license"],
                attribution=r["attribution"],
                source_url=r["source_url"],
                width=r["width"],
                height=r["height"],
                usage_count=int(r["usage_count"]),
                score=float(r["score"]),
            )
            for r in rows
            if float(r["score"]) >= threshold
        ]
        if hits:
            logger.info(
                "library_vector_search",
                query=q,
                n=len(hits),
                top_score=hits[0].score if hits else None,
            )
            return hits

    # Tier 1B: GIN tag overlap fallback (multilingua, NO LLM)
    # Tokenize Italian query crudely; stop-words coperti a livello chiamante.
    tokens = [t.lower() for t in q.split() if len(t) > 2]
    if not tokens:
        return []
    rows = await pool.fetch(
        """
        SELECT id, file_path, tags, source, license, attribution,
               source_url, width, height, usage_count,
               cardinality(ARRAY(SELECT unnest(tags) INTERSECT SELECT unnest($1::text[])))::float
                   / GREATEST(cardinality(tags), 1) AS score
        FROM image_library
        WHERE tags && $1::text[]
        ORDER BY score DESC
        LIMIT $2
        """,
        tokens,
        k,
    )
    hits = [
        LibraryHit(
            id=str(r["id"]),
            file_path=r["file_path"],
            tags=list(r["tags"] or []),
            source=r["source"],
            license=r["license"],
            attribution=r["attribution"],
            source_url=r["source_url"],
            width=r["width"],
            height=r["height"],
            usage_count=int(r["usage_count"]),
            score=float(r["score"]),
        )
        for r in rows
    ]
    logger.info("library_tag_search_fallback", query=q, tokens=tokens, n=len(hits))
    return hits


async def increment_usage(pool: Any, image_id: str) -> None:
    """Incrementa usage_count quando un hit e' scelto dall'utente / cascade."""
    await pool.execute(
        "UPDATE image_library SET usage_count = usage_count + 1 WHERE id = $1::uuid",
        image_id,
    )


async def list_admin(
    pool: Any,
    *,
    page: int = 1,
    per_page: int = 50,
    source_filter: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Lista paginata + filtri per UI admin audit (vast-hopping §F5.2 b).

    Returns:
        (entries, total_count).
    """
    where: list[str] = []
    args: list[Any] = []
    if source_filter:
        args.append(source_filter)
        where.append(f"source = ${len(args)}")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = await pool.fetchval(
        f"SELECT COUNT(*) FROM image_library {where_sql}",
        *args,
    )
    offset = (page - 1) * per_page
    rows = await pool.fetch(
        f"""
        SELECT id, file_path, tags, source, license, attribution, source_url,
               width, height, bytes, usage_count, created_at, updated_at
        FROM image_library
        {where_sql}
        ORDER BY created_at DESC
        LIMIT ${len(args) + 1} OFFSET ${len(args) + 2}
        """,
        *args,
        per_page,
        offset,
    )
    entries = [
        {
            "id": str(r["id"]),
            "file_path": r["file_path"],
            "tags": list(r["tags"] or []),
            "source": r["source"],
            "license": r["license"],
            "attribution": r["attribution"],
            "source_url": r["source_url"],
            "width": r["width"],
            "height": r["height"],
            "bytes": r["bytes"],
            "usage_count": int(r["usage_count"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
        for r in rows
    ]
    return entries, int(total or 0)
