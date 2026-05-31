"""Unit tests per F4 slide_quality_service (analista sign-off 2026-05-31).

Verifica i 9 sensori D9 implementati in compute_slide_issues:
  - image_placeholder (CONTENT_IMAGE/DIAGRAM con strategy=none)
  - diagram_branded_fallback
  - quiz_no_options
  - notes_too_short (sotto layout min_words)
  - module_underpopulated (modulo < 70% expected slide count)
  - image_overused_in_module (≥ 3× stesso URL nello stesso modulo)
  - title_near_duplicate_in_module (primi 5 tokens duplicati)
  - bullet_citation_warning (slug citato nei bullets NON in course.regulation_ids)
  - title_citation_warning (slug citato nel title NON in course.regulation_ids)

Dataset fissi per stabilita' regressione.
"""

from __future__ import annotations

import pytest

from app.services.slide_quality_service import (
    ISSUE_TYPES,
    compute_slide_issues,
)


def _slide(
    *,
    index: int = 0,
    module_index: int = 0,
    slide_type: str = "CONTENT_TEXT",
    title: str = "Test Slide",
    bullets: list[str] | None = None,
    speaker_notes: str = "A " * 100,  # 100 words default, ample
    quiz_options: list[str] | None = None,
    quiz_correct: int | None = None,
    image: dict | None = None,
    source_chunk_ids: list[str] | None = None,
) -> dict:
    """Slide factory con default sicuri (zero issue di default per CONTENT_TEXT)."""
    return {
        "index": index,
        "module_index": module_index,
        "slide_type": slide_type,
        "title": title,
        "bullets": bullets if bullets is not None else ["bullet 1", "bullet 2"],
        "speaker_notes": speaker_notes,
        "quiz_options": quiz_options,
        "quiz_correct": quiz_correct,
        "image": image if image is not None else {"strategy": "none"},
        "source_chunk_ids": source_chunk_ids or [],
    }


def test_empty_slides_returns_zero() -> None:
    result = compute_slide_issues([])
    assert result["total_issues"] == 0
    assert result["issues"] == []


def test_issue_types_lista_chiusa() -> None:
    assert len(ISSUE_TYPES) == 11
    expected = {
        "image_placeholder", "diagram_branded_fallback", "quiz_no_options",
        "notes_too_short", "module_underpopulated", "module_corpus_thin",
        "image_overused_in_module", "title_near_duplicate_in_module",
        "bullet_citation_warning", "bullet_citation_warning_as_object",
        "title_citation_warning",
    }
    assert set(ISSUE_TYPES) == expected


def test_image_placeholder_on_content_image_with_none_strategy() -> None:
    """CONTENT_IMAGE con strategy=none -> image_placeholder warning."""
    slides = [_slide(slide_type="CONTENT_IMAGE", image={"strategy": "none"})]
    # Add 70 generic slides per evitare module_underpopulated noise
    slides.extend(_slide(index=i + 1, slide_type="CONTENT_TEXT") for i in range(70))

    result = compute_slide_issues(slides, expected_slides_per_module=70)
    placeholder_issues = [i for i in result["issues"] if i["issue_type"] == "image_placeholder"]
    assert len(placeholder_issues) == 1
    assert placeholder_issues[0]["severity"] == "warning"
    assert placeholder_issues[0]["slide_index"] == 0


def test_image_placeholder_NOT_on_content_text() -> None:
    """CONTENT_TEXT con strategy=none -> NO issue (immagine non required)."""
    slides = [_slide(slide_type="CONTENT_TEXT", image={"strategy": "none"})]
    slides.extend(_slide(index=i + 1) for i in range(70))

    result = compute_slide_issues(slides, expected_slides_per_module=70)
    placeholder_issues = [i for i in result["issues"] if i["issue_type"] == "image_placeholder"]
    assert len(placeholder_issues) == 0


def test_diagram_branded_fallback_detected() -> None:
    """DIAGRAM con strategy=branded_fallback -> error grave."""
    slides = [_slide(slide_type="DIAGRAM", image={"strategy": "branded_fallback"})]
    slides.extend(_slide(index=i + 1) for i in range(70))

    result = compute_slide_issues(slides, expected_slides_per_module=70)
    fb_issues = [i for i in result["issues"] if i["issue_type"] == "diagram_branded_fallback"]
    assert len(fb_issues) == 1
    assert fb_issues[0]["severity"] == "error"


