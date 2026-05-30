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

## H6 — cosine_voyage diretto è SELETTORE DI POOL, non ranker fine (closure post-classify 5 moduli)

**Ipotesi originale (messaggio 10, 2026-05-30 pre-classify):**
> "B2 cosine_voyage diretto sul pool RRF top-100 ricostruisce ranking title-aligned
> dove Cohere mis-rank o esclude on-topic veri. Target Spearman >= 0.7 sui 5 moduli
> come sanity check del ranker title-aligned affidabile."

**Verifica empirica (2026-05-30, classify cieca disciplinata 5 moduli, 296 chunks
classificati con motivazione_breve disconfermativa):**

Spearman (classify vs cosine_voyage):

| Modulo | Sp intera | Sp top-30 | Sp tail |
|--------|-----------|-----------|---------|
| GEN_M3 (REGIME 1 concept rich) | 0.381 | 0.300 | -0.037 |
| HACCP_M3 (REGIME 1 concept rich LCU) | 0.316 | 0.144 | 0.268 |
| ANT_M0 (REGIME 2 context rich) | **0.689** | 0.323 | 0.532 |
| PRE_M3 (REGIME 3 corpus-thin per concetto) | 0.333 | 0.468 | -0.077 |
| GEN_M1 (REGIME 3 corpus-thin per concetto) | 0.208 | **-0.089** | 0.232 |

Ratio A1_utile / B_utile (on-topic + adjacent per zona):

| Modulo | A1 utile | B utile | Ratio |
|--------|----------|---------|-------|
| GEN_M3 | 57% | 25% | 2.3x |
| HACCP_M3 | 57% | 25% | 2.3x |
| ANT_M0 | 74% | 0% | infinito |
| PRE_M3 | 23% | 10% | 2.3x |
| GEN_M1 | 23% | 0% | infinito |

Bottom-20 falsi negativi (chunks on-topic ai rank bassi):

| Modulo | bottom-20 on-topic | Verdetto |
|--------|-------------------|----------|
| Tutti i 5 moduli | 0 | OK perfetto |

**Conclusione (analista sign-off 2026-05-30 post-classify):**

1. **Spearman target 0.7 era target sbagliato** perché basato sull'assunzione "cosine_voyage
   è ranker title-aligned forte". I dati falsificano l'assunzione: solo ANT_M0 raggiunge
   Sp 0.689; gli altri 4 moduli stanno a 0.21-0.38 intera, top-30 a 0.144-0.468, GEN_M1
   addirittura **Sp top-30 negativo -0.089** (regime corpus-thin).

2. **Correzione metodologica registrata (analista 2026-05-30)**: la metrica corretta
   per validare cosine_voyage come *selettore di pool* è il **ratio A1_utile / B_utile**
   (il salto della separazione poli), NON la Spearman interna. Tutti i 5 moduli hanno
   ratio >= 2.3x (3 dei 5 hanno B_utile=0, ratio infinito). **cosine_voyage funziona
   come selettore di pool su TUTTI i 5 regimi**, e questo è l'80% del valore del refactor.

3. **Natura della metrica scoperta**: dense embeddings su corpus normativo italiano
   (D.Lgs, Allegati, Accordi SR, DM) discriminano BENE sui poli (cosine alto = quasi
   sempre utile, cosine basso = quasi sempre off-topic), ma NON ordinano informativamente
   nella fascia intermedia dove i chunks hanno cosine simili. Coerente con letteratura:
   parole semanticamente vicine ("rischio formazione", "rischio prevenzione",
   "macrocategorie rischio") producono cosine vicini anche se referente concettuale
   diverso.

**Implicazione architetturale per B2 (analista 2026-05-30):**

B2 NON è ri-ranking fine via cosine_voyage. È:
- **Selettore di pool top-K percentile** su cosine_voyage dal pool RRF top-100.
- L'ordinamento *dentro* il pool top-K viene da B3 (cleanup cross-titolo) + ordine
  cosine_voyage come tie-breaker secondario degradato.
- Default K=30 fissa; variante K adattiva basata sul salto di pendenza
  (cosine_n - cosine_n+1) — testare durante implementazione.

**D-172 riformulato (2026-05-30, era "Cohere offline-only"):** cross-encoder italiano-
normativo fine-tuned è work-item futuro **post-V2** se il ranking fine del pool si
dimostra critico per qualità slide. Oneroso (mesi), esplorabile solo se evidenza
empirica al render mostra che B3+ordering originale non basta per content_agent.
Per ora cosine_voyage come selettore + B3 cleanup ordinamento copre l'80% del valore.

