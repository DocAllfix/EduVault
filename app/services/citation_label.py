"""Composizione deterministica di `regulation_chunks.citation_label`.

Sorgente unica per due chiamanti:
1. `ingestion_service.py` — popola la colonna a INSERT-time (chiamato ad ogni
   chunk creato durante l'upload normativa).
2. `scripts/backfill_citations.py` — popola la colonna per chunk vecchi senza
   label (caso storico migrazione 004 + 7 normative pre-bugfix).

Regola (FIX #30.5a, 2026-05-26):
- Se article: "{short_title}, art. {N}[, c. {M}]" oppure "{short_title}, allegato XX"
- Se article NULL + hierarchy_path con "Allegato": hierarchy_path[:200]
- Altrimenti: hierarchy_path[:200] o short_title come fallback.

Pattern speciali per Reg CE/UE, Decreti datati (es. "2 settembre 2021"),
Accordi Stato-Regioni con anno: producono label brevi leggibili senza dipendere
dal pattern numerico {N}/{YY}.

Sicurezza: nessun side-effect, nessun network/DB. Solo regex + string. Importabile
da qualsiasi modulo. Test diretti in tests/unit/test_citation_label.py (TODO).
"""

from __future__ import annotations

import re

_SHORT_TITLE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Decreto\s+Legislativo\s+(\d+)/(\d{2,4})", re.IGNORECASE), "D.Lgs."),
    (re.compile(r"Decreto\s+Min(?:isteriale)?\.?\s+(\d+)/(\d{2,4})", re.IGNORECASE), "D.M."),
    (re.compile(
        r"Decreto\s+del\s+Pres(?:idente)?\s+(?:della\s+Repubblica\s+)?(\d+)/(\d{2,4})",
        re.IGNORECASE,
    ), "D.P.R."),
    (re.compile(r"D\.?\s*[Ll]gs\.?\s+(\d+)/(\d{2,4})"), "D.Lgs."),
    (re.compile(r"D\.?\s*[Mm]\.?\s+(\d+)/(\d{2,4})"), "D.M."),
    (re.compile(r"D\.?\s*[Pp]\.?\s*[Rr]\.?\s+(\d+)/(\d{2,4})"), "D.P.R."),
    (re.compile(r"Accordo\s+Stato.?Regioni\s+(\d+)/(\d+)/(\d{2,4})", re.IGNORECASE), "Accordo SR"),
    (re.compile(r"Legge\s+(\d+)/(\d{2,4})", re.IGNORECASE), "L."),
]

_MONTH_MAP = {
    "gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04",
    "maggio": "05", "giugno": "06", "luglio": "07", "agosto": "08",
    "settembre": "09", "ottobre": "10", "novembre": "11", "dicembre": "12",
}

_ART_PREFIX = re.compile(r"^\s*Art\.?\s*", re.IGNORECASE)
_COMMA_PREFIX = re.compile(r"^\s*[Cc]omma\s*", re.IGNORECASE)


def _strip_article_prefix(article: str) -> str:
    return _ART_PREFIX.sub("", article).strip()


def _strip_comma_prefix(paragraph: str) -> str:
    return _COMMA_PREFIX.sub("", paragraph).strip()


def _special_label(title: str) -> str | None:
    """Pattern speciali con label completa pre-computata (Reg CE/UE, DM datati,
    Accordi anno). Valutati per primi in short_title_from_regulation."""
    m = re.search(r"Regolamento\s+\(CE\)\s+n\.?\s*(\d+)/(\d{4})", title, re.IGNORECASE)
    if m:
        return f"Reg. CE {m.group(1)}/{m.group(2)}"
    m = re.search(r"Regolamento\s+\(UE\)\s+(?:n\.?\s*)?(\d+)/(\d{4})", title, re.IGNORECASE)
    if m:
        return f"Reg. UE {m.group(1)}/{m.group(2)}"
    m = re.search(
        r"Decreto.{1,60}?(\d{1,2})\s+"
        r"(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|"
        r"agosto|settembre|ottobre|novembre|dicembre)\s+(\d{4})",
        title, re.IGNORECASE,
    )
    if m:
        day = m.group(1).zfill(2)
        mm = _MONTH_MAP[m.group(2).lower()]
        return f"D.M. {day}/{mm}/{m.group(3)}"
    m = re.search(r"Accordo\s+Stato.?Regioni\b[^0-9]*?(\d{4})", title, re.IGNORECASE)
    if m:
        return f"Accordo SR {m.group(1)}"
    return None


def short_title_from_regulation(title: str) -> str:
    """'Decreto Legislativo 81/2008 ...' -> 'D.Lgs. 81/08'.

    Prima tenta i pattern speciali (label pre-completata per Reg CE/UE, DM
    datati senza numero progressivo, Accordi anno). Se nessuno matcha, prova i
    pattern numerici {tipo} {N}/{YYYY} con normalizzazione anno a 2 cifre.
    Fallback: primi 50 char del titolo.
    """
    special = _special_label(title)
    if special:
        return special
    for pattern, label in _SHORT_TITLE_PATTERNS:
        m = pattern.search(title)
        if m:
            number = m.group(1)
            year = m.group(2)
            if len(year) == 4:
                year = year[-2:]
            return f"{label} {number}/{year}"
    return title[:50]


def compose_citation_label(
    short_title: str,
    article: str | None,
    paragraph: str | None,
    hierarchy_path: str | None,
) -> str:
    """Componi `citation_label` per un singolo chunk.

    Output max 200 char (schema regulation_chunks.citation_label VARCHAR(200)).
    """
    if article:
        clean_art = _strip_article_prefix(article)
        if re.match(r"[Aa]llegato\b", clean_art):
            ref = f"{short_title}, {clean_art}"
        else:
            ref = f"{short_title}, art. {clean_art}"
        if paragraph:
            clean_comma = _strip_comma_prefix(paragraph)
            ref += f", c. {clean_comma}"
        return ref[:200]
    if hierarchy_path:
        return hierarchy_path[:200]
    return short_title[:200]
