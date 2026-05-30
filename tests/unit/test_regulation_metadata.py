"""Unit tests per regulation_metadata.top_section_of.

Verifica la TOC verificata D.Lgs 81/08 (13 Titoli + 51 Allegati) + single-section
regulations. Casi noti incrociati con sample-read PPTX E2E ANT L1 (articoli citati
per quartile, analista 2026-05-30).

Test disciplinari (analista sign-off):
  - Boundary Art. 61↔62 (Titolo I/II)
  - Boundary Art. 87↔88 (Titolo III/IV)
  - Art. 286-bis...286-septies -> Titolo X-bis
  - Allegato I-bis ESISTE (D.L. 19/2024) -> Titolo I
  - Allegati 3A/3B suddivisione Allegato III -> Titolo I
  - Casi cross-titolo strutturali ANT L1: Art. 121/132 -> Titolo IV (cantieri)
  - Allegato XLI -> Titolo IX (norme UNI atmosfera, target B3 in ANT M3)
  - Single-section regulations (DM antincendio, Reg CE 852) -> slug stesso
"""

from __future__ import annotations

import pytest

from app.services.regulation_metadata import top_section_of


# --------------------------------------------------------------------------
# D.Lgs 81/08 — 13 Titoli, range numerico
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "article, expected",
    [
        # Titolo I — Principi Comuni (Art. 1-61)
        ("Art. 1", "Titolo I"),
        ("Art. 14", "Titolo I"),
        ("Art. 15", "Titolo I"),       # Inizio Capo III (non Titolo I-bis)
        ("Art. 27", "Titolo I"),       # Cita Allegato I-bis patente a punti
        ("Art. 35", "Titolo I"),       # Riunione periodica SPP
        ("Art. 40", "Titolo I"),       # Prevenzione incendi
        ("Art. 46", "Titolo I"),       # Prevenzione incendi CNVVF
        ("Art. 47", "Titolo I"),       # RLS
        ("Art. 54", "Titolo I"),       # Fine Capo III
        ("Art. 55", "Titolo I"),       # Inizio Capo IV
        ("Art. 61", "Titolo I"),       # ULTIMO Titolo I (verificato Normattiva)
        # Titolo II — Luoghi di lavoro (Art. 62-68)
        ("Art. 62", "Titolo II"),      # PRIMO Titolo II (verificato Normattiva)
        ("Art. 65", "Titolo II"),
        ("Art. 68", "Titolo II"),      # Ultimo Titolo II
        # Titolo III — Uso attrezzature e DPI (Art. 69-87)
        ("Art. 69", "Titolo III"),
        ("Art. 80", "Titolo III"),     # Impianti elettrici
        ("Art. 87", "Titolo III"),     # ULTIMO Titolo III (verificato Normattiva)
        # Titolo IV — Cantieri (Art. 88-160)
        ("Art. 88", "Titolo IV"),      # PRIMO Titolo IV (verificato Normattiva)
        ("Art. 89", "Titolo IV"),
        ("Art. 95", "Titolo IV"),      # POS
        ("Art. 98", "Titolo IV"),      # CSE
        ("Art. 121", "Titolo IV"),     # Cantieri scavi (target B3 cross-Titolo ANT)
        ("Art. 132", "Titolo IV"),     # Ponteggi (target B3 cross-Titolo ANT)
        ("Art. 160", "Titolo IV"),     # Ultimo Titolo IV
        # Titolo V — Segnaletica (Art. 161-166)
        ("Art. 161", "Titolo V"),
        ("Art. 166", "Titolo V"),
        # Titolo VI — Mov. manuale (Art. 167-171)
        ("Art. 167", "Titolo VI"),
        ("Art. 171", "Titolo VI"),
        # Titolo VII — Videoterminali (Art. 172-179)
        ("Art. 172", "Titolo VII"),
        ("Art. 179", "Titolo VII"),
        # Titolo VIII — Agenti fisici (Art. 180-220)
        ("Art. 180", "Titolo VIII"),
        ("Art. 209", "Titolo VIII"),
        ("Art. 220", "Titolo VIII"),
        # Titolo IX — Sostanze pericolose (Art. 221-265)
        ("Art. 221", "Titolo IX"),
        ("Art. 222", "Titolo IX"),
        ("Art. 251", "Titolo IX"),
        ("Art. 265", "Titolo IX"),
        # Titolo X — Agenti biologici (Art. 266-286)
        ("Art. 266", "Titolo X"),
        ("Art. 286", "Titolo X"),      # Art. 286 base (senza suffisso)
        # Titolo X-bis — Art. 286-bis...286-septies (suffisso)
        ("Art. 286-bis", "Titolo X-bis"),
        ("Art. 286-ter", "Titolo X-bis"),
        ("Art. 286-quater", "Titolo X-bis"),
        ("Art. 286-quinquies", "Titolo X-bis"),
        ("Art. 286-sexies", "Titolo X-bis"),
        ("Art. 286-septies", "Titolo X-bis"),
        # Titolo XI — ATEX (Art. 287-297)
        ("Art. 287", "Titolo XI"),
        ("Art. 288", "Titolo XI"),
        ("Art. 297", "Titolo XI"),
        # Titolo XII — Disposizioni penali (Art. 298-303)
        ("Art. 298", "Titolo XII"),
        ("Art. 303", "Titolo XII"),
        # Titolo XIII — Norme transitorie (Art. 304-306)
        ("Art. 304", "Titolo XIII"),
        ("Art. 306", "Titolo XIII"),
    ],
)
def test_dlgs_81_08_titoli_numerici(article: str, expected: str) -> None:
    assert top_section_of("dlgs_81_08", article) == expected


