"""Unit tests — FASE 1 vast-hopping-sketch — LAYOUT_CONSTRAINTS + strict validator.

Verifica che il ``model_validator`` in ``app.models.pipeline.SlideContent`` rigetti
(no truncation) ogni violazione di constraint per-SlideType.

I 12 casi coperti coprono i bug reali osservati nei Cluster D run (es. ``quiz_correct="B"``
del Sonnet 4.6 baseline, body troppo lungo, notes fuori range TTS, image mancante).
"""

from __future__ import annotations

import pytest

from app.models.core import LAYOUT_CONSTRAINTS, SlideType
from app.models.pipeline import ImageStrategy, SlideContent


# ───────── Helpers — fixture di slide valide minimali per ogni tipo ─────────


def _valid_notes(words: int = 80) -> str:
    """Speaker notes valide (default 80 parole = nel range CONTENT_TEXT 60-90)."""
    return " ".join(["parola"] * words)


def _make_valid_content_text(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "index": 0,
        "module_index": 0,
        "slide_type": SlideType.CONTENT_TEXT,
        "title": "Titolo breve valido",
        # FIX #27.3: CONTENT_TEXT richiede min 4 bullet (slide piena).
        "body": (
            "Primo bullet breve\nSecondo bullet breve\n"
            "Terzo bullet breve\nQuarto bullet breve"
        ),
        "speaker_notes": _valid_notes(80),
        "normative_ref": "Art. 1, D.Lgs 81/08",
        "source_chunk_ids": ["chunk-1"],
    }
    base.update(overrides)
    return base


def _make_valid_quiz(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "index": 0,
        "module_index": 0,
        "slide_type": SlideType.QUIZ,
        "title": "Domanda quiz valida?",
        "body": "",
        "speaker_notes": _valid_notes(60),
        "normative_ref": "Art. 1, D.Lgs 81/08",
        "quiz_options": ["A breve", "B breve", "C breve", "D breve"],
        "quiz_correct": 2,
    }
    base.update(overrides)
    return base


# ───────── 12 test ─────────


def test_constraints_dict_covers_all_slide_types() -> None:
    """Ogni SlideType definito nell'enum deve avere un entry in LAYOUT_CONSTRAINTS."""
    for st in SlideType:
        assert st in LAYOUT_CONSTRAINTS, f"missing constraints for {st}"


def test_valid_content_text_passes() -> None:
    """Slide CONTENT_TEXT entro i limiti → istanziabile senza raise."""
    slide = SlideContent(**_make_valid_content_text())
    assert slide.slide_type == SlideType.CONTENT_TEXT


def test_title_too_long_rejected() -> None:
    """title > 70 char (CONTENT_TEXT) → ValueError con istruzione SPLIT."""
    long_title = "x" * 71
    with pytest.raises(ValueError, match="title=71 char"):
        SlideContent(**_make_valid_content_text(title=long_title))


def test_too_many_bullets_rejected() -> None:
    """CONTENT_TEXT body > 6 bullets → ValueError che richiede SPLIT."""
    seven_bullets = "\n".join(f"bullet {i}" for i in range(7))
    with pytest.raises(ValueError, match="7 bullets > 6"):
        SlideContent(**_make_valid_content_text(body=seven_bullets))


def test_bullet_too_many_words_rejected() -> None:
    """1 bullet > 12 parole (CONTENT_TEXT) → ValueError per riscrittura/split.
    Best-practice 7±2 + tolleranza. FIX #27.3: servono >= 4 bullet (minimo) di
    cui uno con 13 parole, sennò scatterebbe prima il check "< 4 min"."""
    long_bullet = " ".join(["parola"] * 13)
    body = f"{long_bullet}\nbullet due\nbullet tre\nbullet quattro"
    with pytest.raises(ValueError, match=r"bullets\[0\].*13 parole > 12"):
        SlideContent(**_make_valid_content_text(body=body))


def test_notes_too_few_words_rejected() -> None:
    """speaker_notes < 60 parole per CONTENT_TEXT → TTS sotto-target, rigettata."""
    short_notes = " ".join(["parola"] * 50)
    with pytest.raises(ValueError, match="50 parole < 60"):
        SlideContent(**_make_valid_content_text(speaker_notes=short_notes))


def test_notes_too_many_words_rejected() -> None:
    """speaker_notes oltre il max (CONTENT_TEXT max=120) → TTS sopra-target, rigettata."""
    long_notes = " ".join(["parola"] * 130)
    with pytest.raises(ValueError, match="130 parole > 120"):
        SlideContent(**_make_valid_content_text(speaker_notes=long_notes))