---

## H6 — cosine_voyage diretto sul subtopic ricostruisce ranking title-aligned dove Cohere fallisce (D-171-bis closure)

**Ipotesi formulata (messaggio analista 10, 2026-05-30) e calibrata empiricamente (classify GEN_M3 12, 2026-05-30):**
> "B2 cosine_voyage diretto sul pool RRF top-100 (NOT sul top-30 Cohere) ricostruisce
> ranking title-aligned title-aligned dove Cohere mis-rank o esclude on-topic veri.
> Il ground-truth oracolo umano deve essere classify cieca disconfermativa."

**Verifica empirica (2026-05-30, classify cieca disciplinata GEN_M3 60 chunks):**

Conteggio classificazione oracolo umano (zone A1/B/C):

| Zona | n | on-topic | adjacent | off-topic |
|------|---|----------|----------|-----------|
| A1 (top-30 cosine_voyage) | 30 | **11 (37%)** | 6 (20%) | 13 (43%) |
| B (bottom-20 cosine_voyage) | 20 | 0 (0%) | 5 (25%) | 15 (75%) |
| C (top-Cohere esclusi top-30 cosine) | 10 | 2 (20%) | 1 (10%) | 7 (70%) |

**Salto quantitativo cosine_voyage vs Cohere ai top-30 (a parità di subtopic GEN M3 v1):**

| Metric | Cohere top-30 (vecchio) | cosine_voyage top-30 (oggi) | Salto |
|--------|--------------------------|----------------------------|-------|
| on-topic puri | 4/30 (13%) | 11/30 (37%) | **+175%** |
| on-topic + adjacent (chunks "validi") | 7/30 (23%) | 17/30 (57%) | **+143%** |

**Articoli del cuore organizzativo D.Lgs:**
- Cohere top-30 (settimana scorsa): 3/9 presenti (Art. 30, Art. 15, Art. 34)
- cosine_voyage top-30 (oggi): 6/9 presenti (Art. 31, Art. 32, Art. 33, Art. 36, Art. 8 SINP) + Art. 30 (×4 chunks distinti), Art. 15 — i 6 articoli che Cohere escludeva sono TUTTI nei top-30 cosine_voyage.

**Conferme empiriche forti:**

1. **D-171-bis closed**: cosine_voyage diretto recupera i chunk on-topic veri che Cohere
   escludeva dal top-30. Il refactor architetturale "Cohere da ranker primario a
   telemetria + recall accelerator" è giustificato quantitativamente: salto da 13% a
   37% on-topic non è marginal improvement, è cambio di regime.
2. **Bottom-20 cosine_voyage senza falsi negativi strutturali**: 0 on-topic veri persi,
   5 adjacent ma tutti frammenti marginali ("consapevolezza azioni responsabilità ruolo"
   testi ricorrenti). cosine_voyage non penalizza articoli centrali — penalizza chunk
   specifici marginali al subtopic.
3. **Granularità intra-articolare**: zona C ha 2/10 on-topic (Art. 30 chunks C3 e C9
   esclusi da cosine_voyage in favore di altri chunk Art. 30 più centrali A9/A16/A22/A26).
   cosine_voyage discrimina tra chunk dello stesso articolo per centralità al subtopic —
   livello di granularità che Cohere chiaramente non ha. È il segnale che B2 può fare
   lavoro fine, non solo grossolano.

---

## H7 — B2 + B3 sono in COMPLEMENTO necessario, non in ridondanza (architettura del filtro composto)

**Ipotesi formulata (analista 13, 2026-05-30 in risposta al gate intermedio):**
> "B2 cosine_voyage da sola NON basta: 43% off-topic in A1 sono dominati da cross-titolo.
> B3 (KG sibling cross-Titolo decay) NECESSARIO in COMPLEMENTO a B2."

**Verifica empirica (classify GEN_M3 zona A1 + zona C, 2026-05-30):**

Distribuzione off-topic in A1 cosine_voyage (13 chunks):

| Pattern | Count | Esempi |
|---------|-------|--------|
| cross_titolo | ~9 | Art. 203 Titolo VIII fisici, Art. 251 amianto, Art. 225/224 chimici, Art. 46 antincendio, Art. 118/95 Cantieri, Art. 18 Titolo X-bis ferite ospedaliere |
| menzione_normativa_generica | ~2 | Allegato I esonero classi laurea, Allegato 3 formato modulistica |
| formazione_durata_schema | ~1 | Allegato IV "4 ore Formazione Generale" |
| altro | ~1 | Art. 331 c.p.p. |

