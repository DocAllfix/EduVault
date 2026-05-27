Demo #2 v2 + Demo #3 v2 — analisi finale onesta dopo #31.8 A+B+C

═══════════════════════════════════════════════════════════════════
RIASSUNTO ESECUTIVO IN UNA RIGA
═══════════════════════════════════════════════════════════════════

#31.8 ha funzionato MECCANICAMENTE: tutti i numeri target sono
verdi (per_module_kept ≥30, leve A+B+C tutte attive in log).
Però aprendo i titoli con gli occhi su entrambi i demo emerge
un pattern comune: **la patologia è stata ridotta ma NON eliminata —
è stata spostata**. Il corpus D.Lgs 81/08 ha confini tematici
intrinsecamente sfumati che il retrieval semantico non sa
disambiguare meglio del cosine winner+quota.

BONUS validato live: **sub-batch recovery #31.5B** attivato per la
prima volta in produzione su Demo #3 v2 M2 batch 3 fallito (LLM
emetteva `image.aspect_hint=` come str invece che dict) → 10 slide
salvate via 2 sub-batch da 5 → zero perdita modulo.

═══════════════════════════════════════════════════════════════════
DEMO #2 v2 — Generale 4h
═══════════════════════════════════════════════════════════════════

FILE: DEMO2_Generale_4h_v2.pptx (50.4 MB, 336 slide) sul Desktop
TIME: 12m 14s (vs v1 10m 54s, +13% per leve A+B+C extra)

LOG TELEMETRY:

  Leva A → top_k=67 (formula 4h × 8 + 35) per tutti 4 moduli ✅
  Leva B → adaptive_min_applied=False su tutti 4 (top_score
            0.47-0.65 sopra MIN statico 0.3, nessun rescue necessario)
  Leva C → pinned_count=120 (4 × 30) → ATTIVA su tutti i moduli
  Retrieval finale: per_module_kept={0:60, 1:42, 2:38, 3:40}
  lost_to_other_module={0:7, 1:25, 2:29, 3:27}

CONFRONTO vs Demo #2 v1:
  M0 48 → 60 (+12)
  M1 39 → 42 (+3)
  M2 32 → 38 (+6)
  M3 70 → 40 (-30) ← i 30 chunk Segnaletica sono andati a M0/M2

CLASSIFICAZIONE TITOLI 4 MODULI (analisi onesta):

  M0 "Concetti di rischio" (58 content)
    ✅ ON-TOPIC: ~30 (52%) — tipologie rischio, categorie ATECO,
       valutazione, agenti fisici, sicurezza ambienti
    🟡 ADIACENTE: ~10 (17%) — DPI/segnaletica come esempi
    🔴 OFF-TOPIC: ~18 (31%) ← peggiorato vs v1
       - Medico competente 7 slide (era M3)
       - Sanzioni penali 4 slide (era M3)
       - Verifiche attrezzature 5 slide
       - Sorveglianza sanitaria 2 slide

  M1 "Prevenzione e protezione" (63 content)
    ✅ ON-TOPIC: ~22 (35%) — ponteggi, misure tecniche, livelli
       contenimento, DPI agenti chimici
    🟡 ADIACENTE: ~10 (16%)
    🔴 OFF-TOPIC: ~31 (49%) ← grave
       - Cartella sanitaria/sorveglianza/medico: 18 slide
       - Agenti biologici (registri/vaccinazioni): 11 slide
       - RLS: 1 slide

  M2 "Organizzazione prevenzione" (62 content)
    ✅ ON-TOPIC: ~28 (45%) — SPP, RSPP, ASPP, MOG, SINP, INAIL,
       riunione periodica, comunicazione
    🟡 ADIACENTE: ~12 (19%) — aggiornamento ruoli formativi
    🔴 OFF-TOPIC: ~16 (26%)
       - Cantiere POS: 5 slide (era M0/M1)
       - DPI capelli/occhi/mani: 4 slide (era M1)
       - Verifiche attrezzature: 2 slide
       - Modulo A RSPP formativo: 5 slide

  M3 "Diritti e doveri" (59 content) ⭐
    ✅ ON-TOPIC: ~32 (54%) — formazione, informazione, RLS,
       doveri lavoratore art.19-20
    🟡 ADIACENTE: ~16 (27%) — segnaletica come dovere, formazione
       esplosivi, DPI, scheda sicurezza
    🔴 OFF-TOPIC: ~11 (19%) — sotto la tua soglia 20% ✅
       - locali lavoro, attrezzature operative
    🎯 ZERO slide "Segnaletica" come modulo proprio (era 4 in v1)

