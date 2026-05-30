"""D-178 V1.5 (analista sign-off 2026-05-30): normalizzazione citazioni decreti.

Estrai citazioni di decreti dai bullets/notes/quiz_options di una slide e
normalizzale a canonical slug per confronto con ``course.regulation_ids``.

Patologia coperta (slide 67 PPTX `ANT_L1_0dfe39ad`):
  - bullet: "Decreto ministeriale 3 agosto 2015 — riferimento chiave"
  - course.regulation_ids = [dlgs_81_08, dm_02_09_2021, dm_03_09_2021, dm_01_09_2021]
  - dm_03_08_2015 NON in lista -> citazione hallucinated, slide marked
    `bullet_citation_warning`.

Strategia (a) analista: normalizza bullet -> canonical slug, confronta con
regulation_ids. Strategia (c) `display_citations` field strutturato e' D-181-bis
backlog post-E2E controllo.

Comportamento on-mismatch: marca slide (non scarta), operatore review.

Pure regex + string, no DB no LLM no async. Importabile da qualsiasi modulo.
"""

from __future__ import annotations

import re

_MONTH_TO_NUM = {
    "gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04",
    "maggio": "05", "giugno": "06", "luglio": "07", "agosto": "08",
    "settembre": "09", "ottobre": "10", "novembre": "11", "dicembre": "12",
}

# Pattern citazioni decreti che vogliamo catturare nei bullets/notes.
# Forme: "DM 3 agosto 2015", "D.M. 03/08/2015", "Decreto ministeriale 3 agosto 2015",
#        "D.Lgs 81/2008", "D.Lgs. 81/08", "decreto legislativo n. 81/2008",
#        "Reg. CE 852/2004", "Regolamento (CE) n. 852/2004",
#        "Accordo Stato-Regioni 2025", "Accordo SR 2025".
#
# Ogni regex matcha la forma completa "tipo + numero/data" come unita' singola
# per estrarre componenti normalizzazione.

_DM_DATED_FULL = re.compile(
    r"(?:Decreto\s+[Mm]inisteriale|D\.?\s*M\.?)\s+"
    r"(\d{1,2})\s+"
    r"(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|"
    r"agosto|settembre|ottobre|novembre|dicembre)\s+"
    r"(\d{4})",
    re.IGNORECASE,
)

_DM_DATED_SLASH = re.compile(
    r"(?:Decreto\s+[Mm]inisteriale|D\.?\s*M\.?)\s+"
    r"(\d{1,2})/(\d{1,2})/(\d{2,4})",
    re.IGNORECASE,
)

_DM_NUMBERED = re.compile(
    r"(?:Decreto\s+[Mm]inisteriale|D\.?\s*M\.?)\s+(?:n\.?\s*)?"
    r"(\d+)/(\d{2,4})",
    re.IGNORECASE,
)

_DLGS = re.compile(
    r"(?:Decreto\s+[Ll]egislativo|D\.?\s*[Ll]gs\.?)\s+(?:n\.?\s*)?"
    r"(\d+)/(\d{2,4})",
    re.IGNORECASE,
)

_REG_CE = re.compile(
    r"(?:Regolamento\s*\(?\s*CE\s*\)?|Reg\.?\s*\(?\s*CE\s*\)?)\s+"
    r"(?:n\.?\s*)?(\d+)/(\d{4})",
    re.IGNORECASE,
)

_REG_UE = re.compile(
    r"(?:Regolamento\s*\(?\s*UE\s*\)?|Reg\.?\s*\(?\s*UE\s*\)?)\s+"
    r"(?:n\.?\s*)?(\d+)/(\d{4})",
    re.IGNORECASE,
)

_ACCORDO_SR = re.compile(
    r"(?:Accordo\s+Stato.?Regioni|Accordo\s+SR)[^0-9]{0,40}?(\d{4})",
    re.IGNORECASE,
)

_DPR = re.compile(
    r"(?:Decreto\s+del\s+Presidente\s+della\s+Repubblica|D\.?\s*P\.?\s*R\.?)\s+"
    r"(?:n\.?\s*)?(\d+)/(\d{2,4})",
    re.IGNORECASE,
)


def _normalize_year_2digit(year: str) -> str:
    """Anno -> 2 cifre (per slug convention dm_03_09_2021 / dlgs_81_08)."""
    return year[-2:] if len(year) == 4 else year


def _normalize_year_4digit(year: str) -> str:
    """Anno -> 4 cifre (per slug Reg CE 852/2004 / accordo_stato_regioni_2025)."""
    if len(year) == 2:
        # Heuristic: 00-49 -> 20XX, 50-99 -> 19XX
        n = int(year)
        return f"20{year}" if n <= 49 else f"19{year}"
    return year


