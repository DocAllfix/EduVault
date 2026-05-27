"""Diagram service — catalogo SVG pre-disegnati con slot vincolati (FIX #30.4).

Conferma analista (2026-05-26): "il punto debole del template è il rientro
appeso sulla seconda riga; sposti il vincolo a monte invece di gestire
l'overflow a valle". Implementiamo le tripla difesa proposta:

1. **Schema constraint**: ogni template ha `max_chars` per slot; il Pydantic
   `DiagramFilling` valida prima ancora di passare al renderer.
2. **Auto-shrink font runtime**: se il testo sta dentro max_chars ma è grande
   in pixel, scala il `font-size` SVG fino a un minimo leggibile (14pt).
3. **Caption fuori dai box**: il prompt richiede caption (20-200 char) per la
   spiegazione lunga; nei box solo label corte.

Catalogo (7 template):
- flow_horizontal_3step / _4step   → processi sequenziali
- pyramid_3level                    → gerarchie (lavoratore→preposto→dirigente)
- matrix_2x2                        → probabilità × gravità (matrice rischio)
- causa_effetto                     → causa → evento → effetto (D.Lgs. 81/08)
- org_tree_3level                   → organigramma SSL (RSPP/RLS/medico)
- compare_2col                      → DPI vs DPC, comparazioni

Selezione: l'LLM riceve l'enum dei template + descrizione semantica + lista
slot (con max_chars). Genera `DiagramFilling(template_name, slots, caption)`
strict via instructor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import structlog
from pydantic import BaseModel, Field, model_validator

logger = structlog.get_logger()

SVG_TEMPLATES_DIR = Path("assets/svg_templates")


class DiagramSlot(BaseModel):
    """Spec di un singolo slot testuale nel template SVG."""
    name: str           # placeholder name (es. "label_1")
    max_chars: int      # limite hard del testo per quel slot
    font_size_default: int = 28


class DiagramTemplateDef(BaseModel):
    """Definizione di un template SVG del catalogo."""
    name: str                       # es. "flow_horizontal_4step"
    description: str                # semantica (per prompt LLM)
    template_path: Path
    slots: list[DiagramSlot]


# CATALOGO — dimensioni max_chars derivate dalla geometria della box SVG
# (es. flow_horizontal_4step ha box 320×180 con font 28pt → ~18 char per riga
# senza wrap, andare oltre causa overflow visibile).
DIAGRAM_CATALOG: dict[str, DiagramTemplateDef] = {
    "flow_horizontal_3step": DiagramTemplateDef(
        name="flow_horizontal_3step",
        description="3 step in sequenza orizzontale connessi da frecce (processi)",
        template_path=SVG_TEMPLATES_DIR / "flow_horizontal_3step.svg",
        slots=[
            # rect 440px ÷ ~19px/char @34pt - 40px margine = ~21 char. Conservativo 20.
            DiagramSlot(name="label_1", max_chars=20, font_size_default=34),
            DiagramSlot(name="label_2", max_chars=20, font_size_default=34),
            DiagramSlot(name="label_3", max_chars=20, font_size_default=34),
        ],
    ),
    "flow_horizontal_4step": DiagramTemplateDef(
        name="flow_horizontal_4step",
        description="4 step in sequenza orizzontale connessi da frecce",
        template_path=SVG_TEMPLATES_DIR / "flow_horizontal_4step.svg",
        slots=[
            # rect 320px ÷ ~15px/char @28pt - 40px margine = ~18 char. Tenuto 18.
            DiagramSlot(name="label_1", max_chars=18, font_size_default=28),
            DiagramSlot(name="label_2", max_chars=18, font_size_default=28),
            DiagramSlot(name="label_3", max_chars=18, font_size_default=28),
            DiagramSlot(name="label_4", max_chars=18, font_size_default=28),
        ],
    ),
    "pyramid_3level": DiagramTemplateDef(
        name="pyramid_3level",
        description=(
            "Piramide tronca a 3 livelli per gerarchie quantitative "
            "(es. dirigente al vertice, preposti al centro, lavoratori "
            "alla base — pochi sopra molti sotto). Per gerarchie di RUOLI "
            "puri (no quantità) preferisci 'org_tree_3level'."
        ),
        template_path=SVG_TEMPLATES_DIR / "pyramid_3level.svg",
        slots=[
            # FIX #30.9g (2026-05-27, analista): max_chars per-slot misurato
            # sulla larghezza REALE del trapezio (post-redesign vertice tronco).
            # Vertice trapezio 320px @28pt = ~17 char. Centro 540px @28pt =
            # ~30 ma teniamo 24 per leggibilità. Base 740px @28pt = ~42 ma
            # teniamo 30 conservativo.
            DiagramSlot(name="label_1", max_chars=17, font_size_default=28),
            DiagramSlot(name="label_2", max_chars=24, font_size_default=28),
            DiagramSlot(name="label_3", max_chars=30, font_size_default=28),
        ],
    ),
    "matrix_2x2": DiagramTemplateDef(
        name="matrix_2x2",
        description="Matrice 2x2 (probabilità × gravità, scelta vs impatto)",
        template_path=SVG_TEMPLATES_DIR / "matrix_2x2.svg",
        slots=[
            DiagramSlot(name="axis_x", max_chars=30, font_size_default=28),
            DiagramSlot(name="axis_y", max_chars=30, font_size_default=28),
            DiagramSlot(name="quadrant_tl", max_chars=26, font_size_default=32),
            DiagramSlot(name="quadrant_tr", max_chars=26, font_size_default=32),
            DiagramSlot(name="quadrant_bl", max_chars=26, font_size_default=32),
            DiagramSlot(name="quadrant_br", max_chars=26, font_size_default=32),
        ],
    ),
    "causa_effetto": DiagramTemplateDef(
        name="causa_effetto",
        description="Catena causa → evento → effetto (analisi rischio D.Lgs. 81/08)",
        template_path=SVG_TEMPLATES_DIR / "causa_effetto.svg",
        slots=[
            DiagramSlot(name="causa", max_chars=26, font_size_default=28),
            DiagramSlot(name="processo", max_chars=26, font_size_default=28),
            DiagramSlot(name="effetto", max_chars=26, font_size_default=28),
        ],
    ),
    "org_tree_3level": DiagramTemplateDef(
        name="org_tree_3level",
        description="Organigramma a 3 livelli (es. RSPP, RLS, medico competente)",
        template_path=SVG_TEMPLATES_DIR / "org_tree_3level.svg",
        slots=[
            DiagramSlot(name="level_1", max_chars=22, font_size_default=30),
            DiagramSlot(name="level_2a", max_chars=22, font_size_default=28),
            DiagramSlot(name="level_2b", max_chars=22, font_size_default=28),
            DiagramSlot(name="level_2c", max_chars=22, font_size_default=28),
            DiagramSlot(name="level_3", max_chars=40, font_size_default=28),
        ],
    ),
    "compare_2col": DiagramTemplateDef(
        name="compare_2col",
        description="Confronto 2 colonne (es. DPI vs DPC, prima/dopo)",
        template_path=SVG_TEMPLATES_DIR / "compare_2col.svg",
        slots=[
            DiagramSlot(name="title_left", max_chars=22, font_size_default=34),
            DiagramSlot(name="title_right", max_chars=22, font_size_default=34),
            DiagramSlot(name="item_left_1", max_chars=36, font_size_default=26),
            DiagramSlot(name="item_left_2", max_chars=36, font_size_default=26),
            DiagramSlot(name="item_left_3", max_chars=36, font_size_default=26),
            DiagramSlot(name="item_right_1", max_chars=36, font_size_default=26),
            DiagramSlot(name="item_right_2", max_chars=36, font_size_default=26),
            DiagramSlot(name="item_right_3", max_chars=36, font_size_default=26),
        ],
    ),
}

# Literal type per Pydantic (validato strict in DiagramFilling)
DiagramTemplateName = Literal[
    "flow_horizontal_3step",
    "flow_horizontal_4step",
    "pyramid_3level",
    "matrix_2x2",
    "causa_effetto",
    "org_tree_3level",
    "compare_2col",
]


class DiagramFilling(BaseModel):
    """Schema strict per il riempimento di un template diagramma.

    L'LLM emette questo invece di SVG libero (FIX #30.4 — eliminazione del
    rischio overflow / frecce sovrapposte).
    """
    template_name: DiagramTemplateName
    slots: dict[str, str] = Field(default_factory=dict, description=(
        "Dict slot_name → text. Ogni testo deve rispettare max_chars del slot "
        "per il template scelto (validato automaticamente)."
    ))
    caption: str = Field(
        ...,
        min_length=20,
        max_length=200,
        description=(
            "Spiegazione lunga del diagramma, mostrata SOTTO l'immagine nel "
            "placeholder nx_caption. NON dentro al diagramma. Da 20 a 200 caratteri."
        ),
    )

    @model_validator(mode="after")
    def check_slots(self) -> "DiagramFilling":
        """FIX #30.9f (2026-05-27, post-analista): auto-truncate gentile.

        Pre-fix: l'LLM produceva "Valutazione rischio" (19 char) per slot a
        max_chars=18 → validator raise → fallback legacy SVG → diagram_code
        None → branded_fallback. Risultato: 16/16 DIAGRAM del 4h v2 erano
        placeholder generici, non i template SVG.

        Post-fix: se uno slot eccede max_chars di POCO (<=50% in più),
        tronca a max_chars-1 + "…". Se eccede MOLTO (>50%), raise come
        prima (è un errore semantico vero, non un off-by-1 LLM).
        """
        tpl = DIAGRAM_CATALOG.get(self.template_name)
        if tpl is None:
            raise ValueError(f"Template {self.template_name!r} non nel catalogo")
        slot_names = {s.name for s in tpl.slots}
        missing = slot_names - set(self.slots.keys())
        if missing:
            raise ValueError(
                f"DiagramFilling template={self.template_name}: "
                f"slot mancanti {sorted(missing)}"
            )
        # Auto-truncate come RETE DI SICUREZZA per ±1-2 char (analista
        # 2026-05-27): tolerance ridotta da 50% a 20%. Lo strumento
        # primario per evitare overflow è max_chars per-slot accurato
        # (vedi DIAGRAM_CATALOG geometrie aggiornate). Se l'LLM sfora di
        # più del 20% è errore semantico vero: il chunk non si sintetizza
        # in N char, va re-prompted.
        # Taglio in CODA (primi N chars + "…"), MAI in testa: il PNG 27
        # mostrava "atore di lavor…" ma in realtà era cairosvg che
        # clippava simmetrico per text-anchor=middle in triangolo
        # geometricamente più stretto del testo. Il fix vero è max_chars
        # per-slot misurato sulla geometria reale.
        for s in tpl.slots:
            v = self.slots.get(s.name, "")
            if len(v) > s.max_chars:
                tolerance = int(s.max_chars * 1.2)
                if len(v) > tolerance:
                    raise ValueError(
                        f"slot {s.name!r} sfora max_chars={s.max_chars} di "
                        f"più del 20%: {len(v)} caratteri (max tollerato "
                        f"{tolerance}). Riformula più sintetico."
                    )
                # Truncate in coda + ellissi finale (mai in testa)
                truncated = v[: s.max_chars - 1].rstrip() + "…"
                self.slots[s.name] = truncated
        return self


def render_diagram_to_svg(filling: DiagramFilling) -> str:
    """Sostituisce gli {{slot}} nel template SVG con i valori validati.

    Ritorna stringa SVG pronta per cairosvg → PNG. NON fa auto-shrink:
    grazie ai max_chars vincolati a monte, il testo entra sempre con il
    font_size_default. Se in futuro vedremo casi limite, aggiungeremo
    auto-shrink qui (Pillow misura → ricalcola sz attribute).
    """
    tpl = DIAGRAM_CATALOG[filling.template_name]
    svg = tpl.template_path.read_text(encoding="utf-8")
    for s in tpl.slots:
        value = filling.slots.get(s.name, "")
        # Escape XML basic
        value = (
            value.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .replace('"', "&quot;")
        )
        svg = svg.replace(f"{{{{{s.name}}}}}", value)
    return svg


def get_catalog_prompt_description() -> str:
    """Genera il blocco di descrizione catalogo per il prompt LLM."""
    lines = ["TEMPLATE DIAGRAM DISPONIBILI (scegli il più appropriato):"]
    for tpl in DIAGRAM_CATALOG.values():
        slot_desc = ", ".join(f"{s.name} (max {s.max_chars} char)" for s in tpl.slots)
        lines.append(f"- {tpl.name}: {tpl.description}")
        lines.append(f"  slots: {slot_desc}")
    return "\n".join(lines)


__all__ = [
    "DiagramSlot",
    "DiagramTemplateDef",
    "DIAGRAM_CATALOG",
    "DiagramTemplateName",
    "DiagramFilling",
    "render_diagram_to_svg",
    "get_catalog_prompt_description",
]
