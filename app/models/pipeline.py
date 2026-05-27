"""Pipeline contracts (BLUEPRINT §04.4).

NexusPipelineState (TypedDict) lives in ``app.agents.pipeline`` (PHASE 3),
NOT here. This file holds only Pydantic models.

Only import-path differs from BP §04.4: ``app.models.*`` instead of ``models.*``.
"""

from __future__ import annotations

from typing import Literal, Self

import structlog
from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from app.models.core import (
    DIAGRAM_VIEWBOX_LITERAL,
    LAYOUT_CONSTRAINTS,
    SlideType,
)
from app.models.knowledge import NormativeChunk, StylePattern

logger = structlog.get_logger()


class ImageStrategy(BaseModel):
    """Strategy for the visual support of a slide.

    FIX #30.3 (2026-05-26): ``strategy`` è ora `Literal` strict — l'LLM NON
    può più scrivere "content_image" / "content" / "image" / "search". Solo:
        - "web_search" → cerca foto Pexels via query
        - "diagram"    → renderizza diagram_code SVG
        - "none"       → nessuna immagine (slide testuale pura)
    Recovery nel prefetcher (_resolve_query_urls): se slide_type=CONTENT_IMAGE
    + query valorizzata + strategy=any → tratta come web_search.

    ``diagram_code`` è inline SVG (NOT Mermaid). Generated directly by the LLM.
    ``aspect_hint`` (FASE 4 vast-hopping): passa a Pexels come ``orientation``
    param e a ``fit_image_to_box`` per scegliere lo strategy di sizing.
    """

    strategy: Literal["none", "web_search", "diagram"] = "none"
    query: str | None = None
    query_url: str | None = None
    diagram_code: str | None = None  # legacy: inline SVG free-form (deprecated)
    # FIX #30.4 (2026-05-26): diagram_filling è il path preferito per DIAGRAM.
    # L'LLM sceglie un template del catalogo e riempie gli slot vincolati a
    # max_chars; diagram_service.render_diagram_to_svg() genera l'SVG finale.
    # Eliminate frecce sovrapposte / testo tagliato visti in pag 53 corso #c7e9.
    diagram_filling: dict[str, object] | None = None  # serializzato DiagramFilling
    aspect_hint: Literal["landscape", "portrait", "square"] | None = None