def test_quiz_no_options_detected() -> None:
    """QUIZ senza quiz_options o < 2 opzioni -> error."""
    slides = [
        _slide(slide_type="QUIZ", quiz_options=None, speaker_notes="A " * 50),
        _slide(index=1, slide_type="QUIZ", quiz_options=["only one"], speaker_notes="A " * 50),
    ]
    slides.extend(_slide(index=i + 2) for i in range(70))

    result = compute_slide_issues(slides, expected_slides_per_module=70)
    quiz_issues = [i for i in result["issues"] if i["issue_type"] == "quiz_no_options"]
    assert len(quiz_issues) == 2  # entrambe le QUIZ malformate
    assert all(i["severity"] == "error" for i in quiz_issues)


def test_notes_too_short_detected_below_layout_min() -> None:
    """speaker_notes sotto layout min_words (es. CONTENT_TEXT min=90) -> info."""
    # CONTENT_TEXT min=90 (FIX #29.2). 10 parole = troppo poche.
    slides = [_slide(slide_type="CONTENT_TEXT", speaker_notes="parola " * 10)]
    slides.extend(_slide(index=i + 1) for i in range(70))

    result = compute_slide_issues(slides, expected_slides_per_module=70)
    short_issues = [i for i in result["issues"] if i["issue_type"] == "notes_too_short"]
    assert len(short_issues) >= 1
    target_issue = next(i for i in short_issues if i["slide_index"] == 0)
    assert target_issue["context"]["word_count"] == 10
    assert target_issue["context"]["min_required"] == 90
    assert target_issue["severity"] == "info"


def test_module_underpopulated_detected() -> None:
    """Modulo con < 70% expected slides -> error grave (bug #22 M3 a 2 slide)."""
    # Solo 5 slide in modulo 0, expected=70 → 5 < 49 → underpopulated
    slides = [_slide(index=i, module_index=0) for i in range(5)]

    result = compute_slide_issues(slides, expected_slides_per_module=70)
    under_issues = [i for i in result["issues"] if i["issue_type"] == "module_underpopulated"]
    assert len(under_issues) == 1
    assert under_issues[0]["severity"] == "error"
    assert under_issues[0]["context"]["module_slide_count"] == 5
    assert under_issues[0]["context"]["expected"] == 70


def test_image_overused_in_module() -> None:
    """Stessa URL immagine usata ≥ 3× nello stesso modulo -> warning."""
    same_img = {"strategy": "web_search", "query_url": "https://example.com/door.jpg", "query": "porta"}
    slides = [
        _slide(index=0, module_index=0, slide_type="CONTENT_IMAGE", image=same_img),
        _slide(index=1, module_index=0, slide_type="CONTENT_IMAGE", image=same_img),
        _slide(index=2, module_index=0, slide_type="CONTENT_IMAGE", image=same_img),
        _slide(index=3, module_index=0, slide_type="CONTENT_IMAGE", image={"strategy": "web_search", "query_url": "https://example.com/other.jpg"}),
    ]
    slides.extend(_slide(index=i + 4, module_index=0) for i in range(70))

    result = compute_slide_issues(slides, expected_slides_per_module=70)
    over_issues = [i for i in result["issues"] if i["issue_type"] == "image_overused_in_module"]
    # 3 slide con same URL (slide 0,1,2)
    assert len(over_issues) == 3
    assert all(i["context"]["occurrences"] == 3 for i in over_issues)


