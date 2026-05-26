"""Prompt engineering for the Content Agent (BLUEPRINT §05.6).

Two system prompts (Discente / Formatore) and two user-prompt builders
(per-module + previous-modules summary for narrative coherence).

Prompts are intentionally in Italian — they ARE the product contract with
the LLM, not internal code. Identifiers / docstrings / comments around them
stay in English (REI-7).
"""

from __future__ import annotations

from app.models.core import LAYOUT_CONSTRAINTS, SlideType, TargetType
from app.models.knowledge import StylePattern
from app.models.pipeline import ModuleSpec
from app.models.knowledge import NormativeChunk


SYSTEM_PROMPT_DISCENTE = """Sei un esperto di formazione sulla sicurezza sul lavoro in Italia. Generi slide per corsi normativi destinati ai DISCENTI (lavoratori che devono apprendere).

REGOLE INVIOLABILI:
1. Ogni affermazione fattuale DEVE essere ancorata a un chunk normativo fornito nel contesto. Non inventare MAI informazioni normative.
2. Ogni slide DEVE avere un normative_ref che cita l'articolo/comma di legge.
3. LINGUAGGIO: italiano formativo professionale, 2ª persona singolare ("tu") o plurale ("voi") per coinvolgere il discente. Frasi brevi e attive ("Indossa il casco" non "Il casco deve essere indossato"). Evita legalese: traduci "ai sensi del comma 3" in "secondo la legge". Usa esempi concreti dal contesto lavorativo reale italiano (cantiere, ufficio, magazzino, officina) — mai esempi astratti generici.
4. Struttura slide: Hook (scenario reale di 1 frase) → Concetto chiave → Norma (sintetizzata in italiano semplice) → Pratica operativa ("cosa devi fare in concreto")
5. Per DIAGRAM: genera SVG inline con 3-4 box collegati da frecce CON PUNTA (definisci <marker> in <defs>, usalo con marker-end), testo font-size>=28, palette brand #769E2E/#C82E6E. NON usare Mermaid.js. NON lasciare frecce senza punta. L'SVG sarà convertito in PNG lato server.

REGOLE QUIZ (slide_type=QUIZ):
- Domanda: 1 sola situazione specifica, contestualizzata (es. "In un cantiere edile, quale DPI proteggere la testa?"). NON domande vaghe ("Cos'è il primo soccorso?").
- 4 opzioni di risposta: TUTTE plausibili e tematicamente coerenti. NIENTE distrattori palesemente sbagliati ("Banana", "Auto"). Le 3 opzioni sbagliate devono essere errori COMUNI che un lavoratore potrebbe davvero fare.
- quiz_correct: INTERO 0|1|2|3 (NON stringa "A"/"B").
- speaker_notes: spiega PERCHÉ la risposta corretta è giusta + PERCHÉ ogni opzione sbagliata è sbagliata (formativo, non punitivo).

REGOLE IMMAGINI (slide_type=CONTENT_IMAGE):
- image.query: 2-4 parole italiane CONCRETE e OPERATIVE descrittive del soggetto da illustrare. Esempi buoni: "casco protezione cantiere", "estintore polvere antincendio", "guanti lavoro sicurezza", "kit primo soccorso aziendale", "segnaletica uscita emergenza".
- NO query astratte ("sicurezza", "lavoro") o emotive ("paura incidente"). Le immagini servono a illustrare OGGETTI o AZIONI concrete del concetto della slide.
- L'immagine sarà cercata su Pexels (foto reali professionali) e poi messa nello slide PPTX. Non inventare URL: il sistema cerca lui.

6. Rispondi ESCLUSIVAMENTE con un singolo oggetto JSON valido che ha UNA SOLA key "slides" contenente l'array delle slide. Nessun testo prima o dopo il JSON. Nessun altro field al top level.

REGOLE STRUTTURA PER TIPO (CRITICO — il validator scarta slide che le violano):
- TITLE: title pieno, body="" (STRINGA VUOTA, NON null, NON testo), speaker_notes 75-90 parole. È SOLO un divider. NON mettere bullets/elenchi nel body — body deve essere "".
- CLOSING: identico a TITLE — body="" (STRINGA VUOTA). È SOLO il chiudi-corso.
- CONTENT_TEXT: body con bullets separati da \\n. GENERA da 4 a 6 bullet (MAI meno di 4 — la slide deve essere piena), max 12 parole/bullet. NIENTE prosa lunga.
- CONTENT_IMAGE: body bullets separati da \\n. GENERA da 3 a 5 bullet (MAI meno di 3), max 10 parole/bullet + image.query + image.aspect_hint.
- QUIZ: body="" (STRINGA VUOTA), quiz_options array di 4 stringhe, quiz_correct intero 0|1|2|3.
- DIAGRAM: body 1-2 bullet didascalia + image.diagram_code (SVG inline con viewBox "0 0 1760 800").
- CASE_STUDY: body con ESATTAMENTE 3 sezioni separate dal separatore "---" (tre trattini). Le 3 sezioni sono OBBLIGATORIE e in quest'ordine: Situazione --- Azione --- Risultato. Ognuna 1-3 frasi piene (NON "Decisione/Esito" — usa "Azione/Risultato"). Esempio: "Situazione: un operaio salda vicino a gas senza verificare la zona ATEX. --- Azione: il preposto ferma il lavoro e fa classificare l'area. --- Risultato: esplosione evitata, procedura aggiornata."
- RECAP: body con ESATTAMENTE 5 bullet di riepilogo separati da \\n (il template ha 5 spunte verdi da riempire — MAI meno di 5, MAI più di 5), max 10 parole/bullet.

REGOLE SPEAKER_NOTES (CRITICO — TTS legge ad alta voce per 25-35 secondi):
- Da 60 a 90 parole italiane. Se ne hai meno di 60, AGGIUNGI un esempio concreto o una citazione normativa fino ad arrivare ad almeno 60. NON consegnare mai meno di 60.
- Conta le parole prima di consegnare. Una frase italiana media è 15-20 parole, quindi servono almeno 4-5 frasi piene.
- NON ripetere il body. Espandi: aggiungi esempio operativo, contesto normativo, conseguenza pratica per il lavoratore.

quiz_correct DEVE essere un INTERO (0|1|2|3), NON una stringa ("A"|"B"|"C"|"D").

FORMATO OUTPUT — Oggetto JSON con UNA SOLA key "slides" → array di SlideContent:
{
  "slides": [
    {"index": 0, "module_index": 0, "slide_type": "TITLE", "title": "Modulo 1 — Allertamento", "body": "", "speaker_notes": "75-90 parole...", "normative_ref": "Art. 45 D.Lgs 81/08", "source_chunk_ids": ["uuid"], "image": {"strategy": "none"}, "quiz_options": null, "quiz_correct": null},
    {"index": 1, "module_index": 0, "slide_type": "CONTENT_TEXT", "title": "Numeri di emergenza", "body": "Componi il 112 NUE\\nFornisci posizione esatta\\nDescrivi il tipo di incidente\\nResta in linea fino a istruzioni", "speaker_notes": "75-90 parole...", "normative_ref": "DM 388/2003 art.1", "source_chunk_ids": ["uuid"], "image": {"strategy": "none"}, "quiz_options": null, "quiz_correct": null}
  ]
}

TIPI SLIDE DISPONIBILI: TITLE, CONTENT_TEXT, CONTENT_IMAGE, DIAGRAM, QUIZ, CASE_STUDY, RECAP, CLOSING
"""

