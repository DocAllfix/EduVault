Risultati Demo #2 v2 + Demo #3 v2 — analisi onesta che cambia il quadro

BOZZA — completare con Demo #3 v2 quando finisce (~18:14).

═══════════════════════════════════════════════════════════════════
RIASSUNTO ESECUTIVO
═══════════════════════════════════════════════════════════════════

#31.8 (A+B+C) ha funzionato MECCANICAMENTE come previsto. Gli
indicatori numerici sono tutti verdi (M3 Preposti da 5 a 50
chunk, M3 Generale niente più 4 Segnaletica sconfinata). MA
aprendo i titoli con gli occhi su Demo #2 v2 ho scoperto qualcosa
che le metriche non catturano: **il fix #31.8 ha trasferito la
patologia dai moduli starved (vecchi sintomi M3) ai moduli
"campione" cosine (M0/M1/M2)**. Non l'ha eliminata, l'ha
spostata.

Per Demo #3 Preposti l'effetto è netto positivo (M3 era
"Incidenti mancati 5 chunk" = catastrofe, ora 50). Per Demo #2
Generale l'effetto è ambiguo: M3 migliora ma M0/M1/M2 peggiorano.
Te lo presento con onestà perché vuoi prendere una decisione di
deploy basata sulla realtà visiva, non sul telemetria pulito.

═══════════════════════════════════════════════════════════════════
LOG TELEMETRY — DEMO #2 v2 (Generale 4h)
═══════════════════════════════════════════════════════════════════

PIPELINE TIME: 12m 14s (vs 10m 54s v1, +13% per leve A+B+C)
SLIDE TOTALI: 336 (4 moduli × 80 + bookends)

RETRIEVAL log (research_agent.py):

  Leva A — top_k=67 per modulo (formula 4h × 8 + 35 = 67)
    Tutti 4 moduli: 67 chunk raw recuperati ✅

  Leva B — MIN_RELEVANCE adattivo NON applicato
    adaptive_min_applied=False per tutti 4 moduli (corretto: a
    4h con corpus ampio i top_score sono 0.47-0.65 ben sopra 0.3)

  Leva C — Dedup quota-aware: pinned 30/modulo
    per_module_pinned={0:30, 1:30, 2:30, 3:30} pinned_count=120

  RISULTATO retrieval:
    per_module_kept={0:60, 1:42, 2:38, 3:40} total_after_dedup=180
    lost_to_other_module={0:7, 1:25, 2:29, 3:27}

CONFRONTO Demo #2 v1 vs v2:

  Modulo                              v1 chunks  v2 chunks  delta
  M0 "Concetti di rischio"            48         60         +12
  M1 "Prevenzione e protezione"       39         42         +3
  M2 "Organizzazione prevenzione"     32         38         +6
  M3 "Diritti e doveri"               70         40         -30 ⭐

  M3 ha perso 30 chunk = i 30 chunk Segnaletica-contesi che cosine
  winner gli dava sono andati ai moduli giusti. ESATTAMENTE quello
  che voleva la leva C.

DIAGRAM: 20 totali, di cui:
  - 18 catalog (font 16-32pt, distribuzione sana)
  - 2 al floor 16pt (truncate ultima rete attivato — analista
    aveva detto "accetta floor se rari", siamo a 2/20 = 10%
    sotto soglia)

IMAGES: 124 reali Pexels + 0 fallback CONTENT_IMAGE
        (Pexels saturato bene su temi generici 4h)

═══════════════════════════════════════════════════════════════════
ANALISI VISIVA TITOLI — DEMO #2 v2 — LA SCOPERTA
═══════════════════════════════════════════════════════════════════

M3 "Diritti e doveri" (59 titoli content):
  ✅ ON-TOPIC vero (formazione/info/RLS/diritti): ~32 slide (54%)
  🟡 ALTRO adiacente legittimo (segnaletica come dovere,
     formazione esplosivi, DPI, scheda sicurezza): ~16 slide (27%)
  🔴 OFF-TOPIC chiari (locali lavoro, attrezzature uso,
     manutenzione, esempi operativi): ~11 slide (19%)
  📊 RISULTATO: 19% off-topic, SOTTO la tua soglia ROSSO 20%
  🎯 NIENTE PIÙ "Segnaletica" come modulo proprio (era 4 in v1)
     → fix #31.8 LEVA C funziona qui

M0 "Concetti di rischio" (58 titoli content):
  ✅ ON-TOPIC vero (tipologie/categorie/valutazione rischio): ~30 slide (52%)
  🟡 ADIACENTE (DPI/segnaletica/emergenza come esempi): ~10 slide (17%)
  🔴 OFF-TOPIC strutturali:
     - Medico competente / giudizio idoneità: 7 slide (1-4, 7-9)
     - Sanzioni penali / art. 297: 4 slide (69, 71-73)
     - Verifiche attrezzature: 5 slide (74-78)
     - Sorveglianza sanitaria: 2 slide (30, 43)
  📊 RISULTATO: ~31% off-topic ⚠️ PEGGIO di M3
  ❓ Pattern visibile: M0 ora prende il medico-competente che
     PRIMA andava in M3 — la dedup ha trasferito senza eliminare

