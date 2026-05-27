"""Research Agent (BLUEPRINT §05.4).

PHASE 3.3 — first node of the LangGraph pipeline. Takes the course request,
runs the RAG pipeline (resolve slugs → semantic query → vector search →
relevance filter), builds the pacing plan, distributes the retrieved chunks
to modules via keyword overlap, and returns the merged context.

Skill alignment:
- langgraph-fundamentals "node signatures": ``async def(state) -> dict``
  returning ONLY the fields the node writes (course_context, pacing_plan).
- langgraph-fundamentals "fix-state-must-return-dict": never mutate state.
- langchain-rag "filtri ibridi": vector search + scalar regional filter
  delegated to KnowledgeRepository.search_chunks (already implemented in 2.5).
- Embedding consistency (langchain-rag "fix-consistent-embeddings"):
  voyage-3 / 1024-dim everywhere (index + query).

Architectural notes:
- ``get_pool()`` comes from services.dependencies (BP §02.4) — never global.
- Distribution uses keyword overlap (NOT cosine on chunk embeddings) — zero
  API cost, deterministic, sufficient for Italian normative module titles
  (BP §05.4 explicit choice).
"""

from __future__ import annotations

import re

import structlog

from app.agents.pipeline import NexusPipelineState
from app.models.knowledge import NormativeChunk
from app.models.pipeline import CourseContext, PacingPlan
from app.models.requests import CourseRequest
from app.services.dependencies import get_pool
from app.services.ingestion_service import voyage_embed_with_retry
from app.services.knowledge_repo import KnowledgeRepository
from app.services.pacing_engine import PacingEngine
from config.catalog_config import COURSE_CATALOG

logger = structlog.get_logger()

MIN_RELEVANCE = 0.3


# ─────────────────────────────────────────────────────────────────────
# Chunk distribution helpers (BP §05.4)
# ─────────────────────────────────────────────────────────────────────


def _keyword_overlap(title: str, body: str) -> int:
    """Count keywords shared between a module title and a chunk body.

    For structured Italian normative text this is sufficient: 'DPI' appears
    in chunks about DPI, 'antincendio' in firefighting chunks, etc.
    Zero API cost — no embeddings (BP §05.4).
    """
    title_words = set(title.lower().split())
    body_words = set(body.lower().split())
    return len(title_words & body_words)


def _rebalance_min(
    result: dict[int, list[NormativeChunk]],
    min_per_module: int = 3,
) -> None:
    """Guarantee at least ``min_per_module`` chunks per module.

    Redistribute from over-populated modules to under-populated ones (BP §05.4).
    """
    while True:
        under = [k for k, v in result.items() if len(v) < min_per_module]
        over = [k for k, v in result.items() if len(v) > min_per_module + 2]
        if not under or not over:
            break
        donor = max(over, key=lambda k: len(result[k]))
        receiver = min(under, key=lambda k: len(result[k]))
        result[receiver].append(result[donor].pop())


def _rebalance_max(
    result: dict[int, list[NormativeChunk]],
    max_per_module: int,
) -> None:
    """Redistribute excess chunks from over-populated modules (BP §05.4).

    Prevents keyword-overlap degeneration when generic titles
    (e.g. 'Concetti di rischio') attract ALL chunks because the word
    'rischio' is ubiquitous in safety regulations.
    """
    while True:
        over = [k for k, v in result.items() if len(v) > max_per_module]
        under = [k for k, v in result.items() if len(v) < max_per_module]
        if not over or not under:
            break
        donor = max(over, key=lambda k: len(result[k]))
        receiver = min(under, key=lambda k: len(result[k]))
        result[receiver].append(result[donor].pop())


# ─────────────────────────────────────────────────────────────────────
# FIX #30.9d-rev2 (2026-05-26, analista Q3): rebalance margin-aware.
# Il margin del cosine cluster identifica chunks "spostabili" (margin
# basso = trasversali, decisione fragile) vs "pinned" (margin alto =
# specifici, decisione netta). Il rebalance vecchio sposta a caso
# (ignora il tema). Quello nuovo sposta SOLO chunks a margin basso,
# preservando l'allineamento tematico.
#
# Implementazione: il caller cluster_cosine costruisce un dict
# `chunk_margins: {chunk_id: margin_float}` durante l'assegnazione.
# Le funzioni rebalance lo ricevono e ordinano i donor candidates per
# margin ascendente (i più spostabili prima).
# ─────────────────────────────────────────────────────────────────────

# Soglia: chunks con margin >= MARGIN_PINNED_THRESHOLD NON vengono mai
# spostati dal rebalance. Valore = mediana margin osservata su E2E #11
# (0.073) arrotondata a 0.08 per dare un po' di "cuscinetto sicuro".
MARGIN_PINNED_THRESHOLD = 0.08


def _rebalance_min_margin_aware(
    result: dict[int, list[NormativeChunk]],
    chunk_margins: dict[str, float],
    min_per_module: int = 3,
) -> None:
    """Min-rebalance che sposta SOLO chunks a margin basso (trasversali).

    Chunks pinned (margin >= MARGIN_PINNED_THRESHOLD) restano nel modulo
    di assegnazione cosine originale. Donor: chunks con margin ascendente
    (i più trasversali prima → minimo danno tematico).
    """
    max_iterations = 200  # safety
    iters = 0
    while iters < max_iterations:
        iters += 1
        under = [k for k, v in result.items() if len(v) < min_per_module]
        if not under:
            return
        # Donatori: moduli con > min_per_module+2 chunks, ma SOLO chunks
        # spostabili (margin < threshold)
        donor_candidates: list[tuple[int, NormativeChunk, float]] = []
        for mod_idx, chunks_list in result.items():
            if len(chunks_list) <= min_per_module + 2:
                continue
            for c in chunks_list:
                margin = chunk_margins.get(c.chunk_id, 0.0)
                if margin < MARGIN_PINNED_THRESHOLD:
                    donor_candidates.append((mod_idx, c, margin))
        if not donor_candidates:
            return  # niente di spostabile rimasto
        # Sort ASC margin: spostiamo prima i più "ambigui"
        donor_candidates.sort(key=lambda x: x[2])
        donor_mod, donor_chunk, _ = donor_candidates[0]
        receiver = min(under, key=lambda k: len(result[k]))
        # Move
        result[donor_mod].remove(donor_chunk)
        result[receiver].append(donor_chunk)


def _rebalance_max_margin_aware(
    result: dict[int, list[NormativeChunk]],
    chunk_margins: dict[str, float],
    max_per_module: int,
) -> None:
    """Max-rebalance margin-aware. Stessa logica di _min: donor=chunks a
    margin basso, pinned non vengono mai spostati.
    """
    max_iterations = 200
    iters = 0
    while iters < max_iterations:
        iters += 1
        over = [k for k, v in result.items() if len(v) > max_per_module]
        under = [k for k, v in result.items() if len(v) < max_per_module]
        if not over or not under:
            return
        # Donor candidates: chunks spostabili (margin basso) dai moduli over
        donor_candidates: list[tuple[int, NormativeChunk, float]] = []
        for mod_idx in over:
            for c in result[mod_idx]:
                margin = chunk_margins.get(c.chunk_id, 0.0)
                if margin < MARGIN_PINNED_THRESHOLD:
                    donor_candidates.append((mod_idx, c, margin))
        if not donor_candidates:
            return
        donor_candidates.sort(key=lambda x: x[2])
        donor_mod, donor_chunk, _ = donor_candidates[0]
        receiver = min(under, key=lambda k: len(result[k]))
        result[donor_mod].remove(donor_chunk)
        result[receiver].append(donor_chunk)


_STOPWORDS_IT = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "a",
    "da", "in", "con", "su", "per", "tra", "fra", "del", "dello", "della",
    "dei", "degli", "delle", "al", "allo", "alla", "ai", "agli", "alle",
    "dal", "dalla", "nel", "nella", "sul", "sulla", "e", "o", "ma", "che",
    "se", "non", "è", "sono", "ha", "hanno", "essere", "avere", "fare",
}

