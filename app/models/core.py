"""Core enums + slide constraints shared across the project (BLUEPRINT §04.1).

FASE 1 vast-hopping-sketch: LAYOUT_CONSTRAINTS dict mapping SlideType → numeric limits
(title chars, body bullets/words, notes words, image/options requirements). I limiti
sono derivati matematicamente da:
  - tipografia template nexus_master.pptx (1920×1080, Inter 20pt body, 32pt h2, 60pt h1)
  - regola commerciale GAP-1 v2.0: 1 slide ogni 30 secondi (PacingEngine.SECONDS_PER_SLIDE)
  - velocità narrazione TTS italiano formale: 180 wpm → 75-90 parole per 25-35s
Sono CONTRATTI con l'LLM (iniettati nel prompt FASE 2) E con il rendering (controllati
dal Pydantic model_validator in app/models/pipeline.py).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class TargetType(str, Enum):
    DISCENTE = "discente"
    FORMATORE = "formatore"


class SlideDensity(str, Enum):
    LEGGERA = "leggera"
    STANDARD = "standard"
    INTENSIVA = "intensiva"


class SlideType(str, Enum):
    TITLE = "TITLE"
    # FIX #30.2 (2026-05-26): bookends modulo dedicati. MODULE_OPEN apre
    # ciascuno degli N moduli con "MODULO X — Titolo" grande; MODULE_CLOSE
    # chiude con riepilogo 5 spunte ✓. Forzati come slot fissi dal pacing
    # engine (+2 slide sopra il count contenuto, non dentro).
    MODULE_OPEN = "MODULE_OPEN"
    CONTENT_TEXT = "CONTENT_TEXT"
    CONTENT_IMAGE = "CONTENT_IMAGE"
    DIAGRAM = "DIAGRAM"
    QUIZ = "QUIZ"
    CASE_STUDY = "CASE_STUDY"
    MODULE_CLOSE = "MODULE_CLOSE"
    RECAP = "RECAP"
    CLOSING = "CLOSING"


class ChunkType(str, Enum):
    OBBLIGO = "OBBLIGO"
    SANZIONE = "SANZIONE"
    DEFINIZIONE = "DEFINIZIONE"
    PROCEDURA = "PROCEDURA"
    GENERALE = "GENERALE"


# ─────────────────────────────────────────────────────────────────────
# FASE 1 vast-hopping-sketch — Slide layout constraints
# ─────────────────────────────────────────────────────────────────────


class SlideConstraints(BaseModel):
    """Vincoli numerici per un singolo SlideType (immutabile).

    Best-practice pedagogiche e-learning (Mayer's Multimedia Learning, Tufte,
    Reynolds): "1 slide = 1 idea, 7±2 bullet di 7±2 parole". Derivati da:
      - title_max_chars: 1 riga a 32pt font Inter, larghezza placeholder template
      - body_max_bullets: righe che entrano nel placeholder + leggibilità cognitiva
      - bullet_max_words: regola 7±2 parole per bullet (memoria a breve termine)
      - notes_min/max_words: 75-90 parole = 25-35s TTS a 180 wpm italiano formale
        (regola commerciale 30s/slide PacingEngine §06B + tolleranza)
      - requires_image: True per CONTENT_IMAGE/DIAGRAM
      - requires_options: True per QUIZ (4 opzioni + quiz_correct int 0-3)
    """

    model_config = {"frozen": True}

    title_max_chars: int
    body_max_bullets: int
    bullet_max_words: int
    # FIX #27.3 (2026-05-26): MINIMO bullet obbligatorio. Senza, l'LLM legge i
    # constraints come soli tetti e genera 2-3 bullet lasciando le slide vuote.
    # Il validator rigetta < min → SPLIT-retry del content_agent ri-genera con
    # più contenuto. RECAP=5 (=max) forza ESATTAMENTE 5 punti per i 5 checkmark
    # del template; CASE_STUDY=3 (=max) forza le 3 sezioni piene.
    body_min_bullets: int = 0
    # Range rilassato 30-120 parole (2026-05-25 vast-hopping-sketch fix #6):
    # - Topic tecnici stretti (lista farmaci, valori numerici, codici) producono
    #   naturalmente 30-50 parole anche dopo SPLIT retry
    # - 30 parole @ 150 wpm = ~12s audio (sufficiente per concetto stretto)
    # - 120 parole @ 150 wpm = ~48s audio (OK con UI player skip)
    # - off_target flag in DB resta per tracce fuori 25-35s (informativo)
    # - Pre-fix #6: 106 slide rigettate ANCHE dopo SPLIT retry, 11/15 moduli
    #   producevano 2-13 slide invece di 40 (distribuzione bimodale)
    notes_min_words: int = 30
    notes_max_words: int = 120
    requires_image: bool = False
    requires_options: bool = False


# Mapping SlideType → SlideConstraints. Modificare questi numeri = modificare il
# contratto con l'LLM (CONSTRAINTS_BLOCK FASE 2) E con il rendering. Una sola fonte.
LAYOUT_CONSTRAINTS: dict[SlideType, SlideConstraints] = {
    SlideType.TITLE: SlideConstraints(
        title_max_chars=70,
        body_max_bullets=0,  # TITLE non ha body
        bullet_max_words=0,
        notes_min_words=20,  # title slide più breve in voce
        notes_max_words=90,
    ),
    SlideType.CONTENT_TEXT: SlideConstraints(
        title_max_chars=70,
        body_min_bullets=4,  # FIX #27.3: slide piena, mai 2-3 bullet sparsi
        body_max_bullets=6,
        bullet_max_words=12,  # best-practice 7±2 + tolleranza
        # FIX #29.2 (2026-05-26): audio 45s/slide @ 180 wpm = ~135 parole target.
        # Floor 90 di sicurezza (era 60 → audio 20s, sotto target). Validator
        # downgraded a soft warning (FIX #29.2 in pipeline.py) — il gate hard è
        # mutagen.MP3.info.length nel range 35-55s post-generazione.
        notes_min_words=90,
        notes_max_words=160,
    ),
    SlideType.CONTENT_IMAGE: SlideConstraints(
        title_max_chars=70,
        body_min_bullets=3,
        body_max_bullets=5,  # body ridotto: 40% slide occupato da immagine
        bullet_max_words=10,
        notes_min_words=90,  # FIX #29.2
        notes_max_words=160,
        requires_image=True,
    ),
    SlideType.DIAGRAM: SlideConstraints(
        title_max_chars=70,
        body_min_bullets=1,  # FIX #27.3: almeno una riga di didascalia
        body_max_bullets=2,  # didascalia 2 righe sotto il diagramma
        bullet_max_words=20,
        requires_image=True,  # diagram_code SVG obbligatorio
    ),
    SlideType.QUIZ: SlideConstraints(
        title_max_chars=120,  # domanda quiz, più lunga
        body_max_bullets=0,  # body non usato (le 4 opzioni vivono in quiz_options)
        bullet_max_words=0,
        notes_min_words=25,  # spiegazione risposta corretta + perché altre sbagliate
        notes_max_words=120,
        requires_options=True,
    ),
    SlideType.CASE_STUDY: SlideConstraints(
        title_max_chars=70,
        body_min_bullets=3,  # FIX #27.3: tutte e 3 le sezioni OBBLIGATORIE
        body_max_bullets=3,
        bullet_max_words=50,
        notes_min_words=90,  # FIX #29.2: audio 45s
        notes_max_words=160,
    ),
    SlideType.RECAP: SlideConstraints(
        title_max_chars=70,
        body_min_bullets=5,
        body_max_bullets=5,
        bullet_max_words=10,
        notes_min_words=90,  # FIX #29.2
        notes_max_words=160,
    ),
    SlideType.CLOSING: SlideConstraints(
        title_max_chars=70,
        body_max_bullets=0,  # solo "Grazie" + logo
        bullet_max_words=0,
        notes_min_words=15,  # commiato breve
        notes_max_words=90,
    ),
    # FIX #30.2 (2026-05-26): bookends modulo. Slot fissi generati dal
    # pacing_engine + content_agent, NON dal validator instructor per-modulo.
    # MODULE_OPEN ha 0 bullet (solo "MODULO N" + titolo modulo);
    # MODULE_CLOSE ha 5 ✓ (riepilogo concetti chiave modulo).
    SlideType.MODULE_OPEN: SlideConstraints(
        title_max_chars=80,
        body_max_bullets=0,
        bullet_max_words=0,
        notes_min_words=30,
        notes_max_words=80,  # voiceover breve "Iniziamo il modulo X..."
    ),
    SlideType.MODULE_CLOSE: SlideConstraints(
        title_max_chars=80,
        body_min_bullets=5,
        body_max_bullets=5,  # ESATTAMENTE 5 concetti chiave
        bullet_max_words=10,
        notes_min_words=60,
        notes_max_words=120,
    ),
}


# Convenzione di validazione: usato dai model_validator in pipeline.py + dai prompts.
# Il box DIAGRAM nel template nexus_master.pptx è 1760×800 (vedi FASE 0 inspection JSON).
# L'LLM DEVE emettere SVG con questo viewBox esatto per fit 1:1 in cairosvg.
DIAGRAM_VIEWBOX_LITERAL: str = 'viewBox="0 0 1760 800"'