class SlideContent(BaseModel):
    """Single-slide content produced by the Content Agent.

    FASE 1 vast-hopping-sketch: ``model_validator(mode="after")`` STRICT (no truncation):
    se la slide viola i constraints di LAYOUT_CONSTRAINTS per il suo ``slide_type``,
    raise ``ValueError`` → il content_agent intercetta e chiede SPLIT all'LLM (FASE 2),
    mai compressione né "…" troncamento.
    """

    # FIX #30.6 (2026-05-26): index/module_index sono DEFAULT 0 nello schema
    # instructor: l'LLM non li riempie (sono assegnati post-validation dal
    # batch loop in ingestion_service.generate_module_structured che fa
    # s.index = start_idx + offset). Renderli required nel modello li fa
    # apparire required nello schema TOOLS, l'LLM li omette, instructor fa
    # raise → ZERO slide entrano nel batch (visto nel E2E #4: 16 slide su
    # 80 attese perché solo le poche dove l'LLM ha riempito a caso index
    # sopravvivevano).
    index: int = 0
    module_index: int = 0
    slide_type: SlideType
    title: str = Field(..., max_length=200)  # bound largo, il vincolo vero è per-type
    # FIX #28.1 (2026-05-26): structured output. body:str → bullets:list[str].
    # Il validator conta len(bullets), niente più split("\n") fragile. instructor
    # impone la lista a livello schema → l'LLM NON può consegnare prosa.
    # CASE_STUDY usa `sezioni` (3 elementi: situazione/azione/risultato) invece di
    # bullets, perché semanticamente sono blocchi di testo, non punti elenco.
    bullets: list[str] = Field(default_factory=list)
    sezioni: list[str] = Field(default_factory=list)  # solo CASE_STUDY (3 sezioni)
    # FIX #29 (2026-05-26): speaker_notes ora OBBLIGATORIO (no default).
    # Senza questo, instructor non lo considera required nello schema TOOLS e
    # il modello lo omette → tutte le slide finiscono con note vuote. Il validator
    # poi soft-warna ma è troppo tardi. min_length=1 forza la presenza; il vincolo
    # parole-target resta nel validator per-tipo (notes_min_words/notes_max_words).
    speaker_notes: str = Field(..., min_length=1, description=(
        "Copione audio TTS per la slide. Italiano formativo, 120-140 parole "
        "(~45 sec di audio a 180 wpm). NON ripetere i bullet — espandi con "
        "esempio operativo, contesto normativo, conseguenza pratica."
    ))
    normative_ref: str = ""
    source_chunk_ids: list[str] = Field(default_factory=list)
    image: ImageStrategy = Field(default_factory=lambda: ImageStrategy(strategy="none"))
    quiz_options: list[str] | None = None
    quiz_correct: int | None = None

    @field_validator("source_chunk_ids", mode="before")
    @classmethod
    def _coerce_source_chunk_ids(cls, v: object) -> list[str]:
        """FIX #31.5B (2026-05-27, analista review 6): coercion idempotente
        per chunk_ids emessi malformati dall'LLM.

        In E2E #23 batch 2 di M1 era fallito perché Azure-mini ha emesso
        `source_chunk_ids='source_chunk_ids([id1,id2]'` come stringa
        invece che lista. Instructor ha re-asked 5 volte ma l'LLM ha
        continuato a sbagliare lo schema → batch perso (10 slide).

        Accetta:
          - None / "" → []
          - list[str|Any] → [str(x) per x in list, x non vuoto]
          - str JSON-array '["a", "b"]' → list
          - str con wrapper 'source_chunk_ids([a, b])' → strip e parse
          - str comma-separated 'a,b,c' (fallback) → split
        """
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if x is not None and str(x).strip()]
        if isinstance(v, str):
            import json
            s = v.strip()
            # Strip wrapper 'source_chunk_ids(...)' se presente
            if s.startswith("source_chunk_ids("):
                s = s[len("source_chunk_ids("):].rstrip(")")
            # Prova JSON parse
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if x is not None and str(x).strip()]
                return [str(parsed)] if parsed else []
            except json.JSONDecodeError:
                # Fallback: split comma-separated, strip brackets/quotes
                cleaned = s.strip("[](){}").replace('"', "").replace("'", "")
                return [x.strip() for x in cleaned.split(",") if x.strip()]
        # Tipo non gestito (int, float, ecc.) — fallback safe
        return []

    @model_validator(mode="after")
    def enforce_layout_constraints(self) -> Self:
        """STRICT validation per-SlideType (FASE 1 vast-hopping-sketch).

        Rigetta — non tronca — quando i numeri sforano. Il caller (content_agent)
        intercetta il ValueError, manda corrective prompt SPLIT, ri-tenta una volta.
        Filosofia: meglio una slide in meno che una slide rotta.
        """
        rules = LAYOUT_CONSTRAINTS.get(self.slide_type)
        if rules is None:
            return self  # tipo non mappato (dev/test) — pass-through

        # ─── TITLE char count ───
        if len(self.title) > rules.title_max_chars:
            raise ValueError(
                f"slide_type={self.slide_type.value} title={len(self.title)} char > "
                f"{rules.title_max_chars} max. NON troncare: emetti 2 slide con "
                f"titoli più corti."
            )

        # ─── BODY bullets/words (FIX #28.1: list[str], niente più split) ───
        # PROFONDITÀ per-slide (asse 1). Raise → instructor reask (max_retries).
        # CASE_STUDY usa `sezioni`, gli altri tipi-con-body usano `bullets`.
        from app.models.core import SlideType as _ST

        is_case = self.slide_type == _ST.CASE_STUDY
        items = self.sezioni if is_case else self.bullets
        unit_label = "sezioni" if is_case else "bullets"

        if rules.body_max_bullets > 0:
            n = len(items)
            if n > rules.body_max_bullets:
                raise ValueError(
                    f"slide_type={self.slide_type.value} ha {n} {unit_label} > "
                    f"{rules.body_max_bullets} max. SPLITTA il concetto in 2 slide "
                    f"consecutive (NON troncare, NON comprimere)."
                )
            if rules.body_min_bullets > 0 and n < rules.body_min_bullets:
                raise ValueError(
                    f"slide_type={self.slide_type.value} ha {n} {unit_label} < "
                    f"{rules.body_min_bullets} min. AGGIUNGI {unit_label} fino ad almeno "
                    f"{rules.body_min_bullets} (espandi con altri aspetti del chunk "
                    f"normativo, NON inventare, NON ripetere)."
                )
            for i, item in enumerate(items):
                n_words = len(item.split())
                if n_words > rules.bullet_max_words:
                    raise ValueError(
                        f"slide_type={self.slide_type.value} {unit_label}[{i}] ha {n_words} "
                        f"parole > {rules.bullet_max_words} max. Riscrivi più "
                        f"sintetico o splitta in 2 slide."
                    )
        elif rules.body_max_bullets == 0 and (self.bullets or self.sezioni):
            # FIX #30.6 (2026-05-26): MODULE_OPEN usa bullets[0] come "sub-title"
            # slot (convention con slide_builder_v2: nx_module_title legge da
            # body placeholder idx=1). Quindi 0-1 bullet sono accettabili.
            from app.models.core import SlideType as _ST
            if self.slide_type == _ST.MODULE_OPEN:
                if self.sezioni:
                    raise ValueError(
                        f"slide_type=MODULE_OPEN non deve avere sezioni (solo bullets[0] opzionale come sub-title)."
                    )
                if len(self.bullets) > 1:
                    raise ValueError(
                        f"slide_type=MODULE_OPEN: max 1 bullet (sub-title), trovati {len(self.bullets)}."
                    )
                # 0 o 1 bullet → OK, skip altri controlli
            else:
                raise ValueError(
                    f"slide_type={self.slide_type.value} non deve avere bullets/sezioni (è "
                    f"{'title-only' if self.slide_type.value in ('TITLE', 'CLOSING') else 'options-only'})."
                )

        # ─── SPEAKER NOTES word range ───
        # FIX #29.2 (2026-05-26): under-target = WARNING SOFT (non raise). Motivo
        # (analista): conteggio parole è un PROXY del target reale (durata audio
        # misurata da mutagen 35-55s a slide 45s). Bocciare per 1-4 parole sotto
        # soglia bruciava i retry instructor su un miss sistematico. Il gate hard
        # è ora la durata MP3 post-generazione (off_target flag già esistente in
        # audio_service). Over-target resta hard (spreco token/tempo non recuperabile).
        notes_words = len(self.speaker_notes.split()) if self.speaker_notes else 0
        if notes_words < rules.notes_min_words:
            logger.warning(
                "notes_below_target_soft",
                slide_type=self.slide_type.value,
                got=notes_words,
                min=rules.notes_min_words,
            )
        if notes_words > rules.notes_max_words:
            raise ValueError(
                f"slide_type={self.slide_type.value} speaker_notes ha {notes_words} "
                f"parole > {rules.notes_max_words} max (TTS sopra-target). Sposta "
                f"il contenuto eccedente in una slide successiva."
            )

        # ─── IMAGE required ───
        if rules.requires_image:
            if self.slide_type == SlideType.DIAGRAM:
                # FIX #30.9b (2026-05-26): accetta `diagram_filling` (catalogo
                # SVG #30.4, PREFERRED — zero overflow per design) OPPURE
                # `diagram_code` (legacy free-form SVG, kept per
                # retrocompatibilità). Prima richiedeva solo diagram_code,
                # creando conflitto col prompt #30.7c che chiedeva filling:
                # l'LLM seguiva il path che passa la validation = SVG libero,
                # vanificando il catalogo (visto in E2E #8: 5/5 DIAGRAM tornati
                # a legacy con bug overflow testo).
                has_filling = bool(self.image.diagram_filling)
                has_legacy_svg = bool(self.image.diagram_code)
                if not has_filling and not has_legacy_svg:
                    raise ValueError(
                        "slide_type=DIAGRAM richiede image.diagram_filling "
                        "(catalogo SVG pre-disegnato, preferred — vedi prompt) "
                        "OPPURE image.diagram_code (SVG inline legacy)."
                    )
                if has_filling:
                    # Valida che template_name esista nel catalogo. Il
                    # DiagramFilling Pydantic model fa già validation slot-level
                    # (max_chars), qui controlliamo solo il template_name come
                    # gate veloce — l'LLM potrebbe scrivere nomi inventati.
                    from app.services.diagram_service import DIAGRAM_CATALOG
                    tn = self.image.diagram_filling.get("template_name")
                    if tn not in DIAGRAM_CATALOG:
                        raise ValueError(
                            f"diagram_filling.template_name={tn!r} non nel "
                            f"catalogo. Validi: {sorted(DIAGRAM_CATALOG.keys())}"
                        )
                else:
                    # Solo legacy diagram_code: mantieni check viewBox esistente
                    # FIX #11 (2026-05-25): rilasso il viewBox check — l'LLM
                    # emette spesso viewBox custom (es. "0 0 800 600"). Cairosvg
                    # può renderizzare qualsiasi viewBox e noi forziamo
                    # output_width/height 1760x800. Verifica solo che CI SIA un
                    # viewBox attribute valido (qualunque).
                    if "viewBox" not in self.image.diagram_code:
                        raise ValueError(
                            "slide_type=DIAGRAM image.diagram_code deve avere "
                            "un attributo viewBox SVG (qualunque dimensione)."
                        )
            else:  # CONTENT_IMAGE
                if not self.image.query:
                    raise ValueError(
                        "slide_type=CONTENT_IMAGE richiede image.query (2-4 parole "
                        "italiane descrittive del concetto da illustrare)."
                    )
                # FIX #11: aspect_hint opzionale, default landscape (la maggior
                # parte delle foto sicurezza/cantiere sono landscape).
                if self.image.aspect_hint is None:
                    object.__setattr__(self.image, "aspect_hint", "landscape")

        # ─── QUIZ options ───
        if rules.requires_options:
            if not self.quiz_options or len(self.quiz_options) != 4:
                raise ValueError(
                    f"slide_type=QUIZ richiede esattamente 4 quiz_options, "
                    f"ricevute {len(self.quiz_options) if self.quiz_options else 0}."
                )
            if self.quiz_correct is None or self.quiz_correct not in (0, 1, 2, 3):
                raise ValueError(
                    f"slide_type=QUIZ richiede quiz_correct INTERO ∈ {{0,1,2,3}}, "
                    f"ricevuto {self.quiz_correct!r} (tipo {type(self.quiz_correct).__name__})."
                )
            for i, opt in enumerate(self.quiz_options):
                if len(opt) > 80:
                    raise ValueError(
                        f"slide_type=QUIZ option[{i}] ha {len(opt)} char > 80 max. "
                        f"Riscrivi l'opzione più sintetica."
                    )

        return self


