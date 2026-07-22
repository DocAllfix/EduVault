"""FASE 2 batch adattivo — dimensionamento del batch LLM per durata-slide.

Note piu` lunghe (durata-slide alta) → meno slide per chiamata, per non sforare
il budget di output dell'LLM. A 45s (invarianza) il batch resta 15.
"""

from __future__ import annotations

from app.models.core import SlideType, build_layout_constraints
from app.services.ingestion_service import (
    _BATCH_MAX,
    _BATCH_MIN,
    compute_batch_size,
)


def _notes_max(sps: float) -> int:
    return build_layout_constraints(sps)[SlideType.CONTENT_TEXT].notes_max_words


# ─────────────── 1. Invarianza a 45s ───────────────


def test_batch_is_15_at_default_duration() -> None:
    """A 45s (notes_max=160) il batch e` 15 = vecchio _BATCH_SIZE."""
    assert compute_batch_size(_notes_max(45.0)) == 15


# ─────────────── 2. Riduzione con durate lunghe ───────────────


def test_batch_shrinks_for_long_slides() -> None:
    """A 240s (notes_max~853) il batch scende ma resta >= 3."""
    b = compute_batch_size(_notes_max(240.0))
    assert 3 <= b < 15


def test_batch_at_240_is_eight() -> None:
    # notes_max(240) = 853; per_slide = 853*1.6+120 = 1485; 12000//1485 = 8
    assert compute_batch_size(853) == 8


def test_short_slides_stay_capped_at_15() -> None:
    """Fino a ~90s il batch resta al cap 15 (comportamento pre-esistente)."""
    for sps in (40.0, 45.0, 60.0, 90.0):
        assert compute_batch_size(_notes_max(sps)) == 15


# ─────────────── 3. Clamp e monotonicita` ───────────────


def test_clamp_bounds() -> None:
    assert compute_batch_size(5) == _BATCH_MAX  # note cortissime → cap alto
    assert compute_batch_size(100000) == _BATCH_MIN  # note enormi → floor


def test_monotonic_non_increasing() -> None:
    prev = 999
    for words in (100, 160, 300, 500, 853, 1200):
        b = compute_batch_size(words)
        assert b <= prev
        prev = b


def test_never_below_min_protecting_sub_batch_recovery() -> None:
    """Il floor 3 protegge il sub-batch recovery (si disattiva sotto 4)."""
    assert _BATCH_MIN == 3
    for words in (800, 1000, 2000, 5000):
        assert compute_batch_size(words) >= 3
