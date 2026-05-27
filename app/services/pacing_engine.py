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
    # FIX #29.0 (2026-05-26): 30→45s/slide. Decisione di prodotto (tradizione interna,
    # non vincolo cliente). Effetto: ~33% slide in meno → ogni chiamata LLM rispetta
    # il budget output (max_tokens=8000 → tetto teorico ~24 slide), elimina la causa
    # radice di cardinalità tagliata + note razionate + timeout TPM. Compliance neutra
    # (la durata corso 4h/8h non cambia, SCORM traccia tempo non slide).
    SECONDS_PER_SLIDE = 45

    # FIX #30.2 (2026-05-26): redistribution post-analista per spostare il
    # corso da "muro di bullet" (79% CONTENT_TEXT misurato) verso varietà.
    # Pesi calibrati: CONTENT_TEXT scende (45→0.45), CONTENT_IMAGE sale al
    # 25% (era 20%) per più visivo, RECAP scende a 0.02 (la chiusura modulo
    # è ora forzata da MODULE_CLOSE bookend, NON dipende dalla distribution),
    # CASE_STUDY tenuto a 6%, DIAGRAM a 5%. Sums to 1.00.
    DISTRIBUTION: dict[str, float] = {
        "CONTENT_TEXT": 0.55,
        "CONTENT_IMAGE": 0.25,
        "QUIZ": 0.10,
        "DIAGRAM": 0.05,
        "CASE_STUDY": 0.03,
        "RECAP": 0.02,
    }

    DENSITY_MULTIPLIER: dict[SlideDensity, float] = {
        SlideDensity.LEGGERA: 0.8,
        SlideDensity.STANDARD: 1.0,
        SlideDensity.INTENSIVA: 1.25,
    }

    # FIX #30.2 (2026-05-26): pacing dinamico guidato dalla densità chunk RAG.
    # Cap superiore (max contenuto/modulo) e cap inferiore (min sostenibile)
    # secondo decisione utente (Q3 analista risposta): clamp(round(n_chunks*1.5),18,29).
    # Bookends (MODULE_OPEN + MODULE_CLOSE) sono +2 SOPRA, non dentro.
    SLIDES_PER_MODULE_TARGET = 27  # default fisso quando chunks_per_module non disponibile
    # FIX #30.9e (2026-05-26): MAX 29→80. Quando num_modules viene dal catalogo
    # (es. 4 default_modules per corso 4h), ogni modulo deve contenere ~80 slide
    # contenuto per coprire la durata commerciale 4h × 80slide ÷ 45s = 320 slide.
    # MIN invariato 18 per back-compat (corsi 1h con moduli scarsi).
    SLIDES_PER_MODULE_MAX = 80
    SLIDES_PER_MODULE_MIN = 18
    CHUNKS_TO_SLIDES_RATIO = 1.5

    def calculate(
        self,
        duration_hours: float,
        density: SlideDensity = SlideDensity.STANDARD,
        module_titles: list[str] | None = None,
        chunks_per_module: dict[int, int] | None = None,
    ) -> PacingPlan:
        """Return a PacingPlan for the given duration and density.

        FIX #30.2 (2026-05-26): pacing DINAMICO. Se `chunks_per_module` è
        fornito (dict module_index → n_chunks RAG densi), ogni modulo riceve
        `clamp(round(n_chunks * 1.5), 18, 29)` slide di CONTENUTO, +2 fissi
        per bookends MODULE_OPEN/MODULE_CLOSE. La distribution dei tipi
        contenuto è calcolata sulle slide content (NON sul totale), così le
        percentuali restano coerenti.

        Se chunks_per_module è None, ricade sul comportamento legacy
        (slide_count = base derivato da duration/SECONDS_PER_SLIDE),
        retrocompat. Useremo None quando il caller non ha ancora i chunk
        (preview wizard, test).
        """
        total_seconds = duration_hours * 3600
        multiplier = self.DENSITY_MULTIPLIER[density]
        total_slides_legacy = int((total_seconds / self.SECONDS_PER_SLIDE) * multiplier)

        # FIX #30.9e (2026-05-26, analista): il catalogo definisce i moduli
        # reali. Se module_titles è fornito (vengono dal COURSE_CATALOG
        # default_modules), num_modules rispetta quel count — evita di creare
        # contenitori senza tema (E2E #13 4h aveva 12 moduli, 8 con titolo
        # fallback "Modulo N" e 0 chunks dal cosine cluster perché i temi
        # reali del materiale RAG sono ~5, non 12).
        if module_titles:
            num_modules = len(module_titles)
        else:
            num_modules = max(2, math.ceil(total_slides_legacy / self.SLIDES_PER_MODULE_TARGET))
        base_per_module = total_slides_legacy // num_modules
        remainder = total_slides_legacy % num_modules

        modules: list[ModuleSpec] = []
        total_slides_actual = 0
        for i in range(num_modules):
            # FIX #30.9e (2026-05-26): se module_titles viene dal COURSE_CATALOG
            # (= num_modules fisso al numero di temi reali), prevale il pacing
            # commerciale `base_per_module` per rispettare la durata 4h/8h.
            # Il pacing dinamico chunk-based ha senso SOLO se num_modules è
            # libero (cataloghi senza default_modules) — altrimenti rischia di
            # generare 4 moduli da 18 slide = 72 slide totali per un corso 4h
            # (= ~54 min, sotto durata commerciale).
            if module_titles:
                slide_count_content = base_per_module + (1 if i < remainder else 0)
            elif chunks_per_module is not None and i in chunks_per_module:
                n_chunks = chunks_per_module[i]
                # Clamp pacing dinamico
                slide_count_content = max(
                    self.SLIDES_PER_MODULE_MIN,
                    min(
                        self.SLIDES_PER_MODULE_MAX,
                        round(n_chunks * self.CHUNKS_TO_SLIDES_RATIO),
                    ),
                )
            else:
                slide_count_content = base_per_module + (1 if i < remainder else 0)

            # Distribution sulle slide DI CONTENUTO (bookends fuori)
            distribution: dict[str, int] = {}
            assigned = 0
            types_list = list(self.DISTRIBUTION.items())
            for j, (slide_type, ratio) in enumerate(types_list):
                if j == len(types_list) - 1:
                    distribution[slide_type] = slide_count_content - assigned
                else:
                    count = max(1, round(slide_count_content * ratio))
                    distribution[slide_type] = count
                    assigned += count

            # Bookends: +2 slot fissi (MODULE_OPEN + MODULE_CLOSE) SOPRA il
            # contenuto. NON entrano nel distribution dict (NON contano per
            # le percentuali) — il content_agent li emette come slot dedicati
            # prima/dopo le slide di contenuto.
            slide_count_total = slide_count_content + 2  # +open +close
            total_slides_actual += slide_count_total

            modules.append(
                ModuleSpec(
                    module_index=i,
                    title=(
                        module_titles[i]
                        if module_titles and i < len(module_titles)
                        else f"Modulo {i + 1}"
                    ),
                    slide_count=slide_count_total,  # TOTALE (contenuto + bookends)
                    slide_distribution=distribution,  # solo i tipi di contenuto
                )
            )

        return PacingPlan(total_slides=total_slides_actual, modules=modules)
