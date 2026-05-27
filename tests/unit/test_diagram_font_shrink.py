"""FIX #31.7A (2026-05-27, analista review 8) — test auto-shrink font.

Scopo: il check_slots NON deve più rigettare per sforo lunghezza, e
render_diagram_to_svg deve applicare auto-shrink UNIFORME per diagramma
(non per-slot) per preservare bilanciamento visivo.

I 5 casi coprono: slot tutti sotto max (font default invariato),
slot tutti oltre max ma stesso sforo (font shrink uniforme), un solo
slot oltre max (font shrink ancora uniforme su tutti), sforo brutale
(truncate ultima rete a 16pt come sicurezza), e regressione su
matrix_2x2 (slot con font_default diversi per quadrante).
"""
from __future__ import annotations

import pytest

from app.services.diagram_service import (
    DIAGRAM_CATALOG,
    DiagramFilling,
    _compute_uniform_font_size,
    render_diagram_to_svg,
)


# ─────────────── _compute_uniform_font_size unit tests ───────────────


class TestComputeUniformFontSize:
    """Test isolato della funzione di calcolo font uniforme."""

    def test_all_slots_within_max_returns_default_font(self) -> None:
        """Tutti gli slot entro max_chars → font default invariato."""
        filling = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "Identifica",      # 10c ≤ 18
                "label_2": "Valuta",          # 6c
                "label_3": "Previeni",        # 8c
                "label_4": "Controlla",       # 9c
            },
            caption="Le 4 fasi del processo di prevenzione del rischio.",
        )
        font, _ = _compute_uniform_font_size(filling)
        assert font == 28  # default per flow_horizontal_4step

    def test_one_slot_over_max_shrinks_all(self) -> None:
        """Un solo slot lungo → font shrink applicato a tutti (uniforme)."""
        filling = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "Brevissimo",                  # 10c
                "label_2": "Identificazione rischi",      # 22c > 18
                "label_3": "OK",                          # 2c
                "label_4": "OK",                          # 2c
            },
            caption="Test single slot over max forces uniform shrink.",
        )
        font, _ = _compute_uniform_font_size(filling)
        # font calcolato per label_2: 28 * 18/22 = 22 (int)
        assert font == 22

    def test_uniform_shrink_picks_worst_slot(self) -> None:
        """Il font è dettato dal slot PEGGIORE (più lungo vs max)."""
        filling = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "Valutazione rischio",          # 19c (sforo lieve)
                "label_2": "Sorveglianza sanitaria",       # 22c (peggiore)
                "label_3": "OK",                           # 2c
                "label_4": "OK",                           # 2c
            },
            caption="Slot peggiore dovrebbe dettare il font del diagramma.",
        )
        font, _ = _compute_uniform_font_size(filling)
        # Pre-#31.7A: check_slots gentile su label_1 (19c→17c+…),
        # ma label_2 RESTA INTATTO (22c, ex-raise). Font: min(28, 28*18/22)=22
        assert font == 22

    def test_font_clipped_at_min_16pt(self) -> None:
        """Sforo brutale (label 90c per box 18c) → font clip a 16pt + truncate."""
        filling = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "x" * 90,  # 90c per max 18: 28*18/90=5pt → clip 16
                "label_2": "OK",
                "label_3": "OK",
                "label_4": "OK",
            },
            caption="Sforo brutale per forzare clip a 16pt + truncate.",
        )
        font, final_slots = _compute_uniform_font_size(filling)
        assert font == 16  # clipped
        # Ultima rete: capacity a 16pt = int(18 * 28/16) = 31, quindi truncate
        # a 30c + ellipsis = 31c finali
        assert final_slots["label_1"].endswith("…")
        assert len(final_slots["label_1"]) <= 32  # ~31c

    def test_matrix_2x2_distinct_default_fonts(self) -> None:
        """Template matrix_2x2 ha font_default 28 (axis) e 32 (quadrant).
        Il font uniforme è MIN tra i due se nessuno sfora."""
        filling = DiagramFilling(
            template_name="matrix_2x2",
            slots={
                "axis_x": "Probabilità",        # 11c ≤ 30
                "axis_y": "Gravità",            # 7c
                "quadrant_tl": "Rischio basso",
                "quadrant_tr": "Rischio medio",
                "quadrant_bl": "Rischio medio",
                "quadrant_br": "Rischio alto",
            },
            caption="Matrice 2x2 standard probabilità × gravità.",
        )
        font, _ = _compute_uniform_font_size(filling)
        # default max = 32 (quadrant). Nessuno sfora → font = 32
        assert font == 32


# ─────────────── render_diagram_to_svg integration tests ───────────────