DIAGRAMMI: 20 totali
  - 18 catalog regolari (font 16-32pt sano)
  - 2 al floor 16pt (truncate ultima rete attivato)
  - branded_fallbacks=2 (i 2 al floor)

IMMAGINI: 124 reali Pexels + 0 fallback CONTENT_IMAGE ✅

═══════════════════════════════════════════════════════════════════
DEMO #3 v2 — Preposti 8h
═══════════════════════════════════════════════════════════════════

FILE: DEMO3_Preposti_8h_v2.pptx (68.5 MB, 644 slide) sul Desktop
TIME: 28m 31s (vs v1 15m 19s, +13min) ← grosso, vedi note sotto

NOTA sul tempo: il salto da 15→28 min NON è dovuto a #31.8
(le leve costano +30-60s totali). È dovuto a:
1. Un batch fallito su M2 batch 3 (LLM Pydantic error
   `image.aspect_hint=` emessa come str) → 5 reask main + sub-batch
   recovery 2× max_retries=2 = ~3-4 min totali
2. Reask hidden in altri batch (instructor retry su validation
   errors meno gravi)

LOG TELEMETRY:

  Leva A → top_k=99 (formula 8h × 8 + 35) per tutti 6 moduli ✅
  Leva B → adaptive_min_applied=True su M3:
            adaptive_min=0.243 (era statico 0.3)
            before=10 chunk → after=74 chunk ✅
            (M3 "Incidenti mancati" salvato da starvation totale)
  Leva C → pinned_count=180 (6 × 30) ATTIVA tutti i moduli
  Retrieval: per_module_kept={0:63, 1:44, 2:57, 3:50, 4:45, 5:45}
  lost_to_other_module={0:36, 1:55, 2:42, 3:24, 4:54, 5:54}

SUB-BATCH RECOVERY #31.5B → VALIDATO LIVE ⭐
  module_batch_failed_attempting_split batch_idx=3 module_index=2
    error: "image.aspect_hint=" string vs object validation
  sub_batch_ok batch_idx=3 sub_idx=0 got=5
  sub_batch_ok batch_idx=3 sub_idx=1 got=5
  module_batch_recovered_via_split sub_slides_recovered=10
  → ZERO slide perse, M2 intero 80 slide ✅

CONFRONTO Demo #3 v1 vs v2 (per_module_kept):
  M0 "Principali soggetti"          59 → 63 (+4)
  M1 "Relazioni tra soggetti"       23 → 44 (+21) ⭐ era svuotato
  M2 "Fattori di rischio"           55 → 57 (+2)
  M3 "Incidenti mancati"             5 → 50 (+45) 🚀 era catastrofico
  M4 "Comunicazione"                30 → 45 (+15)
  M5 "Valutazione rischi azienda"   29 → 45 (+15)
  TUTTI sopra quota minima 30 ✅

