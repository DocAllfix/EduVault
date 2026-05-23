"""Prompt engineering for the Content Agent (BLUEPRINT §05.6).

Two system prompts (Discente / Formatore) and two user-prompt builders
(per-module + previous-modules summary for narrative coherence).

Prompts are intentionally in Italian — they ARE the product contract with
the LLM, not internal code. Identifiers / docstrings / comments around them
stay in English (REI-7).
"""

from __future__ import annotations

from app.models.core import TargetType
from app.models.knowledge import StylePattern
from app.models.pipeline import ModuleSpec
from app.models.knowledge import NormativeChunk


SYSTEM_PROMPT_DISCENTE = """Sei un esperto di formazione sulla sicurezza sul lavoro in Italia. Generi slide per corsi normativi destinati ai DISCENTI (lavoratori che devono apprendere).

REGOLE INVIOLABILI:
1. Ogni affermazione fattuale DEVE essere ancorata a un chunk normativo fornito nel contesto. Non inventare MAI informazioni normative.
2. Ogni slide DEVE avere un normative_ref che cita l'articolo/comma di legge.
3. Tono: accessibile, diretto, con esempi concreti dalla vita lavorativa. Traduci il legalese in linguaggio quotidiano.
4. Struttura slide: Hook (scenario reale) → Concetto → Norma (sintetizzata) → Pratica ("cosa devi fare")
5. Per DIAGRAM: genera SVG inline semplice (rettangoli + frecce + testo). NON usare Mermaid.js. L'SVG sarà convertito in PNG lato server.
6. Rispondi ESCLUSIVAMENTE con un array JSON valido. Nessun testo prima o dopo il JSON.

FORMATO OUTPUT — Array JSON di oggetti SlideContent:
[
  {
    "index": 0,
    "module_index": 0,
    "slide_type": "CONTENT_TEXT",
    "title": "Titolo slide (max 80 caratteri)",
    "body": "Testo corpo slide (max 90 parole per CONTENT_TEXT)",
    "speaker_notes": "Note per il relatore",
    "normative_ref": "Art. 37, comma 1, D.Lgs 81/08",
    "source_chunk_ids": ["uuid-del-chunk-usato"],
    "image": {"strategy": "none"},
    "quiz_options": null,
    "quiz_correct": null
  }
]

TIPI SLIDE DISPONIBILI: TITLE, CONTENT_TEXT, CONTENT_IMAGE, DIAGRAM, QUIZ, CASE_STUDY, RECAP, CLOSING
LIMITI PAROLE: CONTENT_TEXT=90, CONTENT_IMAGE=60, QUIZ=60, CASE_STUDY=100, DIAGRAM=50, RECAP=70
"""

SYSTEM_PROMPT_FORMATORE = """Sei un esperto di formazione sulla sicurezza sul lavoro in Italia. Generi slide per corsi destinati ai FORMATORI (chi deve insegnare).

REGOLE INVIOLABILI:
1. Ogni affermazione fattuale DEVE essere ancorata a un chunk normativo fornito nel contesto. Non inventare MAI.
2. Ogni slide DEVE avere un normative_ref con citazione puntuale (articolo, comma, decreto, data).
3. Tono: tecnico-normativo, registro professionale. Citazioni puntuali, non divulgative.
4. Struttura slide: Norma integrale → Interpretazione → Nota metodologica → Esercitazione suggerita
5. Per DIAGRAM: genera SVG inline semplice (rettangoli + frecce + testo). NON usare Mermaid.js.
6. Rispondi ESCLUSIVAMENTE con un array JSON valido. Nessun testo prima o dopo il JSON.

FORMATO OUTPUT: identico al target Discente (stesso schema JSON SlideContent).
"""


def build_content_system_prompt(target: TargetType) -> str:
    """Return the system prompt for the requested target audience (BP §05.6)."""
    if target == TargetType.DISCENTE:
        return SYSTEM_PROMPT_DISCENTE
    return SYSTEM_PROMPT_FORMATORE


def build_module_prompt(
    module: ModuleSpec,
    chunks: list[NormativeChunk],
    style_patterns: list[StylePattern],
    previous_summary: str,
    target: TargetType,
) -> str:
    """Build the user prompt for one module (BP §05.6).

    The Formatore variant appends extra methodological instructions.
    """
    chunks_text = ""
    for i, chunk in enumerate(chunks):
        chunks_text += (
            f"---\n[Chunk {i + 1}] {chunk.hierarchy_path}:\n"
            f'"{chunk.body}"\n'
            f"ID: {chunk.chunk_id} | Tipo: {chunk.chunk_type} | Tags: {chunk.tags}\n"
        )

    style_text = ""
    if style_patterns:
        sp = style_patterns[0]  # most recent pattern
        style_text = (
            f"PATTERN STILISTICI (metadati dai corsi approvati — NON usare come fonte normativa):\n"
            f"- Tono: {sp.tone_register}\n"
            f"- Media parole per slide: {sp.avg_words_per_slide}\n"
            f"- Sequenza slide tipica: {sp.preferred_slide_sequence}\n"
            f"- Sezioni ricorrenti: {sp.recurring_section_titles}\n"
        )

    base_prompt = (
        f"MODULO {module.module_index}: {module.title}\n"
        f"Slide da generare: {module.slide_count} (distribuzione: {module.slide_distribution})\n\n"
        f"CHUNK NORMATIVI PERTINENTI:\n{chunks_text}---\n\n"
        f"{style_text}\n"
        f"MODULI PRECEDENTI (riassunto per coerenza narrativa):\n{previous_summary}\n\n"
        f"Genera {module.slide_count} slide come array JSON."
    )

    if target == TargetType.FORMATORE:
        base_prompt += """

ISTRUZIONI AGGIUNTIVE PER FORMATORE:
- Ogni modulo deve includere almeno 1 slide CASE_STUDY con esercitazione suggerita
- speaker_notes devono contenere note metodologiche (come presentare il concetto, tempi suggeriti, domande da porre all'aula)
- Le citazioni normative devono essere complete (articolo + comma + decreto + data di emanazione)
- Includi varianti regionali dove pertinenti
"""

    return base_prompt


def build_previous_summary(completed_modules: list[dict[str, object]]) -> str:
    """Build a recap of completed modules for narrative coherence (BP §05.6).

    Includes the first 5 slide titles per module so the LLM knows WHICH
    topics have been covered and can avoid cross-module repetition.
    """
    if not completed_modules:
        return "Nessun modulo precedente."
    lines: list[str] = []
    for m in completed_modules:
        slides_raw = m.get("slides", [])
        assert isinstance(slides_raw, list)
        slide_titles = [str(s.get("title", "")) for s in slides_raw[:5] if isinstance(s, dict)]
        titles_str = ", ".join(t for t in slide_titles if t)
        lines.append(
            f"- Modulo {m['module_index']}: \"{m['title']}\" — "
            f"Argomenti trattati: {titles_str}"
        )
    return "\n".join(lines)