def test_title_near_duplicate_in_module() -> None:
    """Titoli con primi 5 tokens duplicati nello stesso modulo -> info."""
    slides = [
        _slide(index=0, module_index=0, title="Prevenzione incendi nei luoghi di lavoro"),
        _slide(index=1, module_index=0, title="Prevenzione incendi nei luoghi di lavoro oggi"),  # primi 5 = duplicati
        _slide(index=2, module_index=0, title="Sicurezza estintori manutenzione periodica"),  # diverso
    ]
    # Padding con titoli univoci (altrimenti tutti fingerprint='test slide N')
    slides.extend(_slide(index=i + 3, module_index=0, title=f"Voce padding modulo argomento {i}") for i in range(70))

    result = compute_slide_issues(slides, expected_slides_per_module=70)
    dup_issues = [i for i in result["issues"] if i["issue_type"] == "title_near_duplicate_in_module"]
    # 2 slide con stesso fingerprint (primi 5 tokens) -> entrambe flag
    assert len(dup_issues) == 2
    assert all(i["severity"] == "info" for i in dup_issues)


def test_bullet_citation_warning_detected() -> None:
    """Citazione decreto NON in course.regulation_ids -> error.

    Pattern slide 67 PPTX ANT L1: bullet "DM 03/08/2015 - riferimento chiave",
    ANT L1 regulation_ids = [dlgs_81_08, dm_02_09_2021, dm_03_09_2021, dm_01_09_2021].
    dm_03_08_2015 NOT in lista -> hallucination.
    """
    slides = [
        _slide(
            index=0,
            bullets=["DM 03/08/2015 - riferimento chiave", "Definizione fuoco"],
            speaker_notes="A " * 50,
        ),
    ]
    slides.extend(_slide(index=i + 1) for i in range(70))

    ant_l1_regs = ["dlgs_81_08", "dm_02_09_2021", "dm_03_09_2021", "dm_01_09_2021"]
    result = compute_slide_issues(slides, course_regulation_ids=ant_l1_regs, expected_slides_per_module=70)

    citation_issues = [i for i in result["issues"] if i["issue_type"] == "bullet_citation_warning"]
    assert len(citation_issues) == 1
    assert citation_issues[0]["severity"] == "error"
    assert "dm_03_08_2015" in citation_issues[0]["context"]["hallucinated_slugs"]


def test_title_citation_warning_detected() -> None:
    """Citazione decreto fuori scope nel TITLE -> error (D-181-quinquies)."""
    slides = [
        _slide(
            index=0,
            title="D.Lgs 8 marzo 2006, n. 139 - Norma antincendio",  # 139/2006 NOT in ANT L1
            bullets=["bullet ok"],
            speaker_notes="A " * 50,
        ),
    ]
    slides.extend(_slide(index=i + 1) for i in range(70))

    ant_l1_regs = ["dlgs_81_08", "dm_02_09_2021", "dm_03_09_2021", "dm_01_09_2021"]
    result = compute_slide_issues(slides, course_regulation_ids=ant_l1_regs, expected_slides_per_module=70)

    title_issues = [i for i in result["issues"] if i["issue_type"] == "title_citation_warning"]
    assert len(title_issues) == 1
    assert title_issues[0]["severity"] == "error"


def test_summary_by_severity_and_by_type_aggregates() -> None:
    """Verifica summary structure rilevante per UI badge dashboard."""
    slides = [
        _slide(index=0, slide_type="QUIZ", quiz_options=None, speaker_notes="A " * 50),
        _slide(index=1, slide_type="DIAGRAM", image={"strategy": "branded_fallback"}),
    ]
    slides.extend(_slide(index=i + 2) for i in range(70))

    result = compute_slide_issues(slides, expected_slides_per_module=70)
    assert result["total_issues"] >= 2  # minimo i 2 issue principali sopra
    assert "error" in result["by_severity"]
    assert result["by_severity"]["error"] >= 2  # quiz_no_options + diagram_fallback


def test_no_regulation_ids_skips_citation_checks() -> None:
    """Senza course_regulation_ids, citation checks vengono saltati (no false positive)."""
    slides = [
        _slide(
            index=0,
            bullets=["DM 03/08/2015 abrogato"],
            title="D.Lgs 139/2006",
        ),
    ]
    slides.extend(_slide(index=i + 1) for i in range(70))

    result = compute_slide_issues(slides, course_regulation_ids=None, expected_slides_per_module=70)
    citation_issues = [
        i for i in result["issues"]
        if i["issue_type"] in ("bullet_citation_warning", "title_citation_warning")
    ]
    assert len(citation_issues) == 0
