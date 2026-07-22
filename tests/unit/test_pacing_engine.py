"""Unit test per PacingEngine (BLUEPRINT §06B + FASE 2 pacing dinamico).

Pure math, nessun I/O. I valori assoluti sono calcolati sulla regola 45s/slide
(FIX #29.0, era 30s). FASE 2 (2026-07-21): ``seconds_per_slide`` e` un parametro
di ``calculate`` (default 45) — l'utente puo` sceglierlo dal wizard (40-240s).
"""

from __future__ import annotations

from app.models.core import DEFAULT_SECONDS_PER_SLIDE, SlideDensity
from app.services.pacing_engine import PacingEngine


# ─────────── Regola di pacing (45s/slide, senza module_titles) ───────────


def test_1h_standard() -> None:
    assert PacingEngine().calculate(1.0, SlideDensity.STANDARD).total_slides == 86


def test_4h_standard() -> None:
    assert PacingEngine().calculate(4.0, SlideDensity.STANDARD).total_slides == 344


def test_8h_standard() -> None:
    assert PacingEngine().calculate(8.0, SlideDensity.STANDARD).total_slides == 688


# ─────────── Moltiplicatore densità ───────────


def test_density_leggera_and_intensiva_4h() -> None:
    eng = PacingEngine()
    assert eng.calculate(4.0, SlideDensity.LEGGERA).total_slides == 276
    assert eng.calculate(4.0, SlideDensity.INTENSIVA).total_slides == 430


def test_density_defaults_to_standard() -> None:
    assert (
        PacingEngine().calculate(1.0).total_slides
        == PacingEngine().calculate(1.0, SlideDensity.STANDARD).total_slides
    )


# ─────────── FASE 2: seconds_per_slide ───────────


def test_default_seconds_per_slide_is_45() -> None:
    assert DEFAULT_SECONDS_PER_SLIDE == 45.0


def test_calculate_default_equals_explicit_45() -> None:
    eng = PacingEngine()
    assert (
        eng.calculate(4.0, SlideDensity.STANDARD).total_slides
        == eng.calculate(4.0, SlideDensity.STANDARD, seconds_per_slide=45.0).total_slides
    )


def test_longer_slides_yield_fewer_slides() -> None:
    """Durata-slide doppia → circa meta` delle slide (scaling inverso)."""
    eng = PacingEngine()
    at_45 = eng.calculate(4.0, SlideDensity.STANDARD, seconds_per_slide=45.0).total_slides
    at_90 = eng.calculate(4.0, SlideDensity.STANDARD, seconds_per_slide=90.0).total_slides
    at_180 = eng.calculate(4.0, SlideDensity.STANDARD, seconds_per_slide=180.0).total_slides
    assert at_90 == at_45 // 2
    assert at_180 == at_45 // 4


def test_seconds_per_slide_monotonic() -> None:
    eng = PacingEngine()
    prev = 10**9
    for sps in (40.0, 45.0, 90.0, 180.0, 240.0):
        n = eng.calculate(8.0, SlideDensity.STANDARD, seconds_per_slide=sps).total_slides
        assert n < prev
        prev = n


# ─────────── DISTRIBUTION ───────────


def test_diagram_in_distribution() -> None:
    assert "DIAGRAM" in PacingEngine.DISTRIBUTION
    assert PacingEngine.DISTRIBUTION["DIAGRAM"] == 0.05


def test_distribution_sums_to_one() -> None:
    assert abs(sum(PacingEngine.DISTRIBUTION.values()) - 1.00) < 1e-9


# ─────────── Invarianti per-modulo (robusti alla durata) ───────────


def test_per_module_distribution_sums_to_content_slides() -> None:
    """La distribuzione copre solo le slide di CONTENUTO; slide_count include
    +2 bookend (MODULE_OPEN/MODULE_CLOSE) che stanno fuori dalla distribution."""
    plan = PacingEngine().calculate(8.0, SlideDensity.STANDARD)
    for m in plan.modules:
        assert sum(m.slide_distribution.values()) == m.slide_count - 2


def test_total_slides_equals_sum_of_modules() -> None:
    plan = PacingEngine().calculate(8.0, SlideDensity.STANDARD)
    assert sum(m.slide_count for m in plan.modules) == plan.total_slides


# ─────────── Titoli moduli ───────────


def test_module_titles_default_to_modulo_n() -> None:
    plan = PacingEngine().calculate(1.0, SlideDensity.STANDARD)
    assert [m.title for m in plan.modules] == ["Modulo 1", "Modulo 2", "Modulo 3"]


def test_module_titles_use_catalog_when_provided() -> None:
    catalog_titles = [
        "Concetti di rischio",
        "Prevenzione e protezione",
        "Organizzazione della prevenzione",
        "Diritti e doveri",
    ]
    plan = PacingEngine().calculate(
        1.0, SlideDensity.STANDARD, module_titles=catalog_titles
    )
    assigned = [m.title for m in plan.modules]
    assert assigned == catalog_titles[: len(plan.modules)]


def test_module_titles_define_module_count() -> None:
    """Se module_titles e` fornito, il numero di moduli = len(titles) (il
    catalogo definisce i moduli reali, FIX #30.9e)."""
    plan = PacingEngine().calculate(
        8.0, SlideDensity.STANDARD, module_titles=["A", "B"]
    )
    assert len(plan.modules) == 2
    assert [m.title for m in plan.modules] == ["A", "B"]
