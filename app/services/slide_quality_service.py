"""F4 D9 Slide Quality Service (analista sign-off 2026-05-31).

Pure deterministic compute, no side effect. Aggrega tutti i sensori D9 esistenti
+ implementa nuovi check per esporre al frontend Course Studio badge slide
problematiche.

Architettura:
  - Input: list[SlideContent dict] (da slide_contents_json) + course metadata
  - Output: list[Issue dict] + summary {total_issues, by_severity, by_type}
  - 11 issue types (lista chiusa, approvata analista BLUEPRINT D9):
      image_placeholder, diagram_branded_fallback, quiz_no_options,
      notes_too_short, module_underpopulated, module_corpus_thin,
      image_overused_in_module, title_near_duplicate_in_module,
      bullet_citation_warning (D-178 V1.5), bullet_citation_warning_as_object
      (D-181-ter, post-impl), title_citation_warning (D-181-quinquies, post-impl)

Severity scale:
  - error: blocca user trust (es. citation hallucination grave)
  - warning: visibilita' alta (es. immagine mancante, quiz senza opzioni)
  - info: segnalazione soft (es. note brevi)

Decisione D9 (NON blocca download): solo segnalazione, no coercizione. UI
mostra badge ma cliente puo' scaricare PPTX comunque.

VAA-c trasparenza: tutti i sensori esposti come issue tipizzati per
abilitare F4b "rigenera singola slide" + F6 chat preconfigurata sul context.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


# Issue types (lista chiusa)
ISSUE_TYPES: list[str] = [
    "image_placeholder",
    "diagram_branded_fallback",
    "quiz_no_options",
    "notes_too_short",
    "module_underpopulated",
    "module_corpus_thin",
    "image_overused_in_module",
    "title_near_duplicate_in_module",
    "bullet_citation_warning",
    "bullet_citation_warning_as_object",
    "title_citation_warning",
]

# Severity per issue type
_SEVERITY: dict[str, str] = {
    "image_placeholder": "warning",
    "diagram_branded_fallback": "error",  # nemico storico
    "quiz_no_options": "error",
    "notes_too_short": "info",
    "module_underpopulated": "error",  # bug-a-2-slide M3 #22
    "module_corpus_thin": "warning",
    "image_overused_in_module": "warning",
    "title_near_duplicate_in_module": "info",
    "bullet_citation_warning": "error",  # citation hallucination grave
    "bullet_citation_warning_as_object": "info",  # soft (oggetto della slide)
    "title_citation_warning": "error",  # Tipo 3 hallucination
}

# Layout constraints lookup (notes_min_words, requires_image per type)
# Riusa LAYOUT_CONSTRAINTS esistente per coerenza
def _layout_min_notes_words(slide_type: str) -> int:
    """Returns notes_min_words per slide_type, default 30."""
    from app.models.core import LAYOUT_CONSTRAINTS, SlideType
    try:
        st = SlideType(slide_type) if isinstance(slide_type, str) else slide_type
        return LAYOUT_CONSTRAINTS[st].notes_min_words
    except (ValueError, KeyError):
        return 30


def _layout_requires_image(slide_type: str) -> bool:
    """Returns requires_image per slide_type, default False."""
    from app.models.core import LAYOUT_CONSTRAINTS, SlideType
    try:
        st = SlideType(slide_type) if isinstance(slide_type, str) else slide_type
        return LAYOUT_CONSTRAINTS[st].requires_image
    except (ValueError, KeyError):
        return False


def _is_image_placeholder(slide: dict[str, Any]) -> bool:
    """Image strategy = 'none' o image url placeholder MA slide_type richiede image."""
    slide_type = slide.get("slide_type", "")
    if not _layout_requires_image(slide_type):
        return False
    img = slide.get("image") or {}
    if not isinstance(img, dict):
        return True  # malformato
    strategy = img.get("strategy", "none")
    return strategy in ("none", "placeholder")


def _is_diagram_branded_fallback(slide: dict[str, Any]) -> bool:
    """DIAGRAM slide con strategy=fallback (nemico storico)."""
    if slide.get("slide_type") != "DIAGRAM":
        return False
    img = slide.get("image") or {}
    if not isinstance(img, dict):
        return False
    # fallback: branded_fallback strategy o diagram_code mancante
    return img.get("strategy") == "branded_fallback" or not img.get("diagram_code")


def _is_quiz_no_options(slide: dict[str, Any]) -> bool:
    """QUIZ senza quiz_options."""
    if slide.get("slide_type") != "QUIZ":
        return False
    opts = slide.get("quiz_options")
    return not opts or not isinstance(opts, list) or len(opts) < 2


def _is_notes_too_short(slide: dict[str, Any]) -> bool:
    """speaker_notes word count < layout min."""
    notes = slide.get("speaker_notes", "")
    if not notes:
        return True
    word_count = len(notes.split())
    min_words = _layout_min_notes_words(slide.get("slide_type", ""))
    return word_count < min_words


def _title_normalize(title: str) -> str:
    """Lowercase + strip per dedup near-duplicate."""
    return " ".join((title or "").lower().split())


def _check_module_underpopulated(slides: list[dict[str, Any]], expected_per_module: int = 70) -> list[dict[str, Any]]:
    """Modulo con slide_count < expected*0.7 -> bug a-2-slide M3 #22."""
    issues: list[dict[str, Any]] = []
    by_module: dict[int, list[dict[str, Any]]] = {}
    for s in slides:
        mi = s.get("module_index")
        if mi is None:
            continue
        by_module.setdefault(mi, []).append(s)
    threshold = expected_per_module * 0.7
    for mi, mod_slides in by_module.items():
        if len(mod_slides) < threshold:
            # Issue applicata alla prima slide del modulo (MODULE_OPEN typically)
            first = mod_slides[0] if mod_slides else None
            if first is not None:
                issues.append({
                    "slide_index": first.get("index", 0),
                    "module_index": mi,
                    "issue_type": "module_underpopulated",
                    "severity": _SEVERITY["module_underpopulated"],
                    "context": {
                        "module_slide_count": len(mod_slides),
                        "expected": expected_per_module,
                        "threshold": int(threshold),
                    },
                })
    return issues


