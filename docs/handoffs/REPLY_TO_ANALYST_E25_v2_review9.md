Hai colto la patologia esatta. Te la conferma il codice: il truncate gentile in check_slots stava mutando i valori PRIMA che _compute_uniform_font_size li leggesse, e lo shrink dimensionava il font sul valore lungo intero MENTRE il "…" sopravviveva sul valore corto già clippato. Erano due meccanismi sovrapposti che si davano fastidio a vicenda.

Fix applicato (#31.7A v2): check_slots ora è validazione strutturale pura, zero mutazioni — solo gate su template_name valido e slot mancanti. Il truncate è stato spostato ESCLUSIVAMENTE dentro _compute_uniform_font_size e scatta solo se uniform_font == 16pt (al floor). Sopra il floor, ZERO truncate, qualsiasi sia la lunghezza dei label.

═══════════════════════════════════════════════════════════════════
PROVE PROGRAMMATICHE
═══════════════════════════════════════════════════════════════════

Ho aggiunto un test che riproduce esattamente la patologia che mi hai
mostrato (M1/idx15): label 19c "Valutazione rischio" + label 26c
"Formazione e addestramento" stesso diagramma. Pre-fix v2: il 19c era
truncato a "Valutazione risch…" mentre il 26c restava intero. Post-fix v2:
ENTRAMBI interi a font 19pt uniforme. Test verde.

Totale test: 32/32 verdi (16 unit/integration sul font-shrink, 15 sui
suffissi normativi pre-esistenti, 1 aggiornato per riflettere la nuova
logica). Zero regressioni.

Verifica diretta sui 4 casi critici del corso E25 (script su DB reale,
non simulato):

  M1/idx15 "Processo di selezione DPI" → 19pt, ZERO ELLIPSIS
    label_1 (19c): "Valutazione rischio"            ← era truncato pre-v2
    label_2 (19c): "Scelta DPI adeguati"            ← era truncato pre-v2
    label_3 (26c): "Formazione e addestramento"     ← intero come prima
    label_4 (24c): "Controllo e sorveglianza"

  M3/idx69 "Flusso sistemi di comando" → 20pt, ZERO ELLIPSIS
    label_1 (25c): "Progettazione dispositivi"
    label_2 (21c): "Posizionamento sicuro"          ← era truncato pre-v2
    label_3 (23c): "Segnali visivi/acustici"
    label_4 (14c): "Blocco comandi"

  M3/idx29 "Combinazioni di segnaletica" → 25pt, ZERO ELLIPSIS
    label_1 (25c): "Segnale Colore o Cartello"
    label_2 (27c): "Segnali Luminosi o Acustici"
    label_3 (26c): "Segnali Gestuali e Verbali"     ← test verbatim del tuo gate

  M0/idx9 "Processo gestione rischio specifico" → 21pt, ZERO ELLIPSIS
    label_1 (22c): "Identificazione rischi"
    label_2-4: tutti interi

═══════════════════════════════════════════════════════════════════
DISTRIBUZIONE FONT POST v2 (vs v1 in parentesi)
═══════════════════════════════════════════════════════════════════

  34pt: 3 (era 4)  ← uno è sceso a 29pt perché aveva slot 20c+ da inscatolare
  29pt: 1 (era 0)
  28pt: 1 (era 8)  ← molti sono scesi perché ora shrink scatta SEMPRE per
                     far entrare gli slot, invece di lasciarli al default
                     + ellipsis sul corto
  26pt: 1 (era 0)
  25pt: 3 (era 1)
  24pt: 4 (era 0)
  23pt: 1 (era 1)
  22pt: 2 (era 2)
  21pt: 4 (era 4)
  20pt: 1 (era 1)
  19pt: 1 (era 1)

Distribuzione più "stretta", più diagrammi tra 24-29pt (zona dolce per
leggibilità). Solo 2/22 sotto 21pt, zero al floor 16pt. ZERO ELLIPSIS
in TUTTI i 22 diagrammi.

═══════════════════════════════════════════════════════════════════
FILE NUOVI SUL DESKTOP (sostituisci i precedenti)
═══════════════════════════════════════════════════════════════════

- CFP_4h_E25_REBUILD_31.7A_v2.pptx (50 MB)
- CFP_4h_E25_REBUILD_31.7A_v2.pdf (0.4 MB)
- Cartella CFP_E25_diagrams_v2_review9/ con 22 PNG (puliti, solo v2)

I PNG con font basso (M1_idx015_19pt e M3_idx069_20pt) sono quelli da
ricontrollare per primi: voglio sentirmi dire che vedi "Valutazione
rischio" e "Posizionamento sicuro" INTERI nel box, senza puntini. Se
quello è verde, la patologia review 9 è chiusa e i diagrammi sono il
gate finale superato.

═══════════════════════════════════════════════════════════════════
PROPOSTA OPERATIVA SUI 3 CORSI DEMO (richiesta esplicita)
═══════════════════════════════════════════════════════════════════

L'utente propone di USARE QUESTO STESSO CORSO E25 (rebuild v2) come
PRIMO dei 3 demo cliente, invece di rigenerarne uno nuovo dello stesso
tipo. Razionale: è già stato passato sotto tutti i fix #31.x, l'hai
revisionato visivamente, è "il file più curato del progetto". Risparmio:
~10 minuti di pipeline + cache prompt.

D1. OK usare E25 v2 come Demo #1 (sicurezza_lavoratori_specifica_basso
    4h)? Se sì, ne servono solo altri 2 (vedi sotto).

