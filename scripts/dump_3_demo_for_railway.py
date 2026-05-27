"""Dump dei 3 demo cliente (full row JSON) per re-INSERT su DB Railway
post-deploy.

USO LOCALE (genera file dump in storage/dumps/):
    docker compose exec backend python /app/scripts/dump_3_demo_for_railway.py

USO RAILWAY (post-deploy, dopo upload PPTX nel volume Railway):
    railway run python /app/scripts/seed_3_demo_on_railway.py

Output:
    storage/dumps/demo1_specifica_4h.json
    storage/dumps/demo2_generale_4h_v3.json
    storage/dumps/demo3_preposti_8h_v2.json

Ogni file contiene il record `courses` row completo (incluso
slide_contents_json) + path PPTX/PDF di destinazione Railway.
"""
from __future__ import annotations

import asyncio
import json
import uuid as uuid_mod
from pathlib import Path

import asyncpg


DB_URL = (
    "postgresql://nexus_admin:"
    "023ed30d33a6ddd13e225e79acb78116788f876619664a34b18540f0faf9e073"
    "@postgres/nexus"
)

DEMOS = [
    {
        "src_course_id": "2eefb83b-cb0f-42b9-a35e-e1f25fc6c02c",
        "new_title": "DEMO — Formazione Specifica Rischio Basso 4h",
        "dst_pptx": "output/demo1_specifica_4h.pptx",
        "dst_pdf": "output/demo1_specifica_4h_dispensa.pdf",
        "dump_file": "demo1_specifica_4h.json",
    },
    {
        "src_course_id": "a849fa1d-17c1-42a5-a03a-325d3cfaa169",
        "new_title": "DEMO — Formazione Generale Lavoratori 4h",
        "dst_pptx": "output/demo2_generale_4h.pptx",
        "dst_pdf": "output/demo2_generale_4h_dispensa.pdf",
        "dump_file": "demo2_generale_4h_v3.json",
    },
    {
        "src_course_id": "18bc0884-f120-49dd-8f5d-fd73c177353d",
        "new_title": "DEMO — Formazione Preposti 8h",
        "dst_pptx": "output/demo3_preposti_8h.pptx",
        "dst_pdf": "output/demo3_preposti_8h_dispensa.pdf",
        "dump_file": "demo3_preposti_8h_v2.json",
    },
]


async def main() -> None:
    out_dir = Path("/app/storage/dumps")
    out_dir.mkdir(parents=True, exist_ok=True)

    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=4)
    try:
        for demo in DEMOS:
            cid = uuid_mod.UUID(demo["src_course_id"])
            row = await pool.fetchrow(
                """
                SELECT
                    id, title, course_type, target, duration_hours, region,
                    brand_preset_id, created_by, status,
                    slide_contents_json::text AS slides_json,
                    normative_fingerprint::text AS fingerprint_json,
                    source_chunk_ids,
                    pptx_path, pdf_path, quiz_json::text AS quiz_json_text
                FROM courses
                WHERE id = $1
                """,
                cid,
            )
            if not row:
                print(f"NOT_FOUND course_id={demo['src_course_id']}")
                continue

            # NUOVO course_id per Railway (evita conflict se cliente
            # genera corsi reali con stesso UUID)
            new_id = str(uuid_mod.uuid4())
            dump = {
                "_meta": {
                    "src_course_id": str(row["id"]),
                    "new_id": new_id,
                    "new_title": demo["new_title"],
                    "dst_pptx": demo["dst_pptx"],
                    "dst_pdf": demo["dst_pdf"],
                },
                "id": new_id,
                "title": demo["new_title"],
                "course_type": row["course_type"],
                "target": row["target"],
                "duration_hours": float(row["duration_hours"]),
                "region": row["region"],
                "status": "completed",
                "pptx_path": demo["dst_pptx"],
                "pdf_path": demo["dst_pdf"],
                "slide_contents_json": json.loads(row["slides_json"]),
                "normative_fingerprint": (
                    json.loads(row["fingerprint_json"])
                    if row["fingerprint_json"] else None
                ),
                "source_chunk_ids": list(row["source_chunk_ids"] or []),
                "quiz_json": (
                    json.loads(row["quiz_json_text"])
                    if row["quiz_json_text"] else None
                ),
            }

            out_path = out_dir / demo["dump_file"]
            out_path.write_text(json.dumps(dump, ensure_ascii=False, indent=2))
            size_mb = out_path.stat().st_size / 1024 / 1024
            print(
                f"OK {demo['dump_file']} ({size_mb:.1f} MB) — "
                f"{demo['new_title']} ({len(dump['slide_contents_json'])} slide)"
            )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
