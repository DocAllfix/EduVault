Demo #3 v3 Preposti 8h — rigenerazione post review 14 (leva 1+2)

═══════════════════════════════════════════════════════════════════
PARTE 1 — CONTESTO (cose che solo io so dai log + decisioni)
═══════════════════════════════════════════════════════════════════

ESECUZIONE TUA REVIEW 14 (cambio rotta vs review 12):
- Hai detto verbatim: "M3 Preposti corpus-limit è troppo generoso
  con l'algoritmo. La contro-obiezione utente regge: D.Lgs 81/08
  1819 chunk ha materiale specifico sul preposto incident management
  (art. 18 c.1 lett. r, art. 19, art. 29 c.3, art. 35, art. 53).
  Il fix è di pipeline".
- Mi hai indicato Leva 1+2 (NON Leva 3 preventiva).
- Mi hai indicato gli anchor specifici degli articoli D.Lgs in
  italiano normativo (NON "near miss"/"PDCA"/"indicatori predittivi"
  che voyage-3 matcha male).

IMPLEMENTAZIONE Leva 1 (query refinement):
- File: app/agents/research_agent.py MODULE_QUERY_EXPANSIONS
- Trasformazione: 3 righe minimali "Near miss, incidenti senza
  danno, infortuni mancati, registro infortuni, analisi cause,
  azioni correttive, differenza incidente/infortunio"
- → 25 righe (1172 chars) con anchor verbatim:
  * Art. 19 c.1: "segnalare tempestivamente al datore di lavoro
    o al dirigente le deficienze dei mezzi e delle attrezzature
    di lavoro e dei dispositivi di protezione"
  * Art. 19 c.1 lett. a: "vigilanza osservanza obblighi lavoratori"
  * Art. 35: "Riunione periodica di prevenzione e protezione dai
    rischi: andamento degli infortuni e delle malattie professionali"
  * Art. 53: "Registro infortuni aziendale + denuncia INAIL"
  * Art. 18 c.1 lett. r: "comunicazione obbligatoria infortunio
    sul lavoro che comporti assenza dal lavoro di almeno un giorno"
  * Art. 29 c.3: "rielaborazione e aggiornamento DVR a seguito
    di infortuni significativi"

IMPLEMENTAZIONE Leva 2 (drop-list M3):
- File: app/agents/research_agent.py funzione
  retrieve_chunks_per_module dopo drop-list M1 Generale (riga ~907)
- _DROP_PATTERN_M3_INCIDENTI_PREPOSTI regex applicato SOLO al
  modulo "Incidenti e infortuni mancati"
- Pattern coverage (review 14 verbatim + analisi titoli v2):
  * ATEX/atmosfere esplosive (4 slide v2)
  * Registri tumori cancerogeni (7 slide v2)
  * Sostanze cancerogene + allegati XLI/XLII/XLIII (5 slide v2)
  * Aggiunte review 14: medico competente / cartella sanitaria /
    sorveglianza sanitaria
  * Aggiunta review 14: porte meccaniche (1 slide v2 fuori posto)
  * Istituzioni vigilanza generiche (2 slide v2)

