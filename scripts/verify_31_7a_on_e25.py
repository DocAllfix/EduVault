"""FIX #31.7A — verifica retroattiva su tutti 22 DIAGRAM di E2E #25.

Riproduce esattamente il flusso di image_service._render_diagram_sync:
  1. DiagramFilling(**slide.image.diagram_filling)  ← ora con check_slots fixato
  2. render_diagram_to_svg(filling)                  ← ora con auto-shrink uniforme

Per ogni diagramma logga: PASS/FAIL, font uniforme calcolato, lunghezza
SVG, e se l'ultima-rete-truncate ha colpito.
"""
from __future__ import annotations

import asyncio
import json

import asyncpg

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


async def main() -> None:
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

    pass_count = 0
    fail_count = 0
    fonts_used: list[int] = []
    truncate_used = 0

    # Try cairosvg too — for the truly-end-to-end signal
    import cairosvg
    render_ok = 0
    render_fail = 0

    print(f"=== FIX #31.7A: verifica su {len(rows)} DIAGRAM E2E #25 ===\n")
    for r in rows:
        tpl_name = r["template"]
        tpl = DIAGRAM_CATALOG[tpl_name]
        slots_in = json.loads(r["slots"])
        caption = r["caption"]

        try:
            filling = DiagramFilling(
                template_name=tpl_name,
                slots=slots_in,
                caption=caption,
            )
        except Exception as exc:
            fail_count += 1
            print(
                f'❌ M{r["m"]}/idx{r["idx"]:>3} [{tpl_name}] FAIL_VALIDATION: {exc!s:.200}'
            )
            continue
        pass_count += 1

        # Compute font + final slots
        uniform_font, final_slots = _compute_uniform_font_size(filling)
        default_font_max = max(s.font_size_default for s in tpl.slots)
        fonts_used.append(uniform_font)
        shrunk = uniform_font < default_font_max
        # Conta truncate ultima rete
        for s in tpl.slots:
            orig = filling.slots.get(s.name, "")
            fin = final_slots.get(s.name, "")
            if fin != orig and fin.endswith("…"):
                # potrebbe essere stato già troncato dal check_slots gentile,
                # distinguiamo: check_slots tronca solo se sotto tolerance 20%
                pass  # generic ellipsis presence – count below

        # Render SVG + cairosvg
        try:
            svg_str = render_diagram_to_svg(filling)
            png = cairosvg.svg2png(bytestring=svg_str.encode("utf-8"), output_width=1280)
            render_ok += 1
            render_status = f"RENDER_OK ({len(png)//1024}KB)"
        except Exception as exc:
            render_fail += 1
            render_status = f"RENDER_FAIL: {exc!s:.100}"

        # Check ellipsis in final slots
        any_ellipsis = any("…" in v for v in final_slots.values())
        if any_ellipsis:
            truncate_used += 1

        marker = "🔻" if shrunk else "✅"
        print(
            f'{marker} M{r["m"]}/idx{r["idx"]:>3} [{tpl_name}] font={uniform_font}/{default_font_max}pt '
            f'{"(shrink)" if shrunk else ""} '
            f'{"(truncate-last-resort)" if any_ellipsis else ""}'
        )
        # mostra solo i slot interessati (sforanti)
        for s in tpl.slots:
            orig = filling.slots.get(s.name, "")
            fin = final_slots.get(s.name, "")
            if len(orig) > s.max_chars or fin != orig:
                marker2 = "💧" if fin != orig else "→"
                print(
                    f'    {marker2} {s.name} (orig {len(orig)}c/max {s.max_chars}): '
                    f'"{orig}" → "{fin}"'
                )
        print(f'    {render_status}')
        print()

    print("=" * 70)
    print(f"VALIDATION: PASS={pass_count}, FAIL={fail_count}")
    print(f"RENDER:     OK={render_ok}, FAIL={render_fail}")
    print(f"FONTS USED: {sorted(set(fonts_used))} (default range tipico 26-34pt)")
    if fonts_used:
        avg = sum(fonts_used) / len(fonts_used)
        print(f"FONT AVG:   {avg:.1f}pt  | MIN: {min(fonts_used)}pt | MAX: {max(fonts_used)}pt")
        below_18 = sum(1 for f in fonts_used if f < 18)
        print(f"FONT < 18pt: {below_18}/{len(fonts_used)} (analista gate: se molti → segnale che box troppo strette → C work-item)")
    print(f"TRUNCATE LAST-RESORT (16pt + ellipsis): {truncate_used}/{len(rows)}")
    print()
    print(f"Pre-#31.7A telemetry diceva: diagram_fallbacks=10/22 (45%)")
    print(f"Post-#31.7A previsto: diagram_fallbacks={fail_count + render_fail}/22")


if __name__ == "__main__":
    asyncio.run(main())
