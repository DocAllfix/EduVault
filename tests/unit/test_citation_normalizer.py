"""D-178 V1.5 unit tests — citation normalizer + hallucination detection.

Dataset stabili (analista sign-off 2026-05-30):
  - Slide patologica vera (slide 67 PPTX `ANT_L1_0dfe39ad`):
      bullet "Decreto ministeriale 3 agosto 2015 - riferimento chiave" +
      "Attua decreto legislativo n. 81/2008 art. 46".
      course.regulation_ids ANT L1 = [dlgs_81_08, dm_02_09_2021,
                                       dm_03_09_2021, dm_01_09_2021].
      Atteso: ["dm_03_08_2015"] hallucinated (dlgs_81_08 in scope).
  - Slide vere positive (66, 3, 5): bullets con citazioni IN scope ANT L1
    o senza citazioni. Atteso: [] hallucinated.

Costruito per evitare falsi positivi e per dare visibilita' immediata se il
regex cattura qualcosa di nuovo dopo edit.
"""

from __future__ import annotations

import pytest

from app.services.citation_normalizer import (
    extract_citation_slugs,
    find_hallucinated_citations,
)

ANT_L1_ALLOWED: set[str] = {
    "dlgs_81_08",
    "dm_02_09_2021",
    "dm_03_09_2021",
    "dm_01_09_2021",
}


# --------------------------------------------------------------------------
# extract_citation_slugs — pattern coverage
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected_slugs",
    [
        # DM datato in lettere
        ("Decreto ministeriale 3 agosto 2015 — riferimento chiave",
         ["dm_03_08_2015"]),
        ("Decreto Ministeriale 10 marzo 1998",
         ["dm_10_03_1998"]),
        ("D.M. 3 settembre 2021",
         ["dm_03_09_2021"]),
        ("DM 2 settembre 2021",
         ["dm_02_09_2021"]),
        # DM datato slash
        ("D.M. 03/09/2021",
         ["dm_03_09_2021"]),
        ("DM 02/09/2021",
         ["dm_02_09_2021"]),
        # DM numerato
        ("D.M. 388/2003",
         ["dm_388_2003"]),
        # D.Lgs
        ("D.Lgs 81/2008 art. 46",
         ["dlgs_81_08"]),
        ("D.Lgs. 81/08",
         ["dlgs_81_08"]),
        ("decreto legislativo n. 81/2008",
         ["dlgs_81_08"]),
        # Reg CE
        ("Reg. CE 852/2004",
         ["reg_ce_852_2004"]),
        ("Regolamento (CE) n. 1272/2008",
         ["reg_ce_1272_2008"]),
        # Accordo SR
        ("Accordo Stato-Regioni 2025",
         ["accordo_stato_regioni_2025"]),
        ("Accordo SR 2011",
         ["accordo_stato_regioni_2011"]),
        # D.P.R.
        ("D.P.R. 151/2011",
         ["dpr_151_2011"]),
        # Mixed: due citazioni in stessa stringa
        ("Attua D.Lgs 81/2008 art. 46 + DM 3 agosto 2015 riferimento",
         ["dm_03_08_2015", "dlgs_81_08"]),
        # Nessuna citazione
        ("Bullet generico senza decreti citati",
         []),
        # Falso positivo prevenzione: numero senza prefix decreto
        ("Stanza 305 con vista panoramica",
         []),
    ],
)
def test_extract_citation_slugs(text: str, expected_slugs: list[str]) -> None:
    """Verifica pattern coverage + normalizzazione canonical slug."""
    result = extract_citation_slugs(text)
    assert sorted(result) == sorted(expected_slugs), f"text={text!r}"


# --------------------------------------------------------------------------
# find_hallucinated_citations — slide patologica vera + slide vere positive
# --------------------------------------------------------------------------


