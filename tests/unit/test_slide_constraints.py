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
        # FIX #28.1 (2026-05-26): schema bullets:list[str] (era body:str).
        # CONTENT_TEXT richiede min 4 bullet (slide piena).
        "bullets": [
            "Primo bullet breve",
            "Secondo bullet breve",
            "Terzo bullet breve",
            "Quarto bullet breve",
        ],
        "sezioni": [],
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
    """CONTENT_TEXT bullets > 6 → ValueError che richiede SPLIT."""
    seven_bullets = [f"bullet {i}" for i in range(7)]
    with pytest.raises(ValueError, match="7 bullets > 6"):
        SlideContent(**_make_valid_content_text(bullets=seven_bullets))


def test_bullet_too_many_words_rejected() -> None:
    """1 bullet > 12 parole (CONTENT_TEXT) → ValueError per riscrittura/split.
    Best-practice 7±2 + tolleranza. Servono >= 4 bullet (minimo) di cui uno con
    13 parole, sennò scatterebbe prima il check "< 4 min"."""
    long_bullet = " ".join(["parola"] * 13)
    bullets = [long_bullet, "bullet due", "bullet tre", "bullet quattro"]
    with pytest.raises(ValueError, match=r"bullets\[0\].*13 parole > 12"):
        SlideContent(**_make_valid_content_text(bullets=bullets))


def test_notes_too_few_words_is_soft_warning_not_rejection() -> None:
    """speaker_notes sotto il min (CONTENT_TEXT min=90) NON rigetta.

    FIX #29.2: il floor sulle note e` un soft warning (log), non un raise —
    topic tecnici stretti producono naturalmente poche parole e il content_agent
    fa padding post-validation. Il gate hard resta il MAX (vedi test sotto).
    """
    short_notes = " ".join(["parola"] * 50)
    slide = SlideContent(**_make_valid_content_text(speaker_notes=short_notes))
    assert len(slide.speaker_notes.split()) == 50  # accettata


def test_notes_too_many_words_rejected() -> None:
    """speaker_notes oltre il max (CONTENT_TEXT max=160) → TTS sopra-target, rigettata."""
    long_notes = " ".join(["parola"] * 170)
    with pytest.raises(ValueError, match="170 parole > 160"):
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
        bullets=["bullet uno", "bullet due", "bullet tre"],  # min 3 per CONTENT_IMAGE
        image=ImageStrategy(strategy="web_search"),  # niente query
    )
    with pytest.raises(ValueError, match="CONTENT_IMAGE richiede image.query"):
        SlideContent(**data)


def test_content_image_aspect_hint_optional_defaults_landscape() -> None:
    """FIX #11: aspect_hint è OPZIONALE (default landscape). CONTENT_IMAGE con
    query ma senza aspect_hint → valido (non più rigettato)."""
    data = _make_valid_content_text(
        slide_type=SlideType.CONTENT_IMAGE,
        bullets=["bullet uno", "bullet due", "bullet tre"],
        image=ImageStrategy(strategy="web_search", query="casco cantiere"),
    )
    slide = SlideContent(**data)
    assert slide.slide_type == SlideType.CONTENT_IMAGE


def test_diagram_without_viewbox_rejected() -> None:
    """FIX #11: DIAGRAM con SVG SENZA viewBox → rigettato (qualunque viewBox OK,
    ma deve esserci). FIX #28.1: bullets list (DIAGRAM didascalia 1-2 elementi)."""
    bad_svg = '<svg width="500" height="300"><rect/></svg>'
    data = _make_valid_content_text(
        slide_type=SlideType.DIAGRAM,
        bullets=["didascalia breve"],
        image=ImageStrategy(strategy="diagram", diagram_code=bad_svg),
    )
    with pytest.raises(ValueError, match="viewBox SVG"):
        SlideContent(**data)


# ───────── FIX #27.3 — minimi obbligatori (slide piena) ─────────


def test_content_text_too_few_bullets_rejected() -> None:
    """FIX #28.1: CONTENT_TEXT con < 4 bullet → rigettato (slide vuota)."""
    three_bullets = ["uno", "due", "tre"]
    with pytest.raises(ValueError, match="3 bullets < 4 min"):
        SlideContent(**_make_valid_content_text(bullets=three_bullets))


def test_recap_not_exactly_five_bullets_rejected() -> None:
    """FIX #28.1: RECAP con < 5 bullet → rigettato (5 checkmark da riempire)."""
    four = ["uno", "due", "tre", "quattro"]
    data = _make_valid_content_text(
        slide_type=SlideType.RECAP, bullets=four, speaker_notes=_valid_notes(70)
    )
    with pytest.raises(ValueError, match="4 bullets < 5 min"):
        SlideContent(**data)


def test_recap_exactly_five_bullets_passes() -> None:
    """FIX #28.1: RECAP con esattamente 5 bullet → valido."""
    five = ["uno", "due", "tre", "quattro", "cinque"]
    data = _make_valid_content_text(
        slide_type=SlideType.RECAP, bullets=five, speaker_notes=_valid_notes(70)
    )
    slide = SlideContent(**data)
    assert slide.slide_type == SlideType.RECAP


def test_case_study_too_few_sections_rejected() -> None:
    """FIX #28.1: CASE_STUDY con < 3 sezioni (lista) → rigettato."""
    data = _make_valid_content_text(
        slide_type=SlideType.CASE_STUDY,
        bullets=[],
        sezioni=["Situazione: operaio senza casco in cantiere edile"],
        speaker_notes=_valid_notes(70),
    )
    with pytest.raises(ValueError, match="1 sezioni < 3 min"):
        SlideContent(**data)


def test_case_study_three_sections_passes() -> None:
    """FIX #28.1: CASE_STUDY con 3 sezioni (lista) → valido."""
    data = _make_valid_content_text(
        slide_type=SlideType.CASE_STUDY,
        bullets=[],
        sezioni=[
            "Operaio salda vicino a gas senza verifica ATEX",
            "Preposto ferma il lavoro e fa classificare la zona",
            "Esplosione evitata, procedura aggiornata in azienda",
        ],
        speaker_notes=_valid_notes(70),
    )
    slide = SlideContent(**data)
    assert slide.slide_type == SlideType.CASE_STUDY
