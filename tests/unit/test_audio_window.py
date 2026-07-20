"""FASE 1 pacing dinamico — finestra di durata attesa per la narrazione TTS.

Matematica pura, zero mock (stile test_pacing_engine.py).

Contesto: prima di questa fase la finestra era la coppia di costanti
``_TARGET_DURATION_MIN/MAX = 25.0/35.0`` in ``audio_service``, derivata dalla
regola "1 slide ogni 30 secondi" e mai aggiornata quando il PacingEngine passo`
a 45s (FIX #29.0). Conseguenza: una slide scritta correttamente (90-160 parole
→ ~30-53s di audio) cadeva SEMPRE fuori finestra e veniva marcata off_target,
rendendo il flag ``audio_tracks.off_target`` privo di valore diagnostico.

Questi test bloccano la regressione e fissano il contratto per la Fase 2, dove
la funzione ricevera` il valore per-corso invece del default.
"""

from __future__ import annotations

from app.models.core import (
    DEFAULT_SECONDS_PER_SLIDE,
    target_duration_window,
)


# ─────────────── 1. Default: il caso che oggi mente ───────────────


def test_default_is_45_seconds() -> None:
    """Il default riflette la regola di pacing corrente, non quella vecchia."""
    assert DEFAULT_SECONDS_PER_SLIDE == 45.0


def test_default_window_contains_a_well_formed_slide() -> None:
    """Una slide da ~45s (135 parole @180wpm) deve risultare ON target.

    E` esattamente il caso che la vecchia finestra 25-35s marcava off_target.
    """
    win_min, win_max = target_duration_window()
    assert win_min <= 45.0 <= win_max
    assert win_min <= 50.0 <= win_max  # estremo alto del range note (160 parole)
    assert win_min <= 35.0 <= win_max  # estremo basso del range note (90 parole)


def test_default_window_exact_bounds() -> None:
    """45s ± 25% = (33.75, 56.25)."""
    assert target_duration_window(45.0) == (33.75, 56.25)


def test_default_window_excludes_clearly_wrong_durations() -> None:
    win_min, win_max = target_duration_window()
    assert not (win_min <= 20.0 <= win_max)   # troppo corta
    assert not (win_min <= 90.0 <= win_max)   # troppo lunga


# ─────────────── 2. Estremi del range consentito (40-240s) ───────────────


def test_lower_bound_40_seconds() -> None:
    """40s: la tolleranza relativa (10.0) coincide col floor."""
    assert target_duration_window(40.0) == (30.0, 50.0)


def test_upper_bound_240_seconds() -> None:
    """240s ± 25% = (180, 300)."""
    assert target_duration_window(240.0) == (180.0, 300.0)


# ─────────────── 3. Proprieta` strutturali ───────────────


def test_floor_protects_short_durations() -> None:
    """Sotto i 40s la tolleranza relativa sarebbe troppo stretta → floor 10s.

    A 20s il 25% varrebbe 5s: la finestra (15, 25) sarebbe cosi` stretta da
    marcare off_target quasi tutto. Il floor la porta a (10, 30).
    """
    assert target_duration_window(20.0) == (10.0, 30.0)


def test_window_is_monotonic_in_duration() -> None:
    """Slide piu` lunghe → finestra interamente piu` alta."""
    _, low_max = target_duration_window(40.0)
    high_min, _ = target_duration_window(240.0)
    assert high_min > low_max


def test_target_is_always_inside_its_own_window() -> None:
    """Invariante: la durata nominale non puo` mai essere off_target."""
    for sps in (40.0, 45.0, 60.0, 120.0, 180.0, 240.0):
        win_min, win_max = target_duration_window(sps)
        assert win_min < sps < win_max


def test_window_is_never_inverted() -> None:
    for sps in (40.0, 45.0, 90.0, 240.0):
        win_min, win_max = target_duration_window(sps)
        assert win_min < win_max
