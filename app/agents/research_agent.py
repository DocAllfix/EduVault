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
        "Cartelli e segnali di sicurezza sul lavoro: divieto, avvertimento, "
        "prescrizione, salvataggio. Forme geometriche, colori, pittogrammi "
        "ISO. Segnali acustici e luminosi. Posizionamento, visibilità, "
        "manutenzione cartellonistica."
    ),

    # === sicurezza_lavoratori_generale (4 moduli) ===
    "Concetti di rischio": (
        "Concetti fondamentali di rischio, pericolo, danno e probabilità "
        "nei luoghi di lavoro. Valutazione del rischio, matrice di rischio, "
        "rischio residuo, livelli di rischio basso medio alto."
    ),
    "Prevenzione e protezione": (
        "Misure di prevenzione e protezione: gerarchia dei controlli, "
        "eliminazione del rischio, sostituzione, controlli tecnici, "
        "controlli amministrativi. Sorveglianza sanitaria."
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


async def distribute_chunks_to_modules_cosine(
    chunks: list[NormativeChunk],
    pacing_plan: PacingPlan,
    course_id: str = "",
    pool: object | None = None,
) -> tuple[dict[int, list[NormativeChunk]], list[dict[str, object]]]:
    """FIX #30.9d (2026-05-26): cluster cosine embedding voyage-3.

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
    """Distribute chunks to modules by thematic similarity (FIX #30.9c).

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
    query_embedding = await voyage_embed_with_retry(query)

    # 3. Vector search with DYNAMIC top_k scaled by course duration.
    top_k = max(30, int(request.duration_hours * 10))  # 30 for 1h, 80 for 8h
    chunks = await knowledge_repo.search_chunks(
        query_embedding=query_embedding,
        regulation_ids=regulation_ids,
        region=request.region,
        top_k=top_k,
    )

    # ═══ RAG GATE: too few chunks → pipeline aborts ═══
    if len(chunks) < 5:
        raise ValueError(
            f"RAG insufficiente: solo {len(chunks)} chunk trovati per "
            f"{regulation_slugs}. Verificare che l'ingestion sia stata "
            f"completata correttamente per queste normative."
        )

    # ═══ RELEVANCE FILTER ═══
    chunks = [c for c in chunks if c.relevance_score and c.relevance_score > MIN_RELEVANCE]

    if len(chunks) < 5:
        raise ValueError(
            f"RAG post-filtro insufficiente: solo {len(chunks)} chunk con "
            f"rilevanza > {MIN_RELEVANCE}. Verificare la qualità degli embedding."
        )

    # 4. Pre-group chunks per module — semantic titles from COURSE_CATALOG
    module_titles = default_modules if default_modules else None
    pacing_plan = PacingEngine().calculate(
        request.duration_hours, request.slide_density, module_titles=module_titles
    )
    # FIX #30.9d (2026-05-26): nuovo cluster cosine embedding voyage-3.
    # Mantiene rebalance_min/max e round-robin fallback identici. Dumpa CSV
    # in output/cluster_logs/cluster_scores_{course_id}.csv per gap analysis
    # con analista (top-3 scores, margin, body_len, thematic_winner come
    # guardia parallela).
    _course_id_for_log = str(state.get("course_request", {}).get("id", "noid"))
    chunks_by_module, _cluster_scores = await distribute_chunks_to_modules_cosine(
        chunks, pacing_plan, course_id=_course_id_for_log, pool=pool,
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

    logger.info(
        "research_completed",
        chunks=len(chunks),
        top_k=top_k,
        modules=len(pacing_plan.modules),
        style_patterns=len(style_patterns),
    )

    return {
        "course_context": context.model_dump(),
        "pacing_plan": pacing_plan.model_dump(),
    }