class TestRenderDiagramToSvg:
    """Test che render_diagram_to_svg applichi correttamente lo shrink."""

    def test_no_shrink_keeps_default_font_in_svg(self) -> None:
        """Tutti slot brevi: SVG mantiene font-size="28" originale."""
        filling = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={"label_1": "A", "label_2": "B", "label_3": "C", "label_4": "D"},
            caption="Caption molto breve di test font invariato.",
        )
        svg = render_diagram_to_svg(filling)
        assert 'font-size="28"' in svg
        # Verifica che NON ci siano font diversi (uniformità)
        # default 28 conservato
        assert svg.count('font-size="28"') == 4

    def test_shrink_replaces_font_in_svg(self) -> None:
        """Slot lungo: SVG ha font-size sostituito col font uniforme calcolato."""
        filling = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "Identificazione rischi",        # 22c
                "label_2": "Valutazione",
                "label_3": "Misure",
                "label_4": "Monitoraggio",
            },
            caption="Test che lo shrink modifichi font-size nel SVG.",
        )
        svg = render_diagram_to_svg(filling)
        # default 28 NON deve più esserci (sostituito da 22)
        assert 'font-size="28"' not in svg
        assert 'font-size="22"' in svg
        assert svg.count('font-size="22"') == 4  # uniforme su tutti 4 slot

    def test_uniform_shrink_no_per_slot_imbalance(self) -> None:
        """Il principio analista: shrink UNIFORME per diagramma, non per-slot."""
        filling = DiagramFilling(
            template_name="flow_horizontal_3step",
            slots={
                "label_1": "Segnale Colore o Cartello",        # 25c > 20
                "label_2": "Segnali Luminosi o Acustici",      # 27c > 20 (peggiore)
                "label_3": "Segnali Gestuali e Verbali",       # 26c > 20
            },
            caption="Categorie di segnaletica D.Lgs. 81/08 Titolo V.",
        )
        svg = render_diagram_to_svg(filling)
        # font calcolato per peggiore (27c): 34 * 20/27 = 25 (int)
        # NB: tutti gli slot del template hanno font_default=34
        assert 'font-size="34"' not in svg  # default rimpiazzato
        assert 'font-size="25"' in svg
        assert svg.count('font-size="25"') == 3  # tutti 3 a 25, non solo il peggiore
        # I valori dei label DEVONO esserci interi (no truncate)
        assert "Segnali Luminosi o Acustici" in svg
        assert "Segnali Gestuali e Verbali" in svg
        assert "Segnale Colore o Cartello" in svg

    def test_label_with_xml_entities_escaped(self) -> None:
        """Regressione: label con &, <, > vengono escapati in entità XML."""
        filling = DiagramFilling(
            template_name="flow_horizontal_3step",
            slots={
                "label_1": "Maschere & filtri",
                "label_2": "DPI < 1mese",
                "label_3": "Vita > 5 anni",
            },
            caption="Test che il render escape correttamente i caratteri XML.",
        )
        svg = render_diagram_to_svg(filling)
        assert "Maschere &amp; filtri" in svg
        assert "DPI &lt; 1mese" in svg
        assert "Vita &gt; 5 anni" in svg
        # E non devono restare i raw
        assert "Maschere & filtri" not in svg
        assert "DPI < 1mese" not in svg


# ─────────────── check_slots regression tests ───────────────


class TestCheckSlotsNoRaise:
    """FIX #31.7A v2 (review 9): check_slots è validazione strutturale pura,
    ZERO mutazioni. Tutti i valori passano intatti al renderer che applica
    font-shrink uniforme + truncate solo al floor 16pt."""

    def test_no_raise_for_extreme_overflow(self) -> None:
        """Pre-#31.7A: label 35c su max 18 → raise. Post: passa intero."""
        filling = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "Identificazione e gestione completa",  # 35c
                "label_2": "Brevi",
                "label_3": "Test",
                "label_4": "OK",
            },
            caption="Test che nessun raise scatti per sforo grosso.",
        )
        assert filling.slots["label_1"] == "Identificazione e gestione completa"

    def test_check_slots_does_not_truncate_anymore(self) -> None:
        """FIX #31.7A v2 (review 9): check_slots NON tronca più. Pre-v2 un
        label 19c veniva mutato a "Valutazione risch…" causando incoerenza
        col font-shrink che lasciava interi label più lunghi nello stesso
        diagramma. Post-v2 il truncate scatta solo al floor 16pt dentro
        _compute_uniform_font_size, mai in check_slots."""
        filling = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "Valutazione rischio",  # 19c, era truncato pre-v2
                "label_2": "Scelta DPI",
                "label_3": "Formazione",
                "label_4": "Controllo",
            },
            caption="Test che check_slots non tronchi più i valori.",
        )
        # 19c resta intero — il render farà font-shrink se serve
        assert filling.slots["label_1"] == "Valutazione rischio"
        assert "…" not in filling.slots["label_1"]

    def test_compute_font_no_truncate_above_floor(self) -> None:
        """Esplicito: anche quando uniform_font è 19pt (sopra floor 16),
        zero truncate scatta sui valori — l'argine della patologia review 9."""
        filling = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "Valutazione rischio",       # 19c
                "label_2": "Scelta DPI adeguati",       # 19c
                "label_3": "Formazione e addestramento",  # 26c
                "label_4": "Controllo e sorveglianza",  # 24c
            },
            caption="Verifica che nessun ellipsis scatti sopra il floor.",
        )
        font, final = _compute_uniform_font_size(filling)
        assert font == 19  # sopra floor 16
        for v in final.values():
            assert "…" not in v

    def test_still_raises_for_missing_slot(self) -> None:
        """Regressione: missing slot DEVE comunque sollevare (errore semantico)."""
        with pytest.raises(ValueError, match="slot mancanti"):
            DiagramFilling(
                template_name="flow_horizontal_4step",
                slots={"label_1": "A", "label_2": "B"},  # mancano 3, 4
                caption="Test missing slots ancora raise come prima.",
            )


