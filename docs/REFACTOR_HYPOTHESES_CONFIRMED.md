# Refactor V2 - Ipotesi confermate empiricamente

> Questo documento traccia le ipotesi architetturali del refactor V2 (vincolo VAA + ordine
> fasi D8→D2+D1→D3→D9→D4/D5→D7→D6→D10) **confermate empiricamente** da audit, stress-test
> ed E2E. Non è la lista dei bug (`VERIFICATION_DEBT.md §1-2`), né delle risorse mancanti
> (`§3`). È la prova del modello concettuale del refactor: ogni volta che il sistema risponde
> al render in modo allineato col modello, lo registriamo qui per (a) difesa empirica contro
> drift architetturale futuro, (b) chiarezza retrospettiva su cosa il refactor sta togliendo
> davvero (cerotti) vs cosa sta aggiungendo (sostanza).

---

## H1 — Patologia cross-titolo intra-corpus V2 era ARTEFATTO V2, non corpus

**Ipotesi formulata pre-refactor (analista review 17, 2026-05-29):**
> "GEN M2 'Organizzazione della prevenzione' produce in V2 grab-bag cross-titolo
> (Modulo A RSPP + Coordinatori in edilizia + sanzioni). Il regime cross-titolo è
> patologia da gestire nel refactor."

**Verifica empirica (2026-05-30, audit GEN M2 voce 1 post-refactor C):**
- Pipeline: (a) pura grounding + skeleton instructor structured + `retrieve_for_subtopic`
  deterministico (no autogen LLM riformulazione, D-170 fix).
- retrieval_query autogen-style scritta da instructor: "_normativa sul ruolo e finalità
  dell'organizzazione della prevenzione nel D.Lgs 81/08 e Accordi Stato-Regioni_".
- Risultati top-30: **top_score 0.988, media 0.468, distribuzione monotona-decrescente**.
- Regime: DENSO equivalente a GEN M1 (top 0.994, media 0.747).

**Conclusione**: la patologia cross-titolo intra-corpus V2 era artefatto del retrieval V2
(drop-list `_DROP_PATTERN_*` + 38 query expansions `MODULE_QUERY_EXPANSIONS` hardcoded),
NON proprietà strutturale del corpus D.Lgs 81/08. Quando il refactor toglie quei cerotti
e sostituisce con (a) pura + by-subtopic + Cohere rerank, il corpus 81/08 risponde in
modo monotono coerente. **Il refactor non sta nascondendo un problema reale dietro una
nuova architettura — sta rivelando che il problema apparente era il cerotto.**

**Conseguenza per calibrazione B2 (2026-05-30):**
I 5 moduli del ground-truth (GEN M1, GEN M2, PRE M3, ANT M0, HACCP M3) coprono **3 regimi
reali**, non 5:
- DENSO: GEN M1, GEN M2 — controllo negativo
- SPARSO: PRE M3, ANT M0 — caso di calibrazione primario
- LOW-CONFIDENCE-UNIFORMLY: HACCP M3 — caso stress, B2↔B4 dipendenza

**Difesa contro drift**: se in futuro si proponesse di reintrodurre query expansions
hardcoded ("le 38 expansions erano utili per GEN M2"), questa entry è la prova empirica
che il regime denso emerge spontaneamente con la combinazione strutturale del refactor,
senza expansions. Le expansions producevano grab-bag, non coerenza.

---

## H2 — Doppio LLM (instructor skeleton → autogen riformulazione) è raddoppio di entropia senza guadagno informativo

**Ipotesi formulata durante STEP 4 estrazione ground-truth (2026-05-30):**
> "L'autogen LLM era pensato per il path V2 by-title (module_title generico). In D3
> abbiamo già una retrieval_query semantica scritta da instructor structured nel contesto
> del sotto-tema. Riformularla via autogen è doppio LLM, doppia stocasticità, zero
> guadagno informativo. Pattern generale: la composizione cieca di LLM produce
> stocasticità composta, e il rimedio è sempre architetturale (non chiamare il secondo
> LLM) prima che operativo (mediare le run)."

**Verifica empirica (2026-05-30, two-run determinacy check post-refactor C):**
- Stessa retrieval_query HACCP M3 voce 1.
- RUN 1 (`retrieve_for_subtopic` deterministico): top_score=0.3388, top-10 ids = X.
- RUN 2 (stesso input, stesso path): top_score=**0.3388**, top-10 ids = **X** (identici).
- Δ top_score = **0.0000** (sotto il jitter Cohere atteso ε=0.05).

