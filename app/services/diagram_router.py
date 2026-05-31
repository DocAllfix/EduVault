"""F5.3 — Diagram-first router (vast-hopping §F5.3).

Heuristic regex su title+bullets della slide: se uno dei 7 template SVG
curati (`assets/svg_templates/`) e' chiaramente piu' adatto della foto Pexels
generica per il contenuto della slide, ritorniamo il template path
direttamente e SALTIAMO la cascata web image_search.

Razionale (D5): slide tipo "matrice rischio probabilita' x gravita'" o "cause
ed effetti del rischio biologico" sono di natura concettuali; Pexels ritorna
una foto generica (operai con elmetto) che non aggiunge informazione e che
viene scartata dall'utente. Il template SVG comunica meglio + e' deterministico
+ non consuma quota Pexels.

VAA-a verifica al render: il router scrive un log strutturato `diagram_router_match`
con `keywords_matched` per debug + il sample read decide se le heuristic vanno
raffinate (es. aggiungere parole o per ambito).

Threshold: confidence >= 0.5 (50% delle parole-chiave del template trovate
in title+bullets). Sotto soglia → fallthrough cascata web.

Output: percorso assoluto del file SVG o None.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.models.core import SlideContent

logger = structlog.get_logger(__name__)

SVG_DIR = Path(__file__).parent.parent.parent / "assets" / "svg_templates"

# Heuristic keywords per template. Italiano + qualche sinonimo.
# Confidence calcolata come (parole-chiave trovate / 2) cap a 1.0 → soglia
# 0.5 = almeno 1 keyword forte deve matchare.
DIAGRAM_HEURISTICS: dict[str, tuple[str, list[str]]] = {
    # template_name → (svg_filename, keyword_list)
    "flow_3step": (
        "flow_horizontal_3step.svg",
        ["tre fasi", "tre step", "3 fasi", "3 step", "fase 1.*fase 2.*fase 3"],
    ),
    "flow_4step": (
        "flow_horizontal_4step.svg",
        [
            "quattro fasi",
            "4 fasi",
            "4 step",
            "ciclo",
            "iter procedurale",
            "processo in 4",
        ],
    ),
    "matrix_2x2": (
        "matrix_2x2.svg",
        [
            "matrice di rischio",
            "matrice rischio",
            "probabilita.*gravita",
            "probabilità.*gravità",
            "rischio.*probabilita",
            "rischio.*gravita",
            "valutazione rischi.*matrice",
            "matrice 2x2",
        ],
    ),
    "causa_effetto": (
        "causa_effetto.svg",
        [
            "cause ed effetti",
            "cause.*effetti",
            "ishikawa",
            "fishbone",
            "analisi.*cause",
            "fattori.*incidente",
            "fattori.*infortunio",
        ],
    ),
    "org_tree": (
        "org_tree_3level.svg",
        [
            "ruoli.*responsabilita",
            "ruoli e responsabilità",
            "organigramma",
            "datore.*rspp.*rls",
            "gerarchia.*sicurezza",
            "soggetti.*sicurezza",
        ],
    ),
    "pyramid_3level": (
        "pyramid_3level.svg",
        [
            "piramide",
            "gerarchia.*livelli",
            "livelli di controllo",
            "tre livelli",
            "gerarchia delle misure",
            "principio.*gerarchia",
        ],
    ),
    "compare_2col": (
        "compare_2col.svg",
        [
            "confronto.*dpi.*dpc",
            "dpi vs dpc",
            "differenze tra",
            "confronto tra",
            "a confronto",
            "individuali.*collettivi",
        ],
    ),
}


def maybe_diagram(slide: "SlideContent") -> str | None:
    """Restituisce path SVG locale se la slide e' meglio servita da un
    template diagrammatico curato, None altrimenti.

    Heuristic: regex case-insensitive su title + body (bullets joined).
    Per ogni template, calcola confidence = match_count / 2 (cap 1.0).
    Il template con confidence >= 0.5 vince (primo nell'ordine inserzione
    in caso di pari merito).

    Args:
        slide: la slide (SlideContent) da analizzare. Considera title +
            body (bullets). Non considera notes (testo audio diverso da
            contenuto visivo).
    """
    # Importi locali per evitare cyclic import con models.core.
    title = (slide.title or "").lower()
    bullets = " ".join(getattr(slide, "body", []) or []).lower()
    haystack = f"{title} {bullets}"

    best_match: tuple[str, str, float, list[str]] | None = None
    for name, (svg_file, patterns) in DIAGRAM_HEURISTICS.items():
        matched: list[str] = []
        for pattern in patterns:
            if re.search(pattern, haystack):
                matched.append(pattern)
        if not matched:
            continue
        confidence = min(len(matched) / 2.0, 1.0)
        if confidence < 0.5:
            continue
        if best_match is None or confidence > best_match[2]:
            best_match = (name, svg_file, confidence, matched)

    if best_match is None:
        return None

    name, svg_file, confidence, matched = best_match
    svg_path = SVG_DIR / svg_file
    if not svg_path.exists():
        logger.warning("diagram_router_missing_svg", template=name, path=str(svg_path))
        return None

    logger.info(
        "diagram_router_match",
        template=name,
        svg_file=svg_file,
        confidence=confidence,
        keywords_matched=matched,
        slide_title=slide.title[:60] if slide.title else None,
    )
    return str(svg_path)


__all__ = ["maybe_diagram", "DIAGRAM_HEURISTICS"]