# --------------------------------------------------------------------------
# D.Lgs 81/08 — 51 Allegati (campionatura significativa)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "article, expected",
    [
        # Titolo I — sanzionatori + organizzazione + sorveglianza
        ("Allegato I", "Titolo I"),
        ("Allegato I-bis", "Titolo I"),         # ESISTE (D.L. 19/2024 patente a punti)
        ("Allegato II", "Titolo I"),
        ("Allegato III", "Titolo I"),
        ("Allegato 3A", "Titolo I"),
        ("Allegato 3B", "Titolo I"),
        # Titolo II
        ("Allegato IV", "Titolo II"),
        # Titolo III
        ("Allegato V", "Titolo III"),
        ("Allegato VIII", "Titolo III"),
        # Titolo IV — Cantieri (14 Allegati, cuore patologia cross-titolo)
        ("Allegato XIV", "Titolo IV"),          # Contenuti corso coordinatori
        ("Allegato XV", "Titolo IV"),           # PSC
        ("Allegato XVI", "Titolo IV"),          # Fascicolo opera
        ("Allegato XVII", "Titolo IV"),
        ("Allegato XX", "Titolo IV"),
        ("Allegato XXI", "Titolo IV"),
        ("Allegato XXIII", "Titolo IV"),
        # Titolo V — Segnaletica
        ("Allegato XXIV", "Titolo V"),
        ("Allegato XXVII", "Titolo V"),         # Segnaletica antincendio
        ("Allegato XXXII", "Titolo V"),
        # Titolo VI — Mov. manuale
        ("Allegato XXXIII", "Titolo VI"),
        # Titolo VII — VDT
        ("Allegato XXXIV", "Titolo VII"),
        # Titolo VIII — Agenti fisici
        ("Allegato XXXV", "Titolo VIII"),
        ("Allegato XXXVI", "Titolo VIII"),
        ("Allegato XXXIX", "Titolo VIII"),
        # Titolo IX — Sostanze pericolose
        ("Allegato XL", "Titolo IX"),
        ("Allegato XLI", "Titolo IX"),          # Atmosfera norme UNI (target B3 ANT M3)
        # Titolo X — Biologici
        ("Allegato XLII", "Titolo X"),
        ("Allegato XLIII", "Titolo X"),
        ("Allegato XLIII-bis", "Titolo X"),
        ("Allegato XLIII-ter", "Titolo X"),
        ("Allegato XLVIII", "Titolo X"),
        # Titolo XI — ATEX
        ("Allegato XLIX", "Titolo XI"),
        ("Allegato L", "Titolo XI"),
        ("Allegato LI", "Titolo XI"),
    ],
)
def test_dlgs_81_08_allegati(article: str, expected: str) -> None:
    assert top_section_of("dlgs_81_08", article) == expected


# --------------------------------------------------------------------------
# Edge cases parsing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "article, expected",
    [
        # Article null o vuoto
        (None, "Sconosciuto"),
        ("", "Sconosciuto"),
        # Numero fuori range valido D.Lgs (Art > 306, era "Sconosciuto"
        # pre-D-177 2026-05-30, ora external_reference: range valido 1..306,
        # numeri oltre sono citazioni Codice Penale/Civile incrociate).
        ("Art. 999", "external_reference"),
        ("Art. 0", "Sconosciuto"),  # 0 below range: parsing-noise, NOT
                                    # external_reference (Art. 0 non esiste
                                    # in nessun codice). Discriminazione
                                    # below-range vs above-range nel branch
                                    # external_reference di _classify_dlgs.
        # Allegato non-classificato
        ("Allegato ZZZZ", "Sconosciuto"),
        # Forme tipografiche variant (parser dovrebbe normalizzare)
        ("allegato i", "Titolo I"),             # lowercase
        ("ALLEGATO XV", "Titolo IV"),           # uppercase
        ("allegato XLI", "Titolo IX"),
    ],
)
def test_dlgs_81_08_edge_cases(article: str | None, expected: str) -> None:
    assert top_section_of("dlgs_81_08", article) == expected


