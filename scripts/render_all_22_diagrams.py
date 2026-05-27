"""Render PNG di TUTTI i 22 DIAGRAM del corso E2E #25 per ispezione
visiva analista (post FIX #31.7A).

Output: /app/output/diagrams_full_e25/M{m}_idx{i:03d}_{font}pt.png

Naming porta in chiaro modulo, indice e font uniforme usato per ogni
diagramma, così l'analista può subito vedere quali hanno font basso
(potenziali "storti/sbordati") e quali sono al default.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import asyncpg
import cairosvg

from app.services.diagram_service import (
    DIAGRAM_CATALOG,
    DiagramFilling,
    _compute_uniform_font_size,
    render_diagram_to_svg,
)


COURSE_ID = "2eefb83b-cb0f-42b9-a35e-e1f25fc6c02c"
DB_URL = (
    "postgresql://nexus_admin:"
    "023ed30d33a6ddd13e225e79acb78116788f876619664a34b18540f0faf9e073"
    "@postgres/nexus"
)


def slugify(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", s)[:40].strip("_")


async def main() -> None:
    out_dir = Path("/app/output/diagrams_full_e25")
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = await asyncpg.connect(DB_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT (elem->>'module_index')::int AS m,
                   (elem->>'index')::int AS idx,
                   elem->>'title' AS title,
                   elem->'image'->'diagram_filling'->>'template_name' AS template,
                   elem->'image'->'diagram_filling'->'slots' AS slots,
                   elem->'image'->'diagram_filling'->>'caption' AS caption
            FROM courses, jsonb_array_elements(slide_contents_json) elem
            WHERE id = $1
              AND elem->>'slide_type' = 'DIAGRAM'
            ORDER BY (elem->>'module_index')::int, (elem->>'index')::int
            """,
            COURSE_ID,
        )
    finally:
        await conn.close()

    print(f"=== Render PNG di {len(rows)} DIAGRAM E2E #25 (post FIX #31.7A) ===\n")
    summary = []
    for r in rows:
        try:
            filling = DiagramFilling(
                template_name=r["template"],
                slots=json.loads(r["slots"]),
                caption=r["caption"],
            )
            font, _ = _compute_uniform_font_size(filling)
            svg = render_diagram_to_svg(filling)
            png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=1600)
            slug = slugify(r["title"])
            out_path = out_dir / f"M{r['m']}_idx{r['idx']:03d}_{font:02d}pt_{slug}.png"
            out_path.write_bytes(png)
            print(f"OK M{r['m']}/idx{r['idx']:>3} font={font:02d}pt → {out_path.name}")
            summary.append((r["m"], r["idx"], font, r["template"]))
        except Exception as exc:
            print(f"FAIL M{r['m']}/idx{r['idx']:>3}: {exc!s:.200}")
            summary.append((r["m"], r["idx"], 0, r["template"]))

    # Statistiche
    fonts = [f for *_, f, _ in summary if f > 0]
    print()
    print("=" * 70)
    print(f"TOTAL: {len(rows)} diagram → {len(fonts)} rendered, {len(rows) - len(fonts)} failed")
    if fonts:
        print(f"FONT distribution:")
        from collections import Counter
        for f, c in sorted(Counter(fonts).items()):
            risk = " ⚠️ sotto 18pt (visibilmente piccolo)" if f < 18 else ""
            print(f"  {f:02d}pt: {c} diagram(s){risk}")
    print(f"\nPNG in: {out_dir}")


if __name__ == "__main__":
    asyncio.run(main())
