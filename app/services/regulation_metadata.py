"""Regulation metadata strutturale derivata da TOC pubblica.

SCOPE (analista sign-off 2026-05-30 + verifica Normattiva 2026-05-30):
  - Questo modulo contiene SOLO la Tabella 1 (mapping Articolo -> Titolo +
    mapping Allegato -> Titolo del D.Lgs 81/08) derivata da TOC PUBBLICA
    delle regulations.
  - NESSUNA Tabella 2 (course_type -> Titoli attesi). Quella va dedotta dallo
    scheletro validato dall'utente, mai hardcoded per-course.
  - Tabella 1 e' TOC, NON heuristic: i range degli articoli per Titolo del
    D.Lgs 81/08 sono pubblicati su Normattiva (testo coordinato vigente).
    Sono fatti immutabili finche' la legge resta.

ARCHITETTURA TARGET (D-166 chiusura via strada A, analista 2026-05-30):
  - Colonna `top_section` su `regulation_chunks` (migration 008), popolata
    a ingestion time dal parser oppure backfilled via UPSERT.
  - B3 diventa una clausola SQL pura: WHERE chunk.top_section !=
    dominante_per_regulation -> decay.
  - Questo modulo resta come **oracolo di backfill + helper di parser**
    runtime path B3 NON lo invoca: legge solo `chunk.top_section` dal DB.

LEZIONE METODOLOGICA (analista 2026-05-30):
  - Mai paste-from-memory per tabella TOC. La bozza iniziale che avevo
    scritto da memoria aveva ~50% di errore (Titoli I/II/III/VI/VII/VIII/XI/
    XII/XIII shift-ati a cascata per errore di base "Titolo I-bis" come
    Titolo separato — in realta' Titolo I-bis NON ESISTE nel D.Lgs 81/08;
    quello che chiamavamo informalmente "Titolo I-bis Prevenzione e
    protezione" e' Capo III di Titolo I, Art. 15-54).
  - Verifica contro TOC ufficiale Normattiva (testo coordinato vigente);
    Bosetti&Gatti come reference di copertura ma con un caso documentato
    di out-of-date (Allegato I-bis su patente a punti — D.L. 19/2024).

VERIFICATION DEBT residuo (post-compilazione):
  - Collegamento Allegati XLIX-LI a Titolo XI ATEX: Bosetti dice Titolo XI,
    Normattiva incerto. Compilato come Titolo XI per coerenza Bosetti +
    coerenza tematica (ATEX); sample-read post-backfill su staging
    convalidera' (chunks degli Allegati XLIX-LI esistono in DB? quali
    article? coerenti con ATEX?).
"""

from __future__ import annotations

import re


# --------------------------------------------------------------------------
# D.Lgs 81/08 — Tabella 1 (TOC pubblica, struttura immutabile)
# --------------------------------------------------------------------------
# Range Articolo -> Titolo. Verificati su Normattiva e Bosetti&Gatti.
# 13 Titoli totali, NESSUN Titolo I-bis separato.
#
# Articoli con suffissi (es. "Art. 286-bis", "Art. 14-bis"): trattati come
# appartenenti al Titolo del numero base, ECCETTO Titolo X-bis che e' un
# Titolo intero costituito SOLO da Art. 286-bis...286-septies. Vedi logica
# in _classify_dlgs_81_08().
#
# Articoli fuori range riconosciuto: top_section = "Sconosciuto".

