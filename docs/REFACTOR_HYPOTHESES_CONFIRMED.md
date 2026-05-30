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

## Schema di registrazione per ipotesi future

Ogni nuova H si registra con:
- **Ipotesi formulata** (data + fonte: analista, review, sessione)
- **Verifica empirica** (data + path + numeri al render)
- **Conclusione** (cosa l'evidenza dimostra)
- **Difesa contro drift** (se in futuro qualcuno proponesse X, questa è la prova del perché no)

Non aggiungere H1+ a meno che ci sia verifica empirica al render. Le ipotesi non verificate
restano in `VERIFICATION_DEBT.md §2` come discrepanze da chiudere.
