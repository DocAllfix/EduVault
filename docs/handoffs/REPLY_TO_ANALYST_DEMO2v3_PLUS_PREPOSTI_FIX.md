Demo #2 v3 — analisi + richiesta fix Preposti 8h

═══════════════════════════════════════════════════════════════════
PARTE 1 — Demo #2 v3 (Generale 4h) — NUOVO, da validare
═══════════════════════════════════════════════════════════════════

Sul Desktop: DEMO2_Generale_4h_v3.pptx (50 MB, 331 slide, 9m 36s).

COSA HO FATTO (review 12 tuo)
  A.1 Query MODULE_QUERY_EXPANSIONS["Prevenzione e protezione"]
      ampliata 4→25 righe (rimosso "Sorveglianza sanitaria",
      aggiunti gerarchia controlli ISO/EN, DPC prima DPI, esempi
      tecnici cadute/elettrico/rumore/macchine)
  A.2 _DROP_PATTERN_M1_PREVENZIONE_GENERALE regex
      applicato SOLO al modulo "Prevenzione e protezione" Generale:
      medico_competent / sorveglianza_sanitaria / agenti_biologici /
      cartella_sanitaria / vaccinazioni / cancerogeni / visite_medic
  A.3 Velocità: _INSTRUCTOR_DEPTH_RETRIES 5→2 (sub_batch recovery
      copre, validato live su Demo #3 v2)

LOG LIVE conferma fix
  m1_prevenzione_drop_list_applied chunks_dropped={1: 9}
    reason=medico_biologico_corpus_blur
  per_module_kept={0:60, 1:32, 2:40, 3:33}
  Tempo: 9m 36s (vs v2 12m 14s = -21%)

CLASSIFICAZIONE M1 v3 (57 titoli content) — mia analisi:

  ON-TOPIC vero "Prevenzione e protezione": ~45 (79%)
  ADIACENTE LEGITTIMO: ~5 (9%)
  OFF-TOPIC medico/biologico: ~1-2 slide (2-3%)

  Confronto v2 vs v3:
    M1 off-topic medico   46%  →  ~3%   (-43%)
    Tempo                 12:14  →  9:36 (-21%)
    diagram_fallbacks     2      →  0
    Test #31.x+#32        n/a    →  60/60 verdi

DOMANDE su Demo #2 v3

DQ1. Apri DEMO2_Generale_4h_v3.pptx e dammi verdetto:
     - VERDE: spedibile cliente
     - GIALLO: spedibile con caveat specifico
     - ROSSO: serve altro fix

DQ2. Verifica slide-per-slide:
     - M0 "Concetti di rischio" (era 31% off-topic v2): migliorato?
     - M1 "Prevenzione e protezione" (ora 3% off-topic): conferma
       gate < 15-20%?
     - M2 "Organizzazione prevenzione" (era 26% off-topic v2):
       migliorato?
     - M3 "Diritti e doveri" (era 19% off-topic v2): migliorato?
     - Immagini 118 reali: contestuali al titolo? Foto stock
       americane fuori contesto? Dedup intra-corso?
     - Diagrammi 19 catalog: tutti renderizzati ok? Testo dentro
       box, no ellipsis sopra floor 16pt?
     - Quiz 44 + Case Study 14: plausibili?
     - Bookends + branding C.F.P. Montessori uniforme?

═══════════════════════════════════════════════════════════════════
PARTE 2 — Richiesta FIX MIRATO per Demo #3 Preposti 8h
═══════════════════════════════════════════════════════════════════

CONTESTO

Tu nella review 12 (verbatim) hai detto:
  "Demo #3 Preposti 8h v2 OK consegnabile con framing onesto.
   M3 al 22% on-topic + 25% sanzioni adiacenti + 47% off-topic
   è prevalentemente limite-del-corpus, non grab-bag del sistema.
   Work-item futuro: ingerire D.M./circolari INAIL su near miss
   specifico."

L'utente ha contro-obiettato: il D.Lgs 81/08 è 140 pagine, 1819
chunk già nel DB. Non vuole aggiungere altre normative non
confermate dal cliente. Se la normativa è quella e basta, allora
il fix deve venire dalla pipeline (query / drop-list / quote),
non dal corpus.

E ha ragione: il sistema NON sta sbagliando perché manca
materiale "near miss specifico", sta scegliendo MALE quale
materiale assegnare a M3. Su 1819 chunk D.Lgs 81/08, ci sono
sicuramente 50-100 chunk genuinamente relevant a "monitoraggio
infortuni / analisi pre-post / azioni correttive / segnalazioni
INAIL / responsabilità preposto sulla rilevazione" — ma la query
attuale M3 li manca e la dedup zero-sum spinge altro.

DOMANDA TECNICA al posto della "ingestione D.M. esterni"

Mi serve un FIX MIRATO equivalente a quello che mi hai dato per
Generale M1, ma per Preposti M3 "Incidenti e infortuni mancati".
Le 3 leve disponibili sulla pipeline:

LEVA 1 — Query refinement (come hai fatto per "Prevenzione")
  Attuale MODULE_QUERY_EXPANSIONS["Incidenti e infortuni mancati"]
  (se esiste, oppure fallback al title nudo): da verificare in
  research_agent.py
  Possibile espansione mirata: "near miss, mancato infortunio,
  segnalazione preposto, rilevazione anomalia, analisi cause,
  azioni correttive, indicatori predittivi, registro infortuni
  art. 53, denuncia INAIL, monitoraggio andamento infortunistico
  aziendale, ciclo Plan-Do-Check-Act sicurezza, modello pre-post
  formazione"
  Effetto atteso: cosine spinge su chunk legati a monitoraggio +
  preposto-vigilanza invece che sanzioni/cancerogeni/ATEX

LEVA 2 — Drop-list M3 Preposti (come Segnaletica + M1 Generale)
  Pattern da escludere: ATEX/atmosfere esplosive (4 slide),
  porte meccaniche (1), registri tumori cancerogeni (7),
  sicurezza attrezzature singole specifiche (11), sostanze
  cancerogene + allegati (5), valutazione rischio + sorveglianza
  sanitaria (7), istituzioni vigilanza (2)
  Pattern proposto:
    "atmosfere\s+esplosiv\w*|zona\s+ATEX|registro\s+tumori|
     agent[ei]\s+cancerogen\w*|allegato\s+(?:XLII|XLIII)|
     sorveglianza\s+sanitaria"
  Applicato SOLO al modulo "Incidenti e infortuni mancati" del
  corso Preposti (NON globale, perché ATEX è on-topic in altri
  corsi)

LEVA 3 — Quota pin M3 aumentata (#31.8 C tuning)
  Oggi: QUOTA_MIN=30 chunk pinned per modulo
  Per Preposti M3 (post leva B adaptive_min ha portato a 50 chunk
  da P25 0.243), aumentare quota a 50 specifico per modulo
  "Incidenti e infortuni mancati" garantirebbe più chunk on-topic
  pre-dedup
  Trade-off: M0/M2 perdono ~5 chunk ciascuno verso M3 (acceptable
  se sono ben coperti)

DQ3. Quale combinazione di leve 1/2/3 mi consigli per Preposti M3?
     Esempi:
     - Solo leva 1 (query refinement, più conservativo, ~10 min)
     - Leva 1 + 2 (query + drop-list, simile a Generale M1
       refinement, ~30 min)
     - Tutte e 3 (query + drop + quota, più aggressivo, ~45 min)
     - Altra combinazione che vedi tu

DQ4. Soglia gate per Demo #3 v3 (Preposti 8h rigenerato):
     - Ti basta M3 < 30% off-topic per consegna cliente?
     - O più stretto (< 20%)?

DQ5. Se DQ3 = "non vale la pena, lasciamo Demo #3 v2 con framing"
     → conferma scelta esplicita, mando come pomeriggio.
     Se DQ3 = "fai leva X/Y/Z" → ti rigenero Demo #3 v3 in ~30
     min e ti rimando metrica + titoli M3 v3.

═══════════════════════════════════════════════════════════════════
SINTESI ATTESA: 2 file Desktop + 2 verdetti tuoi
═══════════════════════════════════════════════════════════════════

Demo #2 v3 (NUOVO): aprilo, dammi VERDE/GIALLO/ROSSO + note sui
4 moduli.

Demo #3 Preposti 8h (esistente o v3): scegli tra
  (a) tieni v2 con framing (come review 12)
  (b) rigenero v3 con leva X (specifica quale)

Aspetto entrambi i verdetti. Deploy Railway+Vercel procede in
parallelo (decisione qualità contenuto indipendente).
