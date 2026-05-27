"""Backfill citation_label per i chunk esistenti in regulation_chunks.

FIX #30.5a (2026-05-26): popola la colonna citation_label aggiunta con
migration 004 usando regola deterministica.

Regola di composizione:
  - se article è valorizzato:
      "{reg_short_title}, art. {article}{comma_part}"
      es: "D.Lgs. 81/08, art. 80, c. 1" (se paragraph='1')
          "D.Lgs. 81/08, art. 77"      (se paragraph è NULL)
  - se article è NULL ma hierarchy_path contiene "Allegato":
      hierarchy_path troncato a 200 char
      es: "Allegato IV"
  - altrimenti: hierarchy_path[:200] o regulation_title come fallback.

regulation_short_title viene derivato da regulations.title cercando pattern
tipo "D.Lgs. 81/2008" o "DM 388/2003" e normalizzando.

Esecuzione:
    python scripts/backfill_citations.py [--dry-run]

Idempotente: scrive citation_label SOLO se NULL (skip già popolati).
"""

from __future__ import annotations

import asyncio
import os
import re
import sys

import asyncpg

# Pattern per estrarre short_title da regulations.title
# Esempi: "D.Lgs. 81/2008" → "D.Lgs. 81/08"
#         "Decreto Ministeriale 388/2003" → "DM 388/03"
_SHORT_TITLE_PATTERNS = [
    # IMPORTANTE: ordine = specificità. "Decreto Legislativo" prima di "D.Lgs."
    # perché "D.Lgs." matcha anche dentro stringhe più ampie.
    (re.compile(r"Decreto\s+Legislativo\s+(\d+)/(\d{2,4})", re.IGNORECASE), "D.Lgs."),
    (re.compile(r"Decreto\s+Min(?:isteriale)?\.?\s+(\d+)/(\d{2,4})", re.IGNORECASE), "D.M."),
    (re.compile(r"Decreto\s+del\s+Pres(?:idente)?\s+(?:della\s+Repubblica\s+)?(\d+)/(\d{2,4})", re.IGNORECASE), "D.P.R."),
    (re.compile(r"D\.?\s*[Ll]gs\.?\s+(\d+)/(\d{2,4})"), "D.Lgs."),
    (re.compile(r"D\.?\s*[Mm]\.?\s+(\d+)/(\d{2,4})"), "D.M."),
    (re.compile(r"D\.?\s*[Pp]\.?\s*[Rr]\.?\s+(\d+)/(\d{2,4})"), "D.P.R."),
    (re.compile(r"Accordo\s+Stato.?Regioni\s+(\d+)/(\d+)/(\d{2,4})", re.IGNORECASE), "Accordo SR"),
    (re.compile(r"Legge\s+(\d+)/(\d{2,4})", re.IGNORECASE), "L."),
]


_ART_PREFIX = re.compile(r"^\s*Art\.?\s*", re.IGNORECASE)
_COMMA_PREFIX = re.compile(r"^\s*[Cc]omma\s*", re.IGNORECASE)


def _strip_article_prefix(article: str) -> str:
    """'Art. 26' → '26' (il prefisso lo aggiungiamo noi in compose_citation_label)."""
    return _ART_PREFIX.sub("", article).strip()


def _strip_comma_prefix(paragraph: str) -> str:
    """'Comma 2' → '2'."""
    return _COMMA_PREFIX.sub("", paragraph).strip()


def short_title_from_regulation(title: str) -> str:
    """Es: 'D.Lgs. 81/2008' → 'D.Lgs. 81/08'."""
    for pattern, label in _SHORT_TITLE_PATTERNS:
        m = pattern.search(title)
        if m:
            number = m.group(1)
            year = m.group(2)
            # Normalizza anno a 2 cifre (2008 → 08)
            if len(year) == 4:
                year = year[-2:]
            return f"{label} {number}/{year}"
    # Fallback: primo 50 char del title
    return title[:50]


def compose_citation_label(
    short_title: str,
    article: str | None,
    paragraph: str | None,
    hierarchy_path: str | None,
) -> str:
    """Regola di composizione (vedi docstring)."""
    if article:
        clean_art = _strip_article_prefix(article)
        # Se l'article è in realtà un allegato (es. "ALLEGATO IV") non usare "art."
        if re.match(r"[Aa]llegato\b", clean_art):
            ref = f"{short_title}, {clean_art}"
        else:
            ref = f"{short_title}, art. {clean_art}"
        if paragraph:
            clean_comma = _strip_comma_prefix(paragraph)
            ref += f", c. {clean_comma}"
        return ref[:200]
    # No article: cerca "Allegato" in hierarchy_path
    if hierarchy_path:
        if re.search(r"[Aa]llegato", hierarchy_path):
            return hierarchy_path[:200]
        return hierarchy_path[:200]
    return short_title[:200]


async def main(dry_run: bool = False) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL non set", file=sys.stderr)
        return 1

    conn = await asyncpg.connect(dsn)

    # Conta righe da processare
    n_total = await conn.fetchval("SELECT COUNT(*) FROM regulation_chunks")
    n_null = await conn.fetchval(
        "SELECT COUNT(*) FROM regulation_chunks WHERE citation_label IS NULL"
    )
    print(f"regulation_chunks: total={n_total}, citation_label NULL={n_null}")

    if n_null == 0:
        print("Niente da backfillare (citation_label già popolato).")
        await conn.close()
        return 0

    # Carica regulations per lookup short_title
    reg_rows = await conn.fetch("SELECT id, title FROM regulations")
    reg_short_titles: dict[str, str] = {
        str(r["id"]): short_title_from_regulation(r["title"]) for r in reg_rows
    }
    print(f"Regulations loaded: {len(reg_short_titles)}")
    for rid, st in reg_short_titles.items():
        print(f"  {rid[:8]} → {st!r}")

    # Carica chunk con citation_label NULL
    chunks = await conn.fetch(
        "SELECT id, regulation_id, article, paragraph, hierarchy_path "
        "FROM regulation_chunks WHERE citation_label IS NULL"
    )

    print()
    print(f"Processing {len(chunks)} chunks...")
    updates = []
    for c in chunks:
        rid = str(c["regulation_id"])
        short = reg_short_titles.get(rid, "?")
        label = compose_citation_label(short, c["article"], c["paragraph"], c["hierarchy_path"])
        updates.append((label, c["id"]))

    # Sample dei primi 10 per controllo
    print()
    print("Sample (first 10):")
    for label, _id in updates[:10]:
        print(f"  → {label!r}")

    if dry_run:
        print()
        print(f"[DRY RUN] {len(updates)} righe SAREBBERO aggiornate. Esci senza scrivere.")
        await conn.close()
        return 0

    # Batch update
    print()
    print(f"Updating {len(updates)} rows...")
    await conn.executemany(
        "UPDATE regulation_chunks SET citation_label = $1 WHERE id = $2",
        updates,
    )

    # Verifica
    n_remaining_null = await conn.fetchval(
        "SELECT COUNT(*) FROM regulation_chunks WHERE citation_label IS NULL"
    )
    print(f"Done. Remaining NULL: {n_remaining_null}")

    await conn.close()
    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(asyncio.run(main(dry_run=dry)))