# 12 Titoli con range numerico continuo (escludiamo Titolo X-bis che e'
# gestito separatamente per via dei suffissi).
DLGS_81_08_TITOLI_NUMERICI: dict[str, range] = {
    "Titolo I":         range(1, 62),       # Principi Comuni (Art. 1-61):
                                            # Capo I Disposizioni generali (1-4),
                                            # Capo II Sistema istituzionale (5-14),
                                            # Capo III Gestione prevenzione (15-54),
                                            # Capo IV Disposizioni penali (55-61).
    "Titolo II":        range(62, 69),      # Luoghi di lavoro (Art. 62-68)
    "Titolo III":       range(69, 88),      # Uso attrezzature e DPI (Art. 69-87)
    "Titolo IV":        range(88, 161),     # Cantieri temporanei o mobili (Art. 88-160)
    "Titolo V":         range(161, 167),    # Segnaletica (Art. 161-166)
    "Titolo VI":        range(167, 172),    # Movimentazione manuale carichi (Art. 167-171)
    "Titolo VII":       range(172, 180),    # Videoterminali (Art. 172-179)
    "Titolo VIII":      range(180, 221),    # Agenti fisici (Art. 180-220)
    "Titolo IX":        range(221, 266),    # Sostanze pericolose: chimici, cancerogeni,
                                            # amianto (Art. 221-265)
    "Titolo X":         range(266, 287),    # Agenti biologici (Art. 266-286)
    # Titolo X-bis: Art. 286-bis...286-septies (vedi logica suffisso sotto)
    "Titolo XI":        range(287, 298),    # Atmosfere esplosive ATEX (Art. 287-297)
    "Titolo XII":       range(298, 304),    # Disposizioni penali (Art. 298-303)
    "Titolo XIII":      range(304, 307),    # Norme transitorie e finali (Art. 304-306)
}

