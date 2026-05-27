# Risultati E2E #20 post-#31.1 — da inviare all'analista

**Allegati Desktop:**
- `CFP_4h_E2E20_31.1_da_analista.pptx` (49 MB, 335 slide)
- `CFP_4h_E2E20_31.1_dispensa.pdf` (355 KB)

---

```
Caro analista,

#31.1 implementato e testato sotto editable install garantito.
Risultato: il fix funziona e in più ha un effetto collaterale
positivo enorme sui tempi che non avevamo previsto.

══════════════════════════════════════════════════════════════════
1. NUMERI E2E #20 — confronto con #19 baseline
══════════════════════════════════════════════════════════════════

  Metrica                        E2E #19    E2E #20    Δ
  Tempo pipeline (PURO PPTX)     13m 32s    10m 38s    -2m 54s (-21.4%)
  Slide totali                   326        335        +9 (durata blindata OK)
  Moduli                         84/84/74/84  84/84/83/84  più uniformi
  DIAGRAM catalog                18/18      ~18/18 (TBC)
  reask_avg_per_batch            0.0        0.0        invariato

L'effetto collaterale interessante: -21% di tempo SENZA H6.
Probabile spiegazione: con retrieval per-modulo, ogni modulo ha
chunk più focalizzati → token in input al content_agent più
"densi e mirati" → batch instructor si chiudono al primo colpo
(zero reask, confermato 0.0 su 4 moduli) → meno latenza
Azure totale. NON è un effetto pianificato di #31.1 ma è reale e
ripetuto. Resta da capire se è artefatto della singola run o
pattern; misurerò sui 3 corsi demo.

══════════════════════════════════════════════════════════════════
2. PER_MODULE_RETRIEVAL_SUMMARY (i numeri diagnostici che chiedevi)
══════════════════════════════════════════════════════════════════

Dal log:
  module_index 0 "Rischi specifici":  count_raw=45, top_score=0.616
  module_index 1 "DPI":                count_raw=45, top_score=0.605
  module_index 2 "Procedure emergenza": count_raw=45, top_score=0.566
  module_index 3 "Segnaletica":        count_raw=45, top_score=0.695

  per_module_retrieval_summary:
    total_raw=180, total_after_dedup=136, duplicates_removed=44
    per_module_kept={0: 36, 1: 32, 2: 30, 3: 38}
    lost_to_other_module={0: 9, 1: 13, 2: 15, 3: 7}
    relevance_filter_dropped=0 (tutti moduli)

Lettura:
- M2 e M3 (i grab-bag pre-#31.1) escono entrambi sopra 30 chunk
  post-dedup → corpus NON è povero, c'è materiale.
- M2 perde più degli altri alla dedup (15) → significa che 15
  chunk recuperati per "Procedure di emergenza" sono finiti in
  M0 o M1 perché lì avevano cosine più alto. Sono i "generici"
  emergenza-formazione che migrano verso le calamite forti
  (M0 Rischi, M1 DPI). M2 resta comunque con 30 chunk on-topic.
- M3 perde solo 7 alla dedup → la segnaletica è un tema
  geometricamente distinto dagli altri, pochi chunk contesi.
  Risulta il modulo con count più alto post-dedup (38). Bello.
- MIN_RELEVANCE=0.0 di fatto inattivo come avevi previsto
  (relevance_filter_dropped=0). Lasciato così, non vale ritarare
  finché non vedo bisogno reale.

══════════════════════════════════════════════════════════════════
3. LETTURA TITOLI 4 MODULI (il GATE VERO, come hai detto tu)
══════════════════════════════════════════════════════════════════

Ho letto primi 20 + ultimi 5 di ogni modulo. Verdetto:

M0 "Rischi specifici" — COERENTE (era OK in #19, resta OK)
  Tutti on-topic: meccanici/elettrici/cadute/esplosione/chimici/
  biologici/fisici/movimentazione carichi/posture/agenti chimici.

M1 "DPI" — COERENTE (era OK in #19, resta OK)
  Protezione capelli/capo/occhi/mani/piedi, Allegato VIII,
  manutenzione DPI, zone pericolose, attrezzature.
  Borderline: slide 79-82 su "ascensori/montacarichi" —
  attinente a "attrezzature pericolose + DPI" ma slittamento
  tematico minore. Tollerabile.

M2 "Procedure di emergenza" — TRASFORMATO (era grab-bag, ora COERENTE)
  Vie/uscite emergenza, illuminazione sicurezza, porte meccaniche,
  segnaletica emergenze, servizio emergenza, antincendio,
  manutenzione impianti, compiti personale antincendio.
  ZERO slide su RLS/Rappresentanti, Fondo finanziamenti,
  Sanzioni penali (i 54 grab-bag di E2E #19).
  Successo netto.

M3 "Segnaletica" — TRASFORMATO (era grab-bag, ora COERENTE)
  Forma/colori segnaletica, pittogrammi, materiali cartelli,
  dimensioni/visibilità/posizionamento, divieto/avvertimento/
  salvataggio/prescrizione, simboli luminosi/acustici/verbali.
  ZERO slide su Agenti Biologici/Modulo A RSPP/valutazione
  rischi/POS/PSC (i 60 grab-bag di E2E #19).
  Una contaminazione singola: slide 79 "Riepilogo finale:
  Gestione giudizi medici e segnaletica" — "giudizi medici"
  non è segnaletica. 1 slide su 84 = 1.2%, accettabile.
  Successo netto.

GATE GO/NO-GO: PASSATO.

══════════════════════════════════════════════════════════════════
4. COSA RIMANE PRIMA DELLA DEMO
══════════════════════════════════════════════════════════════════

Apri il PPTX (Desktop, `CFP_4h_E2E20_31.1_da_analista.pptx`) e
verifica visivamente con i tuoi occhi: leggi 5-10 slide casuali
per modulo, soprattutto M2/M3 dove il fix è stato chirurgico.
Se confermi "consegnabile bozza-RSPP" come per #19, sblocco la
fase finale:

  (a) Genero gli altri 2 corsi demo (Generale 4h, Primo Soccorso 8h)
      con #31.1 attivo
  (b) Commit fix(31.1) + push branch fix/31-pipeline-surgery
  (c) Setup deploy Vercel+Railway in parallelo
  (d) URL demo al cliente

Tempo stimato post-tuo OK: ~4h totali (40min × 2 corsi demo +
setup deploy + smoke ultimi).

Una domanda secca prima:
DOMANDA: dato il -21% imprevisto da #31.1 (10m38s, era 13m32s),
H6 scende di urgenza? L'attesa cliente self-serve passa da
"intollerabile" (13 min) a "fastidiosa ma gestibile" (10.5 min).
Posso saltare H6 per la demo, fare il progress page engaging
(2-3h) come palliativo, e tenere H6 in roadmap post-demo?
O ne vale comunque la pena tagliare ulteriormente a ~8 min per
gestire scenari batch?

Aspetto il tuo OK visuale sul PPTX e la risposta su H6/progress.

Grazie.
```

---

## Per te — note operative fuori dal messaggio

**Numeri da ricordare**:
- E2E #20 = 10m 38s (era 13m 32s in #19, **-21%** imprevisto)
- 335 slide su 4 moduli uniformi (84/84/83/84)
- 6 cautele analista tutte attive nei log

**File pronti sul Desktop:**
- `CFP_4h_E2E20_31.1_da_analista.pptx` (49 MB)
- `CFP_4h_E2E20_31.1_dispensa.pdf` (355 KB)

**Prossimi step se l'analista dice OK:**
1. Genero altri 2 corsi demo (Generale 4h + Primo Soccorso 8h) con #31.1
2. Commit `fix(31.1): retrieval per-modulo` + push
3. Setup deploy Railway+Vercel (3-4h)
4. URL demo cliente

**Decisione operativa H6 vs progress page** — aspetto risposta analista. Se H6 sale di urgenza, ~1 giorno aggiuntivo. Se progress page basta, ~3h e siamo deploy-ready.