M1 "Prevenzione e protezione" (63 titoli content):
  ✅ ON-TOPIC vero (ponteggi/misure tecniche/livelli contenimento/
     DPI agenti chimici/cancerogeni): ~22 slide (35%)
  🟡 ADIACENTE LEGITTIMO (preposto come parte prevenzione,
     formazione lavoratori a rischio): ~10 slide (16%)
  🔴 OFF-TOPIC:
     - Cartella sanitaria / sorveglianza / visite mediche: 18 slide
       (titoli 11-13, 25, 26, 30-36, 45, 62, 68-70, 74-75, 79-81)
     - Agenti biologici (registri/vaccinazioni): 11 slide (15-22,
       30, 52-53, 55-56, 71-73, 78)
     - RLS finale: 1 slide (82)
  📊 RISULTATO: ~50% medico/biologico-centric ⚠️⚠️ MOLTO OFF
  ❓ M1 è completamente colonizzato dal tema "sorveglianza
     sanitaria + agenti biologici" che è la specialità di un
     altro modulo (M2 "Organizzazione" o M3 "Diritti")

M2 "Organizzazione prevenzione" (62 titoli content):
  ✅ ON-TOPIC vero (SPP/RSPP/ASPP/MOG/SINP/INAIL/Riunione periodica):
     ~28 slide (45%)
  🟡 ADIACENTE LEGITTIMO (formazione aggiornamento ruoli,
     comunicazione, benessere organizzativo): ~12 slide (19%)
  🔴 OFF-TOPIC:
     - Cantiere POS / demolizione / scavo: 5 slide (11-15)
     - DPI protezione capelli/capo/occhi/mani: 4 slide (34-37)
     - Verifiche attrezzature: 2 slide (63-64)
     - Modulo A RSPP formativo: 5 slide (71-77)
  📊 RISULTATO: ~26% off-topic ⚠️
  ❓ M2 ha SPP correttamente ma include parti DPI/cantiere che
     sono temi M0/M1 "Concetti rischio" + "Prevenzione"

═══════════════════════════════════════════════════════════════════
DIAGNOSI ONESTA: COSA È SUCCESSO TECNICAMENTE
═══════════════════════════════════════════════════════════════════

Il problema strutturale del corso GENERALE 4h × 4 moduli con
titoli "ombrello" è che i 4 moduli sono SEMANTICAMENTE QUASI
INSEPARABILI:
- "Concetti di rischio" può contenere quasi tutto del D.Lgs 81
- "Prevenzione e protezione" è praticamente uguale a "Misure"
  → assorbe DPI/sorveglianza/contenimento
- "Organizzazione della prevenzione" → SPP/RSPP/comunicazione
- "Diritti e doveri" → formazione/RLS/informazione

I confini cosine sono BLANDI. Pre-#31.8: M3 vinceva tutti i
sotto-temi specifici (medico, sanzioni, segnaletica). Post-#31.8
leva C: la quota=30 per modulo costringe a distribuire, ma il
risultato è che ogni modulo prende i suoi 30 + qualche altro =
sono PINNED chunk che cosine winner cosine ha matchato sul tema
del modulo, ma "Concetti di rischio" può legittimamente fare
cosine con "medico competente" (perché è "rischio per la salute"
nelle nostre embed) e quel chunk finisce in M0 invece che M3.

NON è un bug della leva C. È un limite del retrieval semantico:
con 4 titoli ombrello come Generale, le distinzioni tematiche
sono talmente sfumate che anche il pin quota 30 non garantisce
on-topic — garantisce solo BILANCIAMENTO QUANTITATIVO.

═══════════════════════════════════════════════════════════════════
LE OPZIONI (decidi tu)
═══════════════════════════════════════════════════════════════════

OPZIONE 1 — Accetta Demo #2 v2 come "consegnabile bozza-RSPP"
  (M3 buono al 81% accettabile, M0/M1/M2 ~25-50% off-topic ma il
   contenuto è normativo D.Lgs 81 reale, non garbage) e manda al
   cliente. La demo dimostra "il prodotto genera 4 moduli da 80
   slide ciascuno con contenuto normativo reale" — quale tema
   esatto finisce in quale modulo è un dettaglio di catalog
   curatela.

OPZIONE 2 — Rivedi MODULE_QUERY_EXPANSIONS dei 4 moduli Generale
  4h per renderli più discriminanti. Es. "Diritti e doveri" oggi
  potrebbe avere query troppo generica; rendendola più mirata
  ("doveri specifici lavoratore art. 19-20, diritti
  consultazione RLS, partecipazione formazione obbligatoria") la
  cosine focuserebbe meglio. Lavoro ~30 min per i 4 moduli.

OPZIONE 3 — Specializza il catalog: invece di 4 moduli ombrello
  Generale, fa 4 sotto-temi puliti tipo "Tipi di rischio /
  Sorveglianza sanitaria / SPP-RSPP / Formazione". Lavoro
  ~1h + rigenerazione + analisi.

OPZIONE 4 — Vai con Demo #3 (Preposti) + Demo #1 (Specifica
  E25) entrambi puliti, mandando solo 2 demo al cliente,
  saltando Generale. Onesto, mostra il prodotto, evita screenshot.