class TestShrinkTruncateCoordination:
    """FIX #31.7A v2 (review 9): test specifici per la patologia descritta
    dall'analista — short label troncato accanto a long label intero in
    diagramma a font ridotto."""

    def test_review9_pathology_short_and_long_both_intact_at_shrink(self) -> None:
        """RIPRODUCE patologia M1/idx15 di E2E #25: stesso diagramma con
        label 19c E label 26c. Pre-fix v2: 19c truncato a "Valutazione
        risch…", 26c intero. Post-fix v2: ENTRAMBI interi a font ridotto
        perché capacity@font_uniforme >= max(len) di tutti i label."""
        filling = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "Valutazione rischio",       # 19c
                "label_2": "Scelta DPI adeguati",       # 19c
                "label_3": "Formazione e addestramento",  # 26c (peggior slot)
                "label_4": "Controllo e sorveglianza",  # 24c
            },
            caption="Patologia review 9: short label NON deve essere troncato.",
        )
        font, final_slots = _compute_uniform_font_size(filling)
        # font calcolato per 26c: 28*18/26 = 19 → uniform 19pt (sopra floor)
        assert font == 19
        # Tutti i 4 label devono essere INTERI (zero ellipsis)
        for slot_name, value in final_slots.items():
            assert "…" not in value, f"slot {slot_name} ha ellipsis: '{value}'"
        assert final_slots["label_1"] == "Valutazione rischio"
        assert final_slots["label_2"] == "Scelta DPI adeguati"
        assert final_slots["label_3"] == "Formazione e addestramento"
        assert final_slots["label_4"] == "Controllo e sorveglianza"

    def test_review9_render_to_svg_no_ellipsis_above_floor(self) -> None:
        """Render end-to-end del caso patologico: zero "…" nel SVG generato."""
        filling = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "Valutazione rischio",
                "label_2": "Scelta DPI adeguati",
                "label_3": "Formazione e addestramento",
                "label_4": "Controllo e sorveglianza",
            },
            caption="Render verifica zero ellipsis sopra il floor 16pt.",
        )
        svg = render_diagram_to_svg(filling)
        # Zero "…" character anywhere in the rendered SVG text
        assert "…" not in svg
        # E tutti i 4 label valori INTERI presenti
        assert "Valutazione rischio" in svg
        assert "Scelta DPI adeguati" in svg
        assert "Formazione e addestramento" in svg
        assert "Controllo e sorveglianza" in svg

    def test_truncate_only_at_floor_16pt(self) -> None:
        """Truncate ultima rete scatta SOLO se uniform_font == 16pt."""
        # 4 slot da 90c su max 18 → font_target = 28*18/90 = 5pt → clip floor 16
        # capacity a 16pt = 18*28/16 = 31c → 90c > 31c → truncate scatta
        filling = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "x" * 90,
                "label_2": "y" * 90,
                "label_3": "z" * 90,
                "label_4": "w" * 90,
            },
            caption="Test che truncate scatti solo al floor 16pt.",
        )
        font, final_slots = _compute_uniform_font_size(filling)
        assert font == 16  # clipped al floor
        # Tutti truncati al floor (capacity ~31c + ellipsis)
        for value in final_slots.values():
            assert value.endswith("…")
            assert len(value) <= 32

    def test_no_truncate_just_above_floor_18pt(self) -> None:
        """Esattamente sopra il floor (18pt): nessun truncate, tutti interi."""
        # Construct: font_target = 18 → max_chars * 28 / 18 = 28c capacity
        # Label da 28c (max_chars 18 → font_target 28*18/28 = 18pt) → 18pt OK
        filling = DiagramFilling(
            template_name="flow_horizontal_4step",
            slots={
                "label_1": "x" * 28,  # 28c → font 18pt (sopra floor 16)
                "label_2": "ok",
                "label_3": "ok",
                "label_4": "ok",
            },
            caption="Test che a 18pt (sopra floor) nessun truncate scatti.",
        )
        font, final_slots = _compute_uniform_font_size(filling)
        assert font == 18  # sopra floor 16
        # Nessun ellipsis perché sopra il floor
        for value in final_slots.values():
            assert "…" not in value
        assert final_slots["label_1"] == "x" * 28  # intero
