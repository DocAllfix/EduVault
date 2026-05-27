"""FIX #31.5B (2026-05-27) — Test coercion source_chunk_ids.

In E2E #23 batch 2 di M1 era fallito perché Azure-mini ha emesso
source_chunk_ids come stringa malformata invece di lista. Instructor
ha re-asked 5 volte ma l'LLM ha continuato a sbagliare → batch perso
(10 slide).

Il validator field_validator(mode='before') in pipeline.py coerce
input string/None/list a list[str], prevenendo ValidationError
ricorrente.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.core import SlideType
from app.models.pipeline import SlideContent, ImageStrategy


def _base_slide_kwargs() -> dict:
    """Slide CONTENT_TEXT minima valida (richiede 4+ bullets, notes 90+ words)."""
    return {
        "index": 0,
        "module_index": 0,
        "slide_type": "CONTENT_TEXT",
        "title": "Test slide for coercion",
        "bullets": [
            "Primo bullet di contenuto formativo",
            "Secondo bullet di contenuto formativo",
            "Terzo bullet di contenuto formativo",
            "Quarto bullet di contenuto formativo",
        ],
        "speaker_notes": (
            "Speaker notes lunghe abbastanza per soddisfare il minimum di "
            "novanta parole del validator. Aggiungo testo formativo aggiuntivo "
            "per coprire i vincoli pydantic minimi: descrivo il contenuto del "
            "modulo con riferimento normativo D.Lgs. 81/08, esempi pratici "
            "operativi della formazione sulla sicurezza nei luoghi di lavoro, "
            "scenari applicativi al contesto cantieristico ed industriale che "
            "permettono al discente di consolidare le competenze acquisite "
            "durante lo studio del materiale didattico fornito."
        ),
        "image": ImageStrategy(strategy="none"),
    }


def test_coerce_list_passes_through() -> None:
    """list[str] valida passa inalterata."""
    kw = _base_slide_kwargs()
    kw["source_chunk_ids"] = ["id-1", "id-2", "id-3"]
    s = SlideContent.model_validate(kw)
    assert s.source_chunk_ids == ["id-1", "id-2", "id-3"]


def test_coerce_empty_returns_empty_list() -> None:
    """None, "", missing → []."""
    for v in [None, "", []]:
        kw = _base_slide_kwargs()
        kw["source_chunk_ids"] = v
        s = SlideContent.model_validate(kw)
        assert s.source_chunk_ids == []


def test_coerce_string_json_array() -> None:
    """'["a","b","c"]' stringa JSON-array → list."""
    kw = _base_slide_kwargs()
    kw["source_chunk_ids"] = '["id-a", "id-b", "id-c"]'
    s = SlideContent.model_validate(kw)
    assert s.source_chunk_ids == ["id-a", "id-b", "id-c"]


def test_coerce_string_with_wrapper() -> None:
    """'source_chunk_ids([id1,id2])' (errore visto in E2E #23) → list."""
    kw = _base_slide_kwargs()
    kw["source_chunk_ids"] = 'source_chunk_ids(["uuid-x", "uuid-y"])'
    s = SlideContent.model_validate(kw)
    assert s.source_chunk_ids == ["uuid-x", "uuid-y"]


def test_coerce_string_comma_separated_fallback() -> None:
    """'id-1, id-2, id-3' senza brackets → split su virgola."""
    kw = _base_slide_kwargs()
    kw["source_chunk_ids"] = "id-1, id-2, id-3"
    s = SlideContent.model_validate(kw)
    assert s.source_chunk_ids == ["id-1", "id-2", "id-3"]


def test_coerce_list_with_none_elements_filters_empty() -> None:
    """List con valori vuoti filtrati."""
    kw = _base_slide_kwargs()
    kw["source_chunk_ids"] = ["id-1", None, "", "id-2"]
    s = SlideContent.model_validate(kw)
    assert s.source_chunk_ids == ["id-1", "id-2"]