SYSTEM_PROMPT_FORMATORE = """Sei un esperto di formazione sulla sicurezza sul lavoro in Italia. Generi slide per corsi destinati ai FORMATORI (chi deve insegnare).

REGOLE INVIOLABILI:
1. Ogni affermazione fattuale DEVE essere ancorata a un chunk normativo fornito nel contesto. Non inventare MAI.
2. Ogni slide DEVE avere un normative_ref con citazione puntuale (articolo, comma, decreto, data).
3. Tono: tecnico-normativo, registro professionale. Citazioni puntuali, non divulgative.
4. Struttura slide: Norma integrale → Interpretazione → Nota metodologica → Esercitazione suggerita
5. Per DIAGRAM: genera SVG inline con 3-4 box collegati da frecce CON PUNTA (definisci <marker> in <defs>, usalo con marker-end), testo font-size>=28, palette brand #769E2E/#C82E6E. NON usare Mermaid.js. NON lasciare frecce senza punta.
6. Rispondi ESCLUSIVAMENTE con un singolo oggetto JSON valido che ha UNA SOLA key "slides" contenente l'array delle slide. Nessun testo prima o dopo. quiz_correct DEVE essere INTERO (0|1|2|3), non stringa.

FORMATO OUTPUT: identico al target Discente — oggetto JSON con UNA key "slides" → array di SlideContent.
"""