def test_quiz_correct_as_string_rejected() -> None:
    """Bug reale Cluster D: LLM emette quiz_correct='B' invece di int → rigettato."""
    with pytest.raises(ValueError):
        SlideContent(**_make_valid_quiz(quiz_correct="B"))  # type: ignore[arg-type]


def test_quiz_with_three_options_rejected() -> None:
    """QUIZ richiede esattamente 4 quiz_options."""
    with pytest.raises(ValueError, match="esattamente 4 quiz_options"):
        SlideContent(**_make_valid_quiz(quiz_options=["A", "B", "C"]))


def test_content_image_without_query_rejected() -> None:
    """CONTENT_IMAGE deve avere image.query non vuoto (FASE 4 prerequisito)."""
    data = _make_valid_content_text(
        slide_type=SlideType.CONTENT_IMAGE,
        body="bullet uno\nbullet due\nbullet tre",  # min 3 per CONTENT_IMAGE
        image=ImageStrategy(strategy="web_search"),  # niente query
    )
    with pytest.raises(ValueError, match="CONTENT_IMAGE richiede image.query"):
        SlideContent(**data)


def test_content_image_aspect_hint_optional_defaults_landscape() -> None:
    """FIX #11: aspect_hint è OPZIONALE (default landscape). CONTENT_IMAGE con
    query ma senza aspect_hint → valido (non più rigettato)."""
    data = _make_valid_content_text(
        slide_type=SlideType.CONTENT_IMAGE,
        body="bullet uno\nbullet due\nbullet tre",  # min 3 per CONTENT_IMAGE
        image=ImageStrategy(strategy="web_search", query="casco cantiere"),
    )
    slide = SlideContent(**data)
    assert slide.slide_type == SlideType.CONTENT_IMAGE


def test_diagram_without_viewbox_rejected() -> None:
    """FIX #11: DIAGRAM con SVG SENZA viewBox → rigettato (qualunque viewBox OK,
    ma deve esserci)."""
    bad_svg = '<svg width="500" height="300"><rect/></svg>'
    data = _make_valid_content_text(
        slide_type=SlideType.DIAGRAM,
        body="didascalia breve",
        image=ImageStrategy(strategy="diagram", diagram_code=bad_svg),
    )
    with pytest.raises(ValueError, match="viewBox SVG"):
        SlideContent(**data)


# ───────── FIX #27.3 — minimi obbligatori (slide piena) ─────────


def test_content_text_too_few_bullets_rejected() -> None:
    """FIX #27.3: CONTENT_TEXT con < 4 bullet → rigettato (slide vuota)."""
    three_bullets = "uno\ndue\ntre"
    with pytest.raises(ValueError, match="3 bullets < 4 min"):
        SlideContent(**_make_valid_content_text(body=three_bullets))


def test_recap_not_exactly_five_bullets_rejected() -> None:
    """FIX #27.3: RECAP con < 5 bullet → rigettato (5 checkmark da riempire)."""
    four = "uno\ndue\ntre\nquattro"
    data = _make_valid_content_text(
        slide_type=SlideType.RECAP, body=four, speaker_notes=_valid_notes(70)
    )
    with pytest.raises(ValueError, match="4 bullets < 5 min"):
        SlideContent(**data)


def test_recap_exactly_five_bullets_passes() -> None:
    """FIX #27.3: RECAP con esattamente 5 bullet → valido."""
    five = "uno\ndue\ntre\nquattro\ncinque"
    data = _make_valid_content_text(
        slide_type=SlideType.RECAP, body=five, speaker_notes=_valid_notes(70)
    )
    slide = SlideContent(**data)
    assert slide.slide_type == SlideType.RECAP


def test_case_study_too_few_sections_rejected() -> None:
    """FIX #27.3: CASE_STUDY con < 3 sezioni (split '---') → rigettato."""
    one_section = "Situazione: operaio senza casco in cantiere edile"
    data = _make_valid_content_text(
        slide_type=SlideType.CASE_STUDY,
        body=one_section,
        speaker_notes=_valid_notes(70),
    )
    with pytest.raises(ValueError, match="1 sezioni < 3 min"):
        SlideContent(**data)


def test_case_study_three_sections_passes() -> None:
    """FIX #27.3: CASE_STUDY con 3 sezioni separate da '---' → valido."""
    three = (
        "Operaio salda vicino a gas senza verifica ATEX --- "
        "Preposto ferma il lavoro e fa classificare la zona --- "
        "Esplosione evitata, procedura aggiornata in azienda"
    )
    data = _make_valid_content_text(
        slide_type=SlideType.CASE_STUDY,
        body=three,
        speaker_notes=_valid_notes(70),
    )
    slide = SlideContent(**data)
    assert slide.slide_type == SlideType.CASE_STUDY