class CardinalityError(ValueError):
    """FIX #28.1b: sollevata SOLO in cardinality_mode='strict' (il fill-loop la
    cattura e ri-richiede le slide mancanti). In 'warn'/'off' non viene mai sollevata,
    così NON consuma il budget max_retries di instructor (asse profondità).
    """


class ModuleSlides(BaseModel):
    """FIX #28.1b: wrapper di MODULO — chiude l'asse CARDINALITÀ (quante slide).

    instructor garantisce slide PIENE (profondità, via SlideContent.validate). Questo
    wrapper garantisce ABBASTANZA slide. Il validator è CONTEXT-DRIVEN (4 punti analista):

      cardinality_mode = "off"    → no-op (default; instructor NON reaska sulla cardinalità)
      cardinality_mode = "warn"   → registra warning, non solleva (uso dentro instructor)
      cardinality_mode = "strict" → under-cardinalità solleva CardinalityError (solo il
                                    fill-loop lo attiva, per innescare la sotto-richiesta)

    Budget separati: la PROFONDITÀ vive in SlideContent (→ max_retries instructor); la
    CARDINALITÀ vive qui (→ fill-loop dedicato col suo cap). Non si mescolano.
    """

    module_index: int
    title: str = ""
    slides: list[SlideContent] = Field(default_factory=list)
    cardinality_warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_cardinality(self, info: ValidationInfo) -> Self:
        ctx = info.context or {}
        expected = ctx.get("expected_slides")
        mode = ctx.get("cardinality_mode", "off")

        # TRANELLO #1 (analista): senza context, expected è None → no-op SILENZIOSO.
        # Il fill-loop DEVE passare validation_context, sennò la cardinalità non è vista.
        if expected is None or mode == "off":
            return self

        got = len(self.slides)

        if got > expected:
            # PUNTO 2: over-cardinalità = errore innocuo → warning, MAI raise/reask.
            msg = f"module {self.module_index}: {got} slide > {expected} attese (troncamento a valle)"
            self.cardinality_warnings.append(msg)
            return self

        if got < expected:
            msg = f"module {self.module_index}: {got} slide < {expected} attese (gap={expected - got})"
            if mode == "strict":
                raise CardinalityError(msg)
            self.cardinality_warnings.append(msg)

        return self


