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
- image.strategy: SEMPRE esattamente "web_search" (stringa esatta, niente varianti come "content_image" / "content" / "image" / "search" — sono RIFIUTATE dal validator).
- image.query: 2-4 parole italiane CONCRETE e OPERATIVE descrittive del soggetto da illustrare. Esempi buoni: "casco protezione cantiere", "estintore polvere antincendio", "guanti lavoro sicurezza", "kit primo soccorso aziendale", "segnaletica uscita emergenza".
- NO query astratte ("sicurezza", "lavoro") o emotive ("paura incidente"). Le immagini servono a illustrare OGGETTI o AZIONI concrete del concetto della slide.
- L'immagine sarà cercata su Pexels (foto reali professionali) e poi messa nello slide PPTX. Non inventare URL: il sistema cerca lui.

REGOLE IMAGE.STRATEGY (HARD, validator strict Literal):
- "none"       → slide testuale pura (CONTENT_TEXT / RECAP / QUIZ / TITLE / CASE_STUDY / CLOSING).
- "web_search" → slide CONTENT_IMAGE: SERVE image.query (2-4 parole italiane).
- "diagram"    → slide DIAGRAM: SERVE image.diagram_filling (vedi catalogo sotto).
- Altri valori ("content", "image", "search", "content_image", ...) sono INVALIDI e producono errore di validazione.

