3 demo pronti sul Desktop. Demo #1 e #2 sono pipeline 4h × 4 moduli (zona collaudata), Demo #3 è il PRIMO RUN 8h × 6 moduli — territorio nuovo come avevi anticipato — e ha rivelato ESATTAMENTE la patologia di scaling che temevamo. Te lo presento in modo strutturato perché stiamo deliberando una decisione che vale fino a 32h (catalogo cliente arriva lì).

═══════════════════════════════════════════════════════════════════
FILE SUL DESKTOP
═══════════════════════════════════════════════════════════════════

- CFP_4h_E25_REBUILD_31.7A_v2.pptx  (50 MB, 336 slide, Demo #1 = Specifica 4h già revisionato e approvato da te)
- DEMO2_Generale_4h.pptx             (42 MB, 334 slide)
- DEMO2_Generale_4h.pdf
- DEMO3_Preposti_8h.pptx             (76 MB, 664 slide)
- DEMO3_Preposti_8h.pdf

═══════════════════════════════════════════════════════════════════
METRICHE TECNICHE — confronto sintetico
═══════════════════════════════════════════════════════════════════

                              Demo #1 (E25)   Demo #2 (Generale)  Demo #3 (Preposti)
Course type                   Specifica 4h    Generale 4h         Preposti 8h
Moduli                        4               4                   6
Slide totali                  336             334                 664
Tempo pipeline                9m 36s          10m 54s             15m 19s
Diagrammi totali              22              19                  35
Diagram fallback (post #31.7A)  0/22 (0%)     0/19 (0%)           0/35 (0%)
Image fallback Pexels         0               0                   34 ⚠️
batches_failed                0               0                   0
sub_batch_recovered           0               0                   0
reasks                        0               0                   0

Lo scaling tempo è SANO (4h → 8h = +60% tempo per +100% durata, sotto-lineare
grazie a parallelism research_agent). Diagrammi a 100% catalog su tutti
e 3. Sub-batch recovery e reask MAI attivati (pipeline regge meccanica).

═══════════════════════════════════════════════════════════════════
COSA TI CHIEDO DI VALIDARE — slide per slide, su entrambi i 4h e 8h
═══════════════════════════════════════════════════════════════════

Per OGNUNO dei 3 PPTX, voglio il tuo verdetto su:

A. CONTENUTO SLIDE
   - Bullet sostanziali (citano articoli, allegati, misure concrete) o
     fuffa generica ("è importante", "bisogna fare attenzione")?
   - source_chunk_ids/note speaker hanno riferimenti coerenti al testo?
   - Ripetizioni di concetti riconoscibili in lettura sequenziale?

B. ORGANIZZAZIONE E COERENZA MODULI
   - Demo #1 (Specifica 4h): M0/M1/M2/M3 = Rischi specifici / DPI /
     Procedure emergenza / Segnaletica → ogni modulo è on-topic?
   - Demo #2 (Generale 4h): M0/M1/M2/M3 = Concetti rischio / Prevenzione
     protezione / Organizzazione prevenzione / Diritti e doveri →
     ognuno on-topic? Nessuna deriva?
   - Demo #3 (Preposti 8h): M0-M5 = Principali soggetti / Relazioni /
     Fattori rischio / **INCIDENTI INFORTUNI MANCATI** / Comunicazione /
     Valutazione rischi → M3 in particolare ti aspetto perché c'è la
     patologia che descrivo sotto. Gli altri 5?

C. IMMAGINI (Demo #3 ha 34 branded_fallback specificatamente)
   - Per Demo #1 e #2: immagini contestuali al titolo della slide? dedup?
   - Per Demo #3: i 34 branded_fallback sono su CONTENT_IMAGE (non
     diagrammi) — Pexels non ha trovato foto per "soggetti del sistema
     prevenzione", "relazioni", "comunicazione" (temi astratti, no
     visual concreto). I branded sostituiscono. Cosmeticamente sopportabile
     o ti aspetta che un Preposti 8h abbia molte foto stock astratte?

D. DIAGRAMMI (zero fallback su tutti 3 grazie a #31.7A v2)
   - Demo #1: 22 diagram → già verificati nella review 10, font 19-34pt
   - Demo #2: 19 diagram → tutti renderizzati, font 16-32pt (1 al floor 16pt)
   - Demo #3: 35 diagram → tutti renderizzati, font 16-32pt (3 al floor 16pt)
   - Verifica visiva richiesta su quelli al floor 16pt (vedi sotto Q3).

E. QUIZ e CASE STUDY
   - Opzioni quiz plausibili, distrattori sensati, risposta corretta evidente?
   - Case study scenario credibile, domanda di chiusura ragionata?

F. BOOKENDS + BRANDING
   - INTRO/INDICE/MODULE_OPEN/CLOSE/RECAP/CERTIFICATE coerenti?
   - Branding C.F.P. Montessori uniforme?

═══════════════════════════════════════════════════════════════════
COSA HO TROVATO DAI LOG DEL DEMO #3 (la cosa importante)
═══════════════════════════════════════════════════════════════════

Telemetry per_module retrieval (ti riporto verbatim):

  per_module_kept       = {0:59, 1:23, 2:55, 3:5, 4:30, 5:29}
  lost_to_other_module  = {0:11, 1:47, 2:15, 3:5, 4:40, 5:41}
  relevance_filter_M3   = 60/70 chunk droppati (top_score 0.45)

Tradotto:

  M0 "Principali soggetti del sistema di prevenzione"     → 59 chunk ✅
  M1 "Relazioni tra i vari soggetti"                       → 23 chunk ⚠️ (47 persi a dedup verso M0)
  M2 "Definizione e individuazione dei fattori di rischio" → 55 chunk ✅
  M3 "Incidenti e infortuni mancati"                       → 5  chunk ❌ CATASTROFICO
  M4 "Tecniche di comunicazione e sensibilizzazione"       → 30 chunk ⚠️ (40 persi a dedup)
  M5 "Valutazione dei rischi dell'azienda"                 → 29 chunk ⚠️ (41 persi a dedup)

Patologia M3: 5 chunk per 108 slide attese → 21 slide/chunk. Il
content_agent ha riempito ripetendo/parafrasando. Il risultato è
osservabile coi tuoi occhi nei titoli M3 di Demo #3, te ne incollo un
estratto pulito (sono 108 slide M3, te ne riassumo i pattern):

  - "Sanzioni per mancata X" → 15+ slide ripetitive (sanzioni DPI
    anticaduta, sanzioni mancata formazione, sanzioni POS, sanzioni
    elaborazione documenti) — la dedup ha lasciato pochi chunk
    "infortuni mancati" e il content_agent ha pescato dalla coda
    "sanzioni" del D.Lgs come riempitivo.
  - "DPI anticaduta" → 7+ slide ripetute identiche
  - "Amianto" → 8 slide OFF-TOPIC (M3 doveva essere "Incidenti e
    infortuni mancati", non "Lavori con amianto")
  - "POS / Piano Operativo Sicurezza" → 5+ slide ripetute
  - On-topic vero ("monitoraggio infortuni mancati / azioni
    correttive / analisi pre-post") → ~10-15 slide su 108

Esempio sequenza 4 titoli consecutivi M3 (slide 41-44):
  41. Raccolta dati infortuni e malattie professionali
  42. Riunioni e buone prassi per la sicurezza
  43. Registrazione degli infortuni: obblighi e dettagli
  44. Riunioni per sicurezza lavoro in cantiere    ← copia 42

Confermo empiricamente la patologia: NON è caso isolato, è scaling.

═══════════════════════════════════════════════════════════════════
LA DIAGNOSI TECNICA (3 cause concomitanti)
═══════════════════════════════════════════════════════════════════

1. `top_k_per_module = 70` è una costante (calibrata per 4h in #31.2).
   A 8h × 6 moduli serve di più, a 32h × 12-16 moduli serve molto di
   più. Top_k NON scala con la durata.

2. `MIN_RELEVANCE = 0.3` statico. Su moduli con tema stretto (M3
   "Incidenti e infortuni mancati" è una NICCHIA del D.Lgs 81/08) la
   soglia 0.3 taglia troppo. Su M3 abbiamo droppato 60/70 chunk
   perché tutti i score erano 0.20-0.29 (vicino ma non sotto soglia).

3. Dedup cosine wins è zero-sum: quando i moduli sono semanticamente
   adiacenti (M0 "Soggetti" e M1 "Relazioni" si sovrappongono per
   forza), il modulo "campione" prende tutti i chunk dei sotto-temi
   comuni e gli altri restano svuotati. A 4h × 4 moduli i temi sono
   abbastanza larghi da non pestarsi. A 6+ moduli stretti diventa fame.

ARITMETICA SCALING:

| Durata | Slide tot | Moduli | Slide/mod | Chunk/mod ideali | Disponibili @ top_k=70 |
|--------|-----------|--------|-----------|------------------|------------------------|
| 4h     | 320       | 4      | 80        | ~53              | 30-50 ✅ (E25, Generale)
| 8h     | 640       | 6      | ~107      | ~71              | 5-59 ⚠️ (M3=5 Preposti)
| 16h    | 1280      | 8-10   | ~128-160  | ~85-107          | crash previsto
| 32h    | 2560      | 12-16  | ~160-213  | ~107-142         | crash critico

A top_k=70 fisso il sistema NON PUÒ fornire più di 70 chunk per
modulo, ma a 32h ne servirebbero ~140. È un limite strutturale.

═══════════════════════════════════════════════════════════════════
TRE LEVE DI FIX POSSIBILI (decisione tua)
═══════════════════════════════════════════════════════════════════

LEVA A — top_k scalabile con durata (1 LOC)
  top_k_per_module = min(150, int(35 + 8 * duration_hours))
  → 4h:67 (≈ attuale), 8h:99, 16h:163→cap 150, 32h:291→cap 150
  Pro: deterministico, retroattivo zero, scala correttamente fino a 16h.
  Contro: a 32h cap 150 è ancora sotto i 140 ideali per modulo stretto.
  Tempo extra: ~0 (search_chunks è O(log N) su HNSW).

LEVA B — MIN_RELEVANCE adattivo per modulo (~10 LOC)
  Se un modulo ha < 30 chunk dopo filtro statico, ricalcola MIN come
  percentile 25 dei chunk del modulo. Su M3 Preposti: 70 chunk con
  score [0.45, 0.41, ..., 0.21] → MIN_AUTO = 0.10 (P25) → da 5 a ~50
  chunk salvati.
  Pro: rimedia il "corpus debole sul tema = modulo svuotato".
  Contro: comportamento dinamico per modulo = più test.
  Tempo extra: ~0.

LEVA C — Dedup quota-aware anti-starvation (~30 LOC)
  Pre-dedup: garantisci una quota minima per modulo (es. 25 chunk).
  La dedup trasferisce SOLO gli eccedenti via cosine winner.
  Pro: nessun modulo scende sotto quota.
  Contro: complessità algoritmica.
  Tempo extra: ~0.

═══════════════════════════════════════════════════════════════════
DOMANDE PER LA DECISIONE
═══════════════════════════════════════════════════════════════════

Q1. Diagnosi delle 3 cause confermata?

Q2. Implemento A+B (1+10 LOC, leve indipendenti, basse complicazioni,
    coprono fino a 16h+) e lascio C come work-item per quando saremo
    su 24h-32h? Oppure A+B+C tutte e tre ora?

Q3. Sui 4 diagrammi al floor 16pt (1 in Demo #2 + 3 in Demo #3):
    apro i PNG e verifico che siano leggibili o "leggibili ma
    sgraziati"? Se sgraziati, è il segnale che è ora di lavorare
    sull'opzione C dei diagrammi (allargare box SVG)?

Q4. Sui 34 branded_fallback CONTENT_IMAGE di Demo #3 (Pexels non
    trova foto per temi astratti Preposti): sopporto e mando, o
    introduco fallback su immagini stock astratte CFP curate per
    quei temi (banner colorato + icona generica)?

Q5. Decisione strategica: per il deploy demo cliente ORA, mando i
    3 PPTX così come sono (con M3 Preposti grab-bag visibile) e
    sviluppiamo A+B in parallelo come fix #31.8 prima del lancio
    pubblico? Oppure tengo Demo #3 in casa, implemento A+B,
    rigenero Preposti 8h, e poi mandiamo tutti e 3 puliti?

Q6. Mando D.M. ministeriali Primo Soccorso extra a ingerire per
    rinforzare corpus DM 388/2003 (23 chunk → ~150) così Primo
    Soccorso 8h diventa generabile pulito? È nel tuo radar o lo
    consideri non urgente per la demo?

═══════════════════════════════════════════════════════════════════

In attesa del tuo verdetto slide-per-slide sui 3 PPTX + risposte
Q1-Q6. Da lì capisco se:
  (a) sblocchi i 3 demo per il cliente AS-IS (Demo #1 sicuro, Demo #2
      probabilmente OK, Demo #3 con caveat M3)
  (b) implemento A+B prima e rigenero Demo #3
  (c) altre direzioni che vedi tu

Mi servono 30 min per A+B se decidi (b). Poi rigenero Demo #3 in
~15 min e te lo rimando.