# FIX #30.9c (2026-05-26): mappa sinonimi italiana per matching tematico tra
# title moduli (frasi italiane discorsive) e tags chunk (lowercase keyword).
# Espande il match SENZA cambiare la semantica. Esempi reali dal corpus
# D.Lgs. 81/08: tag "antincendio" → match modulo "emergenza/incendio/evacuazione";
# tag "valutazione_rischi" → match modulo "rischi/valutazione".
_SYNONYMS: dict[str, set[str]] = {
    "emergenza":      {"emergenza", "antincendio", "evacuazione", "incendio", "soccorso", "salvataggio"},
    "emergenze":      {"emergenza", "antincendio", "evacuazione", "incendio", "soccorso"},
    "incendio":       {"incendio", "antincendio", "evacuazione", "emergenza"},
    "rischi":         {"rischi", "rischio", "valutazione_rischi", "valutazione"},
    "rischio":        {"rischi", "rischio", "valutazione_rischi", "valutazione"},
    "specifici":      {"specifici", "specifico", "specifica", "particolari"},
    "dpi":            {"dpi", "calzature", "casco", "guanti", "protezione"},
    "protezione":     {"dpi", "calzature", "protezione", "casco"},
    "formazione":     {"formazione", "addestramento", "corso", "informazione"},
    "informazione":   {"formazione", "informazione", "addestramento"},
    "lavoratore":     {"lavoratori", "lavoratore", "dipendenti"},
    "lavoratori":     {"lavoratori", "lavoratore", "dipendenti"},
    "datore":         {"datore_lavoro", "datore", "dirigente"},
    "preposto":       {"preposto", "preposti", "responsabile"},
    "segnaletica":    {"segnaletica", "cartelli", "segnali"},
    "cantieri":       {"cantieri", "cantiere", "costruzioni"},
    "cantiere":       {"cantieri", "cantiere", "costruzioni"},
    "procedure":      {"procedure", "procedura", "procedurali"},
}


def _normalize_words(text: str) -> set[str]:
    """Lowercase + strip stop-italian + tokenize + sinonimi expansion.

    FIX #30.9c (2026-05-26): split anche su underscore (i tag DB sono
    snake_case tipo "valutazione_rischi") + sinonimi italiani per matching
    cross-vocabulary (es. titolo modulo "Procedure emergenza" deve
    matchare tag "antincendio").
    """
    import re
    # Tokenize: split su whitespace + underscore + punctuation
    raw_words = re.split(r"[\s_\-.,;:!?\"'()\[\]]+", text.lower())
    base = {w for w in raw_words if len(w) > 2 and w not in _STOPWORDS_IT}
    # Espandi con sinonimi
    expanded = set(base)
    for w in base:
        if w in _SYNONYMS:
            expanded |= _SYNONYMS[w]
    return expanded


def _thematic_score(module_title_words: set[str], chunk: NormativeChunk) -> float:
    """Score di matching tematico tra titolo modulo e chunk.

    FIX #30.9c (2026-05-26): sostituisce il keyword overlap puro su `body`
    (riga 119-124 vecchio) che degenerava su titoli generici (es. "Rischi
    specifici" matchava tutto). Pesa SEGNALI metadati specifici (alta
    precisione) MOLTO più del body keyword (ubiquitario):

      +3 per ogni tag overlap  (tags = ["DPI","calzature"] → segnale forte)
      +2 per ogni parola hierarchy_path overlap
      +1 per ogni parola article overlap (es. "Allegato IV")
      +0.5 per ogni parola body overlap (segnale debole, ubiquitario)

    Score 0 = totale assenza di match → quel modulo NON è la casa giusta.
    """
    score = 0.0
    # Tag overlap — pesato +3 (segnale specifico per design)
    if chunk.tags:
        chunk_tag_words: set[str] = set()
        for tag in chunk.tags:
            chunk_tag_words |= _normalize_words(tag)
        score += 3.0 * len(module_title_words & chunk_tag_words)
    # Hierarchy path overlap — pesato +2
    if chunk.hierarchy_path:
        hier_words = _normalize_words(chunk.hierarchy_path)
        score += 2.0 * len(module_title_words & hier_words)
    # Article overlap — pesato +1 (es. "Allegato IV" matcha modulo "Allegati")
    if chunk.article:
        art_words = _normalize_words(chunk.article)
        score += 1.0 * len(module_title_words & art_words)
    # Body keyword overlap — pesato +0.5 (segnale debole, fallback)
    body_words = _normalize_words(chunk.body[:500])  # primi 500 char per perf
    score += 0.5 * len(module_title_words & body_words)
    return score


# ─────────────────────────────────────────────────────────────────────
# FIX #30.9d (2026-05-26): cosine embedding cluster
# Analista: query in prosa naturale (no keyword bag), sinonimi disgiunti
# tra moduli dello stesso corso (no termini condivisi).
# ─────────────────────────────────────────────────────────────────────