CLASSIFICAZIONE M3 "Incidenti e infortuni mancati" (81 content):

  ✅ ON-TOPIC vero: ~18 (22%)
     - Analisi infortunistica (1-2)
     - Gestione dati INAIL (21)
     - Riunioni periodiche (31, 34, 35)
     - Monitoraggio annuale (43)
     - Flussi informativi salute (84-85)
     - Segnalazione infortuni sotto soglia INAIL (87) ⭐
     - Modello pre-post formazione (88) ⭐
     - Questionari autovalutazione (91-94)
     - Misure emergenza + correttivi (95-97, 100, 105)

  🟡 SANZIONI-ADIACENTI: ~20 (25%)
     - Sanzioni varie violazioni (10-14, 17)
     - Sanzioni decurtazioni mancata X (61-69)
     - Sanzioni altri (76, 89-90, 103-104)
     - Sono difendibili come "conseguenze incident-related"

  🔴 OFF-TOPIC chiaro: ~38 (47%) ⚠️
     - Esplosioni/zona ATEX (4-7, 4 slide)
     - Porte meccaniche (15, 1 slide)
     - Registri tumori cancerogeni (22, 28, 41, 44, 81-83, 7 slide)
     - Sicurezza attrezzature (23-25, 27, 33, 71-73, 75, 102, 109, 11 slide)
     - Sostanze cancerogene + allegati (32, 42, 45, 49-50, 5 slide)
     - Valutazione rischio + sorveglianza (51-56, 60, 7 slide)
     - Istituzioni sicurezza (86, INL 101)
     - Esempi attrezzature cantiere (106)

