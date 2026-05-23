# NEXUS EDUVAULT — PROJECT STATUS TRACKER & MODEL STRATEGY

**Progetto:** Nexus EduVault v1.0  
**Cliente:** C.F.P. Montessori  
**Fornitore:** Axialoop di Di Lonardo Alessandro  
**Riferimento:** Execution Plan v4.0 + Blueprint v7.0  
**Ultimo aggiornamento:** 2026-05-23 (Step A.1 + A.2 completati)  

---

## LEGENDA

| Simbolo | Significato |
|---|---|
| ⬜ | Non iniziata |
| 🔄 | In corso |
| ✅ | Completata |
| ❌ | Bloccata / Fallita |
| 🟡 | Completata con riserva (da rivedere) |

### Modelli Claude Code

| Sigla | Modello | Costo (per 1M token) | Quando usarlo |
|---|---|---|---|
| **S** | Sonnet 4.6 | $3 input / $15 output | Default. Task con specifiche chiare, codice da blueprint, CRUD, config, test |
| **O** | Opus 4.7 | $5 input / $25 output | Task complessi: algoritmi custom, architettura multi-file, prompt engineering, UI articolate |

> **Regola d'oro:** Opus costa ~1.67× Sonnet per token, ma usa più thinking token. In pratica su task complessi **Opus costa 2-3× Sonnet per sessione**. Usarlo solo dove il ragionamento profondo evita rework che costerebbe di più in sessioni Sonnet ripetute.

---

## STEP PRE-SVILUPPO

### STEP A — Inizializzazione CLAUDE.md + Struttura Cartelle

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| A.1 | Creazione CLAUDE.md | **S** | Copia esatta da spec, zero ragionamento | ✅ | 2026-05-23 | CLAUDE.md scritto + REI-12/13 aggiunte, .env.example creato, hook SessionStart onboarding configurato. |
| A.2 | Struttura cartelle backend | **S** | Creazione file vuoti da lista, meccanico | ✅ | 2026-05-23 | Struttura BP §14.1 creata in root EduVault: 25 dir, 51 file vuoti, 12 .gitkeep, README, .gitignore. Frontend rimandato a FASE 6. |

### STEP B — Ricerca Estensioni / Skills / MCP

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| B.1 | Analisi ambiente locale | **S** | Comandi shell + report tabellare | ⬜ | | |
| B.2 | Ricerca MCP/Skills/Estensioni | **S** | Web search + filtro, no ragionamento architetturale | ⬜ | | |
| B.3 | Installazione selettiva | **S** | Esecuzione comandi uno per uno | ⬜ | | |

### STEP C — Questionario Cliente

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| C.1 | Stesura questionario | **S** | Template strutturato da spec | ⬜ | | |
| C.2 | Tracking ricezione materiali | **S** | Tabella Markdown semplice | ⬜ | | |

---

## FASI DI SVILUPPO

### FASE 0 — Infrastruttura (Sprint 0)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 0.1 | `pyproject.toml` | **S** | Copia tabella dipendenze da BP §1.1, meccanico | ⬜ | | |
| 0.2 | `Dockerfile` | **S** | Copia da BP §02.1 con adattamento minimo | ⬜ | | |
| 0.3 | `docker-compose.yml` | **S** | Copia da BP §02.2, 4 servizi | ⬜ | | |
| 0.4 | `main.py` + `config.py` + `dependencies.py` + `connection.py` | **S** | BP fornisce codice esatto, pydantic-settings è boilerplate | ⬜ | | |
| 0.5 | Endpoint `/health` | **S** | Endpoint banale, 20 righe | ⬜ | | |
| 0.6 | Verifica E2E Sprint 0 | **S** | Comandi docker + curl | ⬜ | | |

**Stima costo FASE 0:** ~$2-4 (100% Sonnet)

---

### FASE 1 — Database, Auth, Modelli Pydantic (Sprint 1)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 1.1 | Schema SQL `001_initial.sql` | **S** | Copia da BP §03, SQL dichiarativo | ⬜ | | |
| 1.2 | Modelli Pydantic (4 file) | **S** | Copia da BP §04, Pydantic boilerplate con validator | ⬜ | | |
| 1.3 | Servizio Auth (JWT + bcrypt) | **S** | BP §08 fornisce codice esatto, logica lineare | ⬜ | | |
| 1.4 | Seed admin | **S** | Script semplice, idempotente | ⬜ | | |
| 1.5 | Smoke test FASE 1 | **S** | Comandi sequenziali di verifica | ⬜ | | |

