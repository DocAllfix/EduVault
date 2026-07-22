"""FASE 2 pacing dinamico — vincoli di layout calibrati sulla durata-slide.

Il test piu` importante e` l'INVARIANZA a 45s: ``build_layout_constraints(45)``
deve restituire esattamente i valori pre-esistenti (unica eccezione voluta:
DIAGRAM, D-240). Poi lo scaling proporzionale sui tipi narrativi e l'immutabilita`
dei tipi FIXED.
"""

from __future__ import annotations

from app.models.core import (
    _BASE_CONSTRAINTS,
    _NARRATIVE_TYPES,
    DEFAULT_SECONDS_PER_SLIDE,
    SlideType,
    build_layout_constraints,
)

# Valori attesi a 45s (baseline pre-Fase 2). DIAGRAM incluso col nuovo 90/160.
_EXPECTED_AT_45 = {
    SlideType.TITLE: (20, 90),
    SlideType.CONTENT_TEXT: (90, 160),
    SlideType.CONTENT_IMAGE: (90, 160),
    SlideType.DIAGRAM: (90, 160),  # D-240: prima 30/120
    SlideType.QUIZ: (25, 120),
    SlideType.CASE_STUDY: (90, 160),
    SlideType.RECAP: (90, 160),
    SlideType.CLOSING: (15, 90),
    SlideType.MODULE_OPEN: (30, 80),
    SlideType.MODULE_CLOSE: (60, 120),
}


# ─────────────── 1. Invarianza a 45s ───────────────


def test_default_equals_45() -> None:
    assert DEFAULT_SECONDS_PER_SLIDE == 45.0


def test_notes_exact_at_default_duration() -> None:
    """A 45s ogni tipo ha esattamente i valori base (fattore 1.0)."""
    c = build_layout_constraints(45.0)
    for stype, (exp_min, exp_max) in _EXPECTED_AT_45.items():
        assert c[stype].notes_min_words == exp_min, stype
        assert c[stype].notes_max_words == exp_max, stype


def test_default_argument_is_45() -> None:
    assert build_layout_constraints() == build_layout_constraints(45.0)


def test_non_notes_fields_never_change() -> None:
    """Solo notes_min/max scalano: title chars, bullet, flag restano fissi."""
    base = build_layout_constraints(45.0)
    scaled = build_layout_constraints(240.0)
    for stype in _BASE_CONSTRAINTS:
        b, s = base[stype], scaled[stype]
        assert b.title_max_chars == s.title_max_chars, stype
        assert b.body_min_bullets == s.body_min_bullets, stype
        assert b.body_max_bullets == s.body_max_bullets, stype
        assert b.bullet_max_words == s.bullet_max_words, stype
        assert b.requires_image == s.requires_image, stype
        assert b.requires_options == s.requires_options, stype


# ─────────────── 2. Scaling dei tipi narrativi ───────────────


def test_narrative_types_scale_proportionally() -> None:
    """A 90s (2×) i tipi narrativi raddoppiano le note."""
    c = build_layout_constraints(90.0)
    for stype in _NARRATIVE_TYPES:
        assert c[stype].notes_min_words == _BASE_CONSTRAINTS[stype].notes_min_words * 2
        assert c[stype].notes_max_words == _BASE_CONSTRAINTS[stype].notes_max_words * 2


def test_content_text_at_240s() -> None:
    """240s = 5.333× → 90→480, 160→853 (round)."""
    c = build_layout_constraints(240.0)
    assert c[SlideType.CONTENT_TEXT].notes_min_words == round(90 * 240 / 45)
    assert c[SlideType.CONTENT_TEXT].notes_max_words == round(160 * 240 / 45)
    assert c[SlideType.CONTENT_TEXT].notes_min_words == 480
    assert c[SlideType.CONTENT_TEXT].notes_max_words == 853


def test_content_text_at_40s_lower_bound() -> None:
    c = build_layout_constraints(40.0)
    assert c[SlideType.CONTENT_TEXT].notes_min_words == round(90 * 40 / 45)  # 80
    assert c[SlideType.CONTENT_TEXT].notes_max_words == round(160 * 40 / 45)  # 142


def test_narrative_scaling_is_monotonic() -> None:
    low = build_layout_constraints(40.0)[SlideType.CONTENT_TEXT]
    high = build_layout_constraints(240.0)[SlideType.CONTENT_TEXT]
    assert high.notes_min_words > low.notes_min_words
    assert high.notes_max_words > low.notes_max_words


# ─────────────── 3. Immutabilita` dei tipi FIXED ───────────────


def test_fixed_types_never_scale() -> None:
    """Title/closing/quiz/bookend hanno note costanti a ogni durata."""
    fixed = set(_BASE_CONSTRAINTS) - _NARRATIVE_TYPES
    for sps in (40.0, 45.0, 120.0, 240.0):
        c = build_layout_constraints(sps)
        for stype in fixed:
            assert c[stype].notes_min_words == _BASE_CONSTRAINTS[stype].notes_min_words
            assert c[stype].notes_max_words == _BASE_CONSTRAINTS[stype].notes_max_words


# ─────────────── 4. Proprieta` generali ───────────────


def test_min_always_below_max() -> None:
    for sps in (40.0, 45.0, 60.0, 120.0, 180.0, 240.0):
        for rules in build_layout_constraints(sps).values():
            assert rules.notes_min_words < rules.notes_max_words


def test_all_slide_types_present() -> None:
    c = build_layout_constraints(45.0)
    for stype in SlideType:
        assert stype in c, f"{stype} mancante nei vincoli"
