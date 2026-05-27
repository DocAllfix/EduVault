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

import re
from pathlib import Path
from typing import Literal

import structlog
from pydantic import BaseModel, Field, field_validator, model_validator

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


# FIX #31.6B (2026-05-27, analista review 7): coercion regex deterministica
# che strippa i suffissi normativi dai label DIAGRAM PRIMA che il validator
# tolerance veda i valori troppo lunghi. In E2E #24 abbiamo 14/19 (74%)
# DIAGRAM in branded fallback perché l'LLM ostinatamente aggiungeva suffissi
# tipo "secondo la normativa", "secondo D.Lgs. 81/08 Art. X", "secondo
# Allegato VIII". Analista: "rendi deterministico ciò che possiedi — il
# fallback dev'essere riservato a 'struttura non mappabile', non a 'label
# troppo lungo'".
#
# Strategia: regex case-insensitive che rimuove pattern noti di filler
# normativo dalla coda del label. Se dopo lo strip il testo è ancora oltre
# max_chars, il check_slots (con tolerance 20%) si occupa del residuo
# (truncate gentile). Se è ancora oltre tolerance, allora è vero errore
# semantico → ValueError → fallback brandizzato giustificato.
_LABEL_NORMATIVE_SUFFIX_RE = re.compile(
    r"\s*[,;:.]*\s*("
    # "secondo (la|il|gli|le|i)? <qualunque cosa fino a fine>" — greedy fino
    # alla fine. Cattura "secondo D.Lgs. 81/08 Art. 225", "secondo la legge",
    # "secondo l'art. 76", ecc. in un colpo solo. La `.*$` greedy è OK qui
    # perché applichiamo solo a fine stringa (\s*$ in coda).
    r"secondo\s+.*"
    # "ai sensi (del|della|di)? <qualunque cosa fino a fine>"
    r"|ai\s+sensi\s+.*"
    # "in base (al|alla|a)? <qualunque cosa fino a fine>"
    r"|in\s+base\s+.*"
    # "ex art. N" / "ex D.Lgs. X" come suffisso preposizionato
    r"|ex\s+(?:art|d\.?\s*lgs|d\.?\s*m|allegato).*"
    # "D.Lgs. X/YY" puro a fine label (senza "secondo")
    r"|d\.?\s*lgs\.?\s*[\d/°.\s,-]+"
    r"|d\.?\s*m\.?\s*[\d/°.\s,-]+"
    # "art. N" o "art. N comma M" come suffisso puro
    r"|art(?:icolo|\.)\s*\d+[\s,a-z.°]*(?:comma\s*\d+)?"
    # "allegato N" / "Allegato VIII" puro
    r"|allegato\s+[ivxlcdm\d]+[\s,a-z.°]*"
    # "normativa vigente" generico
    r"|normativa(?:\s+vigente)?"
    r")\s*$",
    re.IGNORECASE,
)


