"""F1 — Catalog service (DB-driven, BLUEPRINT D8).

Espone CRUD su ``course_type_catalog`` + ``course_type_modules`` (migration 005).
Sostituisce a regime ``config/catalog_config.py`` quando flag
``v2_catalog_from_db=true`` (default False fino a quando il cliente non ha
approvato tutti i 54 entries dello scraping).

VAA:
  - (b) provenienza: ``source`` ∈ {scraped, manual, imported_v1} preservato per
    ogni entry e per ogni modulo. Audit visibile in UI.
  - (c) safety: l'entry NON è disponibile per generazione finche'
    ``approved_at IS NULL`` (gate analista, pattern "sistema propone, umano
    valida"). Una entry creata via scrape sta in stato "draft" finche' un admin
    non la approva esplicitamente.
  - (e) safety-net: il flag ``v2_catalog_from_db`` resta OFF di default; il
    research_agent legge ``COURSE_CATALOG`` (config-driven) finche' non viene
    flippato. Le 2 sorgenti convivono per A/B prima del cutover.
"""

from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ─── Read helpers ───────────────────────────────────────────────────────────


async def list_catalog_entries(
    pool: Any,
    *,
    page: int = 1,
    per_page: int = 50,
    approved_only: bool = False,
    target_filter: str | None = None,
    search: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Lista paginata + filtri + count totale per UI tabella.

    Args:
        approved_only: True → solo entries con ``approved_at IS NOT NULL``.
        target_filter: filtra per ``target`` (es. 'lavoratori', 'preposti').
        search: substring case-insensitive su title o slug.

    Returns:
        (entries, total_count). Ogni entry include ``n_modules`` (count modules
        di quel course_type) per UI summary, senza N+1.
    """
    where: list[str] = []
    args: list[Any] = []
    if approved_only:
        where.append("c.approved_at IS NOT NULL")
    if target_filter:
        args.append(target_filter)
        where.append(f"c.target = ${len(args)}")
    if search:
        args.append(f"%{search.lower()}%")
        where.append(
            f"(LOWER(c.title) LIKE ${len(args)} OR LOWER(c.slug) LIKE ${len(args)})"
        )
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    # Count first (small query)
    total = await pool.fetchval(
        f"SELECT COUNT(*) FROM course_type_catalog c {where_sql}",
        *args,
    )

    # Paginated rows with module count via LATERAL subquery (avoids N+1)
    offset = (page - 1) * per_page
    rows = await pool.fetch(
        f"""
        SELECT
            c.slug, c.title, c.hours, c.target, c.regulation_slugs,
            c.regional, c.source, c.source_url, c.scraped_at,
            c.approved_at, c.approved_by,
            c.created_at, c.updated_at,
            (SELECT COUNT(*) FROM course_type_modules m WHERE m.course_type_slug = c.slug) AS n_modules
        FROM course_type_catalog c
        {where_sql}
        ORDER BY c.target, c.title
        LIMIT ${len(args) + 1} OFFSET ${len(args) + 2}
        """,
        *args,
        per_page,
        offset,
    )
    entries = [
        {
            "slug": r["slug"],
            "title": r["title"],
            "hours": float(r["hours"]),
            "target": r["target"],
            "regulation_slugs": list(r["regulation_slugs"] or []),
            "regional": bool(r["regional"]),
            "source": r["source"],
            "source_url": r["source_url"],
            "scraped_at": r["scraped_at"].isoformat() if r["scraped_at"] else None,
            "approved_at": r["approved_at"].isoformat() if r["approved_at"] else None,
            "approved_by": str(r["approved_by"]) if r["approved_by"] else None,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            "n_modules": int(r["n_modules"] or 0),
        }
        for r in rows
    ]
    return entries, int(total or 0)


async def get_catalog_entry(
    pool: Any,
    slug: str,
) -> dict[str, Any] | None:
    """Dettaglio singola entry + lista moduli ordinata."""
    row = await pool.fetchrow(
        """
        SELECT slug, title, hours, target, regulation_slugs, regional,
               source, source_url, scraped_at, approved_at, approved_by,
               created_at, updated_at
        FROM course_type_catalog WHERE slug = $1
        """,
        slug,
    )
    if not row:
        return None
    modules_rows = await pool.fetch(
        """
        SELECT id, ordinal, title, normative_refs, source, created_at
        FROM course_type_modules
        WHERE course_type_slug = $1
        ORDER BY ordinal
        """,
        slug,
    )
    return {
        "slug": row["slug"],
        "title": row["title"],
        "hours": float(row["hours"]),
        "target": row["target"],
        "regulation_slugs": list(row["regulation_slugs"] or []),
        "regional": bool(row["regional"]),
        "source": row["source"],
        "source_url": row["source_url"],
        "scraped_at": row["scraped_at"].isoformat() if row["scraped_at"] else None,
        "approved_at": row["approved_at"].isoformat() if row["approved_at"] else None,
        "approved_by": str(row["approved_by"]) if row["approved_by"] else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "modules": [
            {
                "id": str(m["id"]),
                "ordinal": int(m["ordinal"]),
                "title": m["title"],
                "normative_refs": list(m["normative_refs"] or []),
                "source": m["source"],
                "created_at": m["created_at"].isoformat() if m["created_at"] else None,
            }
            for m in modules_rows
        ],
    }


# ─── Write helpers ──────────────────────────────────────────────────────────


async def update_catalog_entry(
    pool: Any,
    slug: str,
    *,
    title: str | None = None,
    hours: float | None = None,
    target: str | None = None,
    regulation_slugs: list[str] | None = None,
    regional: bool | None = None,
) -> bool:
    """PATCH parziale su una entry. Ritorna True se l'entry esisteva."""
    sets: list[str] = []
    args: list[Any] = []
    if title is not None:
        args.append(title)
        sets.append(f"title = ${len(args)}")
    if hours is not None:
        args.append(hours)
        sets.append(f"hours = ${len(args)}")
    if target is not None:
        args.append(target)
        sets.append(f"target = ${len(args)}")
    if regulation_slugs is not None:
        args.append(regulation_slugs)
        sets.append(f"regulation_slugs = ${len(args)}")
    if regional is not None:
        args.append(regional)
        sets.append(f"regional = ${len(args)}")

    if not sets:
        exists = await pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM course_type_catalog WHERE slug = $1)",
            slug,
        )
        return bool(exists)

    args.append(slug)
    result = await pool.execute(
        f"UPDATE course_type_catalog SET {', '.join(sets)} WHERE slug = ${len(args)}",
        *args,
    )
    # asyncpg execute returns "UPDATE n"
    return not result.endswith(" 0")