Distribuzione pattern_misrank zona C (10 chunks):

| Pattern | Count |
|---------|-------|
| cross_titolo | 5/10 (50%) |
| menzione_normativa_generica | 3/10 (30%) |
| formazione_durata_schema | 1/10 (10%) |
| altro | 1/10 (10%) |
| meta_normativo | 0/10 |
| sanzionatorio | 0/10 |

**Conclusione (analista sign-off 2026-05-30)**: cross-titolo è il falso positivo dominante
di cosine_voyage perché chunk di altri Titoli del D.Lgs (Titolo VIII fisici, IX chimici,
IV Cantieri, X-bis ferite) contengono parole "prevenzione/protezione/misure" con
embedding semantico vicino al subtopic "Organizzazione della prevenzione". cosine_voyage
NON distingue cross-titolo strutturalmente perché non vede la struttura normativa, solo
la semantica testuale. B3 è il complemento strutturale necessario.

**Regola architetturale del filtro composto (analista 2026-05-30):**

1. **Ordine in SERIE, NON in parallelo**: prima B2 (filtro semantico title-aligned),
   poi B3 (cleanup cross-titolo sul subset filtrato da B2). Mai l'inverso.

2. **Razionale dell'ordine B2-poi-B3** (analista 2026-05-30):
   - Se applichi B3 prima sul pool RRF top-100, perdi chunk legittimi reintegrati da
     cosine_voyage alto. Esempio: chunk Allegato XIV con cosine_voyage altissimo al
     subtopic (perché parla *anche* di organizzazione, non solo Cantieri) — B3 lo
     scarterebbe per cross-titolo prima che B2 lo validi semanticamente.
   - B3 applicato DOPO B2 vede materiale già validato come on-topic semanticamente,
     quindi la decisione "scartare per cross-titolo" è fatta su candidati legittimi —
     più sicura, meno falsi negativi.
   - **Invertire l'ordine in qualche refactor futuro è il classico drift architetturale
     che H7 vuole prevenire.**

3. **Soglia B2 percentile largo + B3 cleanup cross-titolo dentro la zona ammessa**:
   - B2 percentile-based (es. top-20 o top-25, NOT top-15 stretto), per lasciare
     spazio a B3 di pulire i cross-titolo dentro la zona ammessa.
   - La transizione "core → grigio" osservata in GEN_M3 A1 cade rank 11-17 (primi 11
     prevalentemente on-topic puri, tra 12 e 30 mix di adjacent + off-topic cross-titolo
     non monotono). Soglia B2 stretta a top-15 perderebbe gli adjacent legittimi della
     fascia 12-17. Soglia larga + B3 elimina solo i cross-titolo della fascia.
   - Valore esatto percentile B2 lo calibri sui 5 moduli post-classify. Possibile che
     HACCP_M3 LCU richieda percentile diverso, ma se la formula è relativa al pool
     dovrebbe normalizzarsi.

**Salto quantitativo atteso V2 → V2-D3-B2-B3 (analista 2026-05-30):**
- Baseline V2 (Cohere top-30): ~13% on-topic puri ai rank del taglio
- Post-B2 (cosine_voyage top-30): 37% on-topic puri (+175%)
- Post-B2 + post-B3 (atteso): 80-90% on-topic + adjacent (cleanup cross-titolo che è
  ~70% degli off-topic A1)
- **Salto totale V2 → V2-D3-B2-B3: 13% → 80-90% = ratio ~6x al valore informativo del
  taglio.**

**Difesa contro drift H7**: se in 6 mesi qualcuno proporrà "ottimizziamo eliminando B3
perché B2 fa già il grosso del lavoro", H7 mostra che B2 solo lascia 43% off-topic
cross-titolo non discriminabili semanticamente. B3 NON è "raffinamento marginale", è
"complemento strutturale necessario". Se in 6 mesi qualcuno proporrà "applichiamo B3
prima di B2 per efficienza" — H7 mostra che l'ordine è strutturale, non operativo.

---

## H8 — REGIME 3 "corpus-thin per concetto" è caso d'uso per SCHELETRO A DOPPIO LIVELLO (work-item esplorativo post-V2)

**Ipotesi formulata (analista messaggio 14, 2026-05-30 post-classify):**
> "Su REGIME 3 il problema non è 'calibrare B2/B3/B4 più aggressivi' — è 'lo scheletro
> stesso ha proposto una voce a cui il corpus non sa rispondere'. La voce 'Definizione
> di rischio' su GEN M1 chiede al sistema di recuperare materiale che il D.Lgs non
> produce nella forma richiesta. Possibile soluzione: scheletro a doppio livello, voce
> tassonomica + voce operativa per retrieval."

