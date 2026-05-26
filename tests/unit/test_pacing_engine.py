"""Unit tests for PacingEngine (PHASE 3.2, BLUEPRINT §06B + GAP-1 v2.0).

Pure math, no I/O. Covers:
- Commercial invariant (1 slide / 30 s):
  1h std → 120, 4h std → 480, 8h std → 960, 16h std → 1920
- Density multiplier: 4h leggera → 384 (480 × 0.8), 4h intensiva → 600 (480 × 1.25)
- DIAGRAM excluded from DISTRIBUTION (FIX-8 v1.0)
- DISTRIBUTION sums to 1.00 (per-module distribution sums to slide_count)
- Module count: max(2, ceil(total_slides / 40))
- Semantic module titles from COURSE_CATALOG vs fallback "Modulo N"
"""

from __future__ import annotations

from app.models.core import SlideDensity
from app.services.pacing_engine import PacingEngine


# ─────────── Commercial invariant (1 slide / 30 s) ───────────


def test_1h_standard_yields_120_slides() -> None:
    plan = PacingEngine().calculate(1.0, SlideDensity.STANDARD)
    assert plan.total_slides == 120


def test_4h_standard_yields_480_slides() -> None:
    plan = PacingEngine().calculate(4.0, SlideDensity.STANDARD)
    assert plan.total_slides == 480


def test_8h_standard_yields_960_slides() -> None:
    plan = PacingEngine().calculate(8.0, SlideDensity.STANDARD)
    assert plan.total_slides == 960


def test_16h_standard_yields_1920_slides() -> None:
    plan = PacingEngine().calculate(16.0, SlideDensity.STANDARD)
    assert plan.total_slides == 1920


# ─────────── Density multiplier ───────────


def test_4h_leggera_yields_384_slides() -> None:
    """480 × 0.8 = 384 (prompt 3.2 explicit assertion)."""
    plan = PacingEngine().calculate(4.0, SlideDensity.LEGGERA)
    assert plan.total_slides == 384


def test_4h_intensiva_yields_600_slides() -> None:
    """480 × 1.25 = 600."""
    plan = PacingEngine().calculate(4.0, SlideDensity.INTENSIVA)
    assert plan.total_slides == 600


def test_density_defaults_to_standard() -> None:
    """Calling without density must equal STANDARD."""
    plan_default = PacingEngine().calculate(1.0)
    plan_explicit = PacingEngine().calculate(1.0, SlideDensity.STANDARD)
    assert plan_default.total_slides == plan_explicit.total_slides


# ─────────── FASE 5 vast-hopping: DIAGRAM re-enabled (was FIX-8 excluded) ───────────


def test_diagram_in_class_distribution() -> None:
    """FASE 5: DIAGRAM ora è nella DISTRIBUTION al 7% (era escluso FIX-8 v1.0)."""
    assert "DIAGRAM" in PacingEngine.DISTRIBUTION
    assert PacingEngine.DISTRIBUTION["DIAGRAM"] == 0.07


def test_diagram_in_module_distribution() -> None:
    """FASE 5: i moduli ora includono DIAGRAM nel breakdown per-tipo."""
    plan = PacingEngine().calculate(8.0, SlideDensity.STANDARD)
    # Almeno un modulo deve avere DIAGRAM ≥ 1 (8h = 960 slide, 7% = ~67 diagram)
    assert any("DIAGRAM" in m.slide_distribution for m in plan.modules)


def test_distribution_sums_to_one() -> None:
    """DISTRIBUTION must total 1.00 (no slide budget is silently lost)."""
    assert abs(sum(PacingEngine.DISTRIBUTION.values()) - 1.00) < 1e-9


# ─────────── Per-module distribution invariants ───────────


def test_per_module_distribution_sums_to_slide_count() -> None:
    """Every module's per-type sum must equal its slide_count.

    The last type absorbs the rounding remainder by design (BP §06B).
    """
    plan = PacingEngine().calculate(8.0, SlideDensity.STANDARD)
    for m in plan.modules:
        assert sum(m.slide_distribution.values()) == m.slide_count, (
            f"module {m.module_index}: "
            f"dist={m.slide_distribution} sum={sum(m.slide_distribution.values())} "
            f"!= slide_count={m.slide_count}"
        )


def test_total_slides_equals_sum_of_modules() -> None:
    """No slide is dropped between total_slides and per-module slice."""
    plan = PacingEngine().calculate(8.0, SlideDensity.STANDARD)
    assert sum(m.slide_count for m in plan.modules) == plan.total_slides


# ─────────── Module count ───────────


def test_minimum_two_modules_even_for_short_course() -> None:
    """30 minutes → 60 slides → ceil(60/40)=2 modules (already ≥2)."""
    plan = PacingEngine().calculate(0.5, SlideDensity.STANDARD)
    assert plan.total_slides == 60
    assert len(plan.modules) == 2


def test_module_count_scales_with_duration() -> None:
    plan_1h = PacingEngine().calculate(1.0, SlideDensity.STANDARD)
    plan_8h = PacingEngine().calculate(8.0, SlideDensity.STANDARD)
    # 120 / 40 = 3 modules; 960 / 40 = 24 modules.
    assert len(plan_1h.modules) == 3
    assert len(plan_8h.modules) == 24


# ─────────── Module titles ───────────


def test_module_titles_default_to_modulo_n() -> None:
    plan = PacingEngine().calculate(1.0, SlideDensity.STANDARD)
    titles = [m.title for m in plan.modules]
    assert titles == ["Modulo 1", "Modulo 2", "Modulo 3"]


def test_module_titles_use_catalog_when_provided() -> None:
    """Semantic titles from COURSE_CATALOG (BP §13) win when supplied."""
    catalog_titles = [
        "Concetti di rischio",
        "Prevenzione e protezione",
        "Organizzazione della prevenzione",
        "Diritti e doveri",
    ]
    plan = PacingEngine().calculate(
        1.0, SlideDensity.STANDARD, module_titles=catalog_titles
    )
    # 1h → 3 modules; first 3 catalog titles consumed in order.
    assigned = [m.title for m in plan.modules]
    assert assigned == catalog_titles[: len(plan.modules)]


def test_module_titles_falls_back_when_catalog_shorter_than_modules() -> None:
    """If fewer catalog titles than modules, extra modules get the default."""
    plan = PacingEngine().calculate(
        8.0, SlideDensity.STANDARD, module_titles=["A", "B"]
    )
    assert plan.modules[0].title == "A"
    assert plan.modules[1].title == "B"
    assert plan.modules[2].title == "Modulo 3"