CONFRONTO M3 v1 vs v2:

  Metrica             v1                v2
  on-topic            18%               22% (+4%)
  ripetizioni "Sanzioni X" 15+        20 sanzioni distinte (no ripetizione)
  amianto             8 slide           0 ✅
  POS                 9 slide           0 ✅
  off-topic chiaro    "catastrofico"    47% (still grab-bag)

  Confermo: il fix HA RIDOTTO la patologia (zero ripetizioni
  ossessive, zero amianto, zero POS dominante) MA NON l'ha
  eliminata (47% off-topic permane perché il corpus 81/08 ha
  pochissimi chunk veri sull'argomento "near miss / infortuni
  mancati"; il P25 adattivo recupera chunk vicini ma adiacenti).

═══════════════════════════════════════════════════════════════════
LA SCOPERTA PIÙ IMPORTANTE — pattern comune ai 2 demo
═══════════════════════════════════════════════════════════════════

Le leve #31.8 funzionano contro le 2 patologie tecniche identificate
(M3 starved + dedup zero-sum). Ma una volta che il chunk-budget è
distribuito, il CONTENUTO che ogni modulo riceve è ancora dettato
dal cosine similarity, che ha confini sfumati sul D.Lgs 81/08.

CONSEGUENZA:
- Su corsi con moduli BEN DISTINTI (Specifica Basso 4h E25: Rischi/
  DPI/Emergenza/Segnaletica) → fix funziona pulito
- Su corsi con moduli OMBRELLO (Generale 4h: Concetti rischio/
  Prevenzione/Organizzazione/Diritti) → fix bilancia i numeri ma
  i contenuti vagano tematicamente
- Su corsi con moduli a tema NICCHIA (Preposti M3 "Incidenti
  mancati") → fix salva da starvation MA recupera adiacenti perché
  il corpus non ha materiale veramente specifico

═══════════════════════════════════════════════════════════════════
COSA TI CHIEDO DI VERIFICARE — SLIDE PER SLIDE SU ENTRAMBI
═══════════════════════════════════════════════════════════════════

DEMO #1 E25 Specifica 4h — già OK review 10, niente da rivedere

DEMO #2 v2 Generale 4h:
  A. CONTENUTO 336 slide
     - M0 "Concetti di rischio": medico competente / sanzioni /
       verifiche attrezzature dentro M0 → accettabile come "esempi
       di concetti di rischio" o deriva visibile?
     - M1 "Prevenzione e protezione": 50% medico/biologico → è
       difendibile come "prevenzione include sorveglianza" o
       cliente vede subito patologia?
     - M2 "Organizzazione prevenzione": SPP ✅ ma include DPI
       capelli/occhi/mani (M1) e cantiere POS (M0)
     - M3 "Diritti e doveri": 19% off-topic, il migliore
  B. DIAGRAMMI 20 totali (18 catalog, 2 al floor)
  C. IMMAGINI 124 reali (0 fallback CONTENT_IMAGE)
  D. QUIZ 44 + CASE_STUDY 14
  E. BOOKENDS + branding CFP

DEMO #3 v2 Preposti 8h:
  A. CONTENUTO 644 slide
     - M0-M2-M4-M5: buoni 30-45 chunk on-topic (non analizzati slide
       per slide, ma per_module_kept e lost_to_other_module sono
       sani)
     - M1 "Relazioni tra soggetti" 44 chunk (era 23): da verificare
       on-topic vs sovrapposizione con M0
     - M3 "Incidenti mancati": 22% on-topic + 25% sanzioni + 47%
       attrezzature/sostanze/sorveglianza
  B. DIAGRAMMI: TBD da render — verifica regression #31.7A v2 (zero
     branded fallback per font shrink)
  C. IMMAGINI: 229 reali, ZERO content_image_fallback
  D. QUIZ + CASE STUDY: TBD
  E. BOOKENDS + branding

═══════════════════════════════════════════════════════════════════
LE OPZIONI STRATEGICHE
═══════════════════════════════════════════════════════════════════

OPZIONE 1 — Manda tutti 3 al cliente con framing onesto
  "Stiamo consegnando 3 corsi prodotti dalla pipeline AI: ognuno
   ha 4-6 moduli da 80+ slide con contenuto normativo D.Lgs 81/08
   reale. La cura del topic per modulo è bozza-RSPP da raffinare
   manualmente prima della certificazione."
  Pro: 3 deliverable oggi
  Contro: cliente vede 30-50% off-topic in M0/M1 di Generale e
  47% in M3 di Preposti

OPZIONE 2 — Manda Demo #1 + Demo #3 (escludi Generale)
  Pro: 2 demo più puliti (E25 review 10 OK + Preposti M3 ridotto)
  Contro: Generale è il corso PIÙ richiesto dal cliente medio

OPZIONE 3 — Lavora MODULE_QUERY_EXPANSIONS dei 4 Generale per
  renderle più discriminanti (~30 min) + rigenera (~12 min)
  Pro: Generale pulito mantiene il valore commerciale
  Contro: +45 min, nessuna garanzia che basti

OPZIONE 4 — Lavora la querying di M3 Preposti (~20 min) + accetta
  Generale come sopra
  Pro: solo M3 Preposti necessita refining
  Contro: 2 lavori paralleli

OPZIONE 5 — Manda Demo #1 oggi + comunica al cliente che #2 e #3
  arrivano domani DOPO refinement query
  Pro: cliente vede subito 1 deliverable + qualità non compromessa
  Contro: dripping consegna (avevi sconsigliato in review 11)

═══════════════════════════════════════════════════════════════════
LE MIE DOMANDE
═══════════════════════════════════════════════════════════════════

DQ1. Apri Demo #2 v2 e Demo #3 v2 e dammi un verdetto:
     accetti la patologia "trasferimento moduli" come trade-off
     onesto del fix #31.8 (bilanciamento quantitativo garantito,
     topic curato manualmente), oppure rigeneriamo con query
     refining (OPZIONE 3 o 4)?

DQ2. Conta off-topic visibile in M3 Preposti v2 (47% nel mio
     conteggio): è grab-bag clientside o "il corpus 81/08 non
     copre near miss specifico, è il limite del materiale"?
     Se confermi corpus-limit, il fix tecnico è chiuso e il prox
     work-item è ingestione D.M./circolari INAIL su near miss.

DQ3. Sub-batch recovery #31.5B attivato live (M2 Preposti batch 3):
     vuoi che gli aggiunga un test integration end-to-end con
     mock LLM che ritorna validation error a metà batch?

DQ4. Strategia consegna cliente: OPZIONE 1/2/3/4/5?

DQ5. Deploy Railway+Vercel: posso partire in parallelo alla tua
     decisione qualità (l'utente vuole vedere demo deployato
     comunque)?