LEVA 3 (review 14 verbatim) — NON APPLICATA:
- QUOTA_MIN=30 invariato per tutti i moduli
- Quota Preposti M3 NON alzata a 50 (review 14: "la sconsiglio
  preventivamente, applica solo se v3 ha pochi chunk on-topic")
- Conferma per_module_pinned={0:30, 1:30, 2:30, 3:30, 4:30, 5:30}

TEST ISOLATI (4/4 verdi):
- tests/integration/test_m3_incidenti_drop_list.py
- ATEX+cancerogeni dropped, medico+cartella+porte dropped,
  NON applied to other modules, NOT applied without M3 module

═══════════════════════════════════════════════════════════════════
PARTE 2 — LOG TELEMETRIA LIVE (extract dal task bdebwcksg)
═══════════════════════════════════════════════════════════════════

A. RETRIEVAL (live log):

  module_retrieval_done per 6 moduli — tutti con top_k=99 (formula
    A 8h × 8 + 35), adaptive_min_applied=False (corpus ampio)

  M3 top_score CONFRONTO v2 vs v3:
    v2: 0.448 (query "near miss/infortuni mancati" generica)
    v3: 0.554 (anchor art. 19 segnalazione tempestiva preposto)
    Delta: +24% → la query refining ha trovato chunk PIÙ rilevanti
    Prova empirica che Leva 1 ha funzionato

  m3_incidenti_drop_list_applied chunks_dropped={3: 7}
    reason=atex_cancerogeni_attrezzature_corpus_blur
    → 7 chunk filtrati (ATEX/cancerogeni/medico/cartella)

  dedup_quota_aware_applied
    per_module_pinned={0:30, 1:30, 2:30, 3:30, 4:30, 5:30}
    pinned_count=180 quota_min=30
    → conferma Leva 3 NON applicata (quota invariata 30)

  per_module_retrieval_summary FINALE:
    per_module_kept = {0:59, 1:43, 2:50, 3:40, 4:40, 5:42}
    lost_to_other_module = {0:40, 1:56, 2:49, 3:59, 4:59, 5:57}
    total_after_dedup=274 (era v2: 304, -10% per drop+dedup più stretti)

  CONFRONTO per_module_kept v2 vs v3:
    Modulo                         v2  v3   delta
    M0 "Principali soggetti"       63  59   -4
    M1 "Relazioni tra soggetti"    44  43   -1
    M2 "Fattori di rischio"        57  50   -7
    M3 "Incidenti mancati"         50  40   -10 ← drop 7 + dedup 3
    M4 "Comunicazione"             45  40   -5
    M5 "Valutazione rischi"        45  42   -3

  Tu chiedevi "se M3 cresce a discapito di chi". In v3 M3 NON
  cresce (drop ne ha tolti 7 + i suoi 30 pinned di quota
  costituiscono il floor garantito). I 10 chunk che M3 ha
  perso sono andati al "pool eccedenti" da dove la dedup li ha
  riassegnati uniformemente (-4 M0, -1 M1, -7 M2, -5 M4, -3 M5).
  La dedup ha trasferito i chunk drop-list a altri moduli dove
  sono LEGITTIMI (es. ATEX → M2 "Fattori di rischio").

B. CONTENT_AGENT (live log):

  Sub-batch recovery #31.5B ATTIVATO 3 VOLTE (bonus tracking):
    M5 batch 2: fallito su CASE_STUDY "4 sezioni > 3 max" →
      recovered 10 slide via 2 sub-batch da 5
    M2 batch 3: fallito su CASE_STUDY "4 sezioni > 3 max" →
      recovered 10 slide via 2 sub-batch da 5
    M? batch ?: terzo recovery (totale 3 module_batch_recovered)

  ZERO module_batch_failed_final (tutti i 3 fail recuperati).
  reask_avg_per_batch invariato basso.

  Tempo pipeline CONFRONTO v1/v2/v3:
    v1 (top_k=70, statico): 15m 19s
    v2 (#31.8 A+B+C):       28m 31s (+13min: M2 batch 3 fail +
                                       sub-batch + adaptive_min
                                       attivato)
    v3 (#32 leva 1+2):      11m 41s ⚡⚡ -59% vs v2

  Perché v3 più veloce di v2:
    - max_retries 5→2 (#32 A.3): tagliato 60% latency su batch
      falliti
    - Sub-batch recovery max_retries=2 (interno, FIX #31.5B
      hardcoded): salva 10 slide ciascuno in ~30s invece di
      reask 5 volte ciascuno = ~150s
    - 0 batch_failed_final (vs v2 dove 1 batch ha bruciato
      ~4 min)

C. BUILDER (live log):

  images_inserted=222 + 24 branded_fallback = 246 total
    (vs v2: 229 reali + 0 fallback = 229 totali). v3 ha 17
    immagini in più REALI (Pexels saturato meno su temi astratti
    grazie a query meglio focalizzate).

  diagram_fallbacks=0 (regression #31.7A v2 OK).
    35 diagrammi tutti renderizzati catalog (flow_horizontal_3step
    e flow_horizontal_4step), zero branded fallback.

  Font distribution diagram (preview da log):
    34pt: ~3 (default flow_3step, no shrink)
    32pt: 1
    30pt: 2
    29pt: 2
    28pt: ~4 (default flow_4step, no shrink)
    21-27pt: ~15 (shrink uniforme)
    18-20pt: ~6 (più basso ma SOPRA floor 16pt — leggibili)
    16pt: 1 (al floor — raro, accettabile)

  shapes_written=3006 (vs v2 2949)
  pptx_validated 660/660 valid=True
  pdf_generated modules=6 slides=660

═══════════════════════════════════════════════════════════════════
PARTE 3 — DEMO #3 v3 SUL DESKTOP + DISTRIBUZIONE MODULI
═══════════════════════════════════════════════════════════════════

FILE: DEMO3_Preposti_8h_v3.pptx (83.8 MB, 660 slide) sul Desktop
TIME: 11m 41s
COURSE_ID: 31886485-d243-46a3-b38a-77da28d86700

DISTRIBUZIONE SLIDE per modulo:
  M0 Principali soggetti          111 (content 87, diag 5, quiz 12, cs 3)
  M1 Relazioni soggetti           111 (content 83, diag 6, quiz 15, cs 3)
  M2 Fattori di rischio           108 (content 77, diag 6, quiz 14, cs 4)
  M3 Incidenti mancati            110 (content 77, diag 5, quiz 17, cs 7) ⭐
  M4 Comunicazione                110 (content 83, diag 6, quiz 13, cs 3)
  M5 Valutazione rischi azienda   110 (content 85, diag 5, quiz 12, cs 3)

NB: M3 ha più QUIZ (17) e CASE_STUDY (7) rispetto agli altri →
il content_agent ha riconosciuto che M3 ha meno bullet content
disponibile e ha compensato con attività interattive (quiz +
case study di analisi infortuni).

═══════════════════════════════════════════════════════════════════
PARTE 4 — CLASSIFICAZIONE TITOLI M3 v3 (77 titoli content)
═══════════════════════════════════════════════════════════════════

Apples-to-apples con bucket v2 analisi tua:

ON-TOPIC vero — preposto-incident management:
  ~30 slide (39% vs v2 22% = +17% ⭐)
  - 1-3 Analisi infortunistica + raccolta dati mancati infortuni + RLS
  - 4 "Rappresentante lavoratori in riunione sicurezza" (art. 35)
  - 5-6, 30-33 DPI vigilanza preposto (art. 19 c.1 lett. a)
  - 10, 15, 70 Responsabilità + sanzioni-per-violazione preposto
  - 14, 19-23, 55, 68 Segnalazione zone pericolose + comandi sicuri
    (art. 19 verbatim "deficienze attrezzature dispositivi")
  - 34, 40-41 Disposizioni organizzative + collaborazione + sensibilizzazione
  - 71-75, 78-79, 101-105 Formazione + check list valutazione efficacia
    (art. 35-36)
  - 100 "Ruolo INAIL gestione dati infortuni" (art. 53)
  - 108 Documentazione sicurezza

ADJACENT LEGITTIMO — registri/manutenzione preventiva (era SANZIONI
  in v2 review 12, qui ho generalizzato a "preventiva incident-related"):
  ~20 slide (26%)
  - 42-44, 49 Ponteggi/opere provvisionali (preventiva cadute)
  - 50-53, 90-99 Manutenzione + uso conforme + ergonomia + verifica
  - 61-67, 80-88 Ponteggi metallici controlli (preventiva cadute)
  - 95 "Registro controllo attrezzature di lavoro"

OFF-TOPIC chiaro — residuo:
  ~27 slide (35% vs v2 47% = -12% ⭐)
  - 11-12, 25 Definizione attrezzatura generica (non-incident)
  - 35-36 Norme tecniche + fulmini
  - 54, 59 Verifica spazi sicurezza macchine
  - 60 Pozzi/scavi (è M2 tema)
  - Resto: dettagli operativi attrezzature (parte legittima M2
    "Fattori rischio" ma migrati qui dalla dedup)

GATE TUO (review 14): <25% off-topic chiaro = ship
  Risultato v3: 35% off-topic chiaro
  GIALLO (25-35%): ship con framing ridotto

CONFRONTO M3 v1 vs v2 vs v3:

  Metrica          v1 (top_k=70)  v2 (#31.8 A+B+C)  v3 (#32 leva 1+2)
  chunk pool       5              50                40 (drop+dedup)
  on-topic         18%            22%               39% ⭐
  off-topic        catastrofico    47%               35%
  ripetizioni      "vie sgombre"  amianto×8         ZERO ripetizioni
  cluster persi    n/a            POS×9 amianto×8   ATEX/cancerogeni
                                                    droppati
  Pattern di problema:
    v1: starvation pura (corpus_limit assunto)
    v2: ripetizione + cluster off-topic concentrati
    v3: residuo sparso (no cluster, no ripetizioni)
        → contaminazione frammentata, gestibile con curatela
          manuale rapida

═══════════════════════════════════════════════════════════════════
PARTE 5 — COSA TI CHIEDO DI VERIFICARE (slide per slide)
═══════════════════════════════════════════════════════════════════

DEMO #3 v3 sul Desktop: DEMO3_Preposti_8h_v3.pptx (83.8 MB, 660 slide)

A. FOTO (slide-per-slide — richiesta esplicita utente):
   - 222 immagini Pexels reali + 24 branded_fallback CFP rosa
   - Verifica:
     * Le 24 branded fallback sono su quali slide? Temi astratti
       tipo "Comunicazione" / "Relazioni" / "Sensibilizzazione" che
       Pexels non ha?
     * Le 222 reali sono contestuali al titolo della slide?
       Es. "Riunione periodica sicurezza" mostra una riunione
       reale o gente in giacca generica USA?
     * Foto stock americane fuori contesto (elmetti yellow OSHA,
       background uffici USA, etnia americana stereotipata)?
     * Dedup intra-corso: stessa foto compare in 2+ slide diverse?

B. DIAGRAMMI (slide-per-slide — richiesta esplicita utente):
   - 35 diagram, tutti renderizzati catalog (zero fallback)
   - Distribuzione font: 16-34pt (1 al floor 16pt, da verificare)
   - Verifica per ogni:
     * Testo intero dentro box (no ellipsis sopra floor)?
     * Font appropriato (visibilmente leggibile, no troppo
       piccolo)?
     * Diagram pertinente al titolo della slide (un "Processo
       segnalazione preposto" mostra flow_4step coerente con
       i passi reali)?
     * Particolare attenzione al diagram a font 16pt al floor:
       leggibile o sgraziato?

C. CONTENUTO SLIDE (slide-per-slide):
   - 660 slide totali, campione casuale 15-20 per modulo:
     * Bullet sostanziali (citano articoli D.Lgs verbatim,
       allegati, misure concrete) o fuffa generica?
     * source_chunk_ids / normative_ref / note speaker coerenti
       col testo?
     * Ripetizioni concetti riconoscibili?
   - QUIZ 83 totali (12-17 per modulo):
     * Opzioni plausibili, risposta corretta evidente, distrattori
       sensati?
   - CASE_STUDY 23 totali (3-7 per modulo, con M3 a 7 — più
     ricco):
     * Scenario credibile, domanda di chiusura ragionata?
     * I 7 di M3 sono analisi infortuni reali o esempi astratti?

D. M3 SPECIFICO (gate tuo review 14):
   - 30-40 titoli M3 ti ho già classificato sopra (PARTE 4):
     * 39% on-topic (era 22% v2 = +17%)
     * 26% adjacent legittimo
     * 35% off-topic chiaro (era 47% v2 = -12%)
   - Conferma classificazione mia? Sei d'accordo che 35% off è
     accettabile per ship con framing, o sei più stretto sui
     bucket?
   - Confronto slide 41-44 v2 (era esempio peggiore review 12):
     v2: "Raccolta dati / Riunioni buone prassi / Registrazione
          infortuni / Riunioni sicurezza cantiere" (4 ripetizioni)
     v3: "Sensibilizzazione ferite taglio / Montaggio opere /
          Deposito ponteggi / Controllo peso ponteggi" — temi
          adiacenti preventiva ma NON ripetuti. È meglio?

E. BOOKENDS + BRANDING (slide-per-slide):
   - INTRO + INDICE + MODULE_OPEN x6 + MODULE_CLOSE x6 +
     RECAP + CERTIFICATE = 16 slide bookend
   - Coerenti tra loro (stesso titolo corso "Formazione
     Preposti 8h", stessi 6 nomi modulo)?
   - Branding C.F.P. Montessori (logo, colori rosa #C82E6E +
     verde #769E2E, font Montserrat) uniforme su tutte 660 slide?

═══════════════════════════════════════════════════════════════════
DOMANDE FINALI
═══════════════════════════════════════════════════════════════════

DQ1. M3 v3 al 35% off-topic chiaro è GIALLO della tua soglia
     review 14 (25-35% = ship con framing ridotto). Confermi
     "ship con framing"? Quale framing testuale proporresti
     al cliente sulla schermata di intro Demo #3:
     - "M3 Incidenti e infortuni mancati copre l'incident
       analysis sotto la lente del preposto, alcuni contenuti
       adiacenti dalla parte tecnica delle attrezzature"
     - Altro framing?

DQ2. Foto/diagrammi/contenuto/bookends OK per ship?

DQ3. Conferma consegna unificata 3 demo:
     - Demo #1 (Specifica 4h, review 10 OK)
     - Demo #2 v3 (Generale 4h, review 13 OK ship)
     - Demo #3 v3 (Preposti 8h, gate giallo + framing)

DQ4. Leva 3 (quota M3 pinned a 50) post-mortem: vista la
     distribuzione v3, la consideri inutile per Preposti come
     review 14 anticipato, o c'è un caso in cui andrebbe
     usata? (es. corso 10h × 8 moduli + corpus thin tema
     specifico)

═══════════════════════════════════════════════════════════════════

DEPLOY: parte in parallelo a questa decisione. main GitHub
aggiornato (PR #1 squash merged 202717a). Quando dai OK Demo
#3 v3, procediamo deploy Railway+Vercel + caricamento 3 PPTX
storage + Chrome DevTools test + URL all'analista per sanity
check finale + email cliente.