**Stima costo FASE 1:** ~$3-5 (100% Sonnet)

---

### FASE 2 — Knowledge Base + COURSE_CATALOG + RAG (Sprint 2)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 2.1 | Estrazione e Parsing PDF | **S** | pdfplumber wrapper semplice | ⬜ | | |
| 2.2 | Chunking Ibrido | **O** | ⚠️ Logica custom complessa: regex normative italiane (ART_PATTERN, COMMA_PATTERN, ALLEGATO_PATTERN), coverage check, fallback, dedup. Il cuore differenziante del prodotto. Errori qui si propagano a cascata. | ⬜ | | |
| 2.3 | Classificazione + Embedding | **S** | API call + batch processing, logica lineare | ⬜ | | |
| 2.4 | COURSE_CATALOG | **S** | Dizionario Python statico da BP §13 | ⬜ | | |
| 2.5 | KnowledgeRepository + RAG | **O** | ⚠️ Query vettoriale con JOIN regionale NULL-safe, filtro rilevanza, pattern complesso. Errori producono corsi con contenuto errato. | ⬜ | | |
| 2.6 | Endpoint REST `/api/regulations` | **S** | CRUD standard con rate limit | ⬜ | | |

**Stima costo FASE 2:** ~$8-12 (4 Sonnet + 2 Opus)

---

### FASE 3 — Agenti LangGraph + PacingEngine (Sprint 3)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 3.1 | State LangGraph + Grafo (2 nodi) | **S** | BP §05.2-§05.3 fornisce codice esatto, pattern LangGraph standard | ⬜ | | |
| 3.2 | PacingEngine (30s/slide) | **S** | Calcolo matematico deterministico, formula chiara | ⬜ | | |
| 3.3 | Research Agent | **O** | ⚠️ Orchestrazione complessa: query semantica, top_k dinamico, gate RAG, distribuzione chunk con keyword overlap, ribilanciamento min/max. Molte edge case. | ⬜ | | |
| 3.4 | Content Agent + Circuit Breaker | **O** | ⚠️ La sotto-fase più complessa del progetto: chiamate LLM con retry, parsing JSON robusto, circuit breaker inline, prompt engineering differenziato Discente/Formatore. Errori = corsi illeggibili. | ⬜ | | |
| 3.5 | Pipeline E2E (senza build) | **S** | Test di integrazione, non logica nuova | ⬜ | | |

**Stima costo FASE 3:** ~$10-15 (3 Sonnet + 2 Opus)

---

### FASE 4 — Production Builder (Sprint 4)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 4.1 | `inspect_pptx_template.py` | **S** | Script CLI di ispezione, output report | ⬜ | | |
| 4.2 | SlideBuilder | **O** | ⚠️ Manipolazione python-pptx con layout complessi, posizionamento pixel, inserimento immagini con fallback, gestione template multi-layout. Richiede comprensione visiva della struttura PPTX. | ⬜ | | |
| 4.3 | Image Service + sanitize_svg | **S** | BP fornisce codice esatto, pattern async con semaforo | ⬜ | | |
| 4.4 | PDF Builder (Jinja2 + WeasyPrint) | **S** | Template HTML/CSS + rendering, logica lineare | ⬜ | | |
| 4.5 | ProductionBuilder (orchestratore) | **S** | Composizione di moduli già pronti, pattern semplice | ⬜ | | |
| 4.6 | Audio Service (edge-tts) | **S** | API async semplice, pattern identico a image_service | ⬜ | | |
| 4.7 | Test E2E Build sintetico | **S** | Script di test, non logica nuova | ⬜ | | |

**Stima costo FASE 4:** ~$6-10 (6 Sonnet + 1 Opus)

---