def _check_image_overused(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stessa immagine usata >= 3x nello stesso modulo (foto-porte x4 Corso 1 M2)."""
    issues: list[dict[str, Any]] = []
    # Per modulo, conta image URL/query
    by_module_image: dict[tuple[int | None, str], list[dict[str, Any]]] = {}
    for s in slides:
        mi = s.get("module_index")
        img = s.get("image") or {}
        if not isinstance(img, dict):
            continue
        url = img.get("query_url") or img.get("local_path") or img.get("query") or ""
        if not url or img.get("strategy") in ("none", "placeholder"):
            continue
        by_module_image.setdefault((mi, url), []).append(s)
    for (mi, url), slist in by_module_image.items():
        if len(slist) >= 3:
            for s in slist:
                issues.append({
                    "slide_index": s.get("index", 0),
                    "module_index": mi,
                    "issue_type": "image_overused_in_module",
                    "severity": _SEVERITY["image_overused_in_module"],
                    "context": {
                        "image_url": url[:120],
                        "occurrences": len(slist),
                    },
                })
    return issues


def _check_title_near_duplicate(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Titolo near-duplicate >= 0.85 similarity nello stesso modulo.

    Implementazione semplice: normalizzazione + match esatto sui primi 5 token.
    Pattern slide 11/16, 12/17, 13/18 osservato post-V1.5.
    """
    issues: list[dict[str, Any]] = []
    by_module: dict[int | None, list[tuple[int, str]]] = {}  # module_idx -> [(slide_idx, normalized_title)]
    for s in slides:
        mi = s.get("module_index")
        title = _title_normalize(s.get("title", ""))
        if not title:
            continue
        # First 5 tokens come fingerprint
        fp = " ".join(title.split()[:5])
        by_module.setdefault(mi, []).append((s.get("index", 0), fp))
    for mi, items in by_module.items():
        # Trova fingerprint duplicati
        fp_count = Counter(fp for _, fp in items)
        for slide_idx, fp in items:
            if fp_count[fp] >= 2:
                issues.append({
                    "slide_index": slide_idx,
                    "module_index": mi,
                    "issue_type": "title_near_duplicate_in_module",
                    "severity": _SEVERITY["title_near_duplicate_in_module"],
                    "context": {
                        "title_fingerprint": fp,
                        "duplicates_count": fp_count[fp],
                    },
                })
    return issues


def _check_bullet_citation_warnings(
    slides: list[dict[str, Any]],
    course_regulation_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """D-178 V1.5 bullet citation warnings (riusa citation_normalizer).

    Per ogni slide: scan bullets + speaker_notes + quiz_options per citazioni
    decreti -> se slug NON in course.regulation_ids -> bullet_citation_warning.

    D-181-ter (post-impl): se slug compare nel titolo della slide -> severity
    soft (as-object); se compare solo nei bullets -> severity hard (as-source).
    Implementazione iniziale: tutti hard, D-181-ter da definire dopo.

    D-181-quinquies (post-impl): se slug compare nel title -> title_citation_warning.
    """
    if not course_regulation_ids:
        return []
    from app.services.citation_normalizer import find_hallucinated_citations
    allowed = set(course_regulation_ids)
    issues: list[dict[str, Any]] = []
    for s in slides:
        text_fields: list[str] = []
        bullets = s.get("bullets") or []
        if isinstance(bullets, list):
            text_fields.extend(bullets)
        notes = s.get("speaker_notes") or ""
        if notes:
            text_fields.append(notes)
        opts = s.get("quiz_options") or []
        if isinstance(opts, list):
            text_fields.extend(opts)
        title = s.get("title") or ""
        # Check title separately for D-181-quinquies
        hallucinated_in_body = find_hallucinated_citations(text_fields, allowed) if text_fields else []
        hallucinated_in_title = find_hallucinated_citations([title], allowed) if title else []
        if hallucinated_in_body:
            issues.append({
                "slide_index": s.get("index", 0),
                "module_index": s.get("module_index"),
                "issue_type": "bullet_citation_warning",
                "severity": _SEVERITY["bullet_citation_warning"],
                "context": {
                    "hallucinated_slugs": hallucinated_in_body,
                    "allowed_slugs": sorted(allowed),
                },
            })
        if hallucinated_in_title:
            issues.append({
                "slide_index": s.get("index", 0),
                "module_index": s.get("module_index"),
                "issue_type": "title_citation_warning",
                "severity": _SEVERITY["title_citation_warning"],
                "context": {
                    "hallucinated_slugs": hallucinated_in_title,
                    "title": title[:120],
                },
            })
    return issues


def compute_slide_issues(
    slides: list[dict[str, Any]],
    course_regulation_ids: list[str] | None = None,
    expected_slides_per_module: int = 70,
) -> dict[str, Any]:
    """Compute all D9 quality issues for course slides.

    Returns:
        {
            "total_issues": int,
            "by_severity": {"error": N, "warning": N, "info": N},
            "by_type": {issue_type: count, ...},
            "issues": list[Issue dict],
        }

    Each Issue dict: {slide_index, module_index, issue_type, severity, context}.

    Sensori non implementati qui (richiedono dati esterni telemetria pipeline):
      - module_corpus_thin: richiede top_rerank_score per modulo (ricostruito
        da telemetria, non da slide_contents_json). TODO: leggere da
        generation_events log o ricomputare.

    course_regulation_ids: lista slug ammessi per il corso (per
    bullet_citation_warning + title_citation_warning). Se None, skip questi
    check.
    """
    if not slides:
        return {"total_issues": 0, "by_severity": {}, "by_type": {}, "issues": []}

    all_issues: list[dict[str, Any]] = []

    # Per-slide checks
    for s in slides:
        idx = s.get("index", 0)
        mi = s.get("module_index")
        if _is_image_placeholder(s):
            all_issues.append({
                "slide_index": idx, "module_index": mi,
                "issue_type": "image_placeholder",
                "severity": _SEVERITY["image_placeholder"],
                "context": {"slide_type": s.get("slide_type")},
            })
        if _is_diagram_branded_fallback(s):
            all_issues.append({
                "slide_index": idx, "module_index": mi,
                "issue_type": "diagram_branded_fallback",
                "severity": _SEVERITY["diagram_branded_fallback"],
                "context": {"slide_type": s.get("slide_type")},
            })
        if _is_quiz_no_options(s):
            all_issues.append({
                "slide_index": idx, "module_index": mi,
                "issue_type": "quiz_no_options",
                "severity": _SEVERITY["quiz_no_options"],
                "context": {"quiz_options_count": len(s.get("quiz_options") or [])},
            })
        if _is_notes_too_short(s):
            notes = s.get("speaker_notes", "")
            all_issues.append({
                "slide_index": idx, "module_index": mi,
                "issue_type": "notes_too_short",
                "severity": _SEVERITY["notes_too_short"],
                "context": {
                    "word_count": len(notes.split()) if notes else 0,
                    "min_required": _layout_min_notes_words(s.get("slide_type", "")),
                    "slide_type": s.get("slide_type"),
                },
            })

    # Cross-slide checks
    all_issues.extend(_check_module_underpopulated(slides, expected_slides_per_module))
    all_issues.extend(_check_image_overused(slides))
    all_issues.extend(_check_title_near_duplicate(slides))
    all_issues.extend(_check_bullet_citation_warnings(slides, course_regulation_ids))

    # Summary
    by_severity: dict[str, int] = Counter()
    by_type: dict[str, int] = Counter()
    for iss in all_issues:
        by_severity[iss["severity"]] += 1
        by_type[iss["issue_type"]] += 1

    return {
        "total_issues": len(all_issues),
        "by_severity": dict(by_severity),
        "by_type": dict(by_type),
        "issues": all_issues,
    }