def extract_citation_slugs(text: str) -> list[str]:
    """Estrai canonical slugs di tutte le citazioni decreti in ``text``.

    Strategia (a): regex pattern -> normalizza a canonical slug.
    Output: lista slug deduplicata (ordine match-first preservato).

    Esempi:
      "Decreto ministeriale 3 agosto 2015" -> ["dm_03_08_2015"]
      "D.M. 03/09/2021" -> ["dm_03_09_2021"]
      "D.Lgs 81/2008 art. 46" -> ["dlgs_81_08"]
      "D.Lgs. 81/08" -> ["dlgs_81_08"]
      "Reg. CE 852/2004" -> ["reg_ce_852_2004"]
      "Accordo Stato-Regioni 2025" -> ["accordo_stato_regioni_2025"]
      "Bullet senza decreti citati" -> []

    Mixed text:
      "Attua D.Lgs 81/2008 art. 46 + DM 3 agosto 2015" ->
        ["dlgs_81_08", "dm_03_08_2015"]
    """
    found: list[str] = []
    seen: set[str] = set()

    # IMPORTANTE: priorita' DM datato > DM numerato. I pattern datato consumano
    # (sostituiscono con spazio) la porzione matchata prima di passare al
    # numerato, evitando che "03/09/2021" venga ri-interpretato come "9/2021".
    text_for_numbered = text

    # DM datato in lettere: "3 agosto 2015"
    def _dm_dated_full_repl(m: "re.Match[str]") -> str:
        nonlocal found, seen
        day = m.group(1).zfill(2)
        month_num = _MONTH_TO_NUM[m.group(2).lower()]
        year = m.group(3)
        slug = f"dm_{day}_{month_num}_{year}"
        if slug not in seen:
            seen.add(slug)
            found.append(slug)
        return " " * len(m.group(0))

    text_for_numbered = _DM_DATED_FULL.sub(_dm_dated_full_repl, text_for_numbered)

    # DM datato slash: "03/08/2015"
    def _dm_dated_slash_repl(m: "re.Match[str]") -> str:
        nonlocal found, seen
        day = m.group(1).zfill(2)
        month = m.group(2).zfill(2)
        year = _normalize_year_4digit(m.group(3))
        slug = f"dm_{day}_{month}_{year}"
        if slug not in seen:
            seen.add(slug)
            found.append(slug)
        return " " * len(m.group(0))

    text_for_numbered = _DM_DATED_SLASH.sub(_dm_dated_slash_repl, text_for_numbered)

    # DM numerato: "DM 388/2003" -> "dm_388_2003"
    # Scanna SOLO text_for_numbered (dove i datati sono stati blanked) per
    # evitare overlap con date slash gia' catturate.
    for m in _DM_NUMBERED.finditer(text_for_numbered):
        n = m.group(1)
        year = _normalize_year_4digit(m.group(2))
        slug = f"dm_{n}_{year}"
        if slug not in seen:
            seen.add(slug)
            found.append(slug)

    # D.Lgs: "81/2008" -> "dlgs_81_08"
    for m in _DLGS.finditer(text):
        n = m.group(1)
        year = _normalize_year_2digit(m.group(2))
        slug = f"dlgs_{n}_{year}"
        if slug not in seen:
            seen.add(slug)
            found.append(slug)

    # Reg CE: "852/2004" -> "reg_ce_852_2004"
    for m in _REG_CE.finditer(text):
        n = m.group(1)
        year = _normalize_year_4digit(m.group(2))
        slug = f"reg_ce_{n}_{year}"
        if slug not in seen:
            seen.add(slug)
            found.append(slug)

    # Reg UE: "1907/2006" -> "reg_ue_1907_2006"
    for m in _REG_UE.finditer(text):
        n = m.group(1)
        year = _normalize_year_4digit(m.group(2))
        slug = f"reg_ue_{n}_{year}"
        if slug not in seen:
            seen.add(slug)
            found.append(slug)

    # Accordo SR: "2025" -> "accordo_stato_regioni_2025"
    for m in _ACCORDO_SR.finditer(text):
        year = _normalize_year_4digit(m.group(1))
        slug = f"accordo_stato_regioni_{year}"
        if slug not in seen:
            seen.add(slug)
            found.append(slug)

    # D.P.R.: "151/2011" -> "dpr_151_2011"
    for m in _DPR.finditer(text):
        n = m.group(1)
        year = _normalize_year_4digit(m.group(2))
        slug = f"dpr_{n}_{year}"
        if slug not in seen:
            seen.add(slug)
            found.append(slug)

    return found


def find_hallucinated_citations(
    text_fields: list[str],
    allowed_slugs: set[str],
) -> list[str]:
    """Ritorna lista slug citati in text_fields che NON sono in allowed_slugs.

    text_fields: lista stringhe da scansionare (bullets + speaker_notes + quiz_options).
    allowed_slugs: set di slug ammessi (course.regulation_ids).

    Output: slug citati ma fuori scope (lista deduplicata).
    """
    all_cited: list[str] = []
    seen: set[str] = set()
    for field in text_fields:
        if not field:
            continue
        for slug in extract_citation_slugs(field):
            if slug not in seen:
                seen.add(slug)
                all_cited.append(slug)
    return [s for s in all_cited if s not in allowed_slugs]
