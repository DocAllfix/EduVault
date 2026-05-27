"""Rebuild E2E #25 con NUOVA logica diagrammi #31.7A (no re-research/content).

Le slide_contents_json sono già nel DB; basta rilanciare prefetch_images +
ProductionBuilder per ottenere un PPTX/PDF con i 22 DIAGRAM renderizzati
con auto-shrink font uniforme invece di branded fallback.

Stima tempo: 2-4 minuti (no LLM call, solo image fetch + SVG render + PPTX
serialize + audio TTS).
"""
from __future__ import annotations

import asyncio
import os

import asyncpg

from app.services.rebuild_service import rebuild_course


COURSE_ID = "2eefb83b-cb0f-42b9-a35e-e1f25fc6c02c"
DB_URL = (
    "postgresql://nexus_admin:"
    "023ed30d33a6ddd13e225e79acb78116788f876619664a34b18540f0faf9e073"
    "@postgres/nexus"
)
USER_ID = "00000000-0000-0000-0000-000000000000"  # noop, non usato


async def main() -> None:
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=4)
    try:
        print(f"REBUILD start: course={COURSE_ID}")
        import time
        start = time.time()
        await rebuild_course(COURSE_ID, USER_ID, pool)
        elapsed = time.time() - start
        print(f"REBUILD end after {elapsed:.1f}s")

        row = await pool.fetchrow(
            "SELECT status, pptx_path, pdf_path, dirty FROM courses WHERE id=$1",
            __import__("uuid").UUID(COURSE_ID),
        )
        print(f"FINAL: status={row['status']}, pptx={row['pptx_path']}, "
              f"pdf={row['pdf_path']}, dirty={row['dirty']}")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