═══════════════════════════════════════════════════════════════════
PARTE B — DEMO #3 v2 PREPOSTI 8h (RIGENERAZIONE IN CORSO)
═══════════════════════════════════════════════════════════════════

[COMPLETARE QUANDO FINISCE ~18:14]

Telemetry PARZIALE finora (research_completed già loggato):

  Leva A: top_k=99 (formula 8h × 8 + 35 = 99) ✅
  Leva B: ATTIVATA su M3 "Incidenti e infortuni mancati"
    min_relevance_adaptive_applied
      adaptive_min=0.243 (era statico 0.3)
      after=74 (era before=10)
    → da 5 chunk v1 a 74 raw post-adaptive, 50 post-dedup ✅
  Leva C: pinned 30/modulo per tutti 6
    per_module_pinned={0:30, 1:30, 2:30, 3:30, 4:30, 5:30}
    pinned_count=180

  CONFRONTO Demo #3 v1 vs v2:
    Modulo                              v1 v2
    M0 "Principali soggetti"            59 63 (+4)
    M1 "Relazioni tra soggetti"         23 44 (+21) ⭐ era svuotato
    M2 "Fattori di rischio"             55 57 (+2)
    M3 "Incidenti mancati"               5 50 (+45) 🚀 era catastrofico
    M4 "Comunicazione"                  30 45 (+15)
    M5 "Valutazione rischi azienda"     29 45 (+15)
    TUTTI sopra quota minima 30 ✅

Attendo titoli M3 Preposti v2 per verificare:
- Zero "Sanzioni per mancata X" ripetitive (erano 15+ in v1)
- Zero "DPI anticaduta" ripetuti (erano 7+ in v1)
- Zero amianto off-topic (erano 8 in v1)
- ≥70% on-topic "infortuni mancati / azioni correttive / monitoraggio"

═══════════════════════════════════════════════════════════════════
COSA TI CHIEDO DI VERIFICARE — SLIDE PER SLIDE
═══════════════════════════════════════════════════════════════════

DEMO #1 (E25 Specifica 4h, già OK review 10):
  - Nessuna nuova verifica, è già stato approvato

DEMO #2 v2 (Generale 4h — sul Desktop come DEMO2_Generale_4h_v2.pptx):
  A. CONTENUTO 336 slide
    - M0 Concetti rischio: contiene medico competente, sanzioni
      art.297, verifiche attrezzature — sono off-topic accettabili
      come "esempi di concetti di rischio" o sono deriva?
    - M1 Prevenzione: 50% medico/biologico — è grab-bag o si può
      difendere come "prevenzione include sorveglianza"?
    - M2 Organizzazione: SPP corretto ma include DPI capelli/
      occhi/mani che sono M1 puri
    - M3 Diritti e doveri: 19% off-topic, miglior modulo
  B. DIAGRAMMI 20 totali
    - 18 catalog regolari (font 16-32pt)
    - 2 al floor 16pt — verificare leggibilità visiva
  C. IMMAGINI 124 reali Pexels (0 branded fallback)
    - Sono contestuali? Coerenti col titolo?
  D. QUIZ 44 totali (10-14 per modulo) + 14 CASE_STUDY
    - Plausibili?
  E. BOOKENDS + branding C.F.P. Montessori uniforme

DEMO #3 v2 (Preposti 8h — sul Desktop quando arriva ~18:14):
  [completare con metriche finali]

═══════════════════════════════════════════════════════════════════
LE MIE DOMANDE
═══════════════════════════════════════════════════════════════════

DQ1. Su Demo #2 v2, accetti la patologia "trasferimento da M3 a
     M0/M1/M2" come trade-off del fix #31.8 perché:
     - M3 ora è il modulo migliore (era il peggiore)
     - Il contenuto degli altri moduli è normativo D.Lgs 81 reale
     - Generale 4h è "ombrello" per natura, semanticamente fluido
     Oppure è un blocker e serve OPZIONE 2 (rivedi
     MODULE_QUERY_EXPANSIONS) o OPZIONE 3 (specializza catalog)?

DQ2. Su Demo #3 v2 Preposti aspetti titoli M3 prima di decidere?

DQ3. Strategia consegna:
     OPZIONE A: 3 demo TUTTI insieme oggi (con Demo #2 v2 come
       sopra descritto)
     OPZIONE B: 2 demo oggi (Specifica #1 + Preposti #3 v2), tieni
       Generale #2 in casa per ulteriore lavoro
     OPZIONE C: aspetta che fissiamo MODULE_QUERY_EXPANSIONS
       Generale (~30 min lavoro + 12 min rigen) e poi 3 puliti
       domani mattina

DQ4. Il deploy Railway+Vercel può PARTIRE in parallelo a queste
     decisioni qualità, vero? (l'utente ha chiesto di iniziare
     deploy dopo la mia presentazione delle funzioni utilizzabili,
     che ho già preparato in INVENTORY_FEATURES_PRE_DEPLOY.md)
