# Skills per Phase — Cheatsheet operativa Nexus EduVault

> **Scopo.** Per ogni prompt del `NEXUS_EDUVAULT_Supreme_Master_Execution_Plan_v4_0.md` (FASE 1→7), questo documento dice se e quali skill/MCP attivare, perché, e la **riga esatta** da pre-pendere al prompt per forzarmi a usarle.
>
> **Stato discovery skill.** Nel nostro ambiente VS Code l'estensione Claude Code non auto-attiva le skill in `.claude/skills/` (bug Anthropic noto). Per farmi usare una skill, scrivi nel prompt una **istruzione esplicita in linguaggio naturale**, non `/nome-skill`. Esempio funzionante: `"Prima di scrivere codice, apri e applica .claude/skills/<nome>/SKILL.md."` In questo modo io lancio `Read` su quel file e lo seguo come istruzione operativa.
>
> **Principio di onestà (REI-5).** Dove una skill non aggiunge valore reale al prompt — perché il compito è deterministico, vincolato dalla BP o già coperto dai REI — questo file scrive **"nessuna skill necessaria"** invece di gonfiare la lista. La regola: aggiungo una skill solo se cambia il risultato.

---

## Indice rapido per fase

| Fase | Prompt | Skill chiave | Note |
|---|---|---|---|
| **FASE 1** DB+Auth | 1.1–1.5 | karpathy-guidelines (1.3), niente per 1.1/1.2/1.4/1.5 | quasi tutto deterministico |
| **FASE 2** KB+RAG | 2.1–2.6 | langchain-rag (2.5), karpathy-guidelines (2.2) | parsing/chunking critico |
| **FASE 3** Agenti | 3.1–3.5 | **langgraph-fundamentals** (3.1, 3.3, 3.4, 3.5), langgraph-persistence (3.1), langgraph-cli (3.5), karpathy-guidelines (3.4) | core differenziale |
| **FASE 4** Builder | 4.1–4.7 | postgres MCP (4.6), karpathy-guidelines (4.5) | molto deterministico |
| **FASE 5** API | 5.1–5.5 | karpathy-guidelines (5.1), langgraph-human-in-the-loop (5.1) | endpoint deterministici |
| **FASE 6** Frontend | 6.1–6.10 | **frontend-design + impeccable + ckm:ui-styling + ckm:design-system + shadcn MCP** (massiccio uso), cdt-* (6.10) | dove le skill cambiano davvero il risultato |
| **FASE 7** Deploy | 7.1–7.5 | cdt-debug-optimize-lcp (7.3), cdt-a11y-debugging (7.3) | E2E + perf pre-deploy |

---

## FASE 1 — Database, Auth, Modelli Pydantic

