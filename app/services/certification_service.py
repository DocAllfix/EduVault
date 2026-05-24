"""Certification service (BLUEPRINT §06.2) — MINIMAL implementation.

PHASE 5.2 placeholder: only ``certify_course`` is implemented so
``POST /api/courses/{id}/certify`` can call it. The real
``StylePatternExtractor`` per BP §06.2 (FIX-4: no PDF certificate, no QR)
lands in PHASE 7.1 with the richer heuristics. The current extractor
computes the few aggregate metrics ``StylePattern`` requires from a
list of ``SlideContent`` — strictly anti-poisoning (BP §04.3): no
verbatim text, only structural counts.

D53: BP §06.2 has a more elaborate StylePatternExtractor; here it's
inlined as a few list comprehensions sufficient to satisfy the model
and the endpoint contract. PHASE 7.1 will replace the body.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

import structlog

from app.models.knowledge import StylePattern
from app.models.pipeline import SlideContent

logger = structlog.get_logger()


def _extract_style_pattern(slides: list[SlideContent]) -> StylePattern:
    """Minimum-viable extractor (D53). Strictly structural, no text leaks."""
    if not slides:
        return StylePattern(
            avg_words_per_slide=0,
            preferred_slide_sequence=[],
            tone_register="tecnico-divulgativo",
            recurring_section_titles=[],
            avg_quiz_per_module=0.0,
            preferred_image_ratio=0.0,
        )

    total_words = sum(len(s.body.split()) for s in slides)
    avg_words = total_words // len(slides)

    type_counter = Counter(s.slide_type.value for s in slides)
    preferred_sequence = [t for t, _ in type_counter.most_common(5)]

    title_counter: Counter[str] = Counter(s.title for s in slides if s.title)
    recurring_titles = [t for t, c in title_counter.items() if c > 1][:10]

    modules = {s.module_index for s in slides}
    quiz_count = sum(1 for s in slides if s.slide_type.value == "QUIZ")
    avg_quiz = quiz_count / max(1, len(modules))

    with_image = sum(
        1 for s in slides if s.image.strategy in ("web_search", "diagram")
    )
    image_ratio = with_image / len(slides)

    return StylePattern(
        avg_words_per_slide=avg_words,
        preferred_slide_sequence=preferred_sequence,
        tone_register="tecnico-divulgativo",
        recurring_section_titles=recurring_titles,
        avg_quiz_per_module=round(avg_quiz, 1),
        preferred_image_ratio=round(image_ratio, 2),
    )


async def certify_course(course_id: str, reviewer_id: str, pool: Any) -> str:
    """Certify a course → insert StylePattern in approved_courses (Level 2).

    Returns the new ``approved_courses.id`` (UUID as string).
    Raises ``ValueError`` if the course is missing or has no slide content.
    """
    course = await pool.fetchrow("SELECT * FROM courses WHERE id = $1", course_id)
    if not course or not course["slide_contents_json"]:
        raise ValueError("Course not found or has no slide content")

    raw_slides = json.loads(course["slide_contents_json"])
    slides = [SlideContent(**s) for s in raw_slides]
    pattern = _extract_style_pattern(slides)

    approved_id = await pool.fetchval(
        "INSERT INTO approved_courses "
        "(course_type, target, style_pattern, certified_by, source_course_id) "
        "VALUES ($1, $2, $3, $4, $5) RETURNING id",
        course["course_type"],
        course["target"],
        pattern.model_dump_json(),
        reviewer_id,
        course_id,
    )

    await pool.execute(
        "UPDATE courses SET status = 'certified' WHERE id = $1", course_id
    )

    logger.info("course_certified", course_id=course_id, approved_id=str(approved_id))
    return str(approved_id)


__all__ = ["certify_course"]
