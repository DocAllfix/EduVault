"""PacingEngine — slide-distribution planner (BLUEPRINT §06B + GAP-1 v2.0).

PHASE 3.2 — translates ``duration_hours + density`` into a per-module
slide plan that the Research Agent uses to allocate chunks and that the
Content Agent uses to know how many slides of each type to generate.

═══ COMMERCIAL CONSTRAINT (GAP-1 v2.0, prompt 3.2) ═══
The fundamental pacing rule is **1 slide per 30 seconds of course**.
This is a commercial commitment to the customer and an architectural
invariant. It REPLACES the weighted-average ``SECONDS_PER_TYPE`` formula
of BP §06B literal (see VERIFICATION_DEBT D22).

═══ V1.0 DISTRIBUTION (FIX-8, prompt 3.2) ═══
``DIAGRAM`` is excluded from the v1.0 distribution (D-17 architectural
decision): LLMs are inconsistent at generating valid SVG. If the Content
Agent emits a DIAGRAM slide spontaneously, the Image Service in PHASE 4
sanitises and renders it. The percentages here are FIX-8 verbatim and
differ from BP §06B (see VERIFICATION_DEBT D23).
"""

from __future__ import annotations

import math

from app.models.core import SlideDensity
from app.models.pipeline import ModuleSpec, PacingPlan


class PacingEngine:
    """Compute a per-module slide plan from course duration + density."""

    # GAP-1 v2.0: fixed metric rule.
    SECONDS_PER_SLIDE = 30

    # FIX-8 v1.0: no DIAGRAM. Sums to 1.00.
    DISTRIBUTION: dict[str, float] = {
        "CONTENT_TEXT": 0.50,
        "CONTENT_IMAGE": 0.22,
        "QUIZ": 0.12,
        "CASE_STUDY": 0.06,
        "RECAP": 0.10,
    }

    DENSITY_MULTIPLIER: dict[SlideDensity, float] = {
        SlideDensity.LEGGERA: 0.8,
        SlideDensity.STANDARD: 1.0,
        SlideDensity.INTENSIVA: 1.25,
    }

    SLIDES_PER_MODULE_TARGET = 40

    def calculate(
        self,
        duration_hours: float,
        density: SlideDensity = SlideDensity.STANDARD,
        module_titles: list[str] | None = None,
    ) -> PacingPlan:
        """Return a PacingPlan for the given duration and density.

        If ``module_titles`` is provided (from COURSE_CATALOG, BP §13) it
        names the modules semantically. Otherwise modules are labelled
        ``Modulo N`` (1-indexed) so the Content Agent prompt still reads
        cleanly.
        """
        total_seconds = duration_hours * 3600
        multiplier = self.DENSITY_MULTIPLIER[density]
        total_slides = int((total_seconds / self.SECONDS_PER_SLIDE) * multiplier)

        num_modules = max(2, math.ceil(total_slides / self.SLIDES_PER_MODULE_TARGET))
        base_per_module = total_slides // num_modules
        remainder = total_slides % num_modules

        modules: list[ModuleSpec] = []
        for i in range(num_modules):
            slide_count = base_per_module + (1 if i < remainder else 0)

            distribution: dict[str, int] = {}
            assigned = 0
            types_list = list(self.DISTRIBUTION.items())
            for j, (slide_type, ratio) in enumerate(types_list):
                if j == len(types_list) - 1:
                    # The last type absorbs the remainder so the per-module
                    # distribution always sums to slide_count exactly.
                    distribution[slide_type] = slide_count - assigned
                else:
                    count = max(1, round(slide_count * ratio))
                    distribution[slide_type] = count
                    assigned += count

            modules.append(
                ModuleSpec(
                    module_index=i,
                    title=(
                        module_titles[i]
                        if module_titles and i < len(module_titles)
                        else f"Modulo {i + 1}"
                    ),
                    slide_count=slide_count,
                    slide_distribution=distribution,
                )
            )

        return PacingPlan(total_slides=total_slides, modules=modules)
