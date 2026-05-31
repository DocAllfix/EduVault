"""F9 Regulation→Courses Discovery Service (analista sign-off 2026-05-31).

Pure deterministic compute. Dato un regulation_slug, ritorna l'elenco dei
course_type del catalog che usano quella normativa + coverage score (% chunks
disponibili per regulation rispetto a target ideale per modulo).

Strategia:
  - Lookup inverso COURSE_CATALOG: regulation_slug → [course_type_slug, ...]
  - Per ogni course candidato, conta chunks per regulation (via knowledge_repo)
  - Coverage score:
    - 'generabile' (verde): ≥ avg_chunks_threshold (default 50 chunks/reg)
    - 'corpus_thin' (ambra): < threshold ma > min_floor (default 10)
    - 'no_coverage' (rosso): < min_floor o 0
  - Output include count chunks per regulation per UI badge

VAA-c (D9): UI mostra coverage REALE basato su chunks reali nel DB, non
solo match strutturale "slug in regs[]" booleano.

Reuse:
  - config.catalog_config.COURSE_CATALOG (source of truth course types)
  - app.services.knowledge_repo.KnowledgeRepository (count chunks)
"""

from __future__ import annotations

from typing import Any

from config.catalog_config import COURSE_CATALOG


# Soglie di coverage (calibrate sul corpus attuale: D.Lgs 81/08 1819 chunks,
# DM 03/09 69 chunks, DM 02/09 58, DM 01/09 25, Reg CE 852 147, etc.)
COVERAGE_GENERABLE_THRESHOLD = 50  # >= chunks per reg → "generabile" verde
COVERAGE_THIN_MIN_FLOOR = 10       # < threshold ma >= floor → "corpus_thin" ambra
                                    # < floor → "no_coverage" rosso


def _classify_coverage(n_chunks: int) -> str:
    """Coverage label deterministico basato su soglie."""
    if n_chunks >= COVERAGE_GENERABLE_THRESHOLD:
        return "generabile"
    if n_chunks >= COVERAGE_THIN_MIN_FLOOR:
        return "corpus_thin"
    return "no_coverage"


def _classify_overall(coverages: list[str]) -> str:
    """Overall coverage del corso: worst case fra le regulations."""
    if not coverages or "no_coverage" in coverages:
        return "no_coverage"
    if "corpus_thin" in coverages:
        return "corpus_thin"
    return "generabile"


async def compatible_courses(
    regulation_slug: str,
    pool: Any,
) -> dict[str, Any]:
    """Ritorna corsi del catalog compatibili con questa regulation.

    Args:
        regulation_slug: slug della regulation da cercare (es. "dlgs_81_08")
        pool: asyncpg pool per query DB chunks counts

    Returns:
        {
          "regulation_slug": str,
          "n_courses_compatible": int,
          "courses": [
            {
              "slug": str,
              "title": str,
              "hours": int,                            # min_hours catalog
              "regulation_slugs": list[str],           # tutte le regs del corso
              "overall_coverage": "generabile"|"corpus_thin"|"no_coverage",
              "chunks_per_regulation": {slug: count, ...},
              "missing_regulations": list[str],        # regs nel catalog NON in DB
            }
          ]
        }
    """
    # Trova course_types che usano questa regulation
    candidates: list[tuple[str, dict[str, Any]]] = []
    for ct_slug, ct_data in COURSE_CATALOG.items():
        regs_raw = ct_data.get("regs", [])
        if not isinstance(regs_raw, list):
            continue
        regs = [str(r) for r in regs_raw]
        if regulation_slug in regs:
            candidates.append((ct_slug, ct_data))

    if not candidates:
        return {
            "regulation_slug": regulation_slug,
            "n_courses_compatible": 0,
            "courses": [],
            "note": (
                f"Nessun course_type del catalog usa la regulation '{regulation_slug}'. "
                "Contatta l'amministratore per aggiungere un nuovo course_type."
            ),
        }

    # Per ogni candidato, count chunks per regulation
    courses_result: list[dict[str, Any]] = []
    for ct_slug, ct_data in candidates:
        regs_raw = ct_data.get("regs", [])
        regs = [str(r) for r in regs_raw] if isinstance(regs_raw, list) else []
        chunks_per_reg: dict[str, int] = {}
        missing_regs: list[str] = []
        coverages: list[str] = []

        for reg in regs:
            n_chunks = await pool.fetchval(
                "SELECT COUNT(*) FROM regulation_chunks rc "
                "JOIN regulations r ON rc.regulation_id = r.id "
                "WHERE r.slug = $1 AND rc.is_current = true",
                reg,
            )
            n_chunks = int(n_chunks or 0)
            chunks_per_reg[reg] = n_chunks
            if n_chunks == 0:
                missing_regs.append(reg)
                coverages.append("no_coverage")
            else:
                coverages.append(_classify_coverage(n_chunks))

        # min_hours come "hours" rappresentativo
        hours_raw = ct_data.get("min_hours", 0)
        hours = int(hours_raw) if isinstance(hours_raw, (int, float, str)) else 0
        title = str(ct_data.get("title", ct_slug))

        courses_result.append({
            "slug": ct_slug,
            "title": title,
            "hours": hours,
            "regulation_slugs": regs,
            "overall_coverage": _classify_overall(coverages),
            "chunks_per_regulation": chunks_per_reg,
            "missing_regulations": missing_regs,
        })

    # Sort: generabile prima, poi corpus_thin, poi no_coverage
    coverage_order = {"generabile": 0, "corpus_thin": 1, "no_coverage": 2}
    courses_result.sort(
        key=lambda c: (coverage_order[c["overall_coverage"]], c["slug"]),
    )

    return {
        "regulation_slug": regulation_slug,
        "n_courses_compatible": len(courses_result),
        "courses": courses_result,
    }
