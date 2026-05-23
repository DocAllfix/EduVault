"""Unit tests for config/catalog_config.COURSE_CATALOG (PHASE 2.4).

Verifies the catalog matches BLUEPRINT §13: the 6 expected course types
exist, each carries non-empty module titles and regulation slugs, and the
HACCP entry is flagged regional=True (the only regional course in v1.0).
"""

from __future__ import annotations

from config.catalog_config import COURSE_CATALOG

EXPECTED_SLUGS = {
    "sicurezza_lavoratori_generale",
    "sicurezza_lavoratori_specifica_basso",
    "primo_soccorso_gruppo_b_c",
    "antincendio_livello_1",
    "haccp_addetto",
    "preposti",
}


def test_catalog_has_exactly_six_types() -> None:
    assert set(COURSE_CATALOG.keys()) == EXPECTED_SLUGS


def test_every_entry_has_non_empty_title() -> None:
    for slug, entry in COURSE_CATALOG.items():
        title = entry["title"]
        assert isinstance(title, str) and title.strip(), f"{slug} has empty title"


def test_every_entry_has_non_empty_modules() -> None:
    for slug, entry in COURSE_CATALOG.items():
        modules = entry["default_modules"]
        assert isinstance(modules, list) and modules, f"{slug} has no modules"
        assert all(
            isinstance(m, str) and m.strip() for m in modules
        ), f"{slug} has an empty module title"


def test_every_entry_has_non_empty_regs() -> None:
    for slug, entry in COURSE_CATALOG.items():
        regs = entry["regs"]
        assert isinstance(regs, list) and regs, f"{slug} has no regulation slugs"
        assert all(
            isinstance(r, str) and r.strip() for r in regs
        ), f"{slug} has an empty reg slug"


def test_haccp_is_regional() -> None:
    assert COURSE_CATALOG["haccp_addetto"].get("regional") is True


def test_only_haccp_is_regional() -> None:
    regional = {
        slug for slug, entry in COURSE_CATALOG.items() if entry.get("regional")
    }
    assert regional == {"haccp_addetto"}


def test_hour_bounds_are_coherent() -> None:
    for slug, entry in COURSE_CATALOG.items():
        min_h = entry["min_hours"]
        max_h = entry["max_hours"]
        assert isinstance(min_h, int) and isinstance(max_h, int)
        assert 0 < min_h <= max_h, f"{slug} has incoherent hour bounds"


def test_haccp_allows_hour_range() -> None:
    # HACCP is the only course with a real min<max window (4-8h, BP §13).
    entry = COURSE_CATALOG["haccp_addetto"]
    assert entry["min_hours"] == 4
    assert entry["max_hours"] == 8
