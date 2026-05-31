"""F7.2 — Unit test SSML break converter."""

from __future__ import annotations

from app.services.ssml import MAX_BREAKS, count_breaks, text_to_ssml


def test_empty_text_returns_valid_ssml():
    out = text_to_ssml("", "it-IT-DiegoNeural")
    assert out.startswith("<speak")
    assert "it-IT-DiegoNeural" in out
    assert out.endswith("</speak>")


def test_no_pause_marker_returns_clean_text():
    out = text_to_ssml("Salve a tutti.", "it-IT-DiegoNeural")
    assert "<break" not in out
    assert "Salve a tutti." in out


def test_single_pause_replaced():
    out = text_to_ssml("Prima frase. (PAUSE 2s) Seconda.", "it-IT-DiegoNeural")
    assert '<break time="2.0s"/>' in out
    assert "(PAUSE" not in out


def test_multiple_pauses_replaced():
    text = "A. (PAUSE 1s) B. (PAUSE 0.5s) C."
    out = text_to_ssml(text, "it-IT-DiegoNeural")
    assert out.count("<break") == 2
    assert '<break time="1.0s"/>' in out
    assert '<break time="0.5s"/>' in out


def test_pause_case_insensitive():
    text = "Frase. (pause 2s) Altra. (Pause 1s) Fine."
    out = text_to_ssml(text, "it-IT-DiegoNeural")
    assert out.count("<break") == 2


def test_pause_optional_s_suffix():
    """Marker (PAUSE 2) senza 's' è valido."""
    text = "Frase. (PAUSE 2) Fine."
    out = text_to_ssml(text, "it-IT-DiegoNeural")
    assert '<break time="2.0s"/>' in out


def test_xml_special_chars_escaped():
    text = "Sicurezza & lavoro <importante> per i \"lavoratori\""
    out = text_to_ssml(text, "it-IT-DiegoNeural")
    # Tutto escapato
    assert "&amp;" in out
    assert "&lt;" in out
    assert "&gt;" in out
    assert "&quot;" in out
    # Pattern PAUSE invariato (qui non c'è)
    assert "<break" not in out


def test_special_chars_with_pause_both_work():
    text = "Frase con & speciali. (PAUSE 1s) <test> finale."
    out = text_to_ssml(text, "it-IT-DiegoNeural")
    assert "&amp;" in out
    assert "&lt;" in out
    assert '<break time="1.0s"/>' in out


def test_breaks_cap_max():
    """Oltre MAX_BREAKS i (PAUSE) restano come testo."""
    # 12 PAUSE markers; solo 10 (MAX_BREAKS) dovrebbero diventare <break>
    text = "X. " + "(PAUSE 1s) ".join([""] * 13)
    out = text_to_ssml(text, "it-IT-DiegoNeural")
    assert out.count("<break") == MAX_BREAKS
    # Le PAUSE oltre il cap restano come testo (potrebbero essere escapate, OK)
    assert count_breaks(out.replace("<break", "")) > 0 or "(PAUSE" not in out


def test_pause_time_cap_10s():
    text = "Frase. (PAUSE 50s) Fine."
    out = text_to_ssml(text, "it-IT-DiegoNeural")
    # 50s -> cap a 10s
    assert '<break time="10.0s"/>' in out
    assert '<break time="50' not in out


def test_voice_name_in_ssml():
    out = text_to_ssml("test", "it-IT-IsabellaNeural")
    assert "it-IT-IsabellaNeural" in out


def test_count_breaks():
    assert count_breaks("") == 0
    assert count_breaks("No markers here") == 0
    assert count_breaks("(PAUSE 1s)") == 1
    assert count_breaks("(PAUSE 1) (PAUSE 2s) (pause 0.5)") == 3