# Allegati del D.Lgs 81/08 -> Titolo di appartenenza.
# Verificato su TOC Bosetti + sample chunks DB (post-backfill staging la
# correttezza si vede al render).
# 51 Allegati totali nel testo coordinato 2026 (I a LI, con Allegato I-bis
# aggiunto da decreti correttivi successivi al testo 2008).
DLGS_81_08_ALLEGATI: dict[str, str] = {
    # Titolo I: sospensione attivita' imprenditoriale + sistema sanzionatorio
    "Allegato I":       "Titolo I",         # Gravi violazioni sospensione (Art. 14 c.1)
    "Allegato I-bis":   "Titolo I",         # Lavori particolari patente a punti (Art. 27 c.6)
    "Allegato II":      "Titolo I",         # Casi datore svolge direttamente RSPP (Art. 34)
    "Allegato III":     "Titolo I",         # Cartella sanitaria e di rischio (Capo III Sez. V)
    "Allegato 3A":      "Titolo I",         # Suddivisione Allegato III parte A
    "Allegato 3B":      "Titolo I",         # Suddivisione Allegato III parte B

    # Titolo II: requisiti luoghi di lavoro
    "Allegato IV":      "Titolo II",        # Requisiti dei luoghi di lavoro

    # Titolo III: uso attrezzature e DPI
    "Allegato V":       "Titolo III",       # Requisiti attrezzature di lavoro
    "Allegato VI":      "Titolo III",       # Disposizioni uso attrezzature
    "Allegato VII":     "Titolo III",       # Verifiche periodiche attrezzature
    "Allegato VIII":    "Titolo III",       # DPI - Protezioni particolari
    "Allegato IX":      "Titolo III",       # Valori tensioni nominali macchine

    # Titolo IV: cantieri temporanei o mobili
    "Allegato X":       "Titolo IV",        # Elenco lavori edili/ingegneria civile
    "Allegato XI":      "Titolo IV",        # Elenco lavori con rischi particolari
    "Allegato XII":     "Titolo IV",        # Contenuto notifica preliminare
    "Allegato XIII":    "Titolo IV",        # Prescrizioni logistica cantiere
    "Allegato XIV":     "Titolo IV",        # Contenuti corso coordinatori
    "Allegato XV":      "Titolo IV",        # Contenuti minimi PSC
    "Allegato XVI":     "Titolo IV",        # Fascicolo caratteristiche opera
    "Allegato XVII":    "Titolo IV",        # Idoneita' tecnico professionale
    "Allegato XVIII":   "Titolo IV",        # Viabilita' cantieri, ponteggi, trasporti
    "Allegato XIX":     "Titolo IV",        # Verifiche sicurezza ponteggi metallici
    "Allegato XX":      "Titolo IV",        # Costruzione scale portatili
    "Allegato XXI":     "Titolo IV",        # Accordo corsi formazione lavori in quota
    "Allegato XXII":    "Titolo IV",        # Contenuti minimi Pi.M.U.S.
    "Allegato XXIII":   "Titolo IV",        # Deroga ponti su ruote a torre

    # Titolo V: segnaletica
    "Allegato XXIV":    "Titolo V",         # Prescrizioni generali segnaletica
    "Allegato XXV":     "Titolo V",         # Prescrizioni cartelli segnaletici
    "Allegato XXVI":    "Titolo V",         # Prescrizioni segnaletica contenitori
    "Allegato XXVII":   "Titolo V",         # Prescrizioni segnaletica attrezzature antincendio
    "Allegato XXVIII":  "Titolo V",         # Prescrizioni ostacoli e punti pericolo
    "Allegato XXIX":    "Titolo V",         # Prescrizioni segnali luminosi
    "Allegato XXX":     "Titolo V",         # Prescrizioni segnali acustici
    "Allegato XXXI":    "Titolo V",         # Prescrizioni comunicazione verbale
    "Allegato XXXII":   "Titolo V",         # Prescrizioni segnali gestuali

    # Titolo VI: movimentazione manuale
    "Allegato XXXIII":  "Titolo VI",        # Movimentazione manuale carichi

    # Titolo VII: videoterminali
    "Allegato XXXIV":   "Titolo VII",       # Requisiti minimi videoterminali

    # Titolo VIII: agenti fisici (rumore, vibrazioni, CEM, ROA)
    "Allegato XXXV":    "Titolo VIII",      # Vibrazioni
    "Allegato XXXVI":   "Titolo VIII",      # Campi elettromagnetici (CEM)
    "Allegato XXXVII":  "Titolo VIII",      # Radiazioni ottiche artificiali (ROA)
    "Allegato XXXVIII": "Titolo VIII",      # Valori limite esposizione professionale agenti fisici
    "Allegato XXXIX":   "Titolo VIII",      # Valori limite biologici e sorveglianza

    # Titolo IX: sostanze pericolose (chimici, cancerogeni, amianto)
    "Allegato XL":      "Titolo IX",        # Divieti agenti chimici
    "Allegato XLI":     "Titolo IX",        # Atmosfera - Norme UNI
    # (Allegato XLII e' biologico - vedi sotto)
    "Allegato XLII":    "Titolo X",         # Specifiche misure contenimento biologico
    "Allegato XLIII":   "Titolo X",         # Valori limite esposizione biologica
    "Allegato XLIII-bis": "Titolo X",       # Integrazione valori limite biologici
    "Allegato XLIII-ter": "Titolo X",       # Ulteriore integrazione

    # Titolo X: agenti biologici (continua)
    "Allegato XLIV":    "Titolo X",         # Elenco attivita' con agenti biologici
    "Allegato XLV":     "Titolo X",         # Segnale rischio biologico
    "Allegato XLVI":    "Titolo X",         # Elenco agenti biologici classificati
    "Allegato XLVII":   "Titolo X",         # Specifiche misure contenimento biologico II
    "Allegato XLVIII":  "Titolo X",         # Specifiche processi industriali biologici

    # Titolo XI: atmosfere esplosive ATEX
    "Allegato XLIX":    "Titolo XI",        # Ripartizione aree atmosfere esplosive
    "Allegato L":       "Titolo XI",        # Specifiche atmosfere esplosive
    "Allegato LI":      "Titolo XI",        # Segnale avvertimento atmosfere esplosive
}