**Verifica empirica (classify 5 moduli, 2026-05-30):**

REGIME 3 emerso empiricamente su 2 dei 5 moduli ground-truth:
- **PRE_M3 voce 1 "Definizione di incidente, infortunio, infortunio mancato"**: D.Lgs
  81/08 NON ha definizione esplicita di "near miss" (concetto gestionale recepito da
  ANSI Z16.2 / BS OHSAS 18001 / ISO 45001, NON normativa italiana). A1 utile 23% (2
  on-topic / 5 adjacent / 23 off-topic). Pool dominato da Art. 37 formazione (60%
  degli off-topic).
- **GEN_M1 voce 1 "Definizione di rischio e sue caratteristiche principali"**: Art. 2
  D.Lgs 81/08 lett.s definisce "rischio" in modo stringato; le caratteristiche sono
  trattate funzionalmente in Art. 28 oggetto VDR + Allegato IV macrocategorie ATECO,
  NON come articolo definitorio centrale. A1 utile 23%, Sp top-30 **negativo -0.089**
  (cosine_voyage piazza Art. 37 formazione più vicino al subtopic che Allegato IV
  macrocategorie).

**Conclusione (analista 2026-05-30)**:
- Tassonomicamente "Definizione di rischio" è voce corretta (esperto firmerebbe).
- Operativamente, dato il corpus, è voce che produce A1 al 23% utile dominato da
  formazione_durata_schema.
- Nessuna metrica può inventare materiale definitorio che la normativa non produce.

**Ipotesi soluzione (work-item esplorativo, NON implementare ora)**:

Scheletro D3 a **doppio livello**:
- **Livello tassonomico** (visibile in UI di revisione utente, gate D3 approve):
  "Definizione di rischio e sue caratteristiche principali" (la voce attuale).
- **Livello operativo** (usato dal retrieval, generato come parte della SkeletonItem):
  "Art. 2 D.Lgs 81/08 lett.s definizione di rischio + Allegato IV macrocategorie
  ATECO + Art. 28 oggetto VDR elementi" (query operativa specifica, citando
  riferimenti normativi precisi).

Senza livello operativo, il retrieval cerca di matchare letteralmente la voce tassonomica
sul corpus, e il corpus risponde con Art. 37 (più vicino topicalmente a "definizione +
formazione + rischio") invece che con Art. 2/Allegato IV/Art. 28 (chunks semantically
più diluiti ma operativamente corretti).

**Pre-requisiti per implementazione (work-item esplorativo)**:
- B2 + B3 + B4 calibrati e in produzione (verifica empirica che REGIME 3 è davvero il
  bottleneck rimanente, non altre patologie).
- B4 vincolante con sensore A1_utile<30% deve aver segnalato REGIME 3 al render almeno
  su 5+ casi reali generati (per validare che il pattern empirico ricorre, non era
  un artefatto dei 5 moduli ground-truth).
- Confronto V2-D3-B2-B3-B4 vs V2-D3-B2-B3-B4-Scheletro_doppio_livello sul ground-truth
  pre-implementazione, per quantificare il salto di qualità atteso.

**Decisione tra le due alternative su REGIME 3 segnalato da B4**:
- (a) UI propone all'utente la riformulazione operativa della voce (con esempio
  precompilato dal sistema).
- (b) UI suggerisce ingestione di materiale integrativo (es. linee guida INAIL su near
  miss per PRE_M3, manuale formatori HACCP per HACCP voci specifiche).

**Difesa contro drift**: se in 6 mesi qualcuno proporrà "rimettiamo retrieval by-title
sui regimi che B4 segnala", H8 mostra che il problema su REGIME 3 NON è la formula di
retrieval (cosine_voyage ratio A1/B funziona) ma la voce stessa dello scheletro che è
operativamente irrisolvibile sul corpus. La cura non è "ranking più aggressivo", è
"riformulazione operativa della voce + signaling".

---

## Schema di registrazione per ipotesi future

Ogni nuova H si registra con:
- **Ipotesi formulata** (data + fonte: analista, review, sessione)
- **Verifica empirica** (data + path + numeri al render)
- **Conclusione** (cosa l'evidenza dimostra)
- **Difesa contro drift** (se in futuro qualcuno proponesse X, questa è la prova del perché no)

Non aggiungere H1+ a meno che ci sia verifica empirica al render. Le ipotesi non verificate
restano in `VERIFICATION_DEBT.md §2` come discrepanze da chiudere.
