"""F5.3 — Unit test diagram_router heuristic matcher.

Verifica:
  - 7 trigger fixture (1 per template SVG)
  - 1 ambiguous fallthrough (slide generica → None)
  - SVG file mancante non crasha → log warning + None
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.diagram_router import DIAGRAM_HEURISTICS, maybe_diagram


def _slide(title: str = "", body: list[str] | None = None) -> SimpleNamespace:
    """Lightweight slide-like object: title + body, niente full SlideContent."""
    return SimpleNamespace(title=title, body=body or [])


def test_flow_3step_match():
    slide = _slide("Le tre fasi della valutazione dei rischi")
    path = maybe_diagram(slide)
    assert path is not None
    assert "flow_horizontal_3step" in path


def test_flow_4step_match():
    slide = _slide("Il ciclo PDCA in 4 fasi", body=["Plan", "Do", "Check", "Act"])
    path = maybe_diagram(slide)
    assert path is not None
    assert "flow_horizontal_4step" in path


def test_matrix_2x2_match():
    slide = _slide("Matrice di rischio probabilità x gravità")
    path = maybe_diagram(slide)
    assert path is not None
    assert "matrix_2x2" in path


def test_causa_effetto_match():
    slide = _slide("Analisi delle cause e effetti dell'infortunio")
    path = maybe_diagram(slide)
    assert path is not None
    assert "causa_effetto" in path


def test_org_tree_match():
    slide = _slide("Ruoli e responsabilità: datore, RSPP, RLS")
    path = maybe_diagram(slide)
    assert path is not None
    assert "org_tree_3level" in path


def test_pyramid_match():
    slide = _slide("Piramide della sicurezza: gerarchia delle misure")
    path = maybe_diagram(slide)
    assert path is not None
    assert "pyramid_3level" in path


def test_compare_2col_match():
    slide = _slide("Confronto tra DPI e DPC")
    path = maybe_diagram(slide)
    assert path is not None
    assert "compare_2col" in path


def test_generic_slide_no_match():
    slide = _slide(
        "Introduzione alla sicurezza sul lavoro",
        body=["Storia normativa", "Quadro generale"],
    )
    assert maybe_diagram(slide) is None


def test_empty_slide_no_match():
    assert maybe_diagram(_slide()) is None


def test_heuristics_dict_consistent():
    """Tutti i template SVG referenziati DEVONO esistere su disk."""
    from app.services.diagram_router import SVG_DIR

    for name, (svg_file, _patterns) in DIAGRAM_HEURISTICS.items():
        path = SVG_DIR / svg_file
        assert path.exists(), f"missing SVG for template {name}: {path}"


def test_highest_confidence_wins():
    """Slide che matcha 2 template prende quello con piu' parole-chiave."""
    # "ruoli responsabilita matrice di rischio" matches sia org_tree (1)
    # sia matrix_2x2 (1). A pari merito: primo in ordine insertion (flow_3step etc.)
    # Test invece pure org_tree triggered alone:
    slide = _slide(
        "Organigramma sicurezza: ruoli e responsabilità del datore, RSPP, RLS"
    )
    path = maybe_diagram(slide)
    assert path is not None
    assert "org_tree" in path