# Regulation slugs riconosciuti come "regolamenti singoli" (un solo top_section
# = il regulation_slug). Per questi B3 pool-dominante per regulation e' degenere
# (un solo Titolo per regulation = pool tutto same-Titolo = decay mai applicato).
SINGLE_SECTION_REGULATIONS: set[str] = {
    "reg_ce_852_2004",         # HACCP, regolamento UE singolo
    "reg_ce_1272_2008",        # CLP, regolamento UE singolo
    "dm_02_09_2021",           # DM antincendio gestione e livelli formativi
    "dm_03_09_2021",           # DM antincendio minicodice
    "dm_01_09_2021",           # DM antincendio controlli impianti
    "dlgs_193_2007",           # D.Lgs italiano attuazione Reg CE 852/2004 (#R14 da ingerire)
    "accordo_stato_regioni_2025",  # Accordo Stato-Regioni 17/04/2025
    "accordo_stato_regioni_2011",  # Accordo Stato-Regioni 21/12/2011 (degradato)
    "accordo_stato_regioni_2016",  # Accordo SR 7/07/2016 (in coda all'Allegato 25)
    "dm_388_2003",             # DM Primo Soccorso
}


# Regex per estrarre numero articolo da stringhe di parsing diverse.
_ARTICLE_NUM_RE = re.compile(r"\b(\d+)\b")
_ALLEGATO_RE = re.compile(r"^\s*allegato\b", re.IGNORECASE)
# Pattern Allegato esteso per coprire:
#   - Numeri romani con suffisso bis/ter/quater (Allegato I-bis, XLIII-ter)
#   - Numeri arabi con suffisso lettera singola (Allegato 3A, 3B)
#   - Numeri romani seguiti da lettera (Allegato III A -> normalizzato a 3A)
# La regex matcha il blocco grezzo successivo a "allegato"; la normalizzazione
# in _normalize_allegato_key gestisce le varianti.
_ALLEGATO_PARSE_RE = re.compile(
    r"^\s*allegato\s+([0-9IVXLCDM]+(?:\s*[-_]?\s*(?:bis|ter|quater|quinquies|sexies))?(?:\s*[A-Za-z])?)",
    re.IGNORECASE,
)
# Mapping numeri romani -> arabi per normalizzare "Allegato III A" -> "Allegato 3A".
_ROMAN_TO_ARABIC = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8,
    "IX": 9, "X": 10,
}
# Suffisso per Art. 286-bis...286-septies (Titolo X-bis).
_TITOLO_X_BIS_SUFFISSI = {"bis", "ter", "quater", "quinquies", "sexies", "septies"}
_ART_286_SUFFIX_RE = re.compile(
    r"art\.?\s*286\s*[-_]?\s*(bis|ter|quater|quinquies|sexies|septies)",
    re.IGNORECASE,
)


def _normalize_allegato_key(raw: str) -> str | None:
    """Normalizza una stringa allegato in chiave canonica della tabella.

    Esempi:
      "Allegato I" -> "Allegato I"
      "allegato I" -> "Allegato I"
      "ALLEGATO XV" -> "Allegato XV"
      "Allegato I-bis" -> "Allegato I-bis"
      "allegato I bis" -> "Allegato I-bis"
      "allegato 3A" -> "Allegato 3A"
      "Allegato III A" -> "Allegato 3A"   (romano III + spazio + lettera A normalizzato)
      "Allegato XLIII-ter" -> "Allegato XLIII-ter"
      "allegato\n   d" -> None (parsing noise)
    """
    m = _ALLEGATO_PARSE_RE.match(raw.strip())
    if m is None:
        return None
    captured = m.group(1).strip()

    # Caso 1: numero arabo + lettera (es. "3A", "3B")
    arabic_letter = re.fullmatch(r"(\d+)\s*([A-Za-z])", captured)
    if arabic_letter:
        num = arabic_letter.group(1)
        letter = arabic_letter.group(2).upper()
        return f"Allegato {num}{letter}"

    # Caso 2: numero romano + suffisso lettera singola (es. "III A" -> "3A")
    roman_letter = re.fullmatch(r"([IVXLCDM]+)\s+([A-Za-z])", captured)
    if roman_letter:
        roman = roman_letter.group(1).upper()
        letter = roman_letter.group(2).upper()
        arabic = _ROMAN_TO_ARABIC.get(roman)
        if arabic is not None:
            return f"Allegato {arabic}{letter}"
        # romano non riconosciuto: fallback alla forma romana
        return f"Allegato {roman}{letter}"

    # Caso 3: composto base-suffisso (es. "I-bis", "XLIII-ter", "I bis")
    parts = re.split(r"[-_\s]+", captured)
    if len(parts) >= 2:
        base = parts[0].upper()
        suffix_lc = parts[1].lower()
        return f"Allegato {base}-{suffix_lc}"

    # Caso 4: solo numero (arabo o romano)
    base = parts[0]
    if base.isdigit():
        return f"Allegato {base}"
    # Numero romano: upper
    return f"Allegato {base.upper()}"


