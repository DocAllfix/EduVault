"""Rebuild Demo #3 v3 dopo fix foto slide 415 (M3/84):
- Slide M3/84 ora ha query 'filo a piombo muratura cantiere strumento'
  (era 'pendolino controllo verticalità ponte' che Pexels matchava
  come treno)
- Rebuild riusa prefetch_images + ProductionBuilder esistente
  (FIX #31.7A v2 diagrammi invariato, regression-safe)
- ~30 secondi (no LLM call, solo image fetch + PPTX build + PDF)
"""
from __future__ import annotations

import asyncio
import time

import asyncpg

from app.services.rebuild_service import rebuild_course


COURSE_ID = "31886485-d243-46a3-b38a-77da28d86700"
DB_URL = (
    "postgresql://nexus_admin:"
    "023ed30d33a6ddd13e225e79acb78116788f876619664a34b18540f0faf9e073"
    "@postgres/nexus"
)
USER_ID = "00000000-0000-0000-0000-000000000000"


async def main() -> None:
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=4)
    try:
        print(f"REBUILD start: course={COURSE_ID}")
        start = time.time()
        await rebuild_course(COURSE_ID, USER_ID, pool)
        elapsed = time.time() - start
        print(f"REBUILD end after {elapsed:.1f}s")

        import uuid as uuid_mod
        row = await pool.fetchrow(
            "SELECT status, pptx_path, dirty FROM courses WHERE id=$1",
            uuid_mod.UUID(COURSE_ID),
        )
        print(
            f"FINAL: status={row['status']}, pptx={row['pptx_path']}, "
            f"dirty={row['dirty']}"
        )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
