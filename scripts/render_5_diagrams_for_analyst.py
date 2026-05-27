"""Render 5 PNG di diagrammi rappresentativi del corso E2E #25 per
validazione visiva analista (gate review 8).

Scelta dei 5 casi:
  1. M3/idx29  flow_3step font 25pt "Segnali Colore/Luminosi/Gestuali"  (worst shrink)
  2. M0/idx9   flow_4step font 21pt "Identificazione/Valutazione/..."   (typical shrink)
  3. M3/idx40  flow_3step font 23pt "Misure di manutenzione sicure"     (sforo 29c)
  4. M1/idx29  flow_3step font 34pt "Valutazione/Individuazione/..."    (no shrink, reference)
  5. M3/idx16  flow_4step font 21pt "Segnale di avvertimento/..."       (3 slot lunghi insieme)
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import asyncpg
import cairosvg

from app.services.diagram_service import DiagramFilling, render_diagram_to_svg


COURSE_ID = "2eefb83b-cb0f-42b9-a35e-e1f25fc6c02c"
DB_URL = (
    "postgresql://nexus_admin:"
    "023ed30d33a6ddd13e225e79acb78116788f876619664a34b18540f0faf9e073"
    "@postgres/nexus"
)

SAMPLES = [
    (3, 29, "01_worst_shrink_25pt"),
    (0, 9,  "02_typical_shrink_21pt"),
    (3, 40, "03_extreme_29c_23pt"),
    (1, 29, "04_no_shrink_reference_34pt"),
    (3, 16, "05_three_long_slots_21pt"),
]


async def main() -> None:
    out_dir = Path("/app/output/diagrams_for_analyst_e25")
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = await asyncpg.connect(DB_URL)
    try:
        for m_idx, idx, fname in SAMPLES:
            row = await conn.fetchrow(
                """
                SELECT elem->>'title' AS title,
                       elem->'image'->'diagram_filling'->>'template_name' AS template,
                       elem->'image'->'diagram_filling'->'slots' AS slots,
                       elem->'image'->'diagram_filling'->>'caption' AS caption
                FROM courses, jsonb_array_elements(slide_contents_json) elem
                WHERE id = $1
                  AND elem->>'slide_type' = 'DIAGRAM'
                  AND (elem->>'module_index')::int = $2
                  AND (elem->>'index')::int = $3
                """,
                COURSE_ID, m_idx, idx,
            )
            if not row:
                print(f"NOT_FOUND M{m_idx}/idx{idx}")
                continue
            filling = DiagramFilling(
                template_name=row["template"],
                slots=json.loads(row["slots"]),
                caption=row["caption"],
            )
            svg = render_diagram_to_svg(filling)
            png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=1600)
            out_path = out_dir / f"{fname}.png"
            out_path.write_bytes(png)
            print(f"OK {out_path.name} - {row['title'][:50]} ({len(png)//1024} KB)")
    finally:
        await conn.close()
    print(f"\nDONE. PNG renderizzati in {out_dir}")


if __name__ == "__main__":
    asyncio.run(main())