def test_slide_67_patologica_hallucinated_dm_03_08_2015() -> None:
    """Slide 67 PPTX `0dfe39ad`: 5 bullets reali. dm_03_08_2015 NON in
    course.regulation_ids ANT L1 -> hallucinated. dlgs_81_08 IN scope ->
    NON hallucinated."""
    bullets_67 = [
        "Decreto ministeriale 3 agosto 2015 - riferimento chiave",
        "Attua decreto legislativo n. 81/2008 art. 46",
        "Coinvolge ministri Interno e Lavoro",
        "Definisce criteri e misure per prevenzione e limitazione",
        "Si integra con norme tecniche di prevenzione incendi",
    ]
    hallucinated = find_hallucinated_citations(bullets_67, ANT_L1_ALLOWED)
    assert hallucinated == ["dm_03_08_2015"], (
        f"Atteso ['dm_03_08_2015'] hallucinated, trovato {hallucinated}"
    )


def test_slide_66_legit_dlgs_in_scope() -> None:
    """Slide 66 PPTX `0dfe39ad`: 'D.Lgs. 81/08' nei bullets. IN scope ->
    nessun hallucinated."""
    bullets_66 = [
        "Normativa generale non applicabile a cantieri temporanei",
        "Cantieri regolati da norme specifiche e titolo IV D.Lgs. 81/08",
        "Obbligo di misure di sicurezza antincendio specifiche",
        "Importanza di conoscere regole proprie del cantiere",
        "Garantire sicurezza senza confondere normative",
    ]
    hallucinated = find_hallucinated_citations(bullets_66, ANT_L1_ALLOWED)
    assert hallucinated == [], (
        f"Atteso [] hallucinated, trovato {hallucinated}"
    )


def test_slide_3_legit_no_citations() -> None:
    """Slide 3 PPTX `0dfe39ad`: bullets generici senza citazioni decreti."""
    bullets_3 = [
        "Definizione di combustione e processo chimico",
        "Sostanze combustibili e infiammabili",
        "Elementi necessari per innescare incendio",
        "Fonti di innesco e loro ruolo",
        "Effetti della combustione nel lavoro",
    ]
    hallucinated = find_hallucinated_citations(bullets_3, ANT_L1_ALLOWED)
    assert hallucinated == []


def test_empty_fields_safe() -> None:
    """Edge case: empty list, None field, empty string -> [] safe."""
    assert find_hallucinated_citations([], ANT_L1_ALLOWED) == []
    assert find_hallucinated_citations([""], ANT_L1_ALLOWED) == []
    assert find_hallucinated_citations(["", "   "], ANT_L1_ALLOWED) == []


def test_multiple_hallucinations_deduplicated() -> None:
    """Multiple field cite stessi slug hallucinated: dedup."""
    fields = [
        "DM 3 agosto 2015 e Decreto ministeriale 3 agosto 2015",
        "Ancora DM 03/08/2015",
    ]
    hallucinated = find_hallucinated_citations(fields, ANT_L1_ALLOWED)
    assert hallucinated == ["dm_03_08_2015"]


def test_haccp_course_scope_isolated() -> None:
    """Corso HACCP regulation_ids = {reg_ce_852_2004, dlgs_81_08}.
    DM antincendio citato -> hallucinated per HACCP (in scope per ANT L1)."""
    haccp_allowed = {"reg_ce_852_2004", "dlgs_81_08"}
    fields = ["Vedi DM 03/09/2021 per criteri antincendio"]
    hallucinated = find_hallucinated_citations(fields, haccp_allowed)
    assert hallucinated == ["dm_03_09_2021"]


def test_speaker_notes_included_in_scan() -> None:
    """find_hallucinated_citations accetta tutti i text_fields della slide:
    bullets + speaker_notes + quiz_options."""
    bullets = ["Bullet legittimo"]
    speaker_notes = ["La legge DM 3 agosto 2015 dice..."]
    quiz_options = ["Risposta A"]
    hallucinated = find_hallucinated_citations(
        bullets + speaker_notes + quiz_options, ANT_L1_ALLOWED
    )
    assert hallucinated == ["dm_03_08_2015"]