class ModuleSpec(BaseModel):
    """Specification of a module in the pacing plan."""

    module_index: int
    title: str
    slide_count: int
    slide_distribution: dict[str, int]  # e.g. {"CONTENT_TEXT": 10, "QUIZ": 2, "RECAP": 1}


class PacingPlan(BaseModel):
    """Slide distribution plan computed by the PacingEngine."""

    total_slides: int
    modules: list[ModuleSpec]


class ModuleContent(BaseModel):
    """Content Agent output for a single module."""

    module_index: int
    title: str
    slides: list[SlideContent]


class CourseContext(BaseModel):
    """Full context produced by the Research Agent for the Content Agent."""

    chunks: list[NormativeChunk]
    chunks_by_module: dict[int, list[NormativeChunk]]
    pacing_plan: PacingPlan
    style_patterns: list[StylePattern]
    regulation_ids: list[str]
    regulation_slugs: list[str]


class GenerationReport(BaseModel):
    """Final generation report."""

    total_slides: int
    slides_with_images: int
    slides_with_diagrams: int
    quiz_count: int
    modules_completed: int
    modules_failed: int
    normative_refs_count: int
    warnings: list[str] = []
    truncation_warnings: list[str] = []  # slides truncated by the body validator — visible to the operator
    generation_time_seconds: float