def _strip_normative_suffix(text: str) -> str:
    """Rimuove ricorsivamente suffissi normativi tipici da un label DIAGRAM.

    Esempi:
      "valutaz. periodica DPI secondo la normativa" → "valutaz. periodica DPI"
      "obblighi DPI secondo D.Lgs. 81/08 Art. 225"  → "obblighi DPI"
      "uso DPI secondo l'art. 76"                    → "uso DPI"
      "implementare DPI secondo la legge"            → "implementare DPI"
      "Formazione"                                    → "Formazione"  (nop)
    """
    prev = text
    # Applica fino a fix-point (alcuni label hanno doppio suffisso)
    for _ in range(3):
        stripped = _LABEL_NORMATIVE_SUFFIX_RE.sub("", prev).rstrip(" ,.;:-")
        if stripped == prev or not stripped:
            break
        prev = stripped
    # Edge case: se la regex ha mangiato tutto, ritorna il testo originale
    # ripulito solo dai trailing punctuation (sicurezza > zelo)
    return prev if prev else text.rstrip(" ,.;:-")


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

    @field_validator("slots", mode="before")
    @classmethod
    def _coerce_strip_normative_suffix(cls, v: object) -> object:
        """FIX #31.6B (2026-05-27, analista review 7): strip deterministico
        suffissi normativi dai label PRIMA del check tolerance.

        In E2E #24: 14/19 DIAGRAM finivano in branded fallback per pattern
        ostinato LLM "label + secondo normativa/D.Lgs./art./Allegato". Lo
        strip a monte fa entrare il label nel max_chars senza dipendere
        dalla tolerance del check_slots."""
        if not isinstance(v, dict):
            return v
        return {
            slot_name: (_strip_normative_suffix(slot_text)
                        if isinstance(slot_text, str)
                        else slot_text)
            for slot_name, slot_text in v.items()
        }

    @model_validator(mode="after")
    def check_slots(self) -> "DiagramFilling":
        """FIX #31.7A (2026-05-27, post-analista review 8+9):
        validazione strutturale soltanto, ZERO mutazione dei valori.

        Storia:
        - #30.9f: introdusse raise sopra-tolerance 20% (poi smentito dai dati)
        - #31.7A (v1): rimuove raise + truncate gentile sotto tolerance
        - #31.7A (v2 — review 9): RIMUOVE anche il truncate gentile. L'analista
          ha verificato visivamente che il truncate gentile lasciava il "…" su
          slot SHORTER mentre lo shrink lasciava INTERI slot più lunghi nello
          stesso diagramma — incoerenza visiva ("Valutazione risch…" accanto
          a "Formazione e addestramento" intera, font 19pt). Cause: il truncate
          gentile mutava i valori PRIMA che _compute_uniform_font_size li
          leggesse → shrink calcolato sul valore lungo, "…" sopravvissuto sul
          valore corto.

        Regola di coordinamento (#31.7A v2): se servirà shrink, NON troncare.
        Il truncate scatta SOLO se anche al floor 16pt qualche slot eccede
        capacity reale (rarissimo) → fatto dentro _compute_uniform_font_size.
        Qui: zero mutazioni, solo gate strutturali.
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
        # FIX #31.7A v2: zero mutazioni. Tutti i valori passano intatti al
        # renderer che applica font-shrink uniforme. Il truncate (ultima
        # rete a 16pt) sta in _compute_uniform_font_size, NON qui — così
        # i due meccanismi sono coordinati e mai sovrapposti.
        return self


# FIX #31.7A constants
_MIN_FONT_PT = 16          # Sotto questa soglia il testo è troppo piccolo
_LAST_RESORT_SUFFIX = "…"  # Ellissi per truncate ultima rete a 16pt


def _compute_uniform_font_size(filling: "DiagramFilling") -> tuple[int, dict[str, str]]:
    """FIX #31.7A v2 (2026-05-27, analista review 9): font-shrink uniforme
    + truncate riservato ESCLUSIVAMENTE al floor 16pt.

    Principio di coordinamento (analista review 9 verbatim):
    > "quando un diagramma usa font ridotto, i label NON si troncano —
    > tutto il senso dello shrink è far entrare il testo intero. Il truncate
    > deve restare solo come ultima rete *al floor di 16pt*".

    Algoritmo:
    1. Per ogni slot oltre max_chars: calcola font_target = font_default *
       max_chars / actual_len che farebbe entrare il valore intero.
    2. uniform_font = max(_MIN_FONT_PT, min(font_target_min, font_default_max))
       cioè il font più piccolo che fa entrare TUTTO, clippato al floor.
    3. Truncate ultima rete: scatta SOLO se uniform_font == _MIN_FONT_PT
       (siamo al floor) E un valore sfora la capacity reale a quel font.
       Sopra il floor, mai truncate. Coordina con check_slots che NON tocca
       più i valori (#31.7A v2).

    Esempio della patologia review 9 (M1/idx15, flow_horizontal_4step):
       slots = ["Valutazione rischio" 19c, "Scelta DPI adeguati" 19c,
                "Formazione e addestramento" 26c, "Controllo e sorveglianza" 24c]
       max_chars = 18 per ogni slot, font_default = 28.
       font_target peggior slot (26c): 28*18/26 = 19pt.
       uniform_font = max(16, min(19, 28)) = 19pt.
       19pt > floor 16pt → NESSUN truncate.
       capacity a 19pt = int(18 * 28/19) = 26 char per slot.
       Tutti 4 slot ≤ 26 char → tutti interi. ✅

    Pre-fix patologia: check_slots truncava "Valutazione rischio" 19c → 17c
    perché sopra max_chars=18 sotto tolerance 21, e quel "…" sopravviveva
    nel render anche a 19pt dove sarebbe entrato intero.
    """
    tpl = DIAGRAM_CATALOG[filling.template_name]
    default_font_max = max((s.font_size_default for s in tpl.slots), default=28)

    # Step 1+2: font_target = font che fa entrare il peggior slot intero
    font_target_min = default_font_max
    for s in tpl.slots:
        v = filling.slots.get(s.name, "")
        if len(v) <= s.max_chars:
            continue  # questo slot non spinge il min
        # Approssimazione lineare: width box ≈ max_chars * font_default
        # → font_target = font_default * max_chars / actual_len
        font_target = int(s.font_size_default * s.max_chars / len(v))
        if font_target < font_target_min:
            font_target_min = font_target

    uniform_font = max(_MIN_FONT_PT, min(font_target_min, default_font_max))

    # Step 3: truncate ultima rete — SOLO al floor (coordinamento review 9).
    # Sopra il floor: capacity sufficiente per tutti i valori → mai truncate.
    final_slots: dict[str, str] = {}
    at_floor = uniform_font == _MIN_FONT_PT
    for s in tpl.slots:
        v = filling.slots.get(s.name, "")
        if at_floor:
            # Solo qui può scattare il truncate (rarissimo per testi reali)
            capacity = int(s.max_chars * s.font_size_default / uniform_font)
            if len(v) > capacity:
                v = v[: max(1, capacity - 1)].rstrip() + _LAST_RESORT_SUFFIX
        # Sopra il floor: valore INTATTO, lo shrink garantisce che entri
        final_slots[s.name] = v

    return uniform_font, final_slots


def render_diagram_to_svg(filling: DiagramFilling) -> str:
    """Sostituisce gli {{slot}} nel template SVG con i valori validati,
    applicando auto-shrink font uniforme per il diagramma (FIX #31.7A).

    Strategia (analista review 8):
    1. Calcola font_size uniforme per TUTTI gli slot del diagramma in
       modo che lo slot peggiore (più lungo vs max_chars) entri nel box.
    2. Sostituisce i `font-size="N"` letterali dei tag `<text>` del
       template col font uniforme calcolato (raw_svg replace).
    3. Sostituisce i placeholder `{{slot}}` coi valori finali (escapati,
       eventualmente troncati come ultima rete a 16pt).

    Il fallback brandizzato viene ora riservato esclusivamente a
    template_name invalido o template mancante su filesystem — mai più
    a label "troppo lungo".
    """
    tpl = DIAGRAM_CATALOG[filling.template_name]
    svg = tpl.template_path.read_text(encoding="utf-8")

    # FIX #31.7A: calcola font uniforme + valori finali (possibili truncate
    # ultima rete) per il diagramma
    uniform_font, final_slots = _compute_uniform_font_size(filling)

    # Sostituisci font-size="N" letterale per ogni slot del template.
    # I template hanno tutti font-size="<N>" con N uguale al
    # font_size_default dello slot (per costruzione del catalogo).
    # Replace mirato per default → uniform.
    distinct_default_fonts = {s.font_size_default for s in tpl.slots}
    for default_font in distinct_default_fonts:
        if default_font != uniform_font:
            svg = svg.replace(
                f'font-size="{default_font}"',
                f'font-size="{uniform_font}"',
            )

    # Sostituisci i placeholder {{slot}} coi valori finali escapati
    for s in tpl.slots:
        value = final_slots.get(s.name, "")
        # Escape XML basic
        value = (
            value.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .replace('"', "&quot;")
        )
        svg = svg.replace(f"{{{{{s.name}}}}}", value)

    logger.debug(
        "diagram_rendered",
        template=filling.template_name,
        uniform_font=uniform_font,
        default_font_max=max(
            (s.font_size_default for s in tpl.slots), default=28
        ),
        shrunk=uniform_font < max(
            (s.font_size_default for s in tpl.slots), default=28
        ),
    )
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
    "_compute_uniform_font_size",  # exported for #31.7A unit tests
    "get_catalog_prompt_description",
]