def _classify_dlgs_81_08(article: str | None) -> str:
    """Classifica un chunk D.Lgs 81/08 nel suo Titolo (incluso X-bis e Allegati).

    Logica:
      1. Se article matcha "Art. 286-{bis,ter,...,septies}" -> Titolo X-bis.
      2. Se article matcha "Allegato {X}" -> lookup DLGS_81_08_ALLEGATI.
      3. Altrimenti estrae numero da "Art. X" e cerca nei range
         DLGS_81_08_TITOLI_NUMERICI.
      4. Edge case (article null, parsing noise, fuori range): "Sconosciuto".
    """
    if article is None:
        return "Sconosciuto"

    txt = article.strip()

    # 1. Art. 286-bis...286-septies -> Titolo X-bis
    if _ART_286_SUFFIX_RE.search(txt):
        return "Titolo X-bis"

    # 2. Allegato
    if _ALLEGATO_RE.match(txt):
        key = _normalize_allegato_key(txt)
        if key and key in DLGS_81_08_ALLEGATI:
            return DLGS_81_08_ALLEGATI[key]
        return "Sconosciuto"

    # 3. Art. NNN -> range lookup
    m = _ARTICLE_NUM_RE.search(txt)
    if m is None:
        return "Sconosciuto"
    try:
        art_num = int(m.group(1))
    except (ValueError, TypeError):
        return "Sconosciuto"

    # Caso speciale: numero 286 senza suffisso e' ancora Titolo X (Art. 286
    # base). Con suffisso era gia' gestito sopra al punto 1.
    for titolo_name, art_range in DLGS_81_08_TITOLI_NUMERICI.items():
        if art_num in art_range:
            return titolo_name

    return "Sconosciuto"


def top_section_of(regulation_slug: str, article: str | None) -> str:
    """Ritorna il top_section di un chunk dato regulation_slug + article.

    Per ``dlgs_81_08``: classifica nel Titolo I-XIII (+ Titolo X-bis +
    "Allegato" lookup). Vedi ``_classify_dlgs_81_08`` per logica completa.

    Per regulation_slug in ``SINGLE_SECTION_REGULATIONS``: ritorna lo slug
    stesso (regolamento singolo, no cross-section interno).

    Per regulation_slug sconosciuti: degrada gracefully a single section
    (ritorna lo slug).

    Esempi:
      top_section_of("dlgs_81_08", "Art. 40") -> "Titolo I"
      top_section_of("dlgs_81_08", "Art. 88") -> "Titolo IV"
      top_section_of("dlgs_81_08", "Art. 286-bis") -> "Titolo X-bis"
      top_section_of("dlgs_81_08", "Allegato XV") -> "Titolo IV"
      top_section_of("dlgs_81_08", "Allegato XLI") -> "Titolo IX"
      top_section_of("dm_02_09_2021", "Art. 1") -> "dm_02_09_2021"
      top_section_of("reg_ce_852_2004", "Art. 5") -> "reg_ce_852_2004"
    """
    if regulation_slug == "dlgs_81_08":
        return _classify_dlgs_81_08(article)

    if regulation_slug in SINGLE_SECTION_REGULATIONS:
        return regulation_slug

    # Regulation sconosciuta: degrade graceful.
    return regulation_slug
