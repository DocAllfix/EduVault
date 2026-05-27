"""E2E #19 — corso 4h post FIX #31 per misurare il vero impatto.

Misure attese (target table dal PIANO FIX #31):
- Tempo totale pipeline: ~12-13 min (era 15:41 in E2E #18)
- Numero `backfill_wave` log: 0 (era 5-8 in E2E #18)
- `backfill_entry → backfill_exit` delta: <10s (era ~150s)
- `image_download_retry` (nuovo log): qualche unità (rete glitch)
- URL Pexels duplicate >2× nelle slide: 0 (era 8+ casi)
- `pexels_hits count=N` (nuovo): N tra 1 e 5
- `module_reask_stats reask_total_module`: NUMERO REALE per
  decidere H6 vs H3a (analista: >0.5/batch → batch-size pesa)
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid

import asyncpg
import voyageai

from app.config import settings
from app.services.dependencies import set_pool, set_voyage_client
from app.services.generation_service import run_pipeline


async def main() -> None:
    pool = await asyncpg.create_pool(
        os.environ["DATABASE_URL"], min_size=2, max_size=8
    )
    set_pool(pool)
    set_voyage_client(voyageai.AsyncClient(api_key=settings.voyage_api_key))

    admin_uid = await pool.fetchval(
        "SELECT id FROM users WHERE email LIKE 'admin@%' LIMIT 1"
    )
    bp_id = await pool.fetchval("SELECT id FROM brand_presets LIMIT 1")
    course_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    await pool.execute(
        """
        INSERT INTO courses (
            id, title, course_type, target, duration_hours, region,
            brand_preset_id, created_by, status
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        course_id,
        "E2E #25 4h FIX#31.6",
        "sicurezza_lavoratori_specifica_basso",
        "discente",
        4.0,
        "NAZIONALE",
        bp_id,
        admin_uid,
        "generating",  # courses_status_check: queued NON ammesso, generating sì
    )
    await pool.execute(
        """
        INSERT INTO generation_jobs (id, course_id, status, progress_percent)
        VALUES ($1, $2, $3, $4)
        """,
        job_id,
        course_id,
        "queued",
        0,
    )

    print(f"COURSE_ID={course_id}")
    print(f"JOB_ID={job_id}")
    print("PIPELINE START...")
    start = time.time()
    await run_pipeline(job_id, course_id)
    elapsed = time.time() - start

    row = await pool.fetchrow(
        "SELECT status, pptx_path, slide_contents_json::text as slides_raw "
        "FROM courses WHERE id=$1",
        course_id,
    )
    import json
    slides = json.loads(row["slides_raw"]) if row["slides_raw"] else []
    print(f"FINAL: status={row['status']!r}, slides={len(slides)}, "
          f"pptx_path_set={row['pptx_path'] is not None}, "
          f"elapsed={elapsed:.1f}s ({elapsed/60:.1f}m)")


if __name__ == "__main__":
    asyncio.run(main())
