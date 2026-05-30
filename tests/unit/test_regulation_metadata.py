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
        # Numero fuori range (rumore di parsing)
        ("Art. 999", "Sconosciuto"),
        ("Art. 0", "Sconosciuto"),
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