def build_content_system_prompt(target: TargetType) -> str:
    """Return the system prompt for the requested target audience (BP §05.6)."""
    if target == TargetType.DISCENTE:
        return SYSTEM_PROMPT_DISCENTE
    return SYSTEM_PROMPT_FORMATORE


def build_constraints_block(slide_distribution: dict[str, int]) -> str:
    """Costruisce il blocco CONSTRAINTS specifico per i SlideType presenti in
    questo modulo (FASE 2 vast-hopping-sketch).

    Per ogni SlideType in ``slide_distribution`` con count > 0, emette i 5 limiti
    HARD (title chars, body bullets, bullet words, notes min-max) presi da
    LAYOUT_CONSTRAINTS. L'LLM riceve i numeri esatti che il Pydantic validator
    applicherà → zero retry su violazione, zero slide perse.
    """
    lines = ["VINCOLI HARD PER TIPO SLIDE (rispetta ESATTAMENTE, non superare):"]
    for slide_type_str, count in slide_distribution.items():
        if count <= 0:
            continue
        try:
            slide_type = SlideType(slide_type_str)
        except ValueError:
            continue
        rules = LAYOUT_CONSTRAINTS.get(slide_type)
        if not rules:
            continue
        parts = [
            f"- {slide_type.value} (×{count}):",
            f"  title: max {rules.title_max_chars} caratteri",
        ]
        if rules.body_max_bullets > 0:
            # FIX #27.4: emetti ANCHE il minimo (slide piena). CASE_STUDY usa
            # '---' come separatore sezioni invece di \n.
            sep = "'---'" if slide_type == SlideType.CASE_STUDY else "\\n"
            unit = "sezioni" if slide_type == SlideType.CASE_STUDY else "bullet"
            if rules.body_min_bullets >= rules.body_max_bullets:
                count_spec = f"ESATTAMENTE {rules.body_max_bullets}"
            elif rules.body_min_bullets > 0:
                count_spec = f"da {rules.body_min_bullets} a {rules.body_max_bullets}"
            else:
                count_spec = f"massimo {rules.body_max_bullets}"
            parts.append(
                f"  body: {count_spec} {unit} (separati da {sep}), "
                f"ognuno massimo {rules.bullet_max_words} parole"
            )
        elif slide_type in (SlideType.TITLE, SlideType.CLOSING):
            parts.append("  body: STRINGA VUOTA (è title-only)")
        elif slide_type == SlideType.QUIZ:
            parts.append("  body: STRINGA VUOTA (è options-only)")
        parts.append(
            f"  speaker_notes: {rules.notes_min_words}-{rules.notes_max_words} "
            f"parole (per durata TTS 25-35s)"
        )
        if rules.requires_image:
            if slide_type == SlideType.DIAGRAM:
                parts.append(
                    '  image.diagram_code: SVG inline OBBLIGATORIO con '
                    'viewBox="0 0 1760 800" esatto. REGOLE: 3-4 box collegati da '
                    'frecce CON PUNTA (definisci <marker> in <defs> e usalo con '
                    'marker-end), testo font-size>=28 leggibile, palette brand '
                    '(#769E2E verde, #C82E6E rosa). NO <script>.\n'
                    "    Esempio canonico COMPLETO (copia la struttura, cambia i testi):\n"
                    '    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1760 800">'
                    '<defs><marker id="a" markerWidth="12" markerHeight="12" refX="9" '
                    'refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#C82E6E"/>'
                    "</marker></defs>"
                    '<rect x="60" y="320" width="380" height="170" rx="16" fill="#769E2E"/>'
                    '<text x="250" y="415" font-size="34" fill="#fff" text-anchor="middle" '
                    'font-weight="bold">Identificazione</text>'
                    '<line x1="450" y1="405" x2="650" y2="405" stroke="#C82E6E" '
                    'stroke-width="8" marker-end="url(#a)"/>'
                    '<rect x="690" y="320" width="380" height="170" rx="16" fill="#769E2E"/>'
                    '<text x="880" y="415" font-size="34" fill="#fff" text-anchor="middle" '
                    'font-weight="bold">Valutazione</text>'
                    '<line x1="1080" y1="405" x2="1280" y2="405" stroke="#C82E6E" '
                    'stroke-width="8" marker-end="url(#a)"/>'
                    '<rect x="1320" y="320" width="380" height="170" rx="16" fill="#769E2E"/>'
                    '<text x="1510" y="415" font-size="34" fill="#fff" text-anchor="middle" '
                    'font-weight="bold">Misure</text></svg>'
                )
            else:
                parts.append(
                    "  image.query: 2-4 parole italiane (es. 'casco protezione cantiere')"
                )
                parts.append(
                    '  image.aspect_hint: "landscape"|"portrait"|"square" OBBLIGATORIO'
                )
        if rules.requires_options:
            parts.append(
                "  quiz_options: ESATTAMENTE 4 stringhe, ognuna max 80 caratteri"
            )
            parts.append("  quiz_correct: INTERO (0|1|2|3), NON stringa")
        lines.append("\n".join(parts))
    lines.append(
        "REGOLA SPLIT: se un concetto richiede più capacità di quella ammessa, "
        "EMETTI 2 slide consecutive sullo stesso concetto invece di 1 sola. "
        "NON troncare, NON usare '…', NON comprimere."
    )
    return "\n".join(lines)


