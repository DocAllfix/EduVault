"""Migration auto-runner per startup FastAPI.

Risolve l'avvertenza emersa dall'E2E 2026-05-31 in cui migration 011 e 012
non erano applicate in prod (deploy backend NON applicava migrations) →
endpoint /audio/{idx}/info ritornava 500 perche' colonna `provider` mancante.

Strategia: idempotente + safe-by-default.
  - Mantiene una tabella `_schema_migrations` con (filename, applied_at)
  - All'avvio scansiona `app/db/migrations/*.sql` in ordine alfabetico
  - Esegue solo quelle non gia' registrate
  - Esegue ciascuna in transaction (rollback su errore)
  - Logga ogni step e fallisce in modo NON BLOCCANTE: il backend resta su
    se una migration fallisce (es. permessi mancanti) ma il problema viene
    logged + reso visibile in startup_log.

Skip pattern: file con nome che inizia con `_` o `setup_` (es.
`setup_roles.sql`, `setup_langgraph_grants.sql`) NON sono migrations ma
script one-shot da eseguire manualmente (gia' convention nel repo).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent.parent / "db" / "migrations"


async def _ensure_schema_migrations_table(pool: Any) -> None:
    """Crea la tabella tracking migrations se non esiste. Idempotente."""
    await pool.execute(
        """
        CREATE TABLE IF NOT EXISTS _schema_migrations (
            filename VARCHAR(200) PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT NOW(),
            checksum VARCHAR(64)
        )
        """
    )


async def _list_applied(pool: Any) -> set[str]:
    rows = await pool.fetch("SELECT filename FROM _schema_migrations")
    return {r["filename"] for r in rows}


def _list_pending_files(applied: set[str]) -> list[Path]:
    """Lista i .sql nella dir migrations non ancora applicati.

    Skip: file che iniziano con `_` o `setup_` (script one-shot, non
    migrations regolari).
    """
    if not MIGRATIONS_DIR.exists():
        return []
    out: list[Path] = []
    for path in sorted(MIGRATIONS_DIR.iterdir()):
        name = path.name
        if not name.endswith(".sql"):
            continue
        if name.startswith("_") or name.startswith("setup_"):
            continue
        if name in applied:
            continue
        out.append(path)
    return out


async def run_pending_migrations(pool: Any) -> dict[str, Any]:
    """Esegue migrations pending. Ritorna summary {applied, skipped, errors}.

    Non solleva eccezioni: log + return stats. Il caller (startup) decide
    se procedere o no.
    """
    try:
        await _ensure_schema_migrations_table(pool)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "schema_migrations_table_create_failed",
            error_class=type(exc).__name__,
            error_msg=str(exc)[:200],
        )
        return {"applied": [], "skipped": [], "errors": ["init_failed"]}

    try:
        applied_set = await _list_applied(pool)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "schema_migrations_list_failed",
            error_class=type(exc).__name__,
            error_msg=str(exc)[:200],
        )
        return {"applied": [], "skipped": [], "errors": ["list_failed"]}

    pending = _list_pending_files(applied_set)
    if not pending:
        logger.info("schema_migrations_no_pending", n_applied=len(applied_set))
        return {"applied": [], "skipped": list(applied_set), "errors": []}

    applied_now: list[str] = []
    errors: list[str] = []
    for path in pending:
        name = path.name
        sql = path.read_text(encoding="utf-8")
        # Skip file vuoti / solo commenti (size threshold conservativo)
        if not sql.strip():
            continue
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO _schema_migrations (filename) VALUES ($1)",
                        name,
                    )
            applied_now.append(name)
            logger.info("schema_migration_applied", filename=name)
        except Exception as exc:  # noqa: BLE001
            errors.append(name)
            logger.error(
                "schema_migration_failed",
                filename=name,
                error_class=type(exc).__name__,
                error_msg=str(exc)[:300],
            )
            # NON breakiamo: tentiamo le successive (alcune sono indipendenti).
            # Se l'errore e' critico, il prossimo deploy lo vedra' di nuovo.

    logger.info(
        "schema_migrations_summary",
        applied_n=len(applied_now),
        applied=applied_now,
        errors_n=len(errors),
        errors=errors,
    )
    return {
        "applied": applied_now,
        "skipped": list(applied_set),
        "errors": errors,
    }
