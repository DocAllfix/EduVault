"""Comparative test: generate the SAME course with N different LLM models.

For each model we override the L0 content fallback entry + relevant settings,
run the FULL pipeline (research + content + build), and record metrics so we
can pick the best model on real data (bullet fill, rejects, diagrams, images).

REI-3: the pipeline keeps Semaphore(1) for the PPTX build; courses run
sequentially (we await each before the next), which is correct here.

Run from CONTAINER:
    docker compose exec -T backend python scripts/test_models_comparison.py
"""
from __future__ import annotations

import asyncio
import sys
import uuid

import asyncpg
import voyageai  # type: ignore[import-untyped]

from app.config import settings
from app.services import ingestion_service
from app.services.dependencies import set_pool, set_voyage_client

# (label, provider, model) — each runs one full course.
MODELS: list[tuple[str, str, str]] = [
    ("flash", "deepseek", "deepseek-v4-flash"),
    ("pro", "deepseek", "deepseek-v4-pro"),
    ("gpt41mini", "azure_openai", settings.azure_openai_deployment_content),
    ("haiku", "anthropic", "claude-haiku-4-5-20251001"),
    ("gpt4o", "openai", "gpt-4o"),
]

COURSE_TYPE = "sicurezza_lavoratori_specifica_basso"
DURATION = 4.0


async def _seed_course(pool: asyncpg.Pool, label: str) -> tuple[str, str]:
    brand_id = await pool.fetchval("SELECT id FROM brand_presets LIMIT 1")
    admin_id = await pool.fetchval("SELECT id FROM users WHERE role='admin' LIMIT 1")
    course_id = await pool.fetchval(
        "INSERT INTO courses (title, course_type, target, duration_hours, region, "
        "brand_preset_id, created_by, status) "
        "VALUES ($1,$2,'discente',$3,'NAZIONALE',$4,$5,'generating') RETURNING id",
        f"TEST {label} {COURSE_TYPE}", COURSE_TYPE, DURATION, brand_id, admin_id,
    )
    job_id = await pool.fetchval(
        "INSERT INTO generation_jobs (course_id, status, progress_percent) "
        "VALUES ($1,'queued',0) RETURNING id",
        course_id,
    )
    return str(course_id), str(job_id)


async def main() -> None:
    set_voyage_client(voyageai.AsyncClient(api_key=settings.voyage_api_key))
    pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    assert pool is not None
    set_pool(pool)

    # Import AFTER set_pool so run_pipeline resolves the same pool.
    from app.services.generation_service import run_pipeline

    # Optional CLI filter: run only the models whose label is passed as args.
    # e.g. `python scripts/test_models_comparison.py flash pro` runs 2 models.
    # No args → run all 5.
    wanted = set(sys.argv[1:])
    models_to_run = [m for m in MODELS if not wanted or m[0] in wanted]

    results: list[dict[str, object]] = []
    for label, provider, model in models_to_run:
        # Override the L0 content entry to force this provider+model. The
        # deployment_key must resolve to `model` via getattr(settings, key),
        # so we stash the model on a temp settings attribute.
        setattr(settings, f"_test_model_{label}", model)
        ingestion_service._FALLBACK_CHAIN_CONTENT[0] = (
            provider, f"_test_model_{label}", f"L0_test_{label}"
        )
        course_id, job_id = await _seed_course(pool, label)
        print(f"\n{'='*70}\n[MODEL {label}] provider={provider} model={model}\n"
              f"  course_id={course_id}\n{'='*70}", flush=True)
        try:
            await run_pipeline(job_id, course_id)
            row = await pool.fetchrow(
                "SELECT status, pptx_path, jsonb_array_length(slide_contents_json) AS n "
                "FROM courses WHERE id=$1", uuid.UUID(course_id),
            )
            print(f"[MODEL {label}] DONE status={row['status']} slides={row['n']} "
                  f"pptx={row['pptx_path']}", flush=True)
            results.append({"label": label, "course_id": course_id,
                            "status": row["status"], "slides": row["n"],
                            "pptx": row["pptx_path"]})
        except Exception as exc:
            print(f"[MODEL {label}] FAILED: {type(exc).__name__}: {str(exc)[:300]}", flush=True)
            results.append({"label": label, "course_id": course_id, "status": "EXCEPTION"})

    print(f"\n{'='*70}\nSUMMARY\n{'='*70}", flush=True)
    for r in results:
        print(f"  {r['label']:10s} status={r.get('status')} slides={r.get('slides')} "
              f"course_id={r['course_id']}", flush=True)
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
