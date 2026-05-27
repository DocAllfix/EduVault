"""Test helpers — fixture builders FASE 1 vast-hopping-sketch compliant.

I builder qui prodotti generano istanze ``SlideContent`` che rispettano TUTTI
i constraints in ``LAYOUT_CONSTRAINTS`` (per-SlideType). Sostituiscono le
fixture inline pre-FASE 1 che erano sotto-limiti (body troppo corto, notes
vuote, quiz_correct stringa, ecc.) e che ora falliscono il
``model_validator(mode="after")`` strict.

Uso:
    from tests._helpers import make_slide

    s = make_slide(SlideType.CONTENT_TEXT, index=3, title="X", body="...")
    # ritorna SlideContent valido — i campi mancanti hanno default conformi.
"""

from __future__ import annotations

from typing import Any

from app.models.core import SlideType
from app.models.pipeline import ImageStrategy, SlideContent


def _notes_words(n: int) -> str:
    """Genera stringa di N parole separate da spazi (valida per TTS validation)."""
    return " ".join(["parola"] * n)


def make_slide(
    slide_type: SlideType = SlideType.CONTENT_TEXT,
    *,
    index: int = 0,
    module_index: int = 0,
    title: str | None = None,
    body: str | None = None,
    speaker_notes: str | None = None,
    normative_ref: str = "Art. 1, D.Lgs 81/08",
    source_chunk_ids: list[str] | None = None,
    image: ImageStrategy | None = None,
    quiz_options: list[str] | None = None,
    quiz_correct: int | None = None,
    **extra: Any,
) -> SlideContent:
    """Costruisci una SlideContent VALIDA per LAYOUT_CONSTRAINTS, con override.

    I default sono scelti per essere "nel mezzo" dei range constraint:
      - title: 30-50 char (sotto i 70 max universal)
      - body: 3 bullet brevi per CONTENT_TEXT/CONTENT_IMAGE, 0 per TITLE/QUIZ/CLOSING/DIAGRAM
      - speaker_notes: 80 parole (nel range 75-90 di CONTENT_TEXT default)
      - image: web_search con query+aspect per CONTENT_IMAGE; SVG con viewBox per DIAGRAM
      - quiz_options: 4 opzioni brevi + quiz_correct=0 per QUIZ

    Passa ``body=""`` o ``speaker_notes=""`` esplicito se vuoi testare violazione.
    """
    # ─── Title default per tipo (sotto title_max_chars) ───
    default_title = "Titolo slide breve e valido"

    # ─── Body default per tipo ───
    if body is None:
        if slide_type in (SlideType.TITLE, SlideType.CLOSING, SlideType.QUIZ):
            body = ""  # questi tipi NON devono avere body
        elif slide_type == SlideType.CASE_STUDY:
            body = (
                "Situazione: lavoratore in cantiere senza casco operativo.\n"
                "Azione: preposto richiama immediatamente all'uso del DPI.\n"
                "Risultato: incidente evitato, formazione rinforzata in team."
            )
        elif slide_type == SlideType.DIAGRAM:
            body = "Didascalia breve del diagramma"
        else:  # CONTENT_TEXT, CONTENT_IMAGE, RECAP
            body = (
                "Primo punto chiave breve\n"
                "Secondo punto importante\n"
                "Terzo concetto da memorizzare"
            )

    # ─── Speaker notes default per range TTS (LAYOUT_CONSTRAINTS) ───
    if speaker_notes is None:
        from app.models.core import LAYOUT_CONSTRAINTS

        rules = LAYOUT_CONSTRAINTS.get(slide_type)
        if rules:
            # Punto centrale del range = (min+max)/2
            target = (rules.notes_min_words + rules.notes_max_words) // 2
        else:
            target = 80
        speaker_notes = _notes_words(target)

    # ─── Image default ───
    if image is None:
        if slide_type == SlideType.CONTENT_IMAGE:
            image = ImageStrategy(
                strategy="web_search",
                query="casco protezione cantiere",
                aspect_hint="landscape",
            )
        elif slide_type == SlideType.DIAGRAM:
            image = ImageStrategy(
                strategy="diagram",
                diagram_code=(
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1760 800">'
                    '<rect width="100" height="100" fill="blue"/></svg>'
                ),
            )
        else:
            image = ImageStrategy(strategy="none")

    # ─── Quiz options default ───
    if slide_type == SlideType.QUIZ:
        if quiz_options is None:
            quiz_options = ["Opzione A breve", "Opzione B breve", "Opzione C breve", "Opzione D breve"]
        if quiz_correct is None:
            quiz_correct = 0

    return SlideContent(
        index=index,
        module_index=module_index,
        slide_type=slide_type,
        title=title if title is not None else default_title,
        body=body,
        speaker_notes=speaker_notes,
        normative_ref=normative_ref,
        source_chunk_ids=source_chunk_ids if source_chunk_ids is not None else ["chunk-1"],
        image=image,
        quiz_options=quiz_options,
        quiz_correct=quiz_correct,
        **extra,
    )


def make_slide_dict(slide_type: SlideType = SlideType.CONTENT_TEXT, **kwargs: Any) -> dict[str, Any]:
    """Versione dict (utile per test che chiamano SlideContent(**dict))."""
    return make_slide(slide_type, **kwargs).model_dump()