**Tabella della varianza eliminata** (conserviamo come difesa empirica):

| Misurazione | top_score | Path | Note |
|-------------|-----------|------|------|
| HACCP M3 v1 STEP 3 (recall+rerank diretti, query letterale) | 0.339 | letterale | regime LCU |
| HACCP M3 v1 STEP 4 (retrieve_for_module → autogen riformula) | 0.642 | autogen | sopra alert |
| HACCP M3 v1 E2E del 29-maggio (log prod) | 0.367 | autogen | sotto alert |
| HACCP M3 v1 RUN 1 post-refactor C | **0.3388** | letterale (no autogen) | deterministico |
| HACCP M3 v1 RUN 2 post-refactor C | **0.3388** | letterale (no autogen) | identico a RUN 1 |

Pre-fix: varianza 0.30 punti su stesso input. Post-fix: varianza 0.0000.

**Conclusione**: doppio LLM (instructor produce retrieval_query → autogen riformula
retrieval_query) introduceva varianza inutile in un path che doveva essere deterministico
per design. La cura è architetturale (split `retrieve_for_subtopic` vs `retrieve_for_module`),
non operativa (mediare run). 30 min di refactor, ricalibrazione futura inutile,
allineamento concettuale.

**Pattern generale registrato (analista 2026-05-30):**
> In ogni componente di pipeline, prima di chiamare un LLM, chiediti se l'input è già
> nella forma che ti serve. Riformulare via LLM un testo già LLM-generato è raddoppio di
> entropia senza valore informativo. È la sorella di D-160 ("metrica regex secondaria,
> sample-read manuale primaria") applicata alla composizione di LLM call.

**Difesa contro drift**: se in futuro si proponesse "rimettiamo autogen anche su D3, dai"
(per consistenza col path V2, o per "uniformare il behavior"), questa entry + tabella
della varianza è la prova empirica del motivo per cui non si fa. Determinismo deterministico
non è scelta stilistica: è prerequisito della calibrazione B2 stabile.

---

## H3 — D3 (a) pura scala universalmente, NON era fortuna su 81/08-base

**Ipotesi formulata in analyst audit GEN M1 (2026-05-29):**
> "GEN M1 produce scheletro firmabile con grounding (a) pura. Ma 1 audit su corso facile
> non basta: stress-test su PRE M3 (caso peggiore cross-corso V2) + ANT M0 (corpus-thin)
> + 4° audit neutro fuori dal dominio 81/08-base per confermare universalità."

**Verifica empirica (2026-05-29 + 2026-05-30):**

1. **Stress-test PRE M3 + ANT M0 (2026-05-29)**:
   - PRE M3: 7 sotto-temi tutti su incidenti/infortuni mancati, ZERO sconfinamento RSPP/
     Coordinatore/Datore (era 90% V2). Patologia eliminata alla radice.
   - ANT M0: 8 sotto-temi tecnici antincendio puri, ZERO ruoli formativi/ASL. top_score
     voce1 0.814 (vs V2 0.473): da corpus-thin a coperto.

2. **4° audit neutro HACCP LOMBARDIA (2026-05-30, fuori dominio 81/08-base)**:
   - M0 Principi (10 sotto-temi): 7 principi HACCP ortodossi (CCP, limiti critici,
     monitoraggio, azioni correttive, verifica) + definizione + formazione.
   - M1 Igiene alimenti (8): contaminazioni, conservazione, igiene personale,
     sanificazione, infestazioni, normativa.
   - M2 Rischi bio/chim (9): microbiologia patogeni, contaminanti chimici, prevenzione,
     ruolo addetto.
   - M3 Autocontrollo (10): piano, procedure, registrazioni, non conformità.
   - Zero deriva verso RSPP/Coordinatore/Antincendio/Primo Soccorso.

3. **E2E completo flag-on HACCP (2026-05-30)**:
   - 336 slide, distribuzione **84+84+84+84** perfettamente equa.
   - citation_refs 98% popolate tutte `Reg. CE 852/2004, allegato/art.`
   - **Cross-corso check sul PRODOTTO FINALE** (regex su RSPP/Coordinatore/Preposti/
     antincendio in titoli+bullets+notes di tutte le 336 slide): **0/336 = 0.0%**.
   - Verifica indipendente analista con pattern più larghi (Coordinatore CSE/CSP,
     fascicolo opera, POS, edilizia/cantiere, DPI industriali, antincendio, primo
     soccorso): **0/336**, 1 falso positivo verificato come tale ("preposto" = significato
     generico HACCP "responsabile di settore").

**Conclusione**: D3 (a) pura + by-subtopic deterministico è **production-ready come
fondazione universale**, non solo su 81/08-base. La pipeline materialize_by_subtopic →
content_agent → builder rispetta il perimetro normativo per intero, NON solo allo stadio
scheletro.

**Difesa contro drift**: se in futuro emergesse un caso cross-corso su uno scheletro
generato con (a) pura, NON tornare a (b)/(c)/(d) grounding ipotesi. Indagare prima
artefatti V2 residui (drop-list/expansions ancora vive su quel path? feature flag
spento accidentalmente?). H1 ha mostrato che spesso il problema è il cerotto, non la
sostanza.

---

## H4 — Regime "denso vero" non esiste su questo corpus per query con riferimenti normativi specifici

**Ipotesi formulata in messaggio 9 (2026-05-30) post-extraction GEN M3 v1:**
> "Quello che apparentemente sembra denso (top 0.99, media 0.82) è un 'denso apparente'
> — Cohere uniformemente generoso, ma il cuore on-topic vero è sparso ai rank intermedi
> (3, 9, 11, 17), e i primi rank sono mis-rank topicalmente-larghi (Allegato I esonero,
> Art. 37 formazione durata, Allegato XIV cantieri)."

**Verifica empirica (2026-05-30, sample-read disconfermativa GEN M3 v1):**

Disciplina disconfermativa applicata: predizione 8 chunk attesi PRIMA della lettura
(Art. 30 modelli, Art. 31 SPP, Art. 32 capacità RSPP, Art. 33 compiti SPP, Art. 35
riunione periodica, Art. 15 misure generali, Art. 18 obblighi datore, Art. 28 oggetto
VDR). Poi confronto col top-30 reale di GEN M3 voce 1 ("Principi normativi e obiettivi
dell'organizzazione della prevenzione"), top_score 0.9985, media 0.8202, distribuzione
score 0.998 → 0.541.

Conteggio onesto:
- 4 on-topic / 9 attesi del cuore (Art. 30 rank 3+9, Art. 15 rank 11, Art. 34 rank 17)
- 3 adjacent legittimi (Art. 19 ×2, Art. 21 lavoratori autonomi)
- 15+ off-topic chiari (Art. 37 ×3 formazione, Allegato I esonero formatori, Allegato
  XIV ×3 cross-titolo IV Cantieri, Allegato IV schema ore corsi, Art. 98/95 cross-
  titolo IV, Art. 286-quater cross-titolo X-bis, Allegati VIII/XV/XX/XXXIV/XLI cross-
  titolo, Allegato I-bis sanzionatorio, Art. 1 legge 123/2007)
- 6-7 dubbi su body fragmenti corti

**Top-2 a score 0.998-0.995: entrambi off-topic** (Art. 37 + Allegato I esonero).

**Conclusione**: il regime "denso vero" non esiste su questo corpus per query con
riferimenti normativi specifici. Cohere è uniformemente generoso (tutti i 30 score
>0.5) ma il cuore on-topic è sparso ai rank intermedi e i primi rank sono mis-rank.

**Implicazione architetturale**: i 3 regimi previsti (DENSO/SPARSO/LCU) si comprimono
operativamente a 2 (sparso-con-mis-ranking, low-confidence), perché il "denso
apparente" è strutturalmente sparso-con-mis-ranking + Cohere uniformemente generoso.
B2 deve essere la stessa formula su tutti i regimi, perché il problema di base è
uniforme.

**Difesa contro drift**: se in 6 mesi qualcuno proporrà "rimettiamo Cohere come ranker
primario su corso denso, dai" la registrazione di H4 è la prova empirica del perché
no. Il pattern "regime apparente sbagliato perché la metrica primaria è sbagliata" è
D-160 in altra forma, applicato al rerank score.

---

## H5 — Cohere rerank esclude dal top-30 chunk on-topic veri presenti nel pool RRF (D-171-bis)

**Ipotesi formulata in messaggio 10 (2026-05-30):**
> "D-171 dice: Cohere mis-rank top-1/top-2. D-171-bis dice: Cohere esclude dal top-30
> chunk on-topic veri presenti nel pool RRF. Il primo è errore di ordinamento (correggibile
> riordinando); il secondo è errore di selezione (i chunk omessi non li vedi nemmeno,
> non li puoi riordinare). Le due ipotesi sono di natura diversa, anche se gestite dalla
> stessa formula B2-ri-ranking-su-pool-RRF."

**Verifica empirica (2026-05-30, SQL check + pool RRF check):**

SQL check sui 9 articoli attesi del cuore organizzativo per GEN M3 voce 1 (script
`scripts/check_d_corpus_vs_d_rerank.py`):
- Tutti e 9 INGERITI in `dlgs_81_08` (Art. 15: 14 chunks, Art. 18: 4, Art. 28: 5,
  Art. 30: 10, Art. 31: 3, Art. 32: 5, Art. 33: 1, Art. 34: 4, Art. 35: 5).
- Verdetto: D-rerank, non D-corpus.

Pool RRF top-200 vs Cohere top-30 (script `scripts/check_articles_in_recall_pool.py`):

| Articolo | Rank pool RRF top-200 | Rank top-30 Cohere |
|----------|----------------------|---------------------|
| Art. 30 | **2** | rank 3+9 (OK) |
| Art. 15 | **8** | rank 11 (OK) |
| Art. 34 | **23** | rank 17 (OK) |
| **Art. 33** | **24** | ESCLUSO |
| Art. 28 | 57 | ESCLUSO |
| Art. 32 | 91 | ESCLUSO |
| Art. 18 | 108 | ESCLUSO |
| Art. 35 | 144 | ESCLUSO |
| Art. 31 | 148 | ESCLUSO |

**6 dei 9 articoli del cuore esclusi da Cohere top-30. Art. 33 era rank 24 nel pool
RRF (vicinissimo al top), Cohere lo esclude.** Body chunk di Art. 33: titolo letterale
"Compiti del servizio di prevenzione e protezione" — il più letteralmente correlato
al subtopic "Principi normativi e obiettivi dell'organizzazione della prevenzione".

**Conclusione architetturale (analista sign-off 2026-05-30)**: la formula B2 corretta
è ri-ranking via cosine Voyage diretto sul **pool RRF top-100/200**, saltando Cohere
come ranker. Cohere passa da "ranker primario decisionale" a "telemetria + recall
accelerator". Rinominazione: "Cohere score" → "topical-affinity score" nei log e
metriche (commit D-171-bis), per onestà nominale e per prevenire drift futuro.

**Differenza categorica H4 vs H5** (analista 2026-05-30):
- H4 è ipotesi sul corpus/regime (Cohere generoso uniformemente, cuore sparso in
  zone intermedie).
- H5 è ipotesi sul ranker (Cohere esclude dal pool che vede gli on-topic letterali).
- Sono ipotesi su componenti diversi (corpus vs ranker), entrambe gestite dalla stessa
  formula B2-ri-ranking-su-pool-RRF.

**Difesa contro drift (H5)**: se in 6 mesi qualcuno proporrà "ottimizziamo Cohere
rerank top_n a 50 invece di 30 per recuperare gli on-topic" — H5 mostra che il problema
non è il `top_n` (Art. 33 era rank 24 nel pool e Cohere lo escluderebbe anche
con top_n=50, se il suo ranking lo mette oltre il taglio). Il problema è che Cohere
non è ranker title-aligned. La cura non è "alzare il taglio Cohere"; la cura è "non
usare Cohere come ranker decisionale".

**Work-item esplorativo D-172 (analista 2026-05-30, post-calibrazione)**: se Cohere
passa a telemetria-pura, valutare di non chiamarlo a runtime in produzione, ma solo
periodicamente sul dataset di evaluation. Path generazione corso: BM25+cosine fusi
RRF → cosine_voyage diretto su top-100 fusi → B2 + KG. Zero chiamate Cohere a runtime.
Architettonicamente più pulito, elimina dipendenza esterna runtime, ma non urgente.

---

## Schema di registrazione per ipotesi future

Ogni nuova H si registra con:
- **Ipotesi formulata** (data + fonte: analista, review, sessione)
- **Verifica empirica** (data + path + numeri al render)
- **Conclusione** (cosa l'evidenza dimostra)
- **Difesa contro drift** (se in futuro qualcuno proponesse X, questa è la prova del perché no)

Non aggiungere H1+ a meno che ci sia verifica empirica al render. Le ipotesi non verificate
restano in `VERIFICATION_DEBT.md §2` come discrepanze da chiudere.
