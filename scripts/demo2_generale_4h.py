"""DEMO #2 cliente — Formazione Generale Lavoratori 4h.

Stesse 2 normative di E25 (D.Lgs 81/08 + ASR 2025), 4 moduli diversi:
  - Concetti di rischio
  - Prevenzione e protezione
  - Organizzazione della prevenzione
  - Diritti e doveri

Pipeline identica al corso E2E #25. Aspettativa tempo: ~9-12 min.
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
        "DEMO #2 — Formazione Generale Lavoratori 4h",
        "sicurezza_lavoratori_generale",
        "discente",
        4.0,
        "NAZIONALE",
        bp_id,
        admin_uid,
        "generating",
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
    print("DEMO #2 PIPELINE START (Formazione Generale 4h)...")
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
    print(
        f"DEMO #2 FINAL: status={row['status']!r}, slides={len(slides)}, "
        f"pptx_path_set={row['pptx_path'] is not None}, "
        f"elapsed={elapsed:.1f}s ({elapsed/60:.1f}m)"
    )


if __name__ == "__main__":
    asyncio.run(main())