# Espansione PROSA per module title → embed query.
# Per ogni title del COURSE_CATALOG (38 unici totali), 1-3 frasi italiane
# naturali che descrivono il tema. Title NON presente nel dict → fallback
# a embed del title nudo.
MODULE_QUERY_EXPANSIONS: dict[str, str] = {
    # === sicurezza_lavoratori_specifica_basso (4 moduli) ===
    "Rischi specifici": (
        "Rischi specifici dell'attività lavorativa nei luoghi di lavoro: "
        "rischi elettrici, esplosioni, lavoro in altezza, spazi confinati, "
        "agenti chimici, biologici, fisici, movimentazione manuale dei "
        "carichi, videoterminali, stress lavoro-correlato, agenti cancerogeni."
    ),
    "DPI": (
        "Dispositivi di protezione individuale: casco, guanti, calzature "
        "di sicurezza, occhiali, otoprotettori, maschere, imbracature "
        "anticaduta, abbigliamento da lavoro. Criteri di scelta, uso, "
        "manutenzione, sostituzione, conformità CE marchio europeo."
    ),
    "Procedure di emergenza": (
        "Procedure operative di emergenza: piano di emergenza, evacuazione, "
        "vie di fuga, punti di raccolta, antincendio, estintori, primo "
        "soccorso, gestione infortuni, allarme acustico, addetti emergenza, "
        "lotta antincendio, esercitazioni periodiche."
    ),
    "Segnaletica": (
        # FIX #31.6C (2026-05-27, analista review 7): query ricalibrata
        # DENTRO il tema segnaletica. In #31.5 avevamo aggiunto
        # "formazione" e "obblighi del datore" → self-own: 13 slide M3
        # diventarono formazione/sanzioni. Rimossi entrambi. Allarghiamo
        # ai sotto-tipi LEGITTIMI di segnaletica (cartelli, colori,
        # pittogrammi, luminosi, acustici, gestuali, esodo, antincendio,
        # cantiere) — segnaletica a tutto tondo, non solo cartelli.
        # Aspettativa onesta: corpus 81/08 ha ~60 chunk di vera
        # segnaletica, M3 potrà reggere ~60 slide oneste; le 20 extra
        # saranno ripetizione on-topic (accettabile) invece di sanzioni
        # (inaccettabile). Trade giusto. Il drop-list post-retrieval
        # (#31.6D) elimina il residuo da adiacenza-corpus
        # (sanzioni/medico/inidoneità/RSPP).
        "Segnaletica di salute e sicurezza sul lavoro: "
        # Cartelli (core)
        "cartelli di divieto, avvertimento, prescrizione, salvataggio, "
        "antincendio. "
        # Caratteristiche cartelli
        "Forme geometriche, colori di sicurezza (rosso, giallo, verde, blu), "
        "pittogrammi ISO 7010, dimensioni, materiali resistenti, "
        "posizionamento ottimale, visibilità, manutenzione. "
        # Segnali alternativi (sotto-tipi Titolo V)
        "Segnali luminosi, segnali acustici, comunicazioni verbali, "
        "segnali gestuali per movimentazione manuale e mezzi di sollevamento. "
        # Segnaletica per contesti specifici (allargamento DENTRO tema)
        "Segnaletica delle vie di esodo, segnaletica antincendio, "
        "segnaletica di emergenza, segnaletica di cantiere temporaneo "
        "e mobile, segnaletica per lavori stradali, segnaletica per "
        "sostanze pericolose e marchio CE."
    ),

    # === sicurezza_lavoratori_generale (4 moduli) ===
    "Concetti di rischio": (
        "Concetti fondamentali di rischio, pericolo, danno e probabilità "
        "nei luoghi di lavoro. Valutazione del rischio, matrice di rischio, "
        "rischio residuo, livelli di rischio basso medio alto."
    ),
    "Prevenzione e protezione": (
        # FIX #32 (analista review 12): query ampliata mirata a
        # misure tecniche/organizzative/procedurali per ESCLUDERE
        # cosine match con "sorveglianza sanitaria" / "medico
        # competente" / "agenti biologici" / "cartella sanitaria"
        # che erano 39 chunk = 46% off-topic in Demo #2 v2 M1.
        # NB: la query NON menziona "medico", "sorveglianza",
        # "biologico", "cancerogeno", "sanitaria" intenzionalmente.
        # Questi temi appartengono a moduli diversi del corso
        # (Diritti e doveri, Concetti di rischio).
        "Misure di prevenzione e protezione tecniche e organizzative: "
        # Gerarchia dei controlli (esteso)
        "gerarchia dei controlli ISO/EN, eliminazione del rischio alla "
        "fonte, sostituzione con alternative meno pericolose, controlli "
        "ingegneristici (separazione spaziale, ventilazione, schermature, "
        "interlock di sicurezza), controlli amministrativi (procedure "
        "operative, permessi di lavoro, turni di lavoro). "
        # DPI collettivi e individuali (core)
        "Dispositivi di protezione collettiva (DPC) prima dei DPI: "
        "parapetti, schermi, aspirazione localizzata, isolamento "
        "acustico. Dispositivi di protezione individuale (DPI) come "
        "ultima barriera. "
        # Misure procedurali e organizzative
        "Procedure di sicurezza, istruzioni operative, formazione "
        "specifica preventiva, addestramento all'uso DPI, manutenzione "
        "preventiva delle attrezzature, ispezioni periodiche, "
        "registrazione anomalie. "
        # Esempi pratici (anti-blur)
        "Misure tecniche per cadute dall'alto (parapetti, reti, "
        "imbracature), per rischio elettrico (interruttori magnetotermici, "
        "messa a terra), per rumore (cabine acustiche, cuffie), per "
        "macchine (ripari, dispositivi di consenso)."
    ),
    "Organizzazione della prevenzione": (
        "Servizio prevenzione e protezione aziendale SPP, RSPP, ASPP, "
        "medico competente, rappresentante lavoratori RLS, organigramma "
        "sicurezza, dirigenti, preposti, datore di lavoro."
    ),
    "Diritti e doveri": (
        "Diritti e doveri dei lavoratori in materia di sicurezza: "
        "obblighi del datore di lavoro, sanzioni, partecipazione, "
        "consultazione, formazione obbligatoria, informazione."
    ),

    # === preposti (6 moduli) ===
    "Principali soggetti del sistema di prevenzione": (
        "Soggetti del sistema di prevenzione aziendale: datore di lavoro, "
        "dirigente, preposto, lavoratore, RSPP, ASPP, medico competente, "
        "RLS, addetti emergenza. Ruoli, responsabilità, deleghe."
    ),
    "Relazioni tra i vari soggetti": (
        "Relazioni e comunicazione tra dirigenti, preposti, lavoratori, "
        "RSPP, RLS. Catena di comando, segnalazioni, riunioni periodiche "
        "ex art. 35, coordinamento prevenzione."
    ),
    "Definizione e individuazione dei fattori di rischio": (
        "Identificazione fattori di rischio per il preposto: osservazione "
        "ambiente di lavoro, riconoscimento pericoli, valutazione esposizione "
        "lavoratori, sopralluoghi periodici."
    ),
    "Incidenti e infortuni mancati": (
        "Near miss, incidenti senza danno, infortuni mancati, registro "
        "infortuni, analisi cause, azioni correttive. Differenza tra "
        "incidente e infortunio."
    ),
    "Tecniche di comunicazione e sensibilizzazione": (
        "Comunicazione efficace del preposto verso lavoratori: linguaggio "
        "chiaro, ascolto attivo, feedback, motivazione, esempio personale, "
        "sensibilizzazione sicurezza."
    ),
    "Valutazione dei rischi dell'azienda": (
        "Documento di valutazione dei rischi DVR aziendale: ex art. 28-29, "
        "metodologia, aggiornamento triennale, integrazione con sorveglianza "
        "sanitaria e formazione."
    ),

    # === primo_soccorso_gruppo_b_c + gruppo_a (sovrapposti) ===
    "Aspetti legislativi e allertamento sistema di soccorso": (
        "Normativa primo soccorso aziendale: DM 388/2003, gruppi A B C, "
        "obblighi datore di lavoro, allertamento 118, organizzazione "
        "soccorsi interni."
    ),
    "Riconoscimento emergenze sanitarie e tecniche di autoprotezione": (
        "Riconoscimento emergenze sanitarie sul lavoro: coscienza, "
        "respirazione, polso. Tecniche autoprotezione del soccorritore, "
        "DPI sanitari, isolamento."
    ),
    "Patologie acute: shock, edema polmonare, asma, allergie, lipotimia": (
        "Patologie acute in ambiente di lavoro: shock, edema polmonare "
        "acuto, asma bronchiale, reazioni allergiche, lipotimia, sincope, "
        "crisi cardiocircolatorie."
    ),
    "Traumi scheletrici, cranio-encefalici e della colonna vertebrale": (
        "Traumi muscolo-scheletrici sul lavoro: fratture, lussazioni, "
        "distorsioni. Traumi cranici, commozione cerebrale, lesioni "
        "spinali, immobilizzazione."
    ),
    "Lesioni da agenti fisici e chimici, intossicazioni": (
        "Lesioni da agenti fisici (ustioni, congelamento, elettrocuzione) "
        "e chimici (caustici, solventi). Intossicazioni acute, vie di "
        "esposizione, antidoti."
    ),
    "Emorragie e ferite — gestione delle urgenze": (
        "Emorragie esterne, interne, ferite lacero-contuse. Compressione, "
        "tourniquet, medicazione, prevenzione infezioni. Gestione urgenze."
    ),
    "Aspetti legislativi del primo soccorso in aziende ad alto rischio": (
        "Primo soccorso in aziende gruppo A (alto rischio): obblighi "
        "rafforzati, formazione 16 ore, cassetta di pronto soccorso, "
        "DPI sanitari avanzati."
    ),
    "Allertamento del sistema di soccorso e accertamento condizioni psicofisiche": (
        "Allertamento sistema 118, comunicazioni di emergenza, "
        "accertamento parametri vitali della vittima, valutazione "
        "coscienza, respirazione."
    ),
    "Tecniche di autoprotezione e sostentamento delle funzioni vitali": (
        "Manovre di sostegno funzioni vitali: BLS basic life support, "
        "posizione laterale di sicurezza, autoprotezione del soccorritore."
    ),
    "Respirazione artificiale e massaggio cardiaco esterno (BLS)": (
        "BLS rianimazione cardiopolmonare: massaggio cardiaco, "
        "ventilazione bocca-a-bocca, defibrillatore DAE, sequenza "
        "30 compressioni 2 insufflazioni."
    ),
    "Riconoscimento shock, edema polmonare, asma, reazioni allergiche, emorragie": (
        "Diagnosi differenziale shock, edema polmonare, broncospasmo "
        "asmatico, anafilassi, emorragia esterna e interna. Sintomi, "
        "trattamento immediato."
    ),
    "Traumi in ambiente di lavoro: fratture, lussazioni, traumi cranici e spinali": (
        "Traumi sul posto di lavoro: fratture chiuse aperte, lussazioni, "
        "traumi cranici, lesioni colonna vertebrale. Immobilizzazione, "
        "trasporto del traumatizzato."
    ),
    "Lesioni toracico-addominali, da freddo/calore, corrente elettrica e agenti chimici": (
        "Lesioni toraciche e addominali (penetranti, contundenti), "
        "ipotermia, ipertermia colpo di calore, ustioni elettriche da "
        "folgorazione, ustioni chimiche."
    ),
    "Intossicazioni, ferite lacero-contuse, emorragie esterne": (
        "Intossicazioni acute industriali (vie inalatoria, cutanea, "
        "orale), ferite lacero-contuse, emorragie esterne. Trattamento "
        "sul campo prima del 118."
    ),

    # === primo_soccorso_test_dm388_only (corso 1h test, 2 moduli) ===
    "Allertare il sistema di soccorso": (
        "Allertamento sistema sanitario di emergenza 118: numero unico, "
        "comunicazione efficace, informazioni essenziali, gestione "
        "attesa soccorsi."
    ),
    "Riconoscere emergenza sanitaria": (
        "Riconoscimento situazioni di emergenza sanitaria in azienda: "
        "perdita di coscienza, arresto respiratorio, emorragia massiva, "
        "trauma grave, segni di shock."
    ),

    # === antincendio_livello_1 (4 moduli) ===
    "Principi dell'incendio": (
        "Triangolo del fuoco: combustibile, comburente, energia di "
        "innesco. Classificazione incendi classe A B C D F. Propagazione "
        "fiamme, fumo, calore."
    ),
    "Prevenzione incendi": (
        "Misure di prevenzione incendi: riduzione carico di fuoco, "
        "separazione sostanze incompatibili, controllo sorgenti innesco, "
        "manutenzione impianti elettrici, controllo periodico estintori."
    ),
    "Protezione antincendio": (
        "Sistemi di protezione attiva e passiva: estintori portatili "
        "carrellati, idranti, naspi, sprinkler, rivelatori di fumo, "
        "compartimentazione, porte tagliafuoco, REI."
    ),
    "Procedure operative": (
        "Procedure operative addetto antincendio: uso estintore, "
        "evacuazione coordinata, segnalazione VVF 115, comunicazione "
        "interna, esercitazioni periodiche, piano emergenza."
    ),

    # === haccp_addetto (4 moduli) ===
    "Principi HACCP": (
        "Sistema HACCP Hazard Analysis Critical Control Points: 7 "
        "principi, analisi rischi alimentari, punti critici di controllo "
        "CCP, monitoraggio, azioni correttive."
    ),
    "Igiene degli alimenti": (
        "Igiene degli alimenti: contaminazioni biologiche chimiche "
        "fisiche, conservazione corretta temperature, catena del "
        "freddo, igiene del personale, lavaggio mani."
    ),
    "Rischi biologici e chimici": (
        "Rischi alimentari biologici (batteri, virus, parassiti) e "
        "chimici (residui pesticidi, allergeni, sostanze tossiche). "
        "Allergeni regolamento UE 1169."
    ),
    "Autocontrollo e documentazione": (
        "Autocontrollo aziendale HACCP: manuale di autocontrollo, "
        "registri di temperatura, schede di non conformità, "
        "tracciabilità lotti, audit interni."
    ),
}


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity standard tra 2 vettori. Ritorna 0.0 se uno dei due
    ha norma zero (chunk senza embedding, edge case).
    """
    import math
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ═══════════════════════════════════════════════════════════════════════
# FIX #31.1 (2026-05-27): RETRIEVAL PER-MODULO (precondizione demo CFP).
#
# Sostituisce "1 retrieval globale + cluster + rebalance" con
# N retrieval indipendenti uno per modulo. Risolve il grab-bag M3/M4
# rilevato in E2E #19 (M3 "Procedure emergenza" = 20 vere emergenze
# + 54 RLS/sanzioni/fondi; M4 "Segnaletica" = 22 segnaletica vera +
# 60 formazione/RSPP/agenti). Vedi piano vast-hopping-sketch.md.
#
# Approvato analista 2026-05-27 (review 1 e 2) con 6 cautele integrate:
#   1. lost_to_other_module per modulo (diagnostico: corpus povero vs
#      dedup aggressiva)
#   2. guard module_titles None → flusso legacy (corsi sperimentali)
#   3. test_dedup_does_not_starve_weak_module
#   4. filtro relevance dentro funzione PRIMA dedup (chunks_by_module
#      e chunks_flatten devono vedere stesso insieme)
#   5. log relevance_filter_dropped per modulo
#   6. assert module_index contiguo + allineato con pacing
# ═══════════════════════════════════════════════════════════════════════


async def retrieve_chunks_per_module(
    pacing_plan: PacingPlan,
    regulation_ids: list[str],
    region: str,
    knowledge_repo: KnowledgeRepository,
    top_k_per_module: int = 70,
    min_relevance: float = 0.0,
) -> dict[int, list[NormativeChunk]]:
    """#31.1 — N retrieval indipendenti, uno per modulo + dedup cosine.

    Per ogni modulo del pacing_plan:
      1. Embed query: ``MODULE_QUERY_EXPANSIONS[title]`` OR title nudo.
      2. ``knowledge_repo.search_chunks(top_k=top_k_per_module)``.
      3. Filtro relevance > min_relevance (cautela #4 analista).

    Dedup cross-modulo: un chunk vince in UN SOLO modulo (quello con
    il cosine score più alto vs il suo embed query). Necessario perché
    un chunk può essere rilevante per più temi (es. "DPI" vs "Rischi
    specifici" sui DPI elettrici).

    Ritorna ``dict[module_index, list[NormativeChunk]]`` dove ogni
    chunk appare in al più un modulo.
    """
    from app.services.ingestion_service import embed_query as _embed_query

    # 1. Per ogni modulo: embed query + search_chunks + filtro relevance
    raw_per_module: dict[int, list[NormativeChunk]] = {}
    for m in pacing_plan.modules:
        query_text = MODULE_QUERY_EXPANSIONS.get(m.title, m.title)
        try:
            module_q_embed = await _embed_query(query_text)
        except Exception as exc:
            logger.warning(
                "module_query_embed_failed",
                module_index=m.module_index, title=m.title, error=str(exc),
            )
            raw_per_module[m.module_index] = []
            continue

        module_chunks_raw = await knowledge_repo.search_chunks(
            query_embedding=module_q_embed,
            regulation_ids=regulation_ids,
            region=region,
            top_k=top_k_per_module,
        )
        # Cautela #4 analista review 2: filtro relevance PRIMA della
        # dedup. chunks_by_module (al content_agent) e _flatten_unique
        # (a CourseContext.chunks per audit) devono vedere lo stesso
        # insieme — altrimenti chunk sotto-soglia finiscono in slide
        # mentre l'audit dice scartati = disallineamento silenzioso.
        module_chunks = [
            c for c in module_chunks_raw
            if c.relevance_score and c.relevance_score > min_relevance
        ]
        # FIX #31.8 LEVA B (2026-05-27, analista review 11): MIN_RELEVANCE
        # adattivo per modulo. Se il filtro statico svuota un modulo sotto
        # la soglia gate (30 chunk), ricalcola MIN come P25 dei chunk raw
        # e ri-applica. Salva i moduli con tema stretto / corpus debole
        # (Patologia 1 di Preposti 8h: M3 "Incidenti mancati" → 70 chunk
        # con score [0.21..0.29] → filtro statico 0.3 droppa 60/70 → 5
        # chunk per 108 slide attese. Post-B: P25 ≈ 0.22, ~50 rescued).
        GATE_MIN_CHUNKS = 30
        adaptive_applied = False
        if len(module_chunks) < GATE_MIN_CHUNKS and module_chunks_raw:
            scores_sorted = sorted(
                (c.relevance_score or 0.0) for c in module_chunks_raw
            )
            p25_idx = max(0, len(scores_sorted) // 4)
            adaptive_min = scores_sorted[p25_idx]
            rescued = [
                c for c in module_chunks_raw
                if c.relevance_score and c.relevance_score > adaptive_min
            ]
            if len(rescued) > len(module_chunks):
                logger.info(
                    "min_relevance_adaptive_applied",
                    module_index=m.module_index, title=m.title,
                    static_min=min_relevance,
                    adaptive_min=round(adaptive_min, 4),
                    before=len(module_chunks),
                    after=len(rescued),
                )
                module_chunks = rescued
                adaptive_applied = True
        relevance_dropped = len(module_chunks_raw) - len(module_chunks)
        raw_per_module[m.module_index] = module_chunks
        logger.info(
            "module_retrieval_done",
            module_index=m.module_index, title=m.title,
            count_raw=len(module_chunks_raw),
            count_after_relevance=len(module_chunks),
            relevance_filter_dropped=relevance_dropped,  # cautela #5
            adaptive_min_applied=adaptive_applied,  # FIX #31.8 B
            top_score=max((c.relevance_score or 0) for c in module_chunks)
                if module_chunks else 0,
        )

    # 2. Dedup cross-modulo QUOTA-AWARE (FIX #31.8 LEVA C, analista
    # review 11): garantisci QUOTA_MIN chunk per modulo PRIMA di
    # trasferire eccedenti via cosine winner. Risolve Patologia 2
    # dedup-zero-sum su moduli adiacenti (Preposti M1/M4/M5 perdono
    # 40-47 chunk ciascuno verso moduli "campione" cosine come M0;
    # Generale Demo #2 M3 "Diritti e doveri" perde 4 slot Segnaletica
    # verso M2 "Segnaletica" stesso corso).
    #
    # Algoritmo:
    #   Step 1: ordina chunk per modulo decrescente per score.
    #   Step 2: ogni modulo pin i suoi top QUOTA_MIN chunk (a meno che
    #           non siano già pinned altrove — first-come).
    #   Step 3: chunk NON pinned → dedup cosine winner come prima
    #           (preserva semantica originale per gli eccedenti).
    #   Step 4: costruisci result combinando pinned + cosine-winners.
    #
    # Su corsi 4h × 4 moduli ben distinti (E25) la quota 30 è
    # ampiamente coperta da tutti i moduli → effetto zero su
    # retrocompat. Attiva solo dove dedup-starvation morde.
    QUOTA_MIN = 30  # analista review 11 verbatim

    # Step 1: sort per modulo decrescente per score
    sorted_per_module: dict[int, list[NormativeChunk]] = {
        m_idx: sorted(
            chunks_list,
            key=lambda c: c.relevance_score or 0.0,
            reverse=True,
        )
        for m_idx, chunks_list in raw_per_module.items()
    }

    # Step 2: pin i primi QUOTA_MIN chunk di ogni modulo (first-come,
    # ordine di iterazione = ordine module_index)
    pinned: dict[str, int] = {}  # chunk_id → module_index pinned
    for m_idx, chunks_list in sorted_per_module.items():
        quota_taken = 0
        for c in chunks_list:
            if quota_taken >= QUOTA_MIN:
                break
            if c.chunk_id not in pinned:
                pinned[c.chunk_id] = m_idx
                quota_taken += 1

    # Step 3: dedup cosine winner sui NON pinned (eccedenti)
    chunk_best_module: dict[str, tuple[int, float]] = {}
    for m_idx, chunks_list in raw_per_module.items():
        for c in chunks_list:
            if c.chunk_id in pinned:
                continue  # già pinned, skip dedup
            cid = c.chunk_id
            score = c.relevance_score or 0.0
            current = chunk_best_module.get(cid)
            if current is None or score > current[1]:
                chunk_best_module[cid] = (m_idx, score)

    # Step 4: costruisci result combinando pinned + cosine-winners
    result: dict[int, list[NormativeChunk]] = {
        m.module_index: [] for m in pacing_plan.modules
    }
    for m_idx, chunks_list in raw_per_module.items():
        for c in chunks_list:
            if c.chunk_id in pinned:
                if pinned[c.chunk_id] == m_idx:
                    result[m_idx].append(c)
            else:
                if chunk_best_module.get(c.chunk_id, (None, 0))[0] == m_idx:
                    result[m_idx].append(c)

    # Diagnostico FIX #31.8 C: quanti chunk pinned per modulo + flag
    # per_module_quota_pin_active (= modulo che ha "saturato" la quota
    # — segnale che la rete C è stata utile).
    per_module_pinned: dict[int, int] = {
        m_idx: sum(
            1 for c in chunks_list
            if c.chunk_id in pinned and pinned[c.chunk_id] == m_idx
        )
        for m_idx, chunks_list in raw_per_module.items()
    }
    logger.info(
        "dedup_quota_aware_applied",
        quota_min=QUOTA_MIN,
        pinned_count=len(pinned),
        per_module_pinned=per_module_pinned,
    )

    # FIX #31.6D (2026-05-27, analista review 7): drop-list per Segnaletica.
    # In E2E #24 il modulo M3 "Segnaletica" aveva 13 slide off-topic su
    # sanzioni/medico/inidoneità/RSPP (=15%). Causa: il corpus 81/08 ha
    # cosine alto fra "segnaletica" e questi temi trasversali. Il drop-list
    # rimuove i chunk il cui body matcha pattern non-segnaletica DOPO la
    # dedup (chirurgico, applicato SOLO al modulo "Segnaletica" perché
    # "RSPP" potrebbe essere legittimo in M0 Rischi specifici, "medico"
    # in altri moduli ecc.). Pattern derivati da analisi titoli M3 #24:
    # sanzioni, medico competente, inidoneità, RSPP/SPP, formazione generica
    # (la query ampliata #31.6C ha già tolto "formazione specifica
    # sulla segnaletica" ma il drop-list assicura zero residuo).
    _DROP_PATTERN_SEGNALETICA = re.compile(
        r"\b("
        r"sanzion[ei]"
        r"|inidone(?:o|ita|ità)"
        r"|medico\s+competent\w*"  # competente, competenti
        r"|giudizio\s+(?:medico|di\s+idonei)\w*"
        r"|sorveglianza\s+sanitaria"
        r"|RSPP|ASPP"
        r"|SPP\s+(?:aziendal|servizio)\w*"
        r"|delega\s+di\s+funzion\w*"
        r"|responsabilit[àa]\s+penal\w*"
        r")\b",
        re.IGNORECASE,
    )
    segnaletica_modules = [
        m for m in pacing_plan.modules if m.title == "Segnaletica"
    ]
    drop_counts: dict[int, int] = {}
    for sm in segnaletica_modules:
        kept_chunks = []
        dropped = 0
        for c in result[sm.module_index]:
            if _DROP_PATTERN_SEGNALETICA.search(c.body or ""):
                dropped += 1
                continue
            kept_chunks.append(c)
        if dropped > 0:
            drop_counts[sm.module_index] = dropped
            result[sm.module_index] = kept_chunks
    if drop_counts:
        logger.info(
            "segnaletica_drop_list_applied",
            chunks_dropped=drop_counts,
            reason="off_topic_corpus_adjacency",
        )

    # FIX #32 (2026-05-27, analista review 12): drop-list M1
    # "Prevenzione e protezione" del corso GENERALE 4h. Stesso
    # pattern di Segnaletica drop-list: corpus 81/08 ha cosine
    # alto fra "Prevenzione" e "Sorveglianza sanitaria / medico
    # competente / agenti biologici", e la dedup zero-sum (#31.8 C)
    # ha bilanciato i numeri ma il contenuto recuperato per M1 di
    # Demo #2 v2 era 46% medico/biologico off-topic.
    # Pattern derivato da analisi titoli M1 Demo #2 v2 (analista
    # classificazione: 39/63 medico/sorveglianza/agenti biologici).
    # Applicato SOLO al modulo "Prevenzione e protezione" (M1 di
    # Generale 4h), NON a "Prevenzione e protezione" di altri
    # cataloghi se esistesse (qui è specifico a corsi lavoratori
    # generale per disambiguazione semantica).
    _DROP_PATTERN_M1_PREVENZIONE_GENERALE = re.compile(
        r"\b("
        # Medico competente / sorveglianza sanitaria (core off-topic)
        r"medico\s+competent\w*"
        r"|sorveglianza\s+sanitaria"
        r"|giudizio\s+(?:medico|di\s+idonei)\w*"
        r"|cartella\s+sanitaria"
        r"|visita\s+medic\w*"
        r"|inidone(?:o|ita|ità)"
        # Agenti biologici (registri, vaccinazioni — sono temi di
        # Diritti e doveri come parte formazione obbligatoria specifica)
        r"|agent[ei]\s+biologic\w*"
        r"|vaccinazion\w*"
        r"|registro\s+(?:esposizione|biologic\w*)"
        r"|cancerogen\w*\s+e\s+mutagen\w*"
        # Sanzioni penali (sono M3 Diritti come "conseguenza dovere")
        r"|sanzion[ei]\s+penal\w*"
        r")\b",
        re.IGNORECASE,
    )
    m1_modules = [
        m for m in pacing_plan.modules
        if m.title == "Prevenzione e protezione"
    ]
    drop_counts_m1: dict[int, int] = {}
    for m1 in m1_modules:
        kept_chunks = []
        dropped = 0
        for c in result[m1.module_index]:
            if _DROP_PATTERN_M1_PREVENZIONE_GENERALE.search(c.body or ""):
                dropped += 1
                continue
            kept_chunks.append(c)
        if dropped > 0:
            drop_counts_m1[m1.module_index] = dropped
            result[m1.module_index] = kept_chunks
    if drop_counts_m1:
        logger.info(
            "m1_prevenzione_drop_list_applied",
            chunks_dropped=drop_counts_m1,
            reason="medico_biologico_corpus_blur",
        )

    # 3. Log finale — cautela #1 analista review 2:
    # `lost_to_other_module` per modulo è il numero DIAGNOSTICO che
    # distingue "corpus povero" (mitigation: allarga query) da "dedup
    # aggressiva che migra generici verso moduli forti" (mitigation
    # opposta: dedup quota-aware). Senza, vedi M3=15 e non sai quale
    # fix applicare. Sono due fix opposti.
    total_raw = sum(len(v) for v in raw_per_module.values())
    total_dedup = sum(len(v) for v in result.values())
    per_module_kept: dict[int, int] = {
        m_idx: len(v) for m_idx, v in result.items()
    }
    per_module_lost: dict[int, int] = {
        m_idx: len(raw_per_module.get(m_idx, [])) - per_module_kept[m_idx]
        for m_idx in per_module_kept
    }
    logger.info(
        "per_module_retrieval_summary",
        total_raw=total_raw,
        total_after_dedup=total_dedup,
        duplicates_removed=total_raw - total_dedup,
        per_module_kept=per_module_kept,
        lost_to_other_module=per_module_lost,
    )

    # Cautela #6 analista review 2: assert module_index contiguo +
    # allineato con pacing_plan. Blinda contro disallineamento
    # numerazione moduli (vecchio FIX #27.1 sotto altra forma: se gli
    # indici del retrieval divergono da quelli del content_agent /
    # builder, i chunk finiscono nel modulo sbagliato a valle senza
    # errore visibile).
    expected_keys = {m.module_index for m in pacing_plan.modules}
    actual_keys = set(result.keys())
    assert actual_keys == expected_keys, (
        f"module_index mismatch: pacing={sorted(expected_keys)}, "
        f"retrieval={sorted(actual_keys)}"
    )

    return result


def _flatten_unique(
    chunks_by_module: dict[int, list[NormativeChunk]],
) -> list[NormativeChunk]:
    """Helper #31.1: unione chunk preservando ordine per backward-compat
    con ``chunks`` in CourseContext (usato per audit/fingerprint).

    Itera per ``module_index`` ascendente, scarta duplicati. Necessario
    perché ``CourseContext.chunks`` è ``list[NormativeChunk]`` flat e
    il chunk_id deve essere unico per fingerprint coerente.
    """
    seen: set[str] = set()
    out: list[NormativeChunk] = []
    for m_idx in sorted(chunks_by_module.keys()):
        for c in chunks_by_module[m_idx]:
            if c.chunk_id not in seen:
                seen.add(c.chunk_id)
                out.append(c)
    return out


async def distribute_chunks_to_modules_cosine(
    chunks: list[NormativeChunk],
    pacing_plan: PacingPlan,
    course_id: str = "",
    pool: object | None = None,
) -> tuple[dict[int, list[NormativeChunk]], list[dict[str, object]]]:
    """[DEPRECATED #31.1 — 2026-05-27]: sostituita da
    ``retrieve_chunks_per_module()``. Mantenuta nel file per rollback
    rapido se #31.1 introduce regressioni che la verifica E2E non
    intercetta. Sarà rimossa post-OK analista sui 4 moduli.

    Usata SOLO ora dal flusso legacy quando ``module_titles is None``
    (corsi sperimentali senza catalogo — vedi guard in research_agent).

    --- DOCSTRING ORIGINALE ---

    FIX #30.9d (2026-05-26): cluster cosine embedding voyage-3.

    Step:
      1. Round-robin fallback se chunks < 3 × moduli (invariato).
      2. embed_query(MODULE_QUERY_EXPANSIONS[title] OR title) per ogni modulo.
      3. Per ogni chunk: cosine(module_embed, chunk.embedding) per ogni modulo,
         sort desc, vince max. Loggia top-3 + margin + thematic_winner per CSV.
      4. Rebalance_min/max invariati.
      5. CSV dump in output/cluster_logs/cluster_scores_{course_id}.csv.

    Ritorna (assignment, score_log_rows).

    NON sostituisce distribute_chunks_to_modules() vecchia (mantenuta per
    retrocompat smoke test). Il caller in research_agent() switcha esplicito.
    """
    from app.services.ingestion_service import embed_query as _embed_query

    result: dict[int, list[NormativeChunk]] = {
        m.module_index: [] for m in pacing_plan.modules
    }
    log_rows: list[dict[str, object]] = []

    # 1. Round-robin fallback
    if len(chunks) < len(pacing_plan.modules) * 3:
        module_indices = [m.module_index for m in pacing_plan.modules]
        for i, chunk in enumerate(chunks):
            target = module_indices[i % len(module_indices)]
            result[target].append(chunk)
        return result, log_rows

    # 2. Embed query per ogni module title (con prosa expansion o fallback nudo)
    module_query_embeds: dict[int, list[float]] = {}
    for m in pacing_plan.modules:
        query_text = MODULE_QUERY_EXPANSIONS.get(m.title, m.title)
        try:
            module_query_embeds[m.module_index] = await _embed_query(query_text)
        except Exception as exc:
            logger.warning(
                "module_query_embed_failed",
                module_index=m.module_index,
                title=m.title,
                error=str(exc),
            )
            module_query_embeds[m.module_index] = []  # cosine → 0 ovunque

    # 2b. Batch lookup degli embedding dei chunks (NormativeChunk non li
    # carica per default — search_chunks selectiona solo i campi essenziali
    # per performance). Una sola query SQL.
    chunk_embeddings: dict[str, list[float]] = {}
    if pool is not None:
        try:
            chunk_ids = [c.chunk_id for c in chunks if c.chunk_id]
            if chunk_ids:
                rows = await pool.fetch(
                    "SELECT id::text AS id, embedding::text AS emb "
                    "FROM regulation_chunks WHERE id = ANY($1::uuid[])",
                    chunk_ids,
                )
                for r in rows:
                    raw = r["emb"]
                    if raw and raw.startswith("[") and raw.endswith("]"):
                        # pgvector ritorna "[0.1,0.2,...]" come testo
                        try:
                            vec = [float(x) for x in raw[1:-1].split(",")]
                            chunk_embeddings[r["id"]] = vec
                        except ValueError:
                            pass
                logger.info(
                    "chunk_embeddings_loaded",
                    requested=len(chunk_ids),
                    loaded=len(chunk_embeddings),
                )
        except Exception as exc:
            logger.warning("chunk_embeddings_load_failed", error=str(exc))

    # 3. Cluster: per ogni chunk, cosine vs ogni module, max vince.
    # FIX #30.9d-rev2 (analista 2026-05-26 Q2): thematic_score tolto dal path
    # principale (28/30 agree con cosine sul corpus reale → dead weight).
    # Sopravvive SOLO come fallback per chunks senza embedding (edge case).
    # Raccogliamo `chunk_margins` per il rebalance margin-aware (Q3).
    chunk_margins: dict[str, float] = {}
    for chunk in chunks:
        chunk_emb = chunk_embeddings.get(chunk.chunk_id)
        if not chunk_emb:
            # Chunk senza embedding lookup → fallback thematic (raro)
            best = max(
                pacing_plan.modules,
                key=lambda m: _thematic_score(_normalize_words(m.title), chunk),
            )
            result[best.module_index].append(chunk)
            chunk_margins[chunk.chunk_id] = 0.0  # spostabile (no segnale cosine)
            continue

        scores = [
            (m.module_index,
             _cosine(module_query_embeds[m.module_index], chunk_emb))
            for m in pacing_plan.modules
        ]
        scores.sort(key=lambda x: -x[1])  # desc

        winner_idx, winner_score = scores[0]
        runner_up_idx, runner_up_score = scores[1] if len(scores) > 1 else (-1, 0.0)
        third_idx, third_score = scores[2] if len(scores) > 2 else (-1, 0.0)
        margin = winner_score - runner_up_score
        chunk_margins[chunk.chunk_id] = margin

        log_rows.append({
            "chunk_id": chunk.chunk_id,
            "winner_module": winner_idx,
            "winner_score": round(winner_score, 4),
            "runner_up_module": runner_up_idx,
            "runner_up_score": round(runner_up_score, 4),
            "third_module": third_idx,
            "third_score": round(third_score, 4),
            "margin": round(margin, 4),
            "pinned": int(margin >= MARGIN_PINNED_THRESHOLD),
            "body_len": len(chunk.body),
            "tag_actual": ",".join(chunk.tags or []),
            "hierarchy": (chunk.hierarchy_path or "")[:80],
            "input_type_query": "query",
        })

        result[winner_idx].append(chunk)

    # 4. Rebalance margin-aware (FIX #30.9d-rev2 Q3). Sposta SOLO chunks a
    # margin basso (trasversali), pinned restano nel modulo di assegnazione
    # cosine. Su E2E #11 4 chunks erano stati rimescolati ignorando il tema —
    # ora restano dove cosine li ha messi se margin alto.
    _rebalance_min_margin_aware(result, chunk_margins, min_per_module=3)
    avg_per_module = len(chunks) // max(len(pacing_plan.modules), 1)
    _rebalance_max_margin_aware(result, chunk_margins, max_per_module=avg_per_module + 5)

    # 5. Log per-modulo (diagnostic, mantenuto da #30.9c)
    for m in pacing_plan.modules:
        n = len(result[m.module_index])
        sample_tags: list[str] = []
        for c in result[m.module_index][:20]:
            sample_tags.extend(c.tags or [])
        from collections import Counter
        top_tags = Counter(sample_tags).most_common(5)
        logger.info(
            "chunk_distribution_per_module_cosine",
            module_index=m.module_index,
            module_title=m.title,
            n_chunks=n,
            top_tags=dict(top_tags),
        )

    # 6. CSV dump per gap analysis con analista
    if log_rows:
        import csv
        import pathlib
        out_dir = pathlib.Path("output/cluster_logs")
        out_dir.mkdir(parents=True, exist_ok=True)
        cid_safe = (course_id or "noid").replace("/", "_").replace("\\", "_")
        csv_path = out_dir / f"cluster_scores_{cid_safe}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(log_rows[0].keys()))
            w.writeheader()
            w.writerows(log_rows)
        logger.info(
            "cluster_scores_csv_written",
            path=str(csv_path),
            rows=len(log_rows),
            course_id=course_id,
        )

    return result, log_rows


def distribute_chunks_to_modules(
    chunks: list[NormativeChunk],
    pacing_plan: PacingPlan,
) -> dict[int, list[NormativeChunk]]:
    """[DEPRECATED #31.1 — 2026-05-27]: sostituita da
    ``retrieve_chunks_per_module()``. Mantenuta come fallback storico
    pre-cosine (#30.9c thematic-only). Non più chiamata dal
    research_agent moderno.

    --- DOCSTRING ORIGINALE ---

    Distribute chunks to modules by thematic similarity (FIX #30.9c).

    Algoritmo (3 livelli):
    1. Round-robin fallback se chunks < 3*moduli (poche fonti, evita
       degeneration cluster).
    2. Cluster tematico via `_thematic_score`: tags×3 + hierarchy×2 +
       article×1 + body×0.5. Score più alto → assegnazione. Tiebreak su
       lunghezza body (più corto = più focalizzato).
    3. Rebalance min/max esistenti (invariati): garantisce 3-N+5 chunk
       per modulo, ridistribuisce da over a under.

    Prima del FIX #30.9c (E2E #8 misurato): moduli mescolavano 3-5 temi
    perché `_keyword_overlap(title, body)` su body ubiquitario ("formazione"
    "lavoratore" "sicurezza" matchano TUTTI i moduli) → assegnazione
    pseudo-random. Ora i `tags[]` specifici dei chunk (es. ["DPI","calzature"])
    guidano l'assegnazione al modulo più tematicamente vicino.
    """
    result: dict[int, list[NormativeChunk]] = {
        m.module_index: [] for m in pacing_plan.modules
    }

    if len(chunks) < len(pacing_plan.modules) * 3:
        # Too few chunks for thematic clustering → round-robin
        module_indices = [m.module_index for m in pacing_plan.modules]
        for i, chunk in enumerate(chunks):
            target = module_indices[i % len(module_indices)]
            result[target].append(chunk)
        return result

    # Pre-compute module title keyword sets (UNA volta sola)
    module_word_sets: dict[int, set[str]] = {
        m.module_index: _normalize_words(m.title) for m in pacing_plan.modules
    }

    # Thematic assignment con score-based ranking
    for chunk in chunks:
        scores = [
            (m.module_index, _thematic_score(module_word_sets[m.module_index], chunk))
            for m in pacing_plan.modules
        ]
        # Trova il modulo con score più alto. Tiebreak: lunghezza body
        # crescente (chunk più corti → più focalizzati su un tema specifico).
        scores.sort(key=lambda x: (-x[1], len(chunk.body)))
        best_module_idx = scores[0][0]
        # Se TUTTI i moduli hanno score 0 (zero metadati match), fallback su
        # keyword overlap body classico (back-compat con vecchio comportamento).
        if scores[0][1] == 0.0:
            best_module = max(
                pacing_plan.modules,
                key=lambda m: _keyword_overlap(m.title, chunk.body),
            )
            best_module_idx = best_module.module_index
        result[best_module_idx].append(chunk)

    # Guarantee a minimum coverage per module
    _rebalance_min(result, min_per_module=3)

    # Prevent over-population from generic titles
    avg_per_module = len(chunks) // max(len(pacing_plan.modules), 1)
    _rebalance_max(result, max_per_module=avg_per_module + 5)

    # Diagnostic: log distribution per modulo
    import structlog as _sl
    _logger = _sl.get_logger()
    for m in pacing_plan.modules:
        n = len(result[m.module_index])
        sample_tags: list[str] = []
        for c in result[m.module_index][:20]:
            sample_tags.extend(c.tags or [])
        from collections import Counter
        top_tags = Counter(sample_tags).most_common(5)
        _logger.info(
            "chunk_distribution_per_module",
            module_index=m.module_index,
            module_title=m.title,
            n_chunks=n,
            top_tags=dict(top_tags),
        )

    return result


# ─────────────────────────────────────────────────────────────────────
# Research Agent — LangGraph node (BP §05.4)
# ─────────────────────────────────────────────────────────────────────


async def research_agent(state: NexusPipelineState) -> dict[str, object]:
    """RAG retrieval + pacing + chunk distribution per module.

    Pydantic validation at the input boundary (rehydrate ``course_request``
    into ``CourseRequest``) and at the output boundary (build a
    ``CourseContext`` Pydantic model before serialising).

    Returns ONLY the fields this node writes (langgraph-fundamentals
    ``fix-state-must-return-dict``): ``course_context`` and ``pacing_plan``.
    The reducers on ``completed_modules`` / ``errors`` are not touched here.
    """
    # ═══ INPUT VALIDATION ═══
    request = CourseRequest(**state["course_request"])
    pool = get_pool()
    knowledge_repo = KnowledgeRepository(pool)

    # 1. Resolve slug → UUID (raises ValueError if any slug is missing)
    catalog_entry = COURSE_CATALOG[request.course_type]
    regulation_slugs_raw = catalog_entry["regs"]
    assert isinstance(regulation_slugs_raw, list)
    regulation_slugs: list[str] = [str(s) for s in regulation_slugs_raw]
    regulation_ids = await knowledge_repo.resolve_slugs_to_ids(regulation_slugs)

    # ═══ REGIONAL VALIDATION ═══
    # Courses flagged ``"regional": True`` in COURSE_CATALOG (e.g. HACCP)
    # REQUIRE a specific region (not "NAZIONALE"). CourseRequest.region
    # defaults to "NAZIONALE", so this guard catches the wizard-default
    # case for a regional course (BP §05.4).
    if catalog_entry.get("regional") and request.region == "NAZIONALE":
        raise ValueError(
            f"Il tipo corso '{request.course_type}' richiede la specifica della regione "
            f"(es. 'LAZIO', 'LOMBARDIA'). Il valore 'NAZIONALE' non è valido per corsi regionali. "
            f"Selezionare una regione nel wizard prima di generare."
        )

    # 2. Build the RAG query embedding — SEMANTIC, not slug-based (D-20).
    #    Concatenate catalog title + default module names so the query is
    #    natural-language Italian (high cosine similarity with the indexed
    #    normative chunks).
    default_modules_raw = catalog_entry.get("default_modules", [])
    assert isinstance(default_modules_raw, list)
    default_modules: list[str] = [str(m) for m in default_modules_raw]
    title_str = str(catalog_entry["title"])
    query_parts = [title_str] + default_modules
    query = " ".join(query_parts)
    # FIX #31.1 (2026-05-27): pacing PRIMA del retrieval — serve
    # module_titles per i N retrieval indipendenti.
    module_titles = default_modules if default_modules else None
    pacing_plan = PacingEngine().calculate(
        request.duration_hours, request.slide_density, module_titles=module_titles
    )
    _course_id_for_log = str(state.get("course_request", {}).get("id", "noid"))

    # FIX #31.1 GUARD (analista review rischio #3): se module_titles is None
    # (corso "sperimentale" senza catalogo), gli N retrieval embedderebbero
    # "Modulo 1..N" senza significato semantico → collasso 0×N visto su
    # 12-moduli (#30.9e). Per quei casi resta il flusso legacy global +
    # cluster cosine + rebalance.
    if module_titles is None:
        logger.info(
            "research_legacy_fallback",
            reason="no_catalog_module_titles",
            course_type=request.course_type,
        )
        query_embedding = await voyage_embed_with_retry(query)
        top_k = max(30, int(request.duration_hours * 10))
        chunks = await knowledge_repo.search_chunks(
            query_embedding=query_embedding,
            regulation_ids=regulation_ids,
            region=request.region,
            top_k=top_k,
        )
        if len(chunks) < 5:
            raise ValueError(
                f"RAG insufficiente (legacy path): solo {len(chunks)} chunk "
                f"trovati per {regulation_slugs}."
            )
        chunks = [
            c for c in chunks
            if c.relevance_score and c.relevance_score > MIN_RELEVANCE
        ]
        if len(chunks) < 5:
            raise ValueError(
                f"RAG post-filtro insufficiente (legacy): {len(chunks)} chunk "
                f"con rilevanza > {MIN_RELEVANCE}."
            )
        chunks_by_module, _cluster_scores = await distribute_chunks_to_modules_cosine(
            chunks, pacing_plan, course_id=_course_id_for_log, pool=pool,
        )
    else:
        # FIX #31.1 PATH: N retrieval indipendenti, uno per modulo.
        # Il filtro MIN_RELEVANCE è applicato DENTRO la funzione PRIMA
        # della dedup (cautela #4 analista review 2: chunks_by_module
        # e chunks (post _flatten_unique) devono vedere lo stesso
        # insieme — disallineamento silenzioso altrimenti).
        chunks_by_module = await retrieve_chunks_per_module(
            pacing_plan=pacing_plan,
            regulation_ids=regulation_ids,
            region=request.region,
            knowledge_repo=knowledge_repo,
            # FIX #31.8 LEVA A (2026-05-27, analista review 11): top_k
            # scalabile con duration_hours per coprire scaling fino a
            # 32h del catalogo cliente. Storia:
            # - #31.2 fissò top_k=70 calibrato su 4h × 4 moduli (E25,
            #   Generale 4h: ognuno ~50 chunk post-dedup).
            # - Demo #3 Preposti 8h × 6 moduli ha rivelato top_k=70
            #   sotto-dimensionato: M3 "Incidenti mancati" 5 chunk.
            # - Formula: top_k = min(150, int(35 + 8 * duration_hours))
            #   4h → 67 (≈ vecchio 70, retrocompat)
            #   8h → 99 (+41% vs vecchio, copre 6 moduli stretti)
            #   16h → 163 → cap 150
            #   32h → 291 → cap 150 (mitigato da B+C)
            # search_chunks è O(log N) su HNSW pgvector → costo
            # trascurabile (~+30s atteso su 8h, irrilevante su 15 min).
            top_k_per_module=min(150, int(35 + 8 * request.duration_hours)),
            min_relevance=MIN_RELEVANCE,
        )

        # Ricostruisco `chunks` come unione deduplicata per
        # CourseContext.chunks (audit + fingerprint). Il filtro relevance
        # è già stato applicato dentro retrieve_chunks_per_module → qui
        # solo gate "abbastanza chunk totali post filter+dedup".
        chunks = _flatten_unique(chunks_by_module)
        if len(chunks) < 5:
            raise ValueError(
                f"RAG insufficiente post per-module retrieval (#31.1): solo "
                f"{len(chunks)} chunk con rilevanza > {MIN_RELEVANCE}. "
                f"Allargare MODULE_QUERY_EXPANSIONS o verificare corpus."
            )

    # 5. Retrieve stylistic patterns from Level 2
    style_patterns = await knowledge_repo.get_style_patterns(
        course_type=request.course_type,
        target=request.target.value,
    )

    # ═══ OUTPUT VALIDATION ═══
    context = CourseContext(
        chunks=chunks,
        chunks_by_module=chunks_by_module,
        pacing_plan=pacing_plan,
        style_patterns=style_patterns,
        regulation_ids=regulation_ids,
        regulation_slugs=regulation_slugs,
    )

    # FIX #31.1: top_k esiste solo nel ramo legacy (module_titles is None).
    # Nel ramo per-modulo, ogni modulo ha il suo top_k_per_module
    # (70 dopo FIX #31.2, era 45 in #31.1).
    # Riporto entrambi nel log per coerenza.
    logger.info(
        "research_completed",
        chunks=len(chunks),
        chunks_by_module_sizes={
            k: len(v) for k, v in chunks_by_module.items()
        },
        modules=len(pacing_plan.modules),
        style_patterns=len(style_patterns),
        retrieval_mode="per_module" if module_titles else "legacy_global",
    )

    return {
        "course_context": context.model_dump(),
        "pacing_plan": pacing_plan.model_dump(),
    }