### Prompt 1.1 — Schema SQL `001_initial.sql`
**Tipo task:** deterministico — copia letterale BP §03 + GAP-3.
**Skill necessarie:** **NESSUNA.**
**Perché niente:** il prompt è esplicito su cosa scrivere (tabelle nell'ordine BP, GAP-3 audio_tracks e audio_manifest_path). Nessuna scelta di design. Una skill aggiungerebbe rumore.
**Riga da pre-pendere:** nessuna — il prompt va lanciato così com'è.
**Già eseguito** nella nostra conversazione: ✅ verde, schema applicato a DB di test senza errori.

### Prompt 1.2 — Modelli Pydantic (4 file)
**Tipo task:** deterministico — copia letterale BP §04 distribuita su 4 file.
**Skill necessarie:** **NESSUNA.**
**Perché niente:** stesso ragionamento di 1.1. La BP §04 mostra ogni modello completo. mypy + ruff sono i veri "checker" qui, non una skill.
**Riga da pre-pendere:** nessuna.
**Nota:** se vuoi extra sicurezza che io non aggiunga campi inventati, aggiungi: `"Dopo aver scritto, esegui mypy --strict app/models/ e ruff check app/models/, riporta l'output."` (già nel prompt, ma rinforzo non guasta).

### Prompt 1.3 — Auth service (JWT + bcrypt)
**Tipo task:** semi-deterministico — la BP §08 fornisce le funzioni, ma JWT è un'area dove "scivolare" su dettagli sicurezza costa caro.
**Skill necessarie:** `karpathy-guidelines` come *rinforzo behaviorale*.
**Perché:** karpathy.guidelines rule #1 ("don't assume, surface tradeoffs") è preziosa qui — esempi tipici di assunzioni silenziose in auth: cosa accade se `is_active=false` arriva dopo l'emissione del token? Refresh può ri-emettere senza ricontrollare? La skill mi forza a esplicitarle invece di sceglierle silenziosamente.
**Riga da pre-pendere:**
```
Prima di scrivere codice, leggi .claude/skills/karpathy-guidelines/SKILL.md e applica le 4 regole. In particolare, per ogni decisione di security (claim payload, scadenza, revoca, refresh) dichiara esplicitamente l'assunzione PRIMA di codificarla.
```

### Prompt 1.4 — Seed admin
**Tipo task:** deterministico — copia BP §02.7.
**Skill necessarie:** **NESSUNA.**

### Prompt 1.5 — Smoke test FASE 1
**Tipo task:** esecuzione di comandi shell + verifica output.
**Skill necessarie:** **NESSUNA.**
**Nota REI-15:** dopo lo smoke test, a fine FASE 1, scatta il trigger (a) di REI-15 — devo fare `npx @colbymchenry/codegraph index` perché `app/` ora ha file non vuoti per la prima volta. Lo faccio io, non devi chiederlo.

---

## FASE 2 — Knowledge Base + RAG

### Prompt 2.1 — Parsing PDF con pdfplumber
**Tipo task:** semi-deterministico — la BP §06.1.1 Stadio 1 mostra il codice. Test su PDF reale.
**Skill necessarie:** **NESSUNA.**

### Prompt 2.2 — Chunking ibrido (regex + LLM fallback)
**Tipo task:** **alto rischio over-engineering.** Pattern regex per articoli (ART_PATTERN con bis/ter/quater), coverage check normalizzato, fallback paragrafo con overlap. Tante euristiche, tante scelte arbitrarie possibili.
**Skill necessarie:** `karpathy-guidelines` (rinforzo *simplicity-first*).
**Perché:** la BP §06.1.1 dà la struttura, ma quando scriverò i regex e le soglie sarei tentato di "aggiungere robustezza" (gestire casi limite mai visti). Karpathy.rule #2 ("minimum code, no speculative features") mi obbliga a fermarmi al minimum che passa i test.
**Riga da pre-pendere:**
```
Prima di scrivere codice, leggi .claude/skills/karpathy-guidelines/SKILL.md. Implementa SOLO i pattern regex e le soglie esplicitamente nella BP §06.1.1; non aggiungere casi limite "preventivi" — se il test reale su dm388_03.pdf passa, fermati.
```

### Prompt 2.3 — Classificazione + Embedding
**Tipo task:** integrazione con due servizi esterni (Anthropic per classify, Voyage per embed). La BP §06.1.1 Stadio 3-4 dà l'API.
**Skill necessarie:** **NESSUNA per ora.** Quando sarò in FASE 3 (research_agent) sarò più nel core LangChain/LangGraph; qui è solo "chiamare due API con retry".

### Prompt 2.4 — COURSE_CATALOG
**Tipo task:** deterministico — copia BP §13.
**Skill necessarie:** **NESSUNA.**

### Prompt 2.5 — KnowledgeRepository + RAG query
**Tipo task:** semi-deterministico ma con JOIN regionale NULL-safe complesso e top_k dinamico.
**Skill necessarie:** `langchain-rag`.
**Perché:** `langchain-rag` ha pattern testati per retriever, score filtering, dedup; il nostro `search_chunks` con JOIN regionale è custom ma può beneficiare di esempi di RAG con filtri ibridi (vector + scalar). Anche se la BP §06.3 dà la query SQL, la skill mi aiuta a non fare errori sui pattern di scoring/threshold.
**Riga da pre-pendere:**
```
Prima di scrivere codice, leggi .claude/skills/langchain-rag/SKILL.md per i pattern RAG con filtro ibrido. Applica al nostro caso (pgvector + JOIN regionale, NON LangChain retriever astratti).
```

### Prompt 2.6 — Endpoint `/api/regulations`
**Tipo task:** CRUD su REST. Auth + rate limit + pagination — tutto pattern standard.
**Skill necessarie:** **NESSUNA.**

---

## FASE 3 — Agenti LangGraph (CORE DIFFERENZIALE)

> Questa è la fase dove le skill `langchain-skills` ufficiali fanno la differenza più grande. Il claim di LangChain stesso è "boost Claude da 17% a 92% su task LangSmith/LangGraph". Per i 4 prompt di questa fase mi imporrei sempre l'attivazione esplicita.

### Prompt 3.1 — State + Checkpointer + Grafo (2 nodi)
**Tipo task:** **massima criticità.** NexusPipelineState con `operator.add` reducer, AsyncPostgresSaver, compile del grafo. Sbagliare qui costa rework in tutto il resto della pipeline.
**Skill necessarie:** **`langgraph-fundamentals` + `langgraph-persistence`** — entrambe.
**Perché:**
- `langgraph-fundamentals` (`INVOKE THIS SKILL when writing ANY LangGraph code` — è scritto letteralmente nella frontmatter) → StateGraph, nodi, edge, Command, Send, reducer.
- `langgraph-persistence` → AsyncPostgresSaver setup, schema iniziale, `setup()` first-run.
**Riga da pre-pendere:**
```
Prima di scrivere codice, leggi e applica .claude/skills/langgraph-fundamentals/SKILL.md e .claude/skills/langgraph-persistence/SKILL.md. Verifica che StateGraph e AsyncPostgresSaver vengano usati esattamente come nei pattern di quelle skill. Il grafo deve avere ESATTAMENTE 2 nodi (FIX-1 v2.0).
```

### Prompt 3.2 — PacingEngine (1 slide / 30 secondi)
**Tipo task:** logica deterministica con formula esplicita nel prompt. È matematica, non LangGraph.
**Skill necessarie:** **NESSUNA.**
**Perché niente:** il vincolo `SECONDS_PER_SLIDE = 30` e i risultati attesi (1h→120 slide, 8h→960) sono nel prompt. langgraph-* non aiuta — non c'è grafo qui.

### Prompt 3.3 — Research Agent
**Tipo task:** nodo LangGraph che usa il pool, fa RAG, distribuisce chunk con keyword overlap + ribilanciamento. È **un nodo** del grafo di 3.1.
**Skill necessarie:** `langgraph-fundamentals` (per la firma `research_agent(state) → dict`), `langchain-rag` (per i pattern di query semantica).
**Riga da pre-pendere:**
```
Prima di scrivere codice, leggi .claude/skills/langgraph-fundamentals/SKILL.md (sezione "node signatures and return types") e .claude/skills/langchain-rag/SKILL.md (filtri ibridi). Il nodo deve ritornare un dict che il reducer di NexusPipelineState sappia mergiare.
```

### Prompt 3.4 — Content Agent (circuit breaker INLINE)
**Tipo task:** secondo nodo del grafo. Retry LLM + JSON parsing + **circuit breaker come contatore inline** (FIX-3 — NO classe separata).
**Skill necessarie:** `langgraph-fundamentals` + **`karpathy-guidelines` (critico qui)**.
**Perché karpathy:** FIX-3 dice "NO classe separata, contatore inline". È esattamente il pattern karpathy.rule #2 ("no abstractions for single-use code"). Senza la skill, io sarei tentato di estrarre `class ModuleCircuitBreaker` perché "è più pulito" — la skill mi blocca.
**Riga da pre-pendere:**
```
Prima di scrivere codice, leggi .claude/skills/langgraph-fundamentals/SKILL.md e .claude/skills/karpathy-guidelines/SKILL.md. ATTENZIONE FIX-3: il circuit breaker DEVE essere un contatore inline (failed_count: int) nella funzione content_agent, NON una classe separata. Se vedi te stesso scrivere "class Circuit" → fermati e rileggi karpathy regola #2.
```

### Prompt 3.5 — Pipeline E2E (no build)
**Tipo task:** test di integrazione `graph.ainvoke` con timeout.
**Skill necessarie:** `langgraph-cli` (opzionale — utile per debug interattivo).
**Perché:** se il test fallisce, posso usare `langgraph dev` per ispezionare lo stato a ogni nodo invece di mettere print sparsi. Aggiunge valore solo se il test fa errori.
**Riga da pre-pendere:** non necessaria se tutto fila liscio. Se il test fallisce:
```
Il test di pipeline E2E fallisce. Leggi .claude/skills/langgraph-cli/SKILL.md e dimmi come usare `langgraph dev` per ispezionare lo stato al nodo che fallisce.
```

---

## FASE 4 — Production Builder

### Prompt 4.1 — `inspect_pptx_template.py`
**Tipo task:** script CLI deterministico — BP §07.3.
**Skill necessarie:** **NESSUNA.**

### Prompt 4.2 — SlideBuilder
**Tipo task:** python-pptx con try/except. BP §07.
**Skill necessarie:** **NESSUNA.**
**Nota REI-3:** ricorda Semaphore(1) downstream (architetturale). Già nei REI.

### Prompt 4.3 — Image Service (sanitize_svg INLINE)
**Tipo task:** sanitizzazione SVG + download + Pillow validate. FIX-2 dice INLINE.
**Skill necessarie:** **NESSUNA.**
**Nota karpathy implicita:** "INLINE, not separate utils/svg_sanitizer.py" è esattamente la regola karpathy. Già esplicito nel prompt → non serve attivare la skill, basta il prompt.

### Prompt 4.4 — PDF Builder con Jinja2 (OPT-3)
**Tipo task:** template Jinja2 + WeasyPrint.
**Skill necessarie:** **NESSUNA.**
**Perché niente:** non abbiamo una skill Jinja2 dedicata. La BP §07.2 + il prompt danno tutto quello che serve. `ckm:design` ha contesto sui template HTML ma per un PDF dispensa formativo è eccessiva.

### Prompt 4.5 — ProductionBuilder (orchestratore)
**Tipo task:** orchestrator con memory check, disk check, asyncio.to_thread. Logica complessa di error handling tra 4 builder.
**Skill necessarie:** `karpathy-guidelines`.
**Perché:** orchestrator = tentazione massima di over-engineering ("cosa succede se memoria scende durante PPTX?", "retry?", "fallback parziale?"). karpathy ferma queste derive.
**Riga da pre-pendere:**
```
Prima di scrivere codice, leggi .claude/skills/karpathy-guidelines/SKILL.md. Implementa SOLO il flusso happy path + i 2-3 fallback nella BP §07.1. NON aggiungere strategie di recovery non richieste.
```

### Prompt 4.6 — Audio Service (edge-tts — OPT-1)
**Tipo task:** integrazione edge-tts + mutagen + DB insert. Il prompt è già molto dettagliato.
**Skill necessarie:** `postgres` MCP (read-only, per verificare che lo schema audio_tracks supporti il payload prima di scrivere l'INSERT).
**Perché:** voglio essere sicuro che `voice VARCHAR(50)` accetti `'it-IT-DiegoNeural'` (16 char) e che la FK ON DELETE CASCADE non sorprenda. MCP postgres lo verifica in 2 query.
**Riga da pre-pendere:**
```
Prima di scrivere l'INSERT su audio_tracks, usa il MCP postgres (restricted) per fare \d audio_tracks e verificare i constraint. Dichiara nei commenti che hai verificato lo schema.
```

### Prompt 4.7 — Test E2E Build sintetico (con audio)
**Tipo task:** script test.
**Skill necessarie:** **NESSUNA.**

---

## FASE 5 — Orchestrazione API + WebSocket

### Prompt 5.1 — `generation_service.py`
**Tipo task:** **massima criticità.** Semaphore(1), pipeline wrapper con timeout, recovery, WebSocket progress, shutdown event. È il cuore del backend.
**Skill necessarie:** `karpathy-guidelines` + `langgraph-human-in-the-loop`.
**Perché:**
- `karpathy` per non over-engineering — il prompt dice di non duplicare il semaforo (FIX-7 v2.0).
- `langgraph-human-in-the-loop` per il pattern `interrupt/resume` se decidiamo di supportare cancellazione job da UI (BP cita possibilmente — controlla).
**Riga da pre-pendere:**
```
Prima di scrivere codice, leggi .claude/skills/karpathy-guidelines/SKILL.md. FIX-7 v2.0: _job_semaphore vive QUI (generation_service.py), non in dependencies.py. Se la BP suggerisce duplicazione → ignora, FIX prevale.
```

### Prompt 5.2 — Endpoint `/api/courses`
**Tipo task:** CRUD REST.
**Skill necessarie:** **NESSUNA.**

### Prompt 5.3 — WebSocket progress autenticato
**Tipo task:** WebSocket + JWT + ownership check.
**Skill necessarie:** **NESSUNA.**

### Prompt 5.4 — Endpoint `/api/admin`
**Tipo task:** CRUD REST con ruoli.
**Skill necessarie:** **NESSUNA.**

### Prompt 5.5 — Smoke test E2E backend
**Tipo task:** esecuzione comandi.
**Skill necessarie:** **NESSUNA.**
**REI-15:** trigger (b) fine FASE 5 → reindex codegraph automatico.

---

## FASE 6 — Frontend shadcn-admin (DOVE LE SKILL FANNO LA VERA DIFFERENZA)

> Per FASE 6 vale la **regola design top-down** del SKILLS_PLAYBOOK §7: per ogni componente non triviale, l'ordine di consultazione è:
> 1. `ckm:design-system` (token base)
> 2. `frontend-design` (direzione estetica)
> 3. `impeccable` (audit primo draft)
> 4. `ckm:ui-styling` (traduzione in Tailwind+shadcn)
> 5. `shadcn` MCP (API esatta del componente)
>
> Per evitare che ogni prompt diventi un poema, raccomando di **pre-pendere una sola riga all'inizio della FASE 6** che imposta il workflow, poi i singoli prompt restano puliti.

### Prompt 6.1 — Clone template
**Tipo task:** git clone + cleanup.
**Skill necessarie:** **NESSUNA.**

### Prompt 6.2 — Inventario componenti
**Tipo task:** `find` + scrittura markdown.
**Skill necessarie:** **NESSUNA.**

### Prompt 6.3 — Branding C.F.P. Montessori (CSS vars + Tailwind)
**Tipo task:** **alto valore design.** Sovrascrivere `:root`, `tailwind.config.ts`, sostituire logo.
**Skill necessarie:** **`ckm:design-system` + `ckm:brand`**.
**Perché:**
- `ckm:design-system` → token architecture primitive→semantic→component, mapping HEX→HSL per CSS variables.
- `ckm:brand` → consistency checklist, logo usage rules, voice framework (utile se ci sono claim/footer).
**Riga da pre-pendere:**
```
Prima di scrivere codice, leggi .claude/skills/ckm:design-system/SKILL.md e .claude/skills/ckm:brand/SKILL.md. Mappa la palette HEX del cliente in token semantici (primary, secondary, accent, neutrals) prima di toccare :root.
```

### Prompt 6.4 — Tipi TypeScript da OpenAPI
**Tipo task:** comando CLI `openapi-typescript`.
**Skill necessarie:** **NESSUNA.**

### Prompt 6.5 — API client + WebSocket client
**Tipo task:** scrittura TypeScript di un client REST + WS. Niente design qui.
**Skill necessarie:** **NESSUNA.**

### Prompt 6.6 — Pagina Login
**Tipo task:** prima vera pagina UI custom.
**Skill necessarie:** **`frontend-design` + `impeccable` + `ckm:ui-styling` + `shadcn` MCP.**
**Perché ora attivo tutto il top-down:**
- `frontend-design` (Anthropic ufficiale): forza scelte estetiche deliberate prima di scrivere JSX. Anti-AI-slop.
- `impeccable` (Bakaus): audit del primo draft per gerarchia visiva, spacing, typography.
- `ckm:ui-styling`: shadcn+Tailwind+Radix patterns esatti.
- `shadcn` MCP: API reale di `<Form>`, `<Input>`, `<Button>` (auto-attivo se `components.json` esiste).
**Riga da pre-pendere — usare UNA volta all'inizio di FASE 6 e ripetere su 6.6, 6.7, 6.8, 6.9:**
```
Workflow design top-down obbligatorio per questo prompt:
1. Leggi .claude/skills/frontend-design/SKILL.md → decidi Purpose/Tone/Constraints/Differentiation per la pagina.
2. Leggi .claude/skills/ckm:ui-styling/SKILL.md per gli idiomi shadcn+Tailwind.
3. Scrivi il primo draft.
4. Leggi .claude/skills/impeccable/SKILL.md → fai self-audit (gerarchia, spacing, alignment) e correggi.
5. Usa il MCP shadcn per le API esatte dei componenti che inserisci.
Mostra le decisioni dei punti 1 e 4 nei commenti del file React.
```

### Prompt 6.7 — Dashboard + Lista corsi
**Tipo task:** dashboard con stats card + DataTable. Pattern Linear.app menzionato nel prompt.
**Skill necessarie:** stesse di 6.6 + esplicitamente **`impeccable`** per il badge/stato (la skill ha pattern specifici per stati).
**Riga da pre-pendere:** stessa di 6.6, con aggiunta:
```
Per i badge di stato del corso (generating, completed, certified, failed), applica esplicitamente .claude/skills/impeccable/SKILL.md sezione "stati e badge" — colori semantici, pulse animation solo per stati attivi.
```

### Prompt 6.8 — Wizard 6 step
**Tipo task:** il pezzo più complesso del frontend. Wizard multistep ispirato Stripe Checkout.
**Skill necessarie:** stesse di 6.6 + **`ckm:design-system`** per i token di transizione tra step.
**Riga da pre-pendere:** stessa di 6.6, con aggiunta:
```
Per il wizard, leggi anche .claude/skills/ckm:design-system/SKILL.md per pattern di progress indicator e transition tokens. Il progress indicator deve essere coerente con la palette brand definita in 6.3.
```

### Prompt 6.9 — Progress Monitor + Dettaglio + Normative + Admin
**Tipo task:** 4 pagine in un solo prompt. Volume alto, rischio AI-slop massimo.
**Skill necessarie:** stesse di 6.6 con **forte enfasi su `impeccable`** (4 pagine = 4 audit).
**Riga da pre-pendere:** stessa di 6.6, con aggiunta:
```
ATTENZIONE: questo prompt copre 4 pagine. Per OGNI pagina ripeti il workflow design top-down. NON saltare il self-audit con impeccable per nessuna delle 4. Se trovi che la 4ª sta diventando "copia/incolla" delle prime 3, fermati e rileggi karpathy-guidelines regola #3 (surgical changes).
```

### Prompt 6.10 — Navigazione, routing, build
**Tipo task:** routing + build verification.
**Skill necessarie:** **`cdt-chrome-devtools`** + **`chrome-devtools` MCP** per la verifica visuale post-build.
**Perché:** "verifica manuale: Login → Dashboard → ... → Download" — il modo professionale di farla è con un browser controllato, non con screenshot manuali.
**Riga da pre-pendere:**
```
Dopo `npm run build` e `npm run dev`, usa il MCP chrome-devtools (e la skill .claude/skills/cdt-chrome-devtools/SKILL.md) per simulare il flow utente: Login → Dashboard → Nuovo Corso → submit → Progress → Download. Cattura screenshot per evidenza, riporta eventuali errori console.
```

---

## FASE 7 — Certification, Audit, Metriche, E2E, Deploy

### Prompt 7.1 — Certification Service (SOLO StylePatternExtractor)
**Tipo task:** estrazione metadati strutturali deterministica.
**Skill necessarie:** `karpathy-guidelines`.
**Perché:** FIX-4 dice "NO certificati PDF, NO QR code". Tentazione di "completare" lo scope è alta. karpathy lo blocca.
**Riga da pre-pendere:**
```
Prima di scrivere codice, leggi .claude/skills/karpathy-guidelines/SKILL.md. FIX-4: SOLO StylePatternExtractor + certify_course. NO PDF certificato, NO QR. Se la BP suggerisce features extra → ignora, FIX prevale.
```

### Prompt 7.2 — Audit & cleanup
**Tipo task:** INSERT audit_log + cleanup_old_images schedulato.
**Skill necessarie:** **NESSUNA.**

### Prompt 7.3 — Testing E2E completo
**Tipo task:** test integrazione + EXPLAIN ANALYZE + crash test.
**Skill necessarie:** **`cdt-debug-optimize-lcp` + `cdt-a11y-debugging`** (per la parte UI del flow) + `postgres` MCP (per EXPLAIN ANALYZE).
**Riga da pre-pendere:**
```
Per l'E2E, usa il MCP postgres per EXPLAIN ANALYZE delle query RAG (verifica uso HNSW). Per la verifica frontend nel flow completo, usa la skill .claude/skills/cdt-debug-optimize-lcp/SKILL.md per controllare LCP < 2.5s sulle pagine principali.
```

### Prompt 7.4 — Backup & Ops
**Tipo task:** script bash + doc markdown.
**Skill necessarie:** **NESSUNA.**

### Prompt 7.5 — Deploy su VPS
**Tipo task:** scrittura di artefatti deploy (nginx.conf prod, docker-compose.prod.yml, install.sh, PRECHECK).
**Skill necessarie:** **NESSUNA.**
**Nota:** REI-13 (dominio) prevale ovunque. Anche se in questo prompt sei tentato di specificare un dominio, **lo lasci `<DOMAIN_TBD>` finché l'umano non lo fissa esplicitamente**. La nostra costituzione lo impone (CLAUDE.md REI-13).

---

## Sintesi: prompt che DAVVERO beneficiano di skill esplicite

Se vuoi memorizzare solo l'essenziale, questi sono i **10 prompt** dove pre-pendere una riga skill fa una differenza misurabile:

| # | Prompt | Skill | Motivo in 1 riga |
|---|---|---|---|
| 1 | 1.3 Auth | karpathy | esplicitare assunzioni di sicurezza |
| 2 | 2.2 Chunking | karpathy | no euristiche speculative |
| 3 | 2.5 KnowledgeRepository | langchain-rag | pattern RAG ibridi |
| 4 | 3.1 LangGraph state+graph | langgraph-fundamentals + persistence | API LangGraph esatte |
| 5 | 3.3 Research Agent | langgraph-fundamentals + langchain-rag | firma nodo + query semantica |
| 6 | 3.4 Content Agent | langgraph-fundamentals + karpathy | NO classe circuit breaker |
| 7 | 4.5 ProductionBuilder | karpathy | no over-engineering orchestrator |
| 8 | 4.6 Audio Service | postgres MCP | verifica schema audio_tracks |
| 9 | 5.1 generation_service | karpathy + langgraph-human-in-the-loop | FIX-7 + cancellazione job |
| 10 | 6.3–6.9 Tutte le UI custom | frontend-design + impeccable + ckm:ui-styling + ckm:design-system + shadcn MCP | anti-AI-slop |

Per **tutto il resto** (1.1, 1.2, 1.4, 1.5, 2.1, 2.3, 2.4, 2.6, 3.2, 3.5, 4.1, 4.2, 4.3, 4.4, 4.7, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.4, 6.5, 6.10, 7.2, 7.4, 7.5) il prompt va lanciato così com'è — i REI di CLAUDE.md e la BP danno già istruzioni sufficienti.

---

## Formula universale (se non ricordi la riga specifica)

Se sei a corto di tempo e non vuoi cercare la riga esatta in questa cheatsheet, **una formula generica che funziona quasi sempre**:

```
Prima di iniziare, consulta docs/SKILLS_PER_PHASE_CHEATSHEET.md alla riga di questo prompt (es. "Prompt 3.4") e applica le skill che indica. Poi procedi.
```

Questa formula sposta su di me l'onere di trovare la skill giusta — è una riga sola che funziona per ogni prompt del piano.

---

# 📋 APPENDICE COPIA-INCOLLA

> Solo i prompt che richiedono skill. Per ognuno: numero + riga da pre-pendere al prompt.
> Per tutti i prompt non elencati qui (1.1, 1.2, 1.4, 1.5, 2.1, 2.3, 2.4, 2.6, 3.2, 3.5, 4.1, 4.2, 4.3, 4.4, 4.7, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.4, 6.5, 6.10, 7.2, 7.4, 7.5) → **nessuna riga da aggiungere**, lancia il prompt così com'è.

---

### **1.3** Auth service
```
Prima di scrivere codice, leggi .claude/skills/karpathy-guidelines/SKILL.md e applica le 4 regole. In particolare, per ogni decisione di security (claim payload, scadenza, revoca, refresh) dichiara esplicitamente l'assunzione PRIMA di codificarla.
```

---

### **2.2** Chunking ibrido
```
Prima di scrivere codice, leggi .claude/skills/karpathy-guidelines/SKILL.md. Implementa SOLO i pattern regex e le soglie esplicitamente nella BP §06.1.1; non aggiungere casi limite "preventivi" — se il test reale su dm388_03.pdf passa, fermati.
```

---

### **2.5** KnowledgeRepository + RAG
```
Prima di scrivere codice, leggi .claude/skills/langchain-rag/SKILL.md per i pattern RAG con filtro ibrido. Applica al nostro caso (pgvector + JOIN regionale, NON LangChain retriever astratti).
```

---

### **3.1** LangGraph state + checkpointer + grafo
```
Prima di scrivere codice, leggi e applica .claude/skills/langgraph-fundamentals/SKILL.md e .claude/skills/langgraph-persistence/SKILL.md. Verifica che StateGraph e AsyncPostgresSaver vengano usati esattamente come nei pattern di quelle skill. Il grafo deve avere ESATTAMENTE 2 nodi (FIX-1 v2.0).
```

---

### **3.3** Research Agent
```
Prima di scrivere codice, leggi .claude/skills/langgraph-fundamentals/SKILL.md (sezione "node signatures and return types") e .claude/skills/langchain-rag/SKILL.md (filtri ibridi). Il nodo deve ritornare un dict che il reducer di NexusPipelineState sappia mergiare.
```

---

### **3.4** Content Agent
```
Prima di scrivere codice, leggi .claude/skills/langgraph-fundamentals/SKILL.md e .claude/skills/karpathy-guidelines/SKILL.md. ATTENZIONE FIX-3: il circuit breaker DEVE essere un contatore inline (failed_count: int) nella funzione content_agent, NON una classe separata. Se vedi te stesso scrivere "class Circuit" → fermati e rileggi karpathy regola #2.
```

---

### **4.5** ProductionBuilder
```
Prima di scrivere codice, leggi .claude/skills/karpathy-guidelines/SKILL.md. Implementa SOLO il flusso happy path + i 2-3 fallback nella BP §07.1. NON aggiungere strategie di recovery non richieste.
```

---

### **4.6** Audio Service
```
Prima di scrivere l'INSERT su audio_tracks, usa il MCP postgres (restricted) per fare \d audio_tracks e verificare i constraint. Dichiara nei commenti che hai verificato lo schema.
```

---

### **5.1** generation_service
```
Prima di scrivere codice, leggi .claude/skills/karpathy-guidelines/SKILL.md. FIX-7 v2.0: _job_semaphore vive QUI (generation_service.py), non in dependencies.py. Se la BP suggerisce duplicazione → ignora, FIX prevale.
```

---

### **6.3** Branding C.F.P. Montessori
```
Prima di scrivere codice, leggi .claude/skills/ckm:design-system/SKILL.md e .claude/skills/ckm:brand/SKILL.md. Mappa la palette HEX del cliente in token semantici (primary, secondary, accent, neutrals) prima di toccare :root.
```

---

### **6.6** Pagina Login (e base per 6.7, 6.8, 6.9)
```
Workflow design top-down obbligatorio per questo prompt:
1. Leggi .claude/skills/frontend-design/SKILL.md → decidi Purpose/Tone/Constraints/Differentiation per la pagina.
2. Leggi .claude/skills/ckm:ui-styling/SKILL.md per gli idiomi shadcn+Tailwind.
3. Scrivi il primo draft.
4. Leggi .claude/skills/impeccable/SKILL.md → fai self-audit (gerarchia, spacing, alignment) e correggi.
5. Usa il MCP shadcn per le API esatte dei componenti che inserisci.
Mostra le decisioni dei punti 1 e 4 nei commenti del file React.
```

---

### **6.7** Dashboard + Lista corsi
```
Workflow design top-down obbligatorio per questo prompt:
1. Leggi .claude/skills/frontend-design/SKILL.md → decidi Purpose/Tone/Constraints/Differentiation per la pagina.
2. Leggi .claude/skills/ckm:ui-styling/SKILL.md per gli idiomi shadcn+Tailwind.
3. Scrivi il primo draft.
4. Leggi .claude/skills/impeccable/SKILL.md → fai self-audit (gerarchia, spacing, alignment) e correggi.
5. Usa il MCP shadcn per le API esatte dei componenti che inserisci.
Mostra le decisioni dei punti 1 e 4 nei commenti del file React.
Per i badge di stato del corso (generating, completed, certified, failed), applica esplicitamente .claude/skills/impeccable/SKILL.md sezione "stati e badge" — colori semantici, pulse animation solo per stati attivi.
```

---

### **6.8** Wizard 6 step
```
Workflow design top-down obbligatorio per questo prompt:
1. Leggi .claude/skills/frontend-design/SKILL.md → decidi Purpose/Tone/Constraints/Differentiation per la pagina.
2. Leggi .claude/skills/ckm:ui-styling/SKILL.md per gli idiomi shadcn+Tailwind.
3. Scrivi il primo draft.
4. Leggi .claude/skills/impeccable/SKILL.md → fai self-audit (gerarchia, spacing, alignment) e correggi.
5. Usa il MCP shadcn per le API esatte dei componenti che inserisci.
Mostra le decisioni dei punti 1 e 4 nei commenti del file React.
Per il wizard, leggi anche .claude/skills/ckm:design-system/SKILL.md per pattern di progress indicator e transition tokens. Il progress indicator deve essere coerente con la palette brand definita in 6.3.
```

---

### **6.9** Progress Monitor + Dettaglio + Normative + Admin
```
Workflow design top-down obbligatorio per questo prompt:
1. Leggi .claude/skills/frontend-design/SKILL.md → decidi Purpose/Tone/Constraints/Differentiation per la pagina.
2. Leggi .claude/skills/ckm:ui-styling/SKILL.md per gli idiomi shadcn+Tailwind.
3. Scrivi il primo draft.
4. Leggi .claude/skills/impeccable/SKILL.md → fai self-audit (gerarchia, spacing, alignment) e correggi.
5. Usa il MCP shadcn per le API esatte dei componenti che inserisci.
Mostra le decisioni dei punti 1 e 4 nei commenti del file React.
ATTENZIONE: questo prompt copre 4 pagine. Per OGNI pagina ripeti il workflow. NON saltare il self-audit con impeccable per nessuna delle 4. Se trovi che la 4ª sta diventando "copia/incolla" delle prime 3, fermati e rileggi karpathy-guidelines regola #3 (surgical changes).
```

---

### **7.1** Certification Service
```
Prima di scrivere codice, leggi .claude/skills/karpathy-guidelines/SKILL.md. FIX-4: SOLO StylePatternExtractor + certify_course. NO PDF certificato, NO QR. Se la BP suggerisce features extra → ignora, FIX prevale.
```

---

### **7.3** Testing E2E
```
Per l'E2E, usa il MCP postgres per EXPLAIN ANALYZE delle query RAG (verifica uso HNSW). Per la verifica frontend nel flow completo, usa la skill .claude/skills/cdt-debug-optimize-lcp/SKILL.md per controllare LCP < 2.5s sulle pagine principali.
```