### FASE 5 — Orchestrazione Backend + WebSocket + REST (Sprint 5A)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 5.1 | `generation_service.py` | **O** | ⚠️ Cuore dell'orchestrazione: semaforo, timeout globale, pipeline inner con costruzione initial_state, fingerprint, telemetria. Molte parti mobili interconnesse. | ⬜ | | |
| 5.2 | Endpoint `/api/courses` | **S** | CRUD + download, pattern standard FastAPI | ⬜ | | |
| 5.3 | WebSocket progress autenticato | **S** | BP §08.8 fornisce codice esatto, pattern asincrono | ⬜ | | |
| 5.4 | Endpoint `/api/admin` | **S** | Query aggregate semplici | ⬜ | | |
| 5.5 | Smoke test E2E backend | **S** | Verifica sequenziale, no logica nuova | ⬜ | | |

**Stima costo FASE 5:** ~$6-9 (4 Sonnet + 1 Opus)

---

### FASE 6 — Frontend shadcn-admin + Branding (Sprint 5B)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 6.1 | Clone template shadcn-admin | **S** | Comandi git, zero ragionamento | ⬜ | | |
| 6.2 | Analisi struttura + inventario | **S** | Esplorazione file + report Markdown | ⬜ | | |
| 6.3 | Iniezione brand C.F.P. Montessori | **S** | Sostituzione variabili CSS e config Tailwind, meccanico | ⬜ | | |
| 6.4 | Tipi TypeScript da OpenAPI | **S** | Comando npx + verifica | ⬜ | | |
| 6.5 | API Client + WebSocket Client | **S** | Client fetch tipizzato, pattern ripetitivo per N endpoint | ⬜ | | |
| 6.6 | Pagina Login | **S** | Adattamento minimo di pagina esistente nel template | ⬜ | | |
| 6.7 | Dashboard + Lista Corsi | **O** | ⚠️ Pagina complessa: statistiche cards, DataTable con badge stato, filtri, paginazione, azioni per riga. Richiede comprensione del design system del template e mapping su dati API. | ⬜ | | |
| 6.8 | Wizard 6-step Creazione Corso | **O** | ⚠️ La pagina frontend più complessa: form multi-step con stato condizionale, validazione per step, dati da 3 endpoint diversi (catalog, brand-presets, preview calcolo slide), submit finale. | ⬜ | | |
| 6.9 | Progress + Dettaglio + Normative + Admin | **O** | ⚠️ 4 pagine in un prompt: WebSocket real-time con fasi, download multipli, upload drag-and-drop, metriche aggregate. Volume di output alto, coerenza visiva critica. | ⬜ | | |
| 6.10 | Navigazione, Routing + Build | **S** | Configurazione router, sidebar, guard. Meccanico una volta che le pagine esistono. | ⬜ | | |

**Stima costo FASE 6:** ~$12-18 (7 Sonnet + 3 Opus)

---

### FASE 7 — Certification, Audit, Deploy (Sprint 6)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 7.1 | Certification Service (StylePatternExtractor) | **S** | BP §06.2 fornisce codice esatto, estrattore deterministico | ⬜ | | |
| 7.2 | Audit log + Cleanup | **S** | INSERT in endpoint esistenti, job schedulato semplice | ⬜ | | |
| 7.3 | Testing E2E completo | **O** | ⚠️ Test che attraversa l'intero stack: ingestion → pipeline → build → certificazione → recovery. Richiede comprensione globale del sistema per scrivere asserzioni corrette. | ⬜ | | |
| 7.4 | Backup & Ops docs | **S** | Script bash + Markdown, pattern standard | ⬜ | | |
| 7.5 | Deploy su VPS | **S** | nginx.conf + compose.prod + script install, pattern standard | ⬜ | | |

**Stima costo FASE 7:** ~$5-8 (4 Sonnet + 1 Opus)

---

## RIEPILOGO STRATEGIA MODELLO

### Distribuzione per fase

| Fase | Sotto-fasi totali | Sonnet | Opus | % Opus | Stima costo |
|---|---|---|---|---|---|
| Step A | 2 | 2 | 0 | 0% | $1-2 |
| Step B | 3 | 3 | 0 | 0% | $1-2 |
| Step C | 2 | 2 | 0 | 0% | $1 |
| FASE 0 | 6 | 6 | 0 | 0% | $2-4 |
| FASE 1 | 5 | 5 | 0 | 0% | $3-5 |
| FASE 2 | 6 | 4 | **2** | 33% | $8-12 |
| FASE 3 | 5 | 3 | **2** | 40% | $10-15 |
| FASE 4 | 7 | 6 | **1** | 14% | $6-10 |
| FASE 5 | 5 | 4 | **1** | 20% | $6-9 |
| FASE 6 | 10 | 7 | **3** | 30% | $12-18 |
| FASE 7 | 5 | 4 | **1** | 20% | $5-8 |
| **TOTALE** | **56** | **46** | **10** | **18%** | **$55-86** |