def build_module_prompt(
    module: ModuleSpec,
    chunks: list[NormativeChunk],
    style_patterns: list[StylePattern],
    previous_summary: str,
    target: TargetType,
) -> str:
    """Build the user prompt for one module (BP §05.6 + FASE 2 vast-hopping).

    The Formatore variant appends extra methodological instructions.
    The CONSTRAINTS_BLOCK è iniettato deterministicamente per ogni SlideType
    presente nel modulo (FASE 2 vast-hopping-sketch).
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

    constraints_text = build_constraints_block(module.slide_distribution)

    base_prompt = (
        f"MODULO {module.module_index}: {module.title}\n"
        f"Slide da generare: {module.slide_count} (distribuzione: {module.slide_distribution})\n\n"
        f"CHUNK NORMATIVI PERTINENTI:\n{chunks_text}---\n\n"
        f"{constraints_text}\n\n"
        f"{style_text}\n"
        f"MODULI PRECEDENTI (riassunto per coerenza narrativa):\n{previous_summary}\n\n"
        f"Genera {module.slide_count} slide come oggetto JSON con key 'slides'."
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


def build_complete_slide_prompt(
    slide: dict[str, object],
    chunk_context: str,
    errors: list[str],
    module_index: int,
) -> str:
    """Costruisce prompt per COMPLETARE una slide invalida senza riscriverla.

    Strategia (FIX #14 vast-hopping-sketch): l'LLM riceve la slide attuale,
    il chunk normativo originale, e gli errori specifici. Deve restituire la
    SLIDE COMPLETATA — mantiene tutto ciò che era già scritto, aggiunge solo
    quanto necessario per rispettare i constraint (es. estendere notes troppo
    corti, allungare body, aggiungere campi mancanti). NIENTE riscrittura,
    NIENTE troncamento.
    """
    errs_str = "\n  - ".join(errors) if errors else "completare i campi mancanti"
    slide_json = __import__("json").dumps(slide, ensure_ascii=False, indent=2)
    return (
        f"Hai scritto questa slide ma viola questi vincoli:\n  - {errs_str}\n\n"
        f"SLIDE ATTUALE (mantieni TUTTO ciò che hai già scritto):\n"
        f"```json\n{slide_json}\n```\n\n"
        f"CONTESTO NORMATIVO ORIGINALE (dal chunk RAG):\n"
        f"```\n{chunk_context[:1500]}\n```\n\n"
        f"ISTRUZIONI:\n"
        f"1. MANTIENI tutto il testo già scritto (title, body, speaker_notes, ecc.).\n"
        f"2. ESTENDI solo i campi che violano i constraint (es. se notes < min, "
        f"AGGIUNGI nuove frasi con esempio concreto o citazione normativa).\n"
        f"3. NON troncare, NON comprimere, NON cancellare contenuto.\n"
        f"4. module_index DEVE essere {module_index}.\n"
        f"5. Rispondi con UN OGGETTO JSON con UNA SOLA key 'slides' contenente "
        f"UN ARRAY di UNA sola slide (quella completata)."
    )


def build_extend_module_prompt(
    module_title: str,
    module_index: int,
    chunks_context: str,
    existing_slides: list[dict[str, object]],
    target_slides: int,
) -> str:
    """Costruisce prompt per ESTENDERE un modulo che ha prodotto poche slide.

    Strategia (FIX #14): invece di rigenerare l'intero modulo da zero (fix #7),
    l'LLM riceve le slide già prodotte + i chunks normativi e deve emettere
    SOLO le slide MANCANTI per arrivare a target_slides. Le slide esistenti
    NON vengono toccate.
    """
    n_existing = len(existing_slides)
    n_missing = max(0, target_slides - n_existing)
    existing_titles = "\n".join(f"  {i+1}. {s.get('title', '?')}" for i, s in enumerate(existing_slides))
    return (
        f"MODULO {module_index}: \"{module_title}\"\n\n"
        f"Hai già prodotto {n_existing} slide su {target_slides} obiettivo. "
        f"Mancano {n_missing} slide da aggiungere.\n\n"
        f"SLIDE GIÀ PRODOTTE (NON riscriverle, NON ripeterle):\n"
        f"{existing_titles}\n\n"
        f"CONTESTO NORMATIVO ORIGINALE (dal chunk RAG):\n"
        f"```\n{chunks_context[:3000]}\n```\n\n"
        f"ISTRUZIONI:\n"
        f"1. Genera SOLO le {n_missing} slide MANCANTI per arrivare a {target_slides} totali.\n"
        f"2. NON ripetere i titoli/concetti delle slide esistenti.\n"
        f"3. Copri aspetti normativi/operativi NON ancora trattati.\n"
        f"4. Index parte da {n_existing} e cresce contiguo.\n"
        f"5. module_index DEVE essere {module_index} su tutte.\n"
        f"6. Rispondi con UN OGGETTO JSON con key 'slides' contenente "
        f"l'ARRAY delle {n_missing} slide nuove."
    )


def build_split_correction_prompt(
    invalid_slide: dict[str, object], errors: list[str]
) -> str:
    """Costruisce il corrective prompt SPLIT (FASE 2 vast-hopping-sketch).

    Quando il Pydantic strict validator rigetta una slide, il content_agent
    invia QUESTO prompt per chiedere all'LLM di splittare il concetto in 2
    slide consecutive invece di troncare. È retry mirato (1 attempt max),
    non un fix generico.
    """
    errors_str = "\n  - ".join(errors) if errors else "violazione constraint"
    bad_slide_summary = (
        f"index: {invalid_slide.get('index')}, "
        f"slide_type: {invalid_slide.get('slide_type')}, "
        f"title: {str(invalid_slide.get('title', ''))[:60]!r}"
    )
    return (
        f"La slide {bad_slide_summary} viola i vincoli:\n  - {errors_str}\n\n"
        "ISTRUZIONI HARD:\n"
        "1. NON troncare il testo, NON usare '…', NON comprimere.\n"
        "2. Splitta il concetto in DUE slide consecutive che coprono lo stesso "
        "contenuto in modo distribuito.\n"
        "3. Riusa la stessa normative_ref e gli stessi source_chunk_ids su "
        "entrambe le slide nuove.\n"
        "4. Incrementa gli index delle slide successive di +1 (la slide rotta "
        "diventa 2 slide → tutte le successive scalano).\n"
        "5. Rispondi con UN OGGETTO JSON con key 'slides' contenente SOLO le "
        "2 nuove slide sostitutive (NON l'array completo del modulo)."
    )


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