# --------------------------------------------------------------------------
# Single-section regulations (top_section = slug stesso)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "slug, article",
    [
        ("dm_02_09_2021", "Art. 1"),
        ("dm_02_09_2021", "Allegato I"),
        ("dm_03_09_2021", "Art. 5"),
        ("dm_01_09_2021", "Art. 10"),
        ("reg_ce_852_2004", "Art. 5"),
        ("reg_ce_852_2004", "Allegato II"),
        ("dlgs_193_2007", "Art. 1"),
        ("accordo_stato_regioni_2025", "Capo I"),
        ("dm_388_2003", "Art. 3"),
    ],
)
def test_single_section_regulations(slug: str, article: str) -> None:
    """Per regulations a singolo top_section, top_section = slug stesso."""
    assert top_section_of(slug, article) == slug


# --------------------------------------------------------------------------
# Regulation sconosciuta -> degrade graceful (top_section = slug)
# --------------------------------------------------------------------------


def test_regulation_sconosciuta_degrade_graceful() -> None:
    """Slug non riconosciuto: B3 lo tratta come single-section."""
    assert top_section_of("normativa_inventata_2030", "Art. 5") == "normativa_inventata_2030"


# --------------------------------------------------------------------------
# D-177 external_reference: chunks cross-codice (CP/CC) incrociati in D.Lgs
# --------------------------------------------------------------------------
# Verifica preliminare DB ha rivelato 13 chunks cross-codice in dlgs_81_08:
# Art. 329, 331, 395 (CP) + Art. 589 (CP, ×2) + Art. 1418 (CC, ×2) +
# Art. 1478, 2083 (CC) + Art. 2222 (CC, ×4). Sono semanticamente validi MA
# usarli come fonte primaria di slide produce nx_normative_ref errati
# ("D.Lgs 81/08 Art. 1418" non esiste, Art. 1418 e' Codice Civile).
# Range valido D.Lgs 81/08: Art. 1..306 (testo coordinato vigente).


@pytest.mark.parametrize(
    "article",
    [
        "Art. 329",   # Codice Penale - omissione referto
        "Art. 331",   # Codice Penale - omessa denuncia
        "Art. 395",   # Codice Penale
        "Art. 589",   # Codice Penale - omicidio colposo
        "Art. 1418",  # Codice Civile - nullita' contratto
        "Art. 1478",  # Codice Civile
        "Art. 2083",  # Codice Civile - piccolo imprenditore
        "Art. 2222",  # Codice Civile - lavoro autonomo
        "Art. 307",   # boundary: appena fuori range valido
        "Art. 500",   # numero arbitrario fuori range
    ],
)
def test_dlgs_external_reference_above_range(article: str) -> None:
    """Art. con numero > 306 in dlgs_81_08 -> external_reference."""
    assert top_section_of("dlgs_81_08", article) == "external_reference"


@pytest.mark.parametrize(
    "article,expected",
    [
        ("Art. 1", "Titolo I"),      # boundary inferiore
        ("Art. 306", "Titolo XIII"), # boundary superiore valido
        ("Art. 286-bis", "Titolo X-bis"),
    ],
)
def test_dlgs_at_boundary_remain_classified(article: str, expected: str) -> None:
    """Boundary valido inferiore (Art. 1), superiore (Art. 306), suffisso
    Titolo X-bis (Art. 286-bis): NON external_reference."""
    assert top_section_of("dlgs_81_08", article) == expected


def test_dlgs_allegati_not_external_reference() -> None:
    """Allegati NON sono soggetti al filtro article_range (sono identificati
    dal prefix Allegato e classificati via DLGS_81_08_ALLEGATI lookup).
    Allegato V e' Titolo III, non external_reference."""
    assert top_section_of("dlgs_81_08", "Allegato V") == "Titolo III"


def test_dlgs_parsing_noise_remains_sconosciuto() -> None:
    """Parsing-noise (Art. malformato, NULL) resta 'Sconosciuto', NON diventa
    external_reference. Distinzione semantica: external_reference = sappiamo
    cos'e' (cross-codice), Sconosciuto = parser non riconosce."""
    assert top_section_of("dlgs_81_08", None) == "Sconosciuto"
    assert top_section_of("dlgs_81_08", "garbage") == "Sconosciuto"
    assert top_section_of("dlgs_81_08", "art. malformato senza numero") == "Sconosciuto"


def test_single_section_regulations_no_external_reference() -> None:
    """Regulations single-section (DM, Reg CE) non hanno range articoli
    nominale -> Art. 999 di DM 03/09/2021 resta dm_03_09_2021, NON
    external_reference. La logica external_reference vive solo dove
    ARTICLE_RANGE_VALID_BY_SLUG[slug] e' definito."""
    assert top_section_of("dm_03_09_2021", "Art. 999") == "dm_03_09_2021"
    assert top_section_of("reg_ce_852_2004", "Art. 999") == "reg_ce_852_2004"