### Le 10 sotto-fasi che giustificano Opus

| # | Fase.Sotto-fase | Perché Opus |
|---|---|---|
| 1 | **2.2** Chunking Ibrido | Algoritmo custom con regex normative italiane, coverage check, fallback. Il cuore IP del prodotto. |
| 2 | **2.5** KnowledgeRepository + RAG | Query vettoriale + JOIN regionale + threshold. Errori = corsi con contenuto sbagliato. |
| 3 | **3.3** Research Agent | Orchestrazione RAG end-to-end: query semantica, distribuzione chunk, ribilanciamento. |
| 4 | **3.4** Content Agent | La sotto-fase PIÙ complessa: LLM calls, JSON parsing, circuit breaker, prompt Discente/Formatore. |
| 5 | **4.2** SlideBuilder | Manipolazione python-pptx pixel-level con fallback e multi-layout. |
| 6 | **5.1** generation_service.py | Orchestrazione pipeline con semaforo, timeout, fingerprint, telemetria. Molte parti mobili. |
| 7 | **6.7** Dashboard + Lista Corsi | UI complessa: DataTable, badge stato, filtri, paginazione, azioni. |
| 8 | **6.8** Wizard 6-step | Form multi-step condizionale con validazione e dati da 3 endpoint. |
| 9 | **6.9** 4 pagine (Progress, Dettaglio, Normative, Admin) | Volume alto, WebSocket real-time, upload, coerenza visiva. |
| 10 | **7.3** Testing E2E completo | Test full-stack che richiede comprensione globale dell'architettura. |

### Regola pratica per decidere in tempo reale

```
SE il prompt dice "come BP §XX" e la BP fornisce codice esatto
  → SONNET (traduzione spec → codice)

SE il prompt dice "implementa l'algoritmo/la logica per..."
  E coinvolge >3 file interconnessi
  O richiede gestione di edge case non documentate
  O produce output che impatta la qualità del prodotto finale
  → OPUS (ragionamento architetturale)

SE hai dubbi
  → Inizia con SONNET. Se dopo 2 tentativi il codice ha bug strutturali
  → Passa a OPUS per quella sotto-fase
```

---

## TIMELINE STIMATA

| Settimana | Fasi | Ore umane stimate |
|---|---|---|
| 1 | Step A + B + C | 4-6h |
| 2 | FASE 0 + FASE 1 | 8-12h |
| 3 | FASE 2 | 10-14h |
| 4 | FASE 3 | 12-16h |
| 5 | FASE 4 | 10-14h (+ 4-6h lavoro umano template PPTX) |
| 6 | FASE 5 | 8-12h |
| 7-8 | FASE 6 | 14-20h |
| 9 | FASE 7 + QA finale | 10-14h |
| **TOTALE** | | **76-114h** (~6-9 settimane) |

---

## NOTE OPERATIVE

1. **Configura il modello in Claude Code prima di ogni sotto-fase:**
   ```bash
   # Per sotto-fasi Sonnet:
   claude config set model claude-sonnet-4-6
   
   # Per sotto-fasi Opus:
   claude config set model claude-opus-4-6
   ```

2. **Monitora i costi:** dopo ogni fase, controlla il consumo su https://console.anthropic.com → Usage. Se una fase Sonnet costa più del previsto, non passare a Opus — il problema è probabilmente nel prompt, non nel modello.

3. **Prompt caching:** Claude Code usa il caching automatico. Sessioni lunghe con contesto stabile (stessa Blueprint in memoria) beneficiano del 90% di sconto sugli input token cachati. Motivo in più per fare **una sessione per fase** come da piano.

4. **Il modello indicato è una raccomandazione, non un vincolo.** Se Sonnet produce codice corretto al primo tentativo su una sotto-fase marcata Opus, tanto meglio — hai risparmiato. Se Sonnet fallisce su una sotto-fase semplice dopo 2 tentativi, passa a Opus senza esitare.

---

*Documento da aggiornare ad ogni fase completata. Stampare e tenere accanto al monitor durante lo sviluppo.*
