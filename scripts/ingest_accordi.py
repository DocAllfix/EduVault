"""Ingest the 3 missing Accordi Stato-Regioni (2011, 2016, 2025).

Resolves the gap discovered when courses #15/#16 failed on
`accordo_stato_regioni_2011` slug not found in DB. Adds 2016 (for
formatore_24h + aggiornamento_lavoratori_6h) and 2025 (new ASR coming
into force, 12-month transitional period ends 2026-05-23).

Run from CONTAINER:
    docker compose exec -T backend python scripts/ingest_accordi.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import asyncpg
import voyageai  # type: ignore[import-untyped]

from app.config import settings
from app.services.dependencies import set_pool, set_voyage_client
from app.services.ingestion_service import ingest_regulation_file

# slug → (pdf_filename, title, type, issuing_body, source_url)
ACCORDI = [
    (
        "accordo_stato_regioni_2011",
        "accordo_stato_regioni_2011.pdf",
        "Accordo Stato-Regioni 21/12/2011 (Rep. Atti 221/CSR) — Formazione lavoratori, dirigenti e preposti ex art. 37 c.2 D.Lgs 81/08",
        "ACCORDO_STATO_REGIONI",
        "Conferenza Permanente Stato-Regioni",
        "https://www.gazzettaufficiale.it/eli/id/2012/01/11/12A00058/sg",
    ),
    (
        "accordo_stato_regioni_2016",
        "accordo_stato_regioni_2016.pdf",
        "Accordo Stato-Regioni 07/07/2016 (Rep. Atti 128/CSR) — Requisiti minimi formatori RSPP/ASPP ex art. 32 D.Lgs 81/08 + Allegato V (qualificazione formatori sicurezza)",
        "ACCORDO_STATO_REGIONI",
        "Conferenza Permanente Stato-Regioni",
        "https://www.gazzettaufficiale.it/eli/id/2016/08/19/16A06077/sg",
    ),
    (
        "accordo_stato_regioni_2025",
        "accordo_stato_regioni_2025.pdf",
        "Accordo Stato-Regioni 17/04/2025 — Accordo unico formazione sicurezza lavoro (sostituisce ASR 2011 + 2016; fine periodo transitorio 23/05/2026)",
        "ACCORDO_STATO_REGIONI",
        "Conferenza Permanente Stato-Regioni",
        "https://www.lavoro.gov.it/temi-e-priorita/salute-e-sicurezza/focus/pagine/accordo-stato-regioni-del-17042025-materia-di-formazione",
    ),
]


async def _slug_exists(pool: asyncpg.Pool, slug: str) -> bool:
    row = await pool.fetchval("SELECT 1 FROM regulations WHERE slug=$1", slug)
    return row is not None


async def main() -> None:
    # Bootstrap Voyage client (normally done in app.main.startup) — required by
    # ingestion_service.embed_batch via get_voyage_client().
    set_voyage_client(voyageai.AsyncClient(api_key=settings.voyage_api_key))

    pool = await asyncpg.create_pool(settings.database_admin_url, min_size=1, max_size=4)
    assert pool is not None
    set_pool(pool)  # in case any nested call resolves it from dependencies
    try:
        for slug, pdf_name, title, reg_type, issuer, src_url in ACCORDI:
            pdf_path = Path("storage/pdfs") / pdf_name
            if not pdf_path.exists():
                print(f"[SKIP] {slug}: missing {pdf_path}", flush=True)
                continue

            if await _slug_exists(pool, slug):
                print(f"[SKIP] {slug}: already in DB", flush=True)
                continue

            print(f"[INGEST] {slug} from {pdf_path} ({pdf_path.stat().st_size / 1024:.0f} KB)", flush=True)
            try:
                reg_id, n_chunks = await ingest_regulation_file(
                    str(pdf_path),
                    slug=slug,
                    title=title,
                    reg_type=reg_type,
                    issuing_body=issuer,
                    region="NAZIONALE",
                    source_url=src_url,
                    pool=pool,
                )
                print(f"[OK]     {slug}: reg_id={reg_id}, chunks={n_chunks}", flush=True)
            except BaseException as exc:
                print(f"[FAIL]   {slug}: {type(exc).__name__}: {str(exc)[:300]}", flush=True)
                import traceback
                traceback.print_exc()
                sys.exit(1)
    finally:
        await pool.close()

    print("\nFINAL DB state:", flush=True)
    pool2 = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
    assert pool2 is not None
    try:
        rows = await pool2.fetch("SELECT slug, LEFT(title, 80) AS title FROM regulations ORDER BY slug")
        for r in rows:
            print(f"  - {r['slug']}: {r['title']}", flush=True)
    finally:
        await pool2.close()


if __name__ == "__main__":
    asyncio.run(main())
