"""Analizza tutti i 22 DIAGRAM del corso E2E #25 per identificare i fallback.

Ricostruisce DiagramFilling per ogni slide DIAGRAM, simulando esattamente
quello che fa image_service._render_diagram_sync (riga 283):
   filling = DiagramFilling(**slide.image.diagram_filling)

E logga slot-per-slot perché ognuno passa o fallisce.
"""
from __future__ import annotations

import asyncio
import json

import asyncpg

from app.services.diagram_service import DIAGRAM_CATALOG, DiagramFilling


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

    fail_count = 0
    pass_count = 0
    truncate_used = 0
    print(f"=== ANALIZZO {len(rows)} DIAGRAM corso E2E #25 ===\n")
    for r in rows:
        tpl_name = r["template"]
        tpl = DIAGRAM_CATALOG[tpl_name]
        slots = json.loads(r["slots"])
        caption = r["caption"]

        # Mostra slot per slot lunghezze
        per_slot_info = []
        any_over_max = False
        any_over_tol = False
        for s in tpl.slots:
            sval = slots.get(s.name, "")
            mx = s.max_chars
            tol = int(mx * 1.2)
            slen = len(sval)
            tag = "OK"
            if slen > tol:
                tag = "OVER_TOL"
                any_over_tol = True
                any_over_max = True
            elif slen > mx:
                tag = "OVER_MAX_INTOL"
                any_over_max = True
            per_slot_info.append(
                f'    {s.name}({slen}/{mx},tol{tol}) [{tag}] = "{sval}"'
            )

        # Tenta DiagramFilling istanziazione (come fa image_service)
        try:
            filling = DiagramFilling(
                template_name=tpl_name,
                slots=slots,
                caption=caption,
            )
            outcome = "PASS_RENDER"
            # Verifica se è stato applicato il truncate gentile
            for s in tpl.slots:
                original = slots.get(s.name, "")
                truncated = filling.slots.get(s.name, "")
                if truncated.endswith("…") and truncated != original:
                    outcome = "PASS_RENDER_with_truncate"
                    truncate_used += 1
                    break
            pass_count += 1
        except Exception as exc:
            outcome = f"FAIL_FALLBACK: {str(exc)[:200]}"
            fail_count += 1

        status_emoji = "✅" if outcome.startswith("PASS") else "❌"
        print(
            f'{status_emoji} M{r["m"]}/idx{r["idx"]:>3} [{tpl_name}] '
            f'"{r["title"][:50]}"\n  {outcome}'
        )
        for line in per_slot_info:
            print(line)
        print()

    print(
        f"\n=== SUMMARY E2E #25 ({len(rows)} DIAGRAM): "
        f"PASS={pass_count}, FAIL={fail_count}, "
        f"truncate_applied={truncate_used} ==="
    )
    # Match al telemetry
    print(
        f"\nTelemetry E2E #25 diceva: branded_fallbacks=10, diagram_fallbacks=10"
    )
    print(
        f"Conta reale Pydantic raise: {fail_count} fail su {len(rows)} = "
        f"{100*fail_count/len(rows):.0f}%"
    )


if __name__ == "__main__":
    asyncio.run(main())
