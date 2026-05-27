"""FIX #31.6B (2026-05-27) — Test strip suffissi normativi DIAGRAM labels.

In E2E #24, 14/19 DIAGRAM finivano in branded fallback perché Azure-mini
emetteva ostinatamente label con suffissi "secondo D.Lgs. X/YY", "secondo
la normativa", "ex art. N". Lo schema rigettava (max_chars=18 + tolleranza
21), il fallback brandizzato partiva, e il render finale era un PNG
generico (icona stella in cerchio rosa con testo che sborda).

_strip_normative_suffix rimuove deterministicamente questi suffissi PRIMA
del validator (field_validator mode='before' su slots), riducendo i
fallback brandizzati dal 74% atteso a quasi-zero.
"""

from __future__ import annotations

import pytest

from app.services.diagram_service import (
    DiagramFilling,
    _strip_normative_suffix,
)


# ─────────────── strip unit tests ───────────────


class TestStripNormativeSuffix:
    """10 casi reali ripresi dai log E2E #24."""

    def test_strip_secondo_dlgs_art(self) -> None:
        assert (
            _strip_normative_suffix("Valutazione DPI secondo D.Lgs. 81/08 Art. 225")
            == "Valutazione DPI"
        )

    def test_strip_secondo_art(self) -> None:
        assert _strip_normative_suffix("uso DPI secondo l'art. 76") == "uso DPI"

    def test_strip_secondo_normativa(self) -> None:
        assert (
            _strip_normative_suffix("obblighi DPI secondo la normativa")
            == "obblighi DPI"
        )

    def test_strip_secondo_legge(self) -> None:
        assert (
            _strip_normative_suffix("implementare DPI secondo la legge")
            == "implementare DPI"
        )

    def test_strip_secondo_allegato(self) -> None:
        assert (
            _strip_normative_suffix("informazione DPI secondo Allegato VIII")
            == "informazione DPI"
        )

    def test_strip_secondo_art_numero(self) -> None:
        assert (
            _strip_normative_suffix("lavorare in sicurezza secondo art. 162")
            == "lavorare in sicurezza"
        )

    def test_strip_ex_art(self) -> None:
        assert _strip_normative_suffix("Valutazione DPI ex art. 28") == "Valutazione DPI"

    def test_strip_ai_sensi_di(self) -> None:
        assert (
            _strip_normative_suffix("Rischio biologico ai sensi del Titolo X")
            == "Rischio biologico"
        )

    def test_strip_dlgs_puro(self) -> None:
        """Caso senza 'secondo': label seguita direttamente da D.Lgs."""
        assert _strip_normative_suffix("Misure D.Lgs. 81/08") == "Misure"

    def test_strip_art_comma(self) -> None:
        assert (
            _strip_normative_suffix("Sorveglianza art. 41 comma 2")
            == "Sorveglianza"
        )

    def test_passthrough_label_pulito(self) -> None:
        """Label senza suffisso normativo NON deve essere toccato."""
        assert _strip_normative_suffix("Formazione") == "Formazione"
        assert _strip_normative_suffix("Valutazione del rischio") == "Valutazione del rischio"
        assert _strip_normative_suffix("DPI") == "DPI"

    def test_strip_empty_returns_original(self) -> None:
        """Edge case: se strip svuoterebbe il testo, ritorna originale ripulito."""
        # "secondo la normativa" da solo NON dovrebbe diventare ""
        result = _strip_normative_suffix("secondo la normativa")
        # Edge: il pattern matchato sulla stringa intera potrebbe svuotare;
        # la funzione fa safety check e ritorna originale ripulito
        assert result  # non vuoto


# ─────────────── DiagramFilling integration tests ───────────────


class TestDiagramFillingCoercion:
    """Il field_validator(mode='before') applica lo strip PRIMA del check
    tolerance, riducendo i fallback per i label LLM con suffissi."""

    def test_long_labels_with_suffix_pass_validation(self) -> None:
        """Label che SENZA strip violerebbero tolerance, POST strip entrano."""
        df = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "Valutazione DPI secondo D.Lgs. 81/08 Art. 225",  # 45c
                "label_2": "Formazione",  # 10c
                "label_3": "Sorveglianza ex art. 41",  # 23c
                "label_4": "Uso DPI secondo l'art. 76",  # 25c
            },
            caption="Le 4 fasi obbligatorie del processo di gestione DPI ex art. 76-79.",
        )
        # Strip ha agito: label_1 da 45c → 15c "Valutazione DPI"
        assert df.slots["label_1"] == "Valutazione DPI"
        assert df.slots["label_3"] == "Sorveglianza"
        assert df.slots["label_4"] == "Uso DPI"

    def test_label_within_max_chars_unchanged(self) -> None:
        """Label già entro max_chars NON viene toccato."""
        df = DiagramFilling(
            template_name="flow_horizontal_3step",
            slots={
                "label_1": "Valutazione",  # 11c
                "label_2": "Misure",  # 6c
                "label_3": "Controllo",  # 9c
            },
            caption="Le 3 fasi obbligatorie del processo di gestione rischio art. 28.",
        )
        assert df.slots["label_1"] == "Valutazione"
        assert df.slots["label_2"] == "Misure"
        assert df.slots["label_3"] == "Controllo"

    def test_label_excessive_after_strip_passes_through_for_render_shrink(self) -> None:
        """FIX #31.7A v2 (review 9): post-strip, check_slots NON tronca più.
        Il valore arriva intero al renderer che applica font-shrink uniforme.
        Pre-v2: 19c veniva truncato a 17c + "…". Post-v2: intero, fit gestito
        dal render."""
        df = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "Implementazione DPI",  # 19c, ex-truncated, ora intero
                "label_2": "Formazione",
                "label_3": "Sorveglianza",
                "label_4": "Controllo",
            },
            caption="Le 4 fasi obbligatorie del processo di gestione DPI ex art. 76-79.",
        )
        # FIX v2: il valore resta INTERO (zero truncate in check_slots)
        assert df.slots["label_1"] == "Implementazione DPI"
        assert "…" not in df.slots["label_1"]