async def approve_catalog_entry(
    pool: Any,
    slug: str,
    *,
    approver_user_id: str,
) -> bool:
    """Stamp ``approved_at = NOW(), approved_by = uid``. Gate VAA-c.

    Idempotente: ri-approvare aggiorna il timestamp e l'approver.
    """
    result = await pool.execute(
        "UPDATE course_type_catalog SET approved_at = NOW(), approved_by = $1 WHERE slug = $2",
        uuid_mod.UUID(approver_user_id),
        slug,
    )
    ok = not result.endswith(" 0")
    if ok:
        logger.info("catalog_entry_approved", slug=slug, approver=approver_user_id)
    return ok


async def unapprove_catalog_entry(
    pool: Any,
    slug: str,
) -> bool:
    """Revoca approval (l'entry torna draft, non disponibile per generazione)."""
    result = await pool.execute(
        "UPDATE course_type_catalog SET approved_at = NULL, approved_by = NULL WHERE slug = $1",
        slug,
    )
    ok = not result.endswith(" 0")
    if ok:
        logger.info("catalog_entry_unapproved", slug=slug)
    return ok


async def bulk_approve_catalog_entries(
    pool: Any,
    slugs: list[str],
    *,
    approver_user_id: str,
) -> int:
    """Approve in batch. Ritorna il count di righe aggiornate."""
    if not slugs:
        return 0
    result = await pool.execute(
        "UPDATE course_type_catalog SET approved_at = NOW(), approved_by = $1 "
        "WHERE slug = ANY($2::text[])",
        uuid_mod.UUID(approver_user_id),
        slugs,
    )
    # "UPDATE n"
    n = int(result.split(" ")[1]) if result.startswith("UPDATE") else 0
    logger.info("catalog_bulk_approved", n=n, approver=approver_user_id, slugs=slugs[:5])
    return n


# ─── Stats / aggregates ─────────────────────────────────────────────────────


async def get_catalog_summary(pool: Any) -> dict[str, Any]:
    """Aggregato per header pagina admin: count per stato + per target."""
    total = await pool.fetchval("SELECT COUNT(*) FROM course_type_catalog")
    approved = await pool.fetchval(
        "SELECT COUNT(*) FROM course_type_catalog WHERE approved_at IS NOT NULL"
    )
    pending = int(total or 0) - int(approved or 0)
    target_rows = await pool.fetch(
        """
        SELECT target,
               COUNT(*) AS n_total,
               COUNT(*) FILTER (WHERE approved_at IS NOT NULL) AS n_approved
        FROM course_type_catalog
        GROUP BY target
        ORDER BY target
        """,
    )
    by_target = [
        {
            "target": r["target"],
            "n_total": int(r["n_total"]),
            "n_approved": int(r["n_approved"]),
        }
        for r in target_rows
    ]
    return {
        "total": int(total or 0),
        "approved": int(approved or 0),
        "pending": pending,
        "by_target": by_target,
        "snapshot_at": datetime.utcnow().isoformat(),
    }