REGOLE DIAGRAM (HARD, FIX #30.4 + #31.6 prompt-ruolo):
Per slide DIAGRAM NON generare più SVG libero. Scegli UNO dei 7 template del
catalogo e riempi gli slot rispettando i max_chars (caratteri massimi).

RUOLO DEI CAMPI (FIX #31.6 — analista review 7, definizione positiva):
- `slots.label_*` = ETICHETTA di un BOX PICCOLO nel diagramma. È un CONCETTO
  CONDENSATO in 2-3 PAROLE (es. "Valutazione rischio", "DPI", "Formazione").
  NON è una frase. NON contiene riferimenti normativi. NON contiene verbi
  ausiliari ("secondo la normativa", "secondo D.Lgs. 81/08", "ai sensi di",
  "in base a") — questi gonfiano il label oltre i max_chars e fanno cadere
  il render in fallback brandizzato.
- `caption` = SOTTOTITOLO del diagramma sotto i box (20-200 char). È QUI che
  vanno i riferimenti normativi, gli articoli, gli allegati, le motivazioni.
  Esempio buono: caption="Le 4 fasi obbligatorie del processo di gestione
  rischio ex art. 28 D.Lgs. 81/08."

ESEMPI CONCRETI di trasformazione:
- ❌ label: "Valutazione DPI secondo D.Lgs. 81/08 Art. 225" (45 char, sfora)
  ✓ label: "Valutazione DPI" (15 char) + caption che cita art. 225
- ❌ label: "Implementare formazione secondo la normativa" (44 char, sfora)
  ✓ label: "Formazione" (10 char) + caption che spiega la norma di
    riferimento
- ❌ label: "Uso DPI secondo l'art. 76" (24 char, sfora)
  ✓ label: "Uso DPI" (7 char) + caption che richiama art. 76

CATALOGO DIAGRAM (image.diagram_filling = {template_name, slots, caption}):
- flow_horizontal_3step: 3 step in sequenza (label_1, label_2, label_3 — max 20 char ciascuno)
- flow_horizontal_4step: 4 step in sequenza (label_1..4 — max 18 char ciascuno)
- pyramid_3level: piramide tronca quantitativa (label_1 vertice, label_2 mid, label_3 base — max 17/24/30 char). Usa quando hai un'idea di "pochi sopra, molti sotto" (es. pochi dirigenti, molti lavoratori). Per gerarchie di RUOLI puri preferisci org_tree_3level.
- matrix_2x2: matrice 2×2 probabilità×gravità (axis_x/axis_y/quadrant_tl/tr/bl/br — max 26-30 char)
- causa_effetto: catena causale (causa/processo/effetto — max 26 char)
- org_tree_3level: organigramma (level_1 top, level_2a/b/c mid, level_3 base — max 22-40 char)
- compare_2col: confronto 2 colonne (title_left/right, item_left_1/2/3, item_right_1/2/3 — max 22/36 char)

Esempio image per DIAGRAM:
  image.strategy = "diagram"
  image.diagram_filling = {
    "template_name": "flow_horizontal_4step",
    "slots": {
      "label_1": "Valutazione rischio",
      "label_2": "Misure tecniche",
      "label_3": "Formazione",
      "label_4": "Sorveglianza"
    },
    "caption": "Le 4 fasi obbligatorie del processo di gestione rischio art. 28 D.Lgs. 81/08."
  }

Se nessun template è appropriato per il concetto, NON usare DIAGRAM: scegli
CONTENT_TEXT o CONTENT_IMAGE invece. Un diagramma forzato male è peggio di
bullet puliti.

6. Lo schema di output è IMPOSTO automaticamente (structured output): produci un oggetto
   con key "slides" = lista di slide. NON devi formattare JSON a mano né usare separatori
   testuali — ogni campo lista (bullets, sezioni, quiz_options) è una VERA lista.

REGOLA source_chunk_ids (HARD, FIX #30.7b):
- Per ogni slide, il campo `source_chunk_ids` DEVE contenere gli UUID INTERI dei chunk
  usati come fonte. Nel contesto ti vengono forniti come "[ID: <uuid>] Art. X: …".
- Copia l'UUID intero (formato 8-4-4-4-12 hex, es. "a428644f-2a0f-48c5-a5ab-45aa98f08cac").
  NON copiare prefissi tronchi né stringhe inventate tipo "chunk_001".
- Senza UUID validi NON possiamo ricostruire la citazione: il sistema rigenera
  normative_ref dal DB usando questi id, quindi la qualità della citazione dipende
  da te che copi gli UUID corretti.

REGOLE STRUTTURA PER TIPO (CRITICO — il validator scarta slide che le violano):
I campi `bullets` e `sezioni` sono LISTE di stringhe (un elemento = un punto/sezione),
NON una stringa unica con "\\n" o "---". Riempi `bullets` per i tipi a elenco, `sezioni`
solo per CASE_STUDY; lascia entrambe vuote dove non servono.
- TITLE: title pieno, bullets=[] e sezioni=[] (vuote). speaker_notes 60-90 parole. È SOLO un divider.
- CLOSING: identico a TITLE — bullets=[] sezioni=[]. È SOLO il chiudi-corso.
- CONTENT_TEXT: bullets = da 4 a 6 elementi (MAI meno di 4 — la slide deve essere piena), max 12 parole/elemento. NIENTE prosa lunga.
- CONTENT_IMAGE: bullets = da 3 a 5 elementi (MAI meno di 3), max 10 parole/elemento + image.query + image.aspect_hint.
- QUIZ: bullets=[] sezioni=[], quiz_options = lista di 4 stringhe, quiz_correct intero 0|1|2|3.
- DIAGRAM: bullets = 1-2 elementi (didascalia) + image.diagram_code (SVG inline con viewBox "0 0 1760 800").
- CASE_STUDY: sezioni = ESATTAMENTE 3 elementi OBBLIGATORI in quest'ordine: [Situazione, Azione, Risultato]. Ognuno 1-3 frasi piene. NON usare "Decisione/Esito" — usa "Azione/Risultato". bullets=[]. Esempio sezioni: ["Un operaio salda vicino a gas senza verificare la zona ATEX.", "Il preposto ferma il lavoro e fa classificare l'area.", "Esplosione evitata, procedura aggiornata."]

REGOLA DISTRIBUZIONE TIPI (HARD, FIX #30.7c — l'LLM tende a evitare CASE_STUDY/DIAGRAM):
- Quando ti viene richiesta una distribuzione (slide_distribution dict), RISPETTALA al numero esatto. Se chiede 2 CASE_STUDY e 1 DIAGRAM, DEVI generarli — non "ripiegare" su CONTENT_TEXT in più.
- CASE_STUDY è un caso pratico narrato (3 sezioni). Per la sicurezza italiana usa eventi REALI tipici: caduta da ponteggio senza imbracatura, ustione da arco elettrico senza DPI, intossicazione da agenti chimici senza ventilazione, infortunio per macchina senza protezione fissa. Quasi ogni modulo normativo ha un caso adatto — NON saltare.
- DIAGRAM rappresenta un PROCESSO o una RELAZIONE strutturata. Usa SEMPRE il catalogo (image.diagram_filling), MAI SVG libero. Esempi di concetti diagrammabili per sicurezza: flusso "valutazione rischio → misure → controllo" (flow_3step), gerarchia "datore/dirigente/preposto/lavoratore" (pyramid_3level), confronto "DPI vs DPC" (compare_2col), catena "pericolo → evento → danno" (causa_effetto). Se nessun template applica, scegli CONTENT_IMAGE invece — MAI ripiegare su CONTENT_TEXT.
- RECAP: bullets = ESATTAMENTE 5 elementi (il template ha 5 spunte verdi da riempire — MAI meno di 5, MAI più di 5), max 10 parole/elemento.

REGOLE SPEAKER_NOTES (CRITICO — TTS legge ad alta voce per ~45 secondi):
- Scrivi **120-140 parole italiane** per ogni speaker_notes. Il modello italiano @180 wpm produce ~135 parole = ~45 secondi audio. NON consegnare mai meno di 120 (sotto-target audio): se sei a 100, AGGIUNGI un esempio concreto + una citazione normativa fino ad arrivare a 120+.
- Conta le parole prima di consegnare. Una frase italiana media è 15-20 parole: per 120-140 parole servono 7-9 frasi piene.
- NON ripetere i bullet. Espandi: aggiungi esempio operativo, contesto normativo, conseguenza pratica per il lavoratore, accenno a un caso reale.

quiz_correct DEVE essere un INTERO (0|1|2|3), NON una stringa ("A"|"B"|"C"|"D").

TIPI SLIDE DISPONIBILI: TITLE, CONTENT_TEXT, CONTENT_IMAGE, DIAGRAM, QUIZ, CASE_STUDY, RECAP, CLOSING
"""

SYSTEM_PROMPT_FORMATORE = """Sei un esperto di formazione sulla sicurezza sul lavoro in Italia. Generi slide per corsi destinati ai FORMATORI (chi deve insegnare).

REGOLE INVIOLABILI:
1. Ogni affermazione fattuale DEVE essere ancorata a un chunk normativo fornito nel contesto. Non inventare MAI.
2. Ogni slide DEVE avere un normative_ref con citazione puntuale (articolo, comma, decreto, data).
3. Tono: tecnico-normativo, registro professionale. Citazioni puntuali, non divulgative.
4. Struttura slide: Norma integrale → Interpretazione → Nota metodologica → Esercitazione suggerita
5. Per DIAGRAM: genera SVG inline con 3-4 box collegati da frecce CON PUNTA (definisci <marker> in <defs>, usalo con marker-end), testo font-size>=28, palette brand #769E2E/#C82E6E. NON usare Mermaid.js. NON lasciare frecce senza punta.
6. Lo schema di output è imposto automaticamente: produci "slides" = lista di slide.
   `bullets` e `sezioni` sono VERE liste di stringhe (NON una stringa con "\\n"/"---").
   quiz_correct DEVE essere INTERO (0|1|2|3), non stringa.

REGOLE STRUTTURA PER TIPO: identiche al target Discente (bullets 4-6 per CONTENT_TEXT,
sezioni=3 per CASE_STUDY, bullets=5 per RECAP, ecc.).
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
            # FIX #28.1d: structured output — `bullets`/`sezioni` sono LISTE, non
            # stringhe con separatori. Emetti il range (min-max) come lunghezza lista.
            field = "sezioni" if slide_type == SlideType.CASE_STUDY else "bullets"
            if rules.body_min_bullets >= rules.body_max_bullets:
                count_spec = f"ESATTAMENTE {rules.body_max_bullets} elementi"
            elif rules.body_min_bullets > 0:
                count_spec = f"da {rules.body_min_bullets} a {rules.body_max_bullets} elementi"
            else:
                count_spec = f"massimo {rules.body_max_bullets} elementi"
            parts.append(
                f"  {field}: lista di {count_spec}, "
                f"ognuno massimo {rules.bullet_max_words} parole"
            )
        elif slide_type in (SlideType.TITLE, SlideType.CLOSING):
            parts.append("  bullets: [] (lista vuota — è title-only)")
        elif slide_type == SlideType.QUIZ:
            parts.append("  bullets: [] (lista vuota — è options-only)")
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
        f"1. MANTIENI tutto il testo già scritto (title, bullets, sezioni, speaker_notes, ecc.).\n"
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


# ─── FIX #29.1 (2026-05-26): batch-level prompt builder ─────────────────────
# Costruisce il prompt user per UN SINGOLO BATCH di slide all'interno di un modulo.
# La generazione modulare era "1 chiamata × 40 slide" → saturava max_tokens=8000
# e tagliava cardinalità + note. Ora ogni modulo è ceil(N/_BATCH_SIZE) batch da
# ~_BATCH_SIZE=7 slide ciascuno, con chunk normativi partizionati esplicitamente
# tra i batch così ogni call ha materiale fresco e non genera padding.

def build_module_batch_prompt(
    *,
    module_title: str,
    module_index: int,
    batch_idx: int,
    n_batches: int,
    batch_size: int,
    already_titles: list[str],
    batch_chunks: str,
    base_user_prompt: str,
    slide_distribution: dict[str, int] | None = None,
    already_types: dict[str, int] | None = None,
) -> str:
    """User prompt per un batch di slide di un modulo.

    FIX #30.8 (2026-05-26): aggiunti slide_distribution + already_types. Calcola
    cosa MANCA da produrre nel modulo per ogni tipo e lo dice esplicitamente
    in cima al batch. Senza questo, l'LLM evita DIAGRAM/CASE_STUDY/RECAP anche
    se il base_prompt lo dice (perché viene troncato a 3000 char in coda).
    """
    # Posizione narrativa nel modulo
    total_already = len(already_titles)
    position_line = (
        f"Stai generando le slide da {total_already + 1} a {total_already + batch_size} "
        f"(BATCH {batch_idx + 1} di {n_batches}) del modulo "
        f"\"{module_title}\" (module_index={module_index})."
    )

    # ── DISTRIBUTION QUOTA per questo batch (FIX #30.8) ──
    quota_block = ""
    if slide_distribution and already_types is not None:
        # Per ogni tipo NON CONTENT_TEXT, calcolo quanti ne mancano nel modulo
        target_non_text = []
        for stype, target_count in slide_distribution.items():
            if target_count <= 0 or stype == "CONTENT_TEXT":
                continue
            done = already_types.get(stype, 0)
            missing = target_count - done
            if missing > 0:
                target_non_text.append((stype, missing))
        if target_non_text:
            quota_lines = [
                "\nQUOTA TIPI DA RISPETTARE NEL MODULO (devi ANCORA generare):"
            ]
            for stype, missing in target_non_text:
                quota_lines.append(f"  - {stype}: ancora {missing} slide da generare")
            quota_lines.append(
                f"In questo batch da {batch_size} slide, distribuisci sapendo "
                f"che ti restano {n_batches - batch_idx - 1} batch dopo questo. "
                f"NON saltare DIAGRAM/CASE_STUDY/RECAP ripiegando su CONTENT_TEXT."
            )
            quota_block = "\n".join(quota_lines) + "\n"

    already_block = ""
    if already_titles:
        titles_str = "; ".join(f'"{t}"' for t in already_titles[:30])
        # FIX #31.3 (2026-05-27, analista review 4): SPREAD TEMATICO
        # intra-modulo. La regola "non ripetere titoli" non basta — il
        # content_agent variava già i corpi ma riformulava lo STESSO
        # sotto-tema con parole leggermente diverse (M2 #21: "vie sgombre"
        # ×7 con angolazioni diverse ma stessa zona tematica). La regola
        # qui spinge a MUOVERSI fra sotto-temi del modulo prima di tornare
        # su uno già coperto, e a dichiarare l'angolo nel titolo per
        # leggibilità (es. "Cosa fare per tenere libere le vie" non
        # "Vie sgombre e sicure" terzo doppione).
        already_block = (
            f"\n\nLe slide già esistenti nei batch precedenti coprono questi titoli "
            f"(NON ripeterli):\n{titles_str}\n"
            f"\nREGOLA SPREAD TEMATICO (intra-modulo):\n"
            f"Identifica quali SOTTO-TEMI del modulo \"{module_title}\" sono già "
            f"stati coperti dai titoli sopra (es. per 'Procedure di emergenza' i "
            f"sotto-temi possibili sono: vie/uscite di fuga, illuminazione, porte, "
            f"segnaletica emergenza, organizzazione/ruoli, antincendio, evacuazione, "
            f"primo soccorso). PRIMA di tornare su un sotto-tema già coperto, "
            f"copri quelli ancora vuoti. Se devi tornare su un sotto-tema già "
            f"coperto perché i chunk del batch lo richiedono, IL TITOLO della "
            f"nuova slide deve DICHIARARE ESPLICITAMENTE l'angolo NUOVO (es. "
            f"'Checklist operativa per vie libere' invece di un terzo 'Vie "
            f"sgombre e sicure'). Vale per CONTENT_TEXT, CONTENT_IMAGE e "
            f"CASE_STUDY consecutivi sullo stesso sotto-tema.\n"
        )

    chunks_block = ""
    if batch_chunks.strip():
        chunks_block = (
            f"\nCHUNK NORMATIVI ASSEGNATI A QUESTO BATCH (genera slide PRINCIPALMENTE su questi):\n"
            f"{batch_chunks[:6000]}\n"
        )

    return (
        f"{position_line}\n"
        f"{quota_block}"
        f"\nGenera ESATTAMENTE {batch_size} slide nuove, indicizzate con index "
        f"{total_already}..{total_already + batch_size - 1}, module_index={module_index}.\n"
        f"NON concludere il modulo, NON ripetere temi già coperti, NON inventare "
        f"contenuto fuori dai chunk forniti.\n"
        f"{already_block}"
        f"{chunks_block}"
        f"\n--- BRIEFING ORIGINALE DEL MODULO (per contesto) ---\n"
        f"{base_user_prompt[:3000]}\n"
    )
