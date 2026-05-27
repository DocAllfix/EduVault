"""DEMO #3 cliente — Formazione Preposti 8h (PRIMO RUN 8h × 6 MODULI).

Analista review 10: "Su Preposti 8h fai un primo run 8h serio. Lo SPREAD
intra-modulo regge su 6 moduli invece di 4? Il per-module retrieval +
dedup con 6 moduli che competono? Il sub-batch recovery alla scala ~640
slide? top_k=70 × 6 = ~420 chunk recuperati — corpus regge?"

Normative: D.Lgs 81/08 (1819 chunk) + ASR 2025 (133 chunk) = 1952 chunk
totali, ben sopra 420 desiderati. Margine ampio.

Moduli (6, da catalog_config):
  1. Principali soggetti del sistema di prevenzione
  2. Relazioni tra i vari soggetti
  3. Definizione e individuazione dei fattori di rischio
  4. Incidenti e infortuni mancati
  5. Tecniche di comunicazione e sensibilizzazione
  6. Valutazione dei rischi dell'azienda

Aspettativa tempo: 15-22 min (sub-batch attivi su 6 moduli × ~110 slide).
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
        "DEMO #3 — Formazione Preposti 8h",
        "preposti",
        "discente",
        8.0,
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
    print("DEMO #3 PIPELINE START (Preposti 8h × 6 moduli — primo run scala 8h)...")
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
        f"DEMO #3 FINAL: status={row['status']!r}, slides={len(slides)}, "
        f"pptx_path_set={row['pptx_path'] is not None}, "
        f"elapsed={elapsed:.1f}s ({elapsed/60:.1f}m)"
    )


if __name__ == "__main__":
    asyncio.run(main())