Inventario catalogo + corpus disponibile in DB:

  Demo CANDIDATI per cliente corsi8108 (basato su catalogo configurato):
    A. sicurezza_lavoratori_specifica_basso 4h  → ✅ E25 v2 esiste già
    B. sicurezza_lavoratori_generale 4h         → ✅ pronto (stesse normative)
    C. primo_soccorso_gruppo_b_c 8h             → ⚠️ vedi nota corpus
    D. primo_soccorso_gruppo_a 10h              → ⚠️ vedi nota corpus
    E. antincendio_livello_1 4h                 → ❌ manca DM 02/09/2021 in DB
    F. haccp_addetto 4-8h                       → ❌ manca Reg CE 852/2004 in DB
    G. preposti 8h                              → ✅ pronto

  Normative in DB (n_chunks):
    - D.Lgs 81/08              1819 chunks  ← base solida
    - ASR 17/04/2025            133 chunks  ← buona copertura
    - ASR 21/12/2011             27 chunks  ← residuo (legacy)
    - DM 388/2003 Primo Soccorso 23 chunks  ⚠️ POCHI per 8h
    - ASR 07/07/2016              1 chunk   ← inutile (RSPP/ASPP)

D2. Per Demo #2 propongo: "Formazione Generale Lavoratori 4h"
    (sicurezza_lavoratori_generale). Stesse 2 normative di E25 (D.Lgs
    81/08 + ASR 2025), 4 moduli diversi (Concetti rischio, Prevenzione
    protezione, Organizzazione prevenzione, Diritti e doveri). La
    pipeline è esattamente la stessa di E25, idem aspettativa
    tempo/qualità. Va bene come Demo #2?

D3. Per Demo #3 il candidato classico cliente è "Primo Soccorso Gruppo
    B/C 8h" (primo_soccorso_gruppo_b_c). MA ho un problema potenziale
    da sottoporti: il corpus DM 388/2003 ha solo 23 chunk in DB, e con
    8h x 6 moduli = ~640 slide attese, anche con D.Lgs 81/08 dietro
    siamo a ~80 chunk per modulo desiderati (top_k=70 nostro default)
    contro 23 disponibili sull'unica fonte tematica vera per Primo
    Soccorso. Il rischio è grab-bag (M3 Segnaletica #19 sotto altra
    forma): i moduli "Patologie acute" e "Traumi" si ritrovano a
    pescare da art. 28 D.Lgs sul DVR perché DM 388 finisce dopo 23
    chunk. Le opzioni:

    D3a. Procediamo con Primo Soccorso 8h così com'è e accettiamo che
         possa esserci grab-bag sui moduli sanitari. Lo verifichi tu sul
         PPTX e decidiamo se va al cliente o se serve fix.

    D3b. Sostituiamo Primo Soccorso con "Preposti 8h" (preposti) che ha
         normative ampie (1952 chunk totali tra D.Lgs 81/08 + ASR 2025)
         e 6 moduli su soggetti/relazioni/fattori rischio/incidenti/
         comunicazione/valutazione. Profilo richiesto cliente generico,
         non specialistico-sanitario.

    D3c. Ingeriamo D.M. del Ministero della Salute più ampi su Primo
         Soccorso per rinforzare corpus DM 388 (~1-2h di lavoro di
         ingestione PDF — ho già il codice di ingestione, mi servono i
         PDF). Poi rigenero. Più solido ma più lento.

D4. Procedura di validazione dei 3 demo: dopo che li produco, tu li
    apri uno per uno e mi dai un OK/KO per ognuno. Eventuali fix
    localizzati li applico via Course Studio (l'editor in-app) senza
    rigenerare l'intero corso. Va bene questa procedura?

D5. Su cosa mi serve sapere PRIMA di produrre i 2/3 corsi, dato tutto
    quello che abbiamo cambiato (#31.1 → #31.7A v2): c'è qualche
    aspetto della pipeline corrente di cui tu vuoi che verifichi ancora
    una cosa specifica (es. ricontrollare che il sub-batch recovery
    funzioni anche sui corsi 8h, o che lo SPREAD intra-modulo regga su
    6 moduli invece di 4)? Oppure consideri la pipeline post-#31.7A v2
    sufficientemente collaudata da poter procedere a fiducia con i 2-3
    corsi e poi giudicare a output?

═══════════════════════════════════════════════════════════════════

In attesa del tuo OK sui PNG v2 + risposte D1-D5. Appena hai detto sì
sui diagrammi, lancio i corsi che mi dici (in parallelo dove
possibile, asyncio.Semaphore(1) permettendo), te li mando uno per uno
per validazione, e poi chiudiamo con Chrome DevTools + commit + deploy.
