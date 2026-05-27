"""Verifica review 9 fix sui 4 casi critici (M1/idx15, M3/idx69, M3/idx29,
M0/idx9): zero ellipsis sopra il floor 16pt."""
from __future__ import annotations

import asyncio
import json

import asyncpg

from app.services.diagram_service import (
    DiagramFilling,
    _compute_uniform_font_size,
    render_diagram_to_svg,
)


async def main() -> None:
    conn = await asyncpg.connect(
        "postgresql://nexus_admin:"
        "023ed30d33a6ddd13e225e79acb78116788f876619664a34b18540f0faf9e073"
        "@postgres/nexus"
    )
    print("=== Verifica review 9 fix: zero ellipsis sopra floor 16pt ===\n")
    cases = [(1, 15), (3, 69), (3, 29), (0, 9), (1, 47), (0, 15)]
    for m, idx in cases:
        row = await conn.fetchrow(
            """
            SELECT elem->>'title' AS t,
                   elem->'image'->'diagram_filling' AS df
            FROM courses, jsonb_array_elements(slide_contents_json) elem
            WHERE id = '2eefb83b-cb0f-42b9-a35e-e1f25fc6c02c'
              AND elem->>'slide_type' = 'DIAGRAM'
              AND (elem->>'module_index')::int = $1
              AND (elem->>'index')::int = $2
            """,
            m, idx,
        )
        if not row:
            print(f"NOT_FOUND M{m}/idx{idx}\n")
            continue
        df = json.loads(row["df"])
        filling = DiagramFilling(
            template_name=df["template_name"],
            slots=df["slots"],
            caption=df["caption"],
        )
        font, final = _compute_uniform_font_size(filling)
        any_ellipsis = any("…" in v for v in final.values())
        status = "❌ TRUNCATE PRESENT" if any_ellipsis else "✅ ZERO ELLIPSIS"
        print(f'M{m}/idx{idx} "{row["t"][:50]}" → font={font}pt {status}')
        for k, v in final.items():
            mark = "  [ELLIPSIS]" if "…" in v else ""
            orig = df["slots"][k]
            same = "" if v == orig else f"  (input was \"{orig}\")"
            print(f'    {k} ({len(v)}c): "{v}"{mark}{same}')
        # Verifica anche il render SVG
        svg = render_diagram_to_svg(filling)
        svg_has_ellipsis = "…" in svg
        print(f"    SVG render: ellipsis_in_svg={svg_has_ellipsis}")
        print()

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
