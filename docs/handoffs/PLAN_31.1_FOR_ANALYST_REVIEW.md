# Piano #31.1 implementazione — chiedere conferma analista

**Da copiaincollare in chat all'analista prima che io tocchi codice.**

---

```
Caro analista,

OK ricevuto su #31.1 precondizione demo. Prima di toccare codice ti
mostro il piano concreto in 5 minuti di lettura. Cambia 1 solo file
(research_agent.py), zero rischio su pacing/durata/audio/builder.

══════════════════════════════════════════════════════════════════
SCOPE — quello che cambio
══════════════════════════════════════════════════════════════════

File UNICO: app/agents/research_agent.py

PRIMA (righe 826-867): 1 search_chunks globale top_k=40 → cluster
cosine + rebalance per quote → grab-bag su M3/M4.

DOPO: N search_chunks indipendenti, uno per modulo, top_k=45
ciascuno, query = MODULE_QUERY_EXPANSIONS[title] (già curate in
#30.9d), poi dedup cross-modulo per cosine score (un chunk vince
nel modulo dove ha lo score più alto). Cluster + rebalance globali
SPARISCONO (li lascio nel file deprecati per rollback rapido).

Effetto sui chunk:
- Oggi: 40 chunk totali, sbilanciati sui temi reali
- Domani: ~180 chunk (4×45), ognuno tematicamente puro per il suo
  modulo. Dedup garantisce che lo stesso chunk non appaia in 2
  moduli (succederebbe per chunk genuinamente cross-tema, es. DPI
  elettrici sia per "DPI" che per "Rischi specifici"); vince il
  modulo con cosine più alto.

Effetto sulla durata: NESSUNO. Pacing decide slide (4h → ~320),
chunk decidono solo coerenza tematica. 326 slide / 180 chunk =
1.8 slide/chunk = espansione pedagogica sana.

══════════════════════════════════════════════════════════════════
COSA NON TOCCO (vincoli che hai ribadito)
══════════════════════════════════════════════════════════════════

- pacing_engine.py: invariato. Durata 4h resta 4h.
- MODULE_QUERY_EXPANSIONS: invariate (le hai approvate in #30.9d).
- content_agent.py / builders / prompts: contratto `chunks_by_module`
  identico (stessa shape dict[int, list[NormativeChunk]]), zero
  cambi a valle.
- H6 load-balance: NON in questo fix (hai detto "una variabile alla
  volta, le due interagiscono sui token, #31.1 prima poi tariamo H6
  sul profilo nuovo"). Lo faccio dopo se verifico OK.
- distribute_chunks_to_modules_cosine() (174 LOC esistenti): NON
  cancellata, solo marcata DEPRECATED in docstring. Rollback in 1
  riga se #31.1 fallisce sul test.

══════════════════════════════════════════════════════════════════
TEST + GATE PRIMA DELLA DEMO
══════════════════════════════════════════════════════════════════

4 test isolati pytest:
  1. retrieve_chunks_per_module fa 1 chiamata per modulo con top_k=45
  2. dedup assegna chunk al modulo con cosine più alto
  3. usa MODULE_QUERY_EXPANSIONS quando esiste
  4. fallback a title nudo se title non in MODULE_QUERY_EXPANSIONS

E2E #20 corso 4h (~13 min, atteso stesso ordine #19, +2s per N
SQL queries seriali, irrilevante). Lettura titoli 4 moduli (faccio
io come hai fatto tu su M3/M4). Gate:

  ✅ M0 "Rischi specifici" + M1 "DPI" rimangono coerenti come #19
  ✅ M2 "Procedure emergenza" contiene SOLO emergenze (era grab-bag)
  ✅ M3 "Segnaletica" contiene SOLO segnaletica (era grab-bag)

Se gate verde → rigenero i 3 corsi demo + commit + deploy demo
Se M2/M3 ancora non coerenti → log `per_module_retrieval_summary`
mostra quanti chunk on-topic ha il corpus per quei moduli; se < 30
chunk veri, allargo MODULE_QUERY_EXPANSIONS per quel tema specifico
(come hai detto: "decisione di design del corso, non taglio durata").

Se M0/M1 peggiorati (rischio basso ma reale, voglio escluderlo
prima di consegnare): rollback in 1 riga al vecchio flow,
investiga.

══════════════════════════════════════════════════════════════════
TIMELINE — quanto ci metto
══════════════════════════════════════════════════════════════════

Codice + test isolati: ~2h
E2E #20: ~13 min
Verifica titoli 4 moduli: ~15 min
Se OK: rigenero 3 corsi demo finali (~40 min)
Totale prima della demo: ~3.5-4h

Inizio quando mi dai il "vai" su questo piano concreto. Una
sola domanda di sanity check prima di partire:

DOMANDA: top_k=45 per modulo è il numero che mi hai detto.
Vedi rischio che per moduli con tema stretto (es. "Segnaletica")
top_k=45 peschi 25 chunk forti + 20 deboli adiacenti
introducendo drift residuo? La tua risposta ieri diceva "drift
residuo molto minore del grab-bag attuale" — confermo che
accettiamo quel drift come trade-off accettabile per la demo, e
post-demo si tara per-modulo (es. M_segnaletica top_k=30, M_rischi
top_k=60)?

Aspetto il tuo "vai" + risposta secca sulla domanda top_k.
```

---

## Per te — note operative fuori dal messaggio

Il plan tecnico completo è in `~/.claude/plans/vast-hopping-sketch.md`
(linee dettagliate con codice, signature funzioni, struttura test, log).

Cosa farò appena l'analista risponde "vai":
1. Implemento `retrieve_chunks_per_module()` + `_flatten_unique()` (80 LOC)
2. Refactor blocco righe 826-867 di `research_agent()` (~30 LOC)
3. Sync container + verifica editable install
4. 4 test isolati pytest
5. E2E #20 (background, ~13 min)
6. Lettura titoli 4 moduli + screenshot/log per analista
7. Se gate verde → 3 corsi demo definitivi + commit + push

Tempo totale stimato: 3.5-4h, finisce in serata o domani mattina.

Branch attuale: `fix/31-pipeline-surgery`. Per #31.1 due opzioni
git:
- (a) Aggiungo commit `feat(31.1): retrieval per-modulo` sullo
  stesso branch (semplice, tutto in `fix/31-*`)
- (b) Apro nuovo branch `feat/31.1-per-module-retrieval` (più
  pulito ma 1 PR in più)

Default: (a) — è continuazione logica del FIX #31. Se tu vuoi (b)
dimmelo prima del commit.
