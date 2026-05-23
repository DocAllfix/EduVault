# NEXUS EDUVAULT — SUPREME MASTER EXECUTION PLAN & PROMPT BOOK v4.0

**Documento di controllo assoluto per lo sviluppo agentico di Nexus EduVault tramite Claude Code (CLI di Anthropic per VS Code).**

> **Fonte di verità unica del codice:** `NEXUS_EDUVAULT_Blueprint_v7.0_FINAL.md` (d'ora in poi "Blueprint" o "BP").
> **Fonte di verità unica del processo:** questo documento.
> **Sviluppatore:** axialoop · **Dominio:** corsi8108.it · **Cliente:** corsi8108
> **Vincolo Frontend v4.0:** UI sviluppata internamente da Claude Code a partire dal template open-source **shadcn-admin** (https://github.com/satnaing/shadcn-admin.git), clonato in `frontend/` e personalizzato con il branding C.F.P. Montessori. Claude Code genera, modifica e personalizza componenti React/TypeScript/Tailwind/shadcn-ui per le 7 schermate operative del sistema (Login, Dashboard, Wizard, Progress, Dettaglio Corso, Gestione Normative, Admin). La sezione §1.2 della Blueprint (Next.js 15 / shadcn / Zustand) è il riferimento tecnologico per lo stack frontend. I contratti API descritti in §10 sono invariati.

> **v2.0 CHANGELOG rispetto a v1.0:**
> - **FIX-1:** Grafo LangGraph corretto da 3 a 2 nodi (research + content). Production Builder è funzione post-pipeline, NON nodo.
> - **FIX-2:** Struttura cartelle riallineata a BP §14.1 (4 file models/, agents/pipeline.py include state, knowledge_repo.py non rag_service.py, pacing_engine.py in services/, no circuit_breaker.py separato, no utils/ spuri).
> - **FIX-3:** Circuit breaker rimosso come classe separata. Logica contatore inline nel content_agent.py come da BP §05.5.
> - **FIX-4:** Generazione certificati PDF/QR rimossa da FASE 7.1 (non nella BP). Mantenuto solo certify_course + StylePatternExtractor.
> - **FIX-5:** Variabili JWT allineate alla BP: `JWT_SECRET` (singola chiave), `JWT_EXPIRY_MINUTES=60`, `JWT_REFRESH_EXPIRY_DAYS=7`.
> - **FIX-6:** Rimosso `regulations.source_hash` non presente nello schema BP §03.
> - **FIX-7:** Semaforo `_job_semaphore` resta in `generation_service.py` come nella BP §09, NON in dependencies.py.
> - **FIX-8:** DIAGRAM rimosso dalla DISTRIBUTION del PacingEngine (escluso in v1.0, D-17).
> - **GAP-1 INTEGRATO:** PacingEngine ricalibrato a **1 slide ogni 30 secondi** (regola metrica dal PDF commerciale, ora vincolo architetturale).
> - **GAP-3 INTEGRATO:** Servizio narrazione audio TTS aggiunto in FASE 4 (sotto-fase 4.6). Nuova tabella `audio_tracks`, nuovo servizio `audio_service.py`, nuovo endpoint download audio, manifesto sincronizzazione.
>
> **v3.0 CHANGELOG rispetto a v2.0 (Ottimizzazione BaaS & Open-Source):**
> - **OPT-1:** Audio TTS migrato da OpenAI API (`openai` SDK) a **`edge-tts`** (Microsoft Edge Neural TTS). Gratuito, nessuna API key, nessun vendor lock-in. Voce default: `it-IT-DiegoNeural`. Durata MP3 calcolata via `mutagen`. Eliminata dipendenza `OPENAI_API_KEY` dal `.env`.
> - **OPT-2:** Gestione configurazione migrata da `os.environ[]` sparso a **`pydantic-settings`** v2. Classe `Settings` in `app/config.py` con validazione all'avvio. Ogni modulo importa `from app.config import settings`.
> - **OPT-3:** Template PDF dispensa migrato da f-string `.format()` a **Jinja2** template engine. File template separato in `templates/dispensa.html`. Migliore manutenibilità e estensibilità.
> - **OPT-4:** Aggiunta dipendenza `mutagen>=1.47` per calcolo durata MP3 generati da edge-tts.
> - **IMPATTO CONSEGNA:** L'eliminazione di `OPENAI_API_KEY` riduce le dipendenze cloud post-consegna. Il cliente C.F.P. Montessori non dovrà mantenere un account OpenAI attivo per la funzionalità audio.
>
> **v4.0 CHANGELOG rispetto a v3.0 (Frontend Swap & Visual Branding):**
> - **SWAP-1:** Frontend migrato da **Base 44** (tool esterno, vendor lock-in) a **shadcn-admin** (template open-source MIT, clonato in `frontend/`). Claude Code ora genera e personalizza direttamente componenti React/TypeScript/Tailwind/shadcn-ui. Eliminata dipendenza `BASE44_REPO_URL`.
> - **SWAP-2:** REI-1 riscritta: Claude Code ORA genera UI a partire dal template shadcn-admin, seguendo i design patterns del template e il branding C.F.P. Montessori. NON inventa design dalla tela bianca.
> - **SWAP-3:** FASE 6 completamente riscritta con 10 sotto-fasi granulari: Clone template → Analisi struttura → Branding injection (variabili CSS, logo, palette Tailwind) → Tipi OpenAPI → API client → 7 pagine custom (Login, Dashboard, Wizard 6-step, Progress Monitor, Dettaglio Corso, Gestione Normative, Admin) → WebSocket integration → Build & Smoke test.
> - **SWAP-4:** Step B arricchito con ambiti UI/UX: ricerca skills per Figma MCP, shadcn/ui component library, Tailwind CSS IntelliSense, frontend testing.
> - **SWAP-5:** Aggiunta sezione branding C.F.P. Montessori in FASE 6 con istruzioni esplicite per sovrascrittura variabili `:root` CSS, `tailwind.config.ts`, sostituzione logo, favicon, e titoli applicazione.
> - **IMPATTO ARCHITETTURALE:** Zero impatto sul backend. Contratti Pydantic, schema DB, pipeline LangGraph, orchestrazione e API REST restano invariati. Solo la FASE 6 e le regole frontend cambiano.

---

## INDICE

- [SEZIONE 0 — Credenziali, API Keys & Materiali da Preparare PRIMA di Aprire VS Code](#sezione-0)
- [SEZIONE 1 — Regole di Ingaggio di Claude Code (lettura obbligatoria)](#sezione-1)
- [STEP A — Inizializzazione `CLAUDE.md` + Struttura Cartelle](#step-a)
- [STEP B — Ricerca Autonoma Estensioni VS Code / Skills / MCP Servers](#step-b)
- [STEP C — Generazione Questionario Cliente per Ingestion](#step-c)
- [FASE 0 — Infrastruttura (Sprint 0 Blueprint)](#fase-0)
- [FASE 1 — Database, Auth, Modelli Pydantic (Sprint 1 Blueprint)](#fase-1)
- [FASE 2 — Knowledge Base + COURSE_CATALOG + RAG (Sprint 2 Blueprint)](#fase-2)
- [FASE 3 — Agenti LangGraph + PacingEngine (Sprint 3 Blueprint)](#fase-3)
- [FASE 4 — Production Builder (PPTX / PDF / Image / SVG / Audio TTS) (Sprint 4 Blueprint)](#fase-4)
- [FASE 5 — Orchestrazione Backend + WebSocket + REST (Sprint 5A Blueprint)](#fase-5)
- [FASE 6 — Frontend shadcn-admin + Branding C.F.P. Montessori (Sprint 5B Blueprint)](#fase-6)
- [FASE 7 — Certification, Audit, Metriche, E2E, Deploy (Sprint 6 Blueprint)](#fase-7)
- [SEZIONE FINALE — Human QA Master Checklist Pre-Go-Live](#qa-finale)

---

<a id="sezione-0"></a>
## SEZIONE 0 — CREDENZIALI, API KEYS & MATERIALI DA PREPARARE PRIMA DI APRIRE VS CODE

> **Regola:** non avviare nemmeno Step A finché ogni voce qui sotto non è materialmente nelle tue mani o in un password manager. Claude Code si pianta se mancano variabili `.env` a runtime e si entra in un loop di rigenerazione di codice che corrompe la coerenza dello sprint.

### 0.1 API Keys di Servizi Esterni (obbligatorie)

| # | Variabile `.env` | Servizio | Dove ottenerla | Note d'uso (rif. Blueprint) |
|---|---|---|---|---|
| 1 | `ANTHROPIC_API_KEY` | Anthropic Console | https://console.anthropic.com → Settings → API Keys | Modello target: **Claude Sonnet 4** (200K ctx). Usata da Research Agent, Content Agent e classificatore chunk. Configurare anche budget alert. |
| 2 | `VOYAGE_API_KEY` | Voyage AI | https://dash.voyageai.com → API Keys | Modello target: **voyage-3** (1024 dim). Embedding RAG normativo multilingua. |
| 3 | `BRAVE_SEARCH_API_KEY` | Brave Search API | https://api.search.brave.com → Subscriptions | Endpoint Images. Filtri risoluzione/licenza/tipo per `image_service.py`. |
| 4 | ~~`OPENAI_API_KEY`~~ | **RIMOSSA in v3.0 (OPT-1)** | — | Audio TTS ora via `edge-tts` (gratuito, nessuna API key). Voce italiana: `it-IT-DiegoNeural`. Vedi FASE 4.6. |
| 5 | (nessuna chiave, ma serve token) `GITHUB_TOKEN` | GitHub | Settings → Developer settings → Personal access tokens (classic, repo+workflow scope) | Necessario per push su origin e gestione repo. |
| 6 | ~~`BASE44_REPO_URL`~~ | **RIMOSSA in v4.0 (SWAP-1)** | — | Frontend ora sviluppato internamente da shadcn-admin. Nessun repo esterno. |
| 7 | (facoltativo v1.0) `CLOUDFLARE_API_TOKEN` | Cloudflare | Dashboard → API Tokens | Solo per FASE 7 (proxy DDoS + SSL su `corsi8108.it`). |
| 8 | (facoltativo v1.0) `LETS_ENCRYPT_EMAIL` | Let's Encrypt | Indirizzo email amministratore | Per cert-bot in produzione, FASE 7. |

### 0.2 Secrets Generati Localmente (da generare con `openssl`)

<!-- FIX-5 APPLICATO: JWT_SECRET singolo come da BP §02.6, §08.1. Rimosso JWT_REFRESH_SECRET_KEY. -->

| # | Variabile `.env` | Comando di generazione | Lunghezza minima |
|---|---|---|---|
| 9 | `JWT_SECRET` | `openssl rand -hex 64` | 64 byte hex (128 char) — **chiave unica** per access e refresh token (BP §08.1 distingue per campo `type` nel payload) |
| 10 | `POSTGRES_PASSWORD` (utente admin `nexus_admin`) | `openssl rand -base64 32` | ≥32 char |
| 11 | `POSTGRES_APP_PASSWORD` (utente runtime `nexus_app`, ruolo limitato) | `openssl rand -base64 32` | ≥32 char |
| 12 | `ADMIN_BOOTSTRAP_PASSWORD` (seed admin@corsi8108.it) | `openssl rand -base64 24` | ≥24 char, da cambiare al primo login |
| 13 | `COOKIE_SECRET` (se il frontend usa cookie sessione) | `openssl rand -hex 32` | 32 byte hex |

### 0.3 Parametri di Configurazione di Dominio

| # | Variabile | Valore atteso |
|---|---|---|
| 14 | `APP_DOMAIN` | `corsi8108.it` |
| 15 | `APP_BASE_URL` | `https://corsi8108.it` (prod) / `http://localhost:3000` (dev) |
| 16 | `API_BASE_URL` | `https://api.corsi8108.it` (prod) / `http://localhost:8000` (dev) |
| 17 | `CORS_ALLOWED_ORIGINS` | Lista esplicita — **mai wildcard `*`** (BP §1.1) |
| 18 | `PIPELINE_TIMEOUT_SECONDS` | `1800` (30 min, da BP §00) |
| 19 | `LLM_REQUEST_TIMEOUT_SECONDS` | `120` |
| 20 | `MAX_CONCURRENT_JOBS` | `1` (vincolo D-02 BP §1.4 — **NON alzare**) |
| 21 | `TTS_VOICE` | `it-IT-DiegoNeural` (voce italiana edge-tts — configurabile: `it-IT-ElsaNeural` femminile, `it-IT-IsabellaNeural` femminile alternativa, `it-IT-BenignoNeural` maschile alternativo) |

### 0.4 Accessi Infrastrutturali

| # | Risorsa | Necessario per |
|---|---|---|
| 23 | Credenziali root/sudo VPS dedicato EU (4 vCPU / 8 GB RAM minimo) | FASE 7 deploy |
| 24 | SSH key pair generata e public key registrata sul VPS | FASE 7 |
| 25 | Accesso DNS provider per `corsi8108.it` (record A, CNAME) | FASE 7 |
| 26 | Bucket / volume backup off-site (S3-compatibile EU o snapshot VPS) | FASE 7 (recovery & pg_dump) |
| 27 | Account Sentry/Glitchtip (facoltativo v1.0) | Telemetria errori production |

### 0.5 Materiali del Cliente da Reperire ENTRO Step C

| # | Materiale | Uso operativo |
|---|---|---|
| 28 | PDF integrale D.Lgs 81/08 (Testo Unico Sicurezza) versione consolidata | Test ingestion FASE 2, RAG semantico |
| 29 | PDF DM 388/2003 (Primo Soccorso, 4 pagine — test mini) | **Primo test chunking** in FASE 2 (BP §16 punto 3) |
| 30 | PDF Accordo Stato-Regioni 21/12/2011 (Formazione lavoratori) | Validazione COURSE_CATALOG (BP §13) |
| 31 | Reg. CE 852/2004 (HACCP) + normativa regionale Campania HACCP | Test corso HACCP con join regionale NULL-safe (BP §13) |
| 32 | Logo aziendale `.png` 512×512 + 2048×2048, palette HEX brand, font ufficiale `.ttf/.otf` | Calibrazione template PPTX (BP §16 punto 4 — lavoro UMANO, NON delegabile a Claude Code) |
| 33 | Disclaimer legali, footer obbligatori, claim di certificazione | PDF builder (FASE 4) |
| 34 | Lista nominativa amministratori, operatori, revisori (email) | Seed utenti FASE 1 |

### 0.6 File `.env.example` da Generare Subito (PRIMA di Step A)

Crea manualmente in locale, in una cartella vuota chiamata `nexus-eduvault/`, il file `.env.example` con tutte le chiavi sopra **commentate ma presenti**. Quando in Step A Claude Code creerà la struttura, troverà già questo file e lo userà come contratto. Esempio minimo:

```bash
# === Secrets esterni ===
ANTHROPIC_API_KEY=
VOYAGE_API_KEY=
BRAVE_SEARCH_API_KEY=
# OPENAI_API_KEY rimossa in v3.0 (OPT-1): audio TTS ora via edge-tts, nessuna API key

# === JWT (BP §02.6 — chiave SINGOLA, tipo token nel payload) ===
JWT_SECRET=
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60
JWT_REFRESH_EXPIRY_DAYS=7

# === PostgreSQL ===
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=nexus
POSTGRES_USER=nexus_admin
POSTGRES_PASSWORD=
POSTGRES_APP_USER=nexus_app
POSTGRES_APP_PASSWORD=
DB_POOL_MIN_SIZE=5
DB_POOL_MAX_SIZE=20

# === Runtime ===
APP_DOMAIN=corsi8108.it
APP_BASE_URL=http://localhost:3000
API_BASE_URL=http://localhost:8000
CORS_ALLOWED_ORIGINS=http://localhost:3000
FRONTEND_URL=http://localhost:3000
PIPELINE_TIMEOUT_SECONDS=1800
LLM_REQUEST_TIMEOUT_SECONDS=120
MAX_CONCURRENT_JOBS=1

# === TTS Audio (OPT-1 v3.0 — edge-tts, nessuna API key necessaria) ===
TTS_VOICE=it-IT-DiegoNeural

# === Seed ===
ADMIN_BOOTSTRAP_EMAIL=admin@corsi8108.it
ADMIN_BOOTSTRAP_PASSWORD=

# === Branding (BP §02.6) ===
ORGANIZATION_NAME=corsi8108

# === Frontend (v4.0 SWAP-1: shadcn-admin locale, nessun repo esterno) ===
# BASE44_REPO_URL rimossa in v4.0 — frontend sviluppato internamente
NEXT_PUBLIC_API_URL=http://localhost:8000
```

> **Check finale Sezione 0:** se anche una sola riga di questa lista è vuota, **NON proseguire**. Tornare al cliente o al provider e completare.

---

<a id="sezione-1"></a>
## SEZIONE 1 — REGOLE DI INGAGGIO DI CLAUDE CODE (LEGGERE PRIMA DI OGNI PROMPT)

1. **Una sessione Claude Code per Fase.** Mai mescolare due Fasi nello stesso contesto: l'agente degrada oltre ~15 file (BP §16 regola 1).
2. **Ogni prompt è atomico.** "Leggi sezione X → crea file Y → scrivi test → fermati." Mai "implementa l'intero modulo".
3. **CLAUDE.md è la bussola.** Ogni nuova sessione inizia con: `claude` → primo prompt `Leggi CLAUDE.md e attendi istruzioni.`
4. **No invenzioni.** Se una funzione non è definita nella Blueprint, Claude Code deve fermarsi e segnalare il gap (BP §16 regola 5).
5. **Test obbligatori prima del commit.** Ogni Fase termina con: `pytest -q && mypy --strict app/ && ruff check app/`. Se non passano → no commit.
6. **Frontend = shadcn-admin personalizzato.** Claude Code clona il template, lo analizza, lo personalizza con il branding C.F.P. Montessori e genera le 7 pagine operative cablate su API/WebSocket. NON inventa design dalla tela bianca — parte SEMPRE dal template e ne rispetta i pattern visivi (layout, sidebar, componenti shadcn/ui).
7. **Lingua codice/log/commenti = inglese.** Lingua prompt e questo documento = italiano.
8. **Git workflow:** branch `feat/phaseN-<short>` per ogni Fase, PR auto-mergiata in `main` solo dopo checklist umana. Tag `vN.0.0-phaseN` ad ogni chiusura Fase.

---

<a id="step-a"></a>
## STEP A — INIZIALIZZAZIONE `CLAUDE.md` + STRUTTURA CARTELLE

**Obiettivo:** dare a Claude Code la sua "Costituzione" prima di scrivere una riga di codice. Il file `CLAUDE.md` è caricato automaticamente all'avvio della sessione (`claude` in terminale) e definisce regole inviolabili.

**Setup manuale prima del prompt:**

```bash
# In una cartella vuota
mkdir nexus-eduvault && cd nexus-eduvault
git init
cp /percorso/al/.env.example .
cp /percorso/al/NEXUS_EDUVAULT_Blueprint_v7_0_FINAL.md ./BLUEPRINT.md
claude   # avvia la sessione Claude Code
```

### A.1 — Prompt: Creazione `CLAUDE.md`

```text
Sei Claude Code. La cartella corrente è la root del progetto Nexus EduVault.
Trovi qui due file:
1. BLUEPRINT.md  — Costituzione tecnica v7.0 del progetto (3486 righe). Unica fonte di verità per il codice.
2. .env.example  — contratto delle variabili d'ambiente.

COMPITO ATOMICO:
Crea il file CLAUDE.md nella root con il seguente contenuto ESATTO (non aggiungere paragrafi tuoi, non riassumere, non interpretare). Dopo averlo creato, fermati e stampa solo: "CLAUDE.md scritto. In attesa di Step A.2."

--- INIZIO CONTENUTO CLAUDE.md ---
# CLAUDE.md — Nexus EduVault Operating Constitution

## Identità del Progetto
- **Nome:** Nexus EduVault
- **Versione target:** v1.0 SUPREME PRODUCTION READY
- **Cliente:** corsi8108 (dominio corsi8108.it)
- **Sviluppatore umano:** axialoop (solo, in VS Code, deleghi codice a me Claude Code)
- **Fonte di verità tecnica:** ./BLUEPRINT.md (v7.0 FINAL) — qualunque divergenza tra ciò che ricordo e la blueprint vince SEMPRE la blueprint.

## Regole Inviolabili (REI)

REI-1  Frontend = shadcn-admin (template open-source clonato in frontend/). Genero, modifico e personalizzo componenti React/TypeScript/Tailwind/shadcn-ui partendo SEMPRE dalla struttura del template. NON invento design dalla tela bianca. Rispetto i pattern visivi del template (sidebar, header, card, table). Applico il branding C.F.P. Montessori (colori, logo, font) sovrascrivendo le variabili CSS `:root` e `tailwind.config.ts`. Se mi viene chiesto di "creare una pagina", parto dalla pagina più simile nel template e la adatto.

REI-11 UI/UX Design Quality: quando genero o modifico componenti frontend, perseguo qualità pixel-perfect. Uso esclusivamente componenti shadcn/ui esistenti nel template (Button, Card, Table, Dialog, Select, Input, Badge, Progress, Tabs, Sheet). Mantengo coerenza visiva: spacing uniforme (gap-4, p-6), tipografia gerarchica (text-2xl per titoli, text-sm per caption), colori dal design system del template. Se devo scegliere tra "funziona" e "funziona ed è bello", scelgo il secondo. Ispirazione pattern: Linear.app per stati e badge, Vercel Dashboard per layout pulito, Stripe per wizard multi-step.

REI-2  La normativa è la fonte di verità, non l'AI (BP §00). Non genero contenuti normativi inventati. Tutte le slide e i PDF ancorano ogni affermazione a un chunk reale recuperato dalla Knowledge Base.

REI-3  D-02 — Concorrenza: asyncio.Semaphore(1) è VINCOLO ARCHITETTONICO (python-pptx + lxml non thread-safe). MAI alzare a 2+ senza convertire a process pool o Celery.

REI-4  D-03 — Niente Supabase, niente cloud auth. PostgreSQL 16 + pgvector + asyncpg, JWT custom + bcrypt. Storage = volume Docker locale.

REI-5  Una funzione/classe/SQL = una sola fonte. Se non la trovo nella BLUEPRINT, mi fermo e segnalo "GAP rilevato, prompt da raffinare", NON la invento.

REI-6  Test prima del commit. pytest deve essere verde; mypy --strict deve passare sui moduli `app/`; ruff check non deve avere errori. Solo allora propongo `git commit`.

REI-7  Lingua: codice, commenti, log, docstring, identificatori, messaggi di errore → INGLESE. Risposte all'umano nel terminale → ITALIANO.

REI-8  Atomicità: ogni mio output produce un file (o un piccolo gruppo coeso di file della stessa unità funzionale). Dopo ogni completamento, mi fermo e attendo istruzione.

REI-9  Dipendenze: rispetto le versioni minime di BLUEPRINT §1.1. Niente librerie alternative senza istruzione esplicita.

REI-10 Sicurezza by default: CORS con origin esplicito mai wildcard, rate limiting su endpoint critici, audit log append-only, sanitizzazione SVG, validazione integrità immagini con Pillow.verify(), JWT con check is_active in ogni richiesta autenticata.

## Comandi che eseguo a inizio sessione
1. `ls -la` (verificare struttura)
2. `cat .env.example` (capire contratto secrets)
3. `head -200 BLUEPRINT.md` se non già in contesto recente
4. Attendere istruzione dell'umano.

## Comandi che eseguo a fine task
1. `pytest -q tests/`  → tutti verdi
2. `mypy --strict app/<modulo_modificato>`
3. `ruff check app/`
4. Propongo all'umano comando git esatto. Non eseguo `git commit` di mia iniziativa.

## Sezioni della Blueprint e loro mapping
- §00 Executive Summary, §01 Stack         → riferimento generale
- §02 Infrastruttura                       → FASE 0
- §03 Schema DB, §04 Modelli, §08 Auth     → FASE 1
- §06 Knowledge Base, §13 COURSE_CATALOG   → FASE 2
- §05 Agenti, §06B PacingEngine            → FASE 3
- §07 Production Builder + Audio TTS       → FASE 4
- §09 Orchestrazione, §10 API/WebSocket    → FASE 5 (5A backend) + FASE 6 (5B frontend shadcn-admin)
- §12 Deploy, §14 Testing                  → FASE 7
- §15 Checklist Sprint, §16 Piano Sprint   → riferimento trasversale

## Architettura Pipeline (VINCOLO v2.0)
- LangGraph ha ESATTAMENTE 2 nodi: research e content.
- Il Production Builder (PPTX, PDF, Audio) è una funzione POST-PIPELINE, NON un nodo LangGraph.
- Il Circuit Breaker è un contatore inline nel content_agent, NON una classe separata.
- Il Semaphore(1) vive in generation_service.py, NON in dependencies.py.

## In caso di dubbio
1. Rileggi BLUEPRINT.md sezione pertinente.
2. Se persiste → output "GAP: <descrizione>" e fermati.
3. NON allucinare strutture, schemi SQL, payload Pydantic o endpoint.

## Ottimizzazioni v3.0 (OPTIMIZATION_BLUEPRINT.md)

OPT-1  Audio TTS = edge-tts (NON OpenAI). Voce default: it-IT-DiegoNeural. Nessuna OPENAI_API_KEY necessaria. Durata MP3 calcolata con mutagen.

OPT-2  Config = pydantic-settings v2. Importare `from app.config import settings`. MAI os.environ[] diretto in nessun modulo.

OPT-3  PDF Template = Jinja2. File template in templates/dispensa.html. MAI f-string .format() per HTML lungo.

--- FINE CONTENUTO CLAUDE.md ---
```

### A.2 — Prompt: Creazione Struttura Cartelle Backend

<!-- FIX-2 APPLICATO: struttura riallineata a BP §14.1. Nomi file e path identici alla Blueprint. -->

```text
Leggi CLAUDE.md (REI-1 a REI-10) e BLUEPRINT.md §14 (Struttura Codebase) e §10 (API REST/WebSocket).

COMPITO ATOMICO:
Crea esattamente la seguente struttura di cartelle e file vuoti (placeholder `.gitkeep` dove serve, NO contenuto applicativo, niente codice ancora). La cartella frontend/ conterrà il template shadcn-admin clonato in FASE 6 — non creare file frontend ora.

ATTENZIONE: questa struttura rispecchia ESATTAMENTE la BP §14.1. NON modificare nomi o path.

nexus-eduvault/
├── BLUEPRINT.md                 (già esistente)
├── CLAUDE.md                    (già esistente)
├── .env.example                 (già esistente)
├── .gitignore
├── README.md                    (placeholder 1 riga: "Nexus EduVault — see BLUEPRINT.md")
├── docker-compose.yml           (vuoto)
├── Dockerfile                   (vuoto)
├── pyproject.toml               (vuoto)
├── app/
│   ├── __init__.py
│   ├── main.py                  (vuoto)
│   ├── config.py                (vuoto)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── core.py              (vuoto — Enum: TargetType, SlideDensity, SlideType, ChunkType)
│   │   ├── requests.py          (vuoto — CourseRequest, CourseResponse)
│   │   ├── knowledge.py         (vuoto — NormativeChunk, StylePattern)
│   │   └── pipeline.py          (vuoto — SlideContent, ImageStrategy, ModuleSpec, PacingPlan, ModuleContent, CourseContext, GenerationReport)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── pipeline.py          (vuoto — NexusPipelineState TypedDict + grafo LangGraph, NELLO STESSO FILE)
│   │   ├── research_agent.py    (vuoto)
│   │   ├── content_agent.py     (vuoto — include circuit breaker INLINE come contatore, NON classe separata)
│   │   └── prompts.py           (vuoto — system prompt Discente/Formatore + template user prompt)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── dependencies.py      (vuoto — set_pool/get_pool, set_voyage_client/get_voyage_client, get_shutdown_event. NO semaforo qui)
│   │   ├── generation_service.py (vuoto — include _job_semaphore asyncio.Semaphore(1) QUI)
│   │   ├── auth_service.py       (vuoto)
│   │   ├── ingestion_service.py  (vuoto — include parsing PDF + chunking ibrido + classificazione + embedding INLINE)
│   │   ├── knowledge_repo.py     (vuoto — KnowledgeRepository: resolve_slugs, search_chunks, get_style_patterns)
│   │   ├── pacing_engine.py      (vuoto — PacingEngine deterministico, regola 1 slide / 30 secondi)
│   │   ├── image_service.py      (vuoto — include sanitize_svg() INLINE)
│   │   ├── audio_service.py      (vuoto — TTS narrazione FAD via edge-tts, OPT-1 v3.0)
│   │   └── certification_service.py (vuoto — include StylePatternExtractor INLINE)
│   ├── builders/
│   │   ├── __init__.py
│   │   ├── production_builder.py (vuoto)
│   │   ├── slide_builder.py     (vuoto)
│   │   ├── pdf_builder.py       (vuoto — usa Jinja2 + WeasyPrint, OPT-3 v3.0)
│   │   └── pptx_validator.py    (vuoto)
│   ├── templates/
│   │   └── dispensa.html        (vuoto — template Jinja2 per PDF dispensa, OPT-3 v3.0)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py      (vuoto — get_current_user, require_role)
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py          (vuoto)
│   │   │   ├── courses.py       (vuoto)
│   │   │   ├── regulations.py   (vuoto)
│   │   │   ├── admin.py         (vuoto)
│   │   │   └── health.py        (vuoto)
│   │   └── websocket.py         (vuoto)
│   └── db/
│       ├── __init__.py
│       ├── connection.py        (vuoto — Pool asyncpg min 5, max 20)
│       └── migrations/
│           ├── 001_initial.sql  (vuoto)
│           └── setup_roles.sql  (vuoto)
├── config/
│   └── catalog_config.py        (vuoto — COURSE_CATALOG completo)
├── assets/
│   ├── templates/
│   │   └── .gitkeep             (nexus_master.pptx andrà qui — LAVORO UMANO)
│   └── fonts/
│       └── Montserrat/
│           └── .gitkeep
├── scripts/
│   ├── seed.py                  (vuoto — UNO solo, nessun duplicato)
│   ├── create_pptx_template.py  (vuoto)
│   └── inspect_pptx_template.py (vuoto)
├── tests/
│   ├── __init__.py
│   ├── conftest.py              (vuoto)
│   ├── unit/
│   │   └── .gitkeep
│   ├── integration/
│   │   └── .gitkeep
│   └── fixtures/
│       ├── pdfs/
│       │   └── .gitkeep
│       └── pptx/
│           └── .gitkeep
├── storage/
│   ├── pdfs/
│   │   └── .gitkeep
│   ├── pptx_templates/
│   │   └── .gitkeep
│   ├── generated/
│   │   └── .gitkeep
│   └── cache_images/
│       └── .gitkeep
├── frontend/
│   └── .gitkeep
└── docs/
    └── .gitkeep

Crea inoltre un .gitignore corretto per progetto Python+Docker che escluda:
- __pycache__/, *.pyc, .pytest_cache, .mypy_cache, .ruff_cache
- .env, .env.local, *.env (mai *.env.example)
- storage/generated/*, storage/cache_images/*  (ma mantieni .gitkeep)
- *.sqlite, *.db
- node_modules/
- .DS_Store, .vscode/settings.json

Termina con: stampa `find . -type d | head -60` e poi "Struttura creata. In attesa di Step B.1."
```

### Checklist Umana — fine Step A

```text
[ ] CLAUDE.md presente e leggibile, contiene le 11 REI (REI-1 shadcn-admin, REI-11 UI Quality) + sezione "Architettura Pipeline v2.0" + sezione "Ottimizzazioni v3.0" (OPT-1/2/3)
[ ] Tutte le cartelle indicate esistono (verifica `tree -L 3 -d`)
[ ] models/ contiene 4 file: core.py, requests.py, knowledge.py, pipeline.py (NON un file unico pydantic_models.py)
[ ] agents/ contiene pipeline.py (con state + grafo), research_agent.py, content_agent.py, prompts.py (NON circuit_breaker.py, NON pacing_engine.py)
[ ] services/ contiene dependencies.py, knowledge_repo.py (NON rag_service.py), pacing_engine.py, audio_service.py
[ ] NO cartella utils/ con file spuri (chunking, svg_sanitizer, style_extractor sono inline nei loro service)
[ ] builders/ contiene pdf_builder.py; templates/ contiene dispensa.html (OPT-3)
[ ] db/ contiene connection.py (NON pool.py)
[ ] config/ contiene catalog_config.py
[ ] scripts/seed.py esiste UNA sola volta (nessun duplicato in app/db/)
[ ] .gitignore esclude .env e *.pyc, mantiene .gitkeep
[ ] La cartella frontend/ contiene solo .gitkeep
[ ] BLUEPRINT.md NON è in .gitignore
```

### Git — fine Step A

```bash
git add .
git commit -m "chore(step-a): bootstrap CLAUDE.md v4.0, .gitignore and BP-aligned project skeleton"
git tag v0.0.1-step-a
```

---

<a id="step-b"></a>
## STEP B — RICERCA AUTONOMA ESTENSIONI VS CODE / SKILLS / MCP SERVERS

**Obiettivo:** lasciare a Claude Code la responsabilità di scegliere il proprio "toolbelt" basato su stack reale (LangGraph + asyncpg/PostgreSQL+pgvector + FastAPI + python-pptx + WeasyPrint + Voyage + Anthropic). Riduce gli sviluppatori-fantasma che inventano tool inesistenti.

### B.1 — Prompt: Analisi Ambiente Locale

```text
Leggi CLAUDE.md e BLUEPRINT.md §01 (Stack tecnologico blindato 1.1, 1.2, 1.3) e §1.4 (Decisioni vincolanti D-01..D-06).

COMPITO ATOMICO 1 di 3 (Step B):
Esegui in shell ed allega l'output testuale, NON modificare nulla:
  - `python3 --version` (deve essere 3.12.x)
  - `docker --version` e `docker compose version`
  - `psql --version` (se non installato segnala "PSQL client locale non installato — non bloccante, usiamo docker exec")
  - `git --version`
  - `node --version` (necessario per frontend shadcn-admin in FASE 6 — se mancante, segnala "Node non presente, da installare prima di FASE 6")
  - `code --version`  (verifica VS Code CLI disponibile)
  - `uname -a` e disponibilità memoria `free -h` (o `vm_stat` su mac)

Poi produci un blocco markdown chiamato ENV_REPORT.md nella root contenente:
1. Tabella delle versioni rilevate vs versioni richieste in BLUEPRINT §1.1
2. Lista delle dipendenze mancanti o sotto versione minima
3. Comandi di remediation suggeriti (apt/brew/asdf)
NON installare nulla. Solo report.

Termina con: "ENV_REPORT.md generato. In attesa di Step B.2."
```

### B.2 — Prompt: Ricerca MCP Servers / Skills

```text
Leggi CLAUDE.md (REI-5: niente invenzioni) e BLUEPRINT.md §01-§02.

COMPITO ATOMICO 2 di 3 (Step B):
Per ciascuno dei seguenti ambiti di sviluppo, cerca su internet (usa i tool web search e web fetch a tua disposizione) MCP servers ufficiali o community-mantained ad alto rating, skills Claude Code installabili e estensioni VS Code consigliate. Filtra duramente: includi SOLO progetti con:
  - ultimo commit < 6 mesi
  - autore identificabile (azienda nota, manutentore con storia, repo Anthropic/awesome-mcp)
  - documentazione installazione chiara
  - licenza permissiva (MIT/Apache-2)

Ambiti da coprire (uno per riga):
  a) PostgreSQL + pgvector (introspect schema, run query in sicurezza, generare migrations)
  b) FastAPI scaffolding, OpenAPI lint, async testing
  c) LangGraph (debug state machine, visualizzare grafo, checkpoint inspect)
  d) Python typing strict + ruff + mypy
  e) Docker + docker-compose (lint, run-in-container)
  f) Git / GitHub (PR review, branch hygiene)
  g) Anthropic API monitoring (token usage, cost)
  h) Markdown / Mermaid (per documentazione interna)
  i) **[v4.0 SWAP-4] UI/UX Design & Frontend:** Figma MCP server (lettura design da Figma se disponibili), shadcn/ui component library docs, Tailwind CSS IntelliSense, React/Next.js best practices. Cerca il plugin ufficiale Figma per Claude Code: `claude plugin install figma@claude-plugins-official`
  j) **[v4.0 SWAP-4] Frontend Testing:** Playwright, Vitest, React Testing Library per test componenti e E2E frontend

OUTPUT richiesto:
File `docs/TOOLBELT.md` con questo schema esatto:

# Toolbelt suggerito da Claude Code (data: <oggi>)

## A) PostgreSQL + pgvector
### MCP servers
| Nome | URL repo | Manutentore | Ultimo commit | Motivo della scelta |
### Skills Claude Code (se applicabile)
| Nome | URL | ... |
### Estensioni VS Code
| Nome | Marketplace ID | ... |

(ripeti per b..h)

## Raccomandazione di installazione
Lista ordinata da 1 a N dei tool che IO (Claude Code) considero ESSENZIALI per non allucinare durante lo sviluppo di questo progetto specifico. Per ciascuno: 1 riga "perché serve in Nexus EduVault" che cita la sezione BLUEPRINT.

REGOLE:
- Se non trovi un MCP affidabile per un ambito, scrivi "Nessun MCP affidabile al <data>. Procedere senza."
- NON installare nulla. Lascia all'umano la decisione finale.
- NON inventare nomi di server: se non li hai trovati via web search, omettili.

Termina con: "TOOLBELT.md generato. In attesa di Step B.3."
```

### B.3 — Prompt: Installazione Selettiva

```text
Leggi TOOLBELT.md.

COMPITO ATOMICO 3 di 3 (Step B):
Aspetta che l'umano ti dica una stringa nella forma:
  "Installa: <lista separata da virgole dei nomi esatti scelti da TOOLBELT.md>"

Quando ricevi la lista, per ciascun elemento:
  1. Mostra il comando di installazione previsto (npm/pip/code --install-extension/claude mcp add).
  2. Attendi conferma "OK".
  3. Esegui e mostra l'output.
  4. Aggiungi una riga nel file `docs/INSTALLED_TOOLBELT.md` con: nome, versione installata, data, comando usato.

NON eseguire nessuna installazione senza la stringa "Installa:" e poi "OK" per riga.
```

### Checklist Umana — fine Step B

```text
[ ] ENV_REPORT.md elenca Python 3.12.x, Docker, Git, Node (anche se da installare)
[ ] TOOLBELT.md non contiene MCP/skill di fantasia (verifica almeno 3 URL a campione)
[ ] Hai installato solo ciò che vuoi davvero (cautela: il toolbelt minimo basta)
[ ] INSTALLED_TOOLBELT.md riflette lo stato reale
[ ] Hai aggiunto i .vscode/extensions.json se condivido VS Code workspace col team
```

### Git — fine Step B

```bash
git add ENV_REPORT.md docs/TOOLBELT.md docs/INSTALLED_TOOLBELT.md
git commit -m "chore(step-b): env report, toolbelt research and selective install"
git tag v0.0.2-step-b
```

---

<a id="step-c"></a>
## STEP C — GENERAZIONE QUESTIONARIO CLIENTE PER INGESTION

**Obiettivo:** prima di scrivere il pipeline di ingestion in FASE 2, ottenere materiali normativi REALI dal cliente per evitare di calibrare chunker e RAG su PDF sintetici. Senza PDF reali, FASE 2 è un test cieco.

### C.1 — Prompt: Stesura Questionario per il Cliente

```text
Leggi CLAUDE.md, BLUEPRINT.md §00 (Executive Summary), §06 (Knowledge Base e Chunking), §13 (COURSE_CATALOG con i 6 tipi corso, incluso HACCP regionale).

COMPITO ATOMICO:
Crea il file `docs/CLIENT_INTAKE_QUESTIONNAIRE.md` con un questionario professionale, in italiano, da inviare a corsi8108 (cliente). Deve essere strutturato come segue, e DEVE generare materiale sufficiente per testare immediatamente l'ingestion in FASE 2.

Sezioni del questionario (ognuna numerata, con campi compilabili tipo `____________`):

## 1. Identificazione cliente e ruoli
   - Ragione sociale, P.IVA, sede legale, dominio (atteso: corsi8108.it)
   - Lista nominativa: Amministratori (max 2), Operatori (max 5-10), Revisori (max 3) → email + nome + ruolo
   - Procedura di reset password preferita (manuale via admin / mail)

## 2. Materiale normativo richiesto (PDF — TUTTI obbligatori per FASE 2)
   Per ciascun documento richiediamo: PDF integrale, versione consolidata, data di pubblicazione, fonte ufficiale (es. normattiva.it, EUR-Lex):
   2.1  D.Lgs 81/08 (Testo Unico Sicurezza sul Lavoro)
   2.2  DM 388/2003 (Primo Soccorso) — USATO PER PRIMO TEST CHUNKING (4 pagine)
   2.3  Accordo Stato-Regioni 21/12/2011 (Formazione lavoratori)
   2.4  Accordo Stato-Regioni 22/02/2012 (Attrezzature di lavoro)
   2.5  Reg. CE 852/2004 (HACCP)
   2.6  Normativa HACCP regionale Campania (se applicabile, altrimenti dichiarare "non applicabile")
   2.7  Eventuali circolari INAIL/INL recenti rilevanti per i corsi

## 3. Catalogo corsi target (cross-check con BLUEPRINT §13)
   Per ciascuno dei 6 tipi corso del COURSE_CATALOG, conferma:
   - se va attivato in v1.0 (Sì/No)
   - durata target in ore
   - target audience
   - se richiede attestato finale
   - se richiede validazione regionale (es. HACCP Campania)

## 4. Identità visuale e branding (LAVORO UMANO — non delegabile a Claude Code, BP §16 punto 4)
   - Logo principale: PNG 512×512 e 2048×2048
   - Palette colori brand: HEX primario, secondario, accento, neutri
   - Font ufficiale: nome, licenza, file .ttf/.otf
   - Disclaimer legali obbligatori in footer

## 5. Hosting e dominio
   - VPS già acquistato? Provider, IP, OS, RAM, vCPU
   - Accesso DNS per corsi8108.it

## 6. SLA e ciclo di vita
   - Frequenza attesa di generazione corsi
   - Numero max utenti simultanei (BP atteso 5-15)
   - Backup: frequenza desiderata, retention

## 7. Note legali e privacy
   - DPO/RPD del cliente
   - Conservazione audit log (per quanti anni?)

## 8. Tempi di ritorno
   - Entro quale data si impegna il cliente a fornire ognuna delle sezioni 2 e 4
   - Persona di riferimento operativa lato cliente

In fondo aggiungi una sezione "**Cosa BLOCCA il go-live se manca:**" che elenca: 2.1, 2.2, 4 (logo+palette+font), 5 (VPS).

Termina con: "CLIENT_INTAKE_QUESTIONNAIRE.md generato. In attesa di Step C.2."
```

### C.2 — Prompt: Tracking della Ricezione Materiali

```text
COMPITO ATOMICO:
Crea il file `docs/CLIENT_INTAKE_TRACKING.md` con una tabella di tracking (Markdown) che replica le sezioni del questionario.

| Sezione | Item | Stato | Data richiesta | Data ricezione | Path locale | Note |
|---|---|---|---|---|---|---|
| 2.1 | D.Lgs 81/08 PDF | ⏳ in attesa | YYYY-MM-DD | — | storage/pdfs/dlgs81_08.pdf | — |
| 2.2 | DM 388/2003 PDF | ⏳ in attesa | YYYY-MM-DD | — | storage/pdfs/dm388_03.pdf | TEST chunking minimo |
| ... | ... | ... | ... | ... | ... | ... |

Termina con: "CLIENT_INTAKE_TRACKING.md generato. Step C completato. In attesa di FASE 0."
```

### Checklist Umana — fine Step C

```text
[ ] CLIENT_INTAKE_QUESTIONNAIRE.md inviato al cliente
[ ] CLIENT_INTAKE_TRACKING.md committato
[ ] Almeno DM 388/2003 atteso entro l'inizio di FASE 2
[ ] Logo + palette + font attesi entro l'inizio di FASE 4
```

### Git — fine Step C

```bash
git add docs/CLIENT_INTAKE_QUESTIONNAIRE.md docs/CLIENT_INTAKE_TRACKING.md
git commit -m "docs(step-c): client intake questionnaire and tracking sheet"
git tag v0.0.3-step-c
```

> **STOP — Non procedere alla FASE 0 finché:**
> - Hai ricevuto risposta cliente almeno alle sezioni 1, 2.1, 2.2, 5, 8,
> - Il VPS è raggiungibile,
> - `.env` è materialmente compilato.

---

<a id="fase-0"></a>
## FASE 0 — INFRASTRUTTURA (Sprint 0 Blueprint)

**Riferimenti BP:** §02 (Infrastruttura), §1.3 (Container/Web Server), §15 Sprint 0.
**Deliverable:** `docker-compose up -d` porta su PostgreSQL+pgvector + backend FastAPI; `/health` ritorna verde; primo login JWT funziona dopo seed.

### 0.1 — Prompt: `pyproject.toml` con Dipendenze Esatte

```text
Leggi CLAUDE.md (REI-9 versioni minime) e BLUEPRINT.md §1.1 (intera tabella stack backend).

COMPITO ATOMICO:
Scrivi `pyproject.toml` (formato PEP 621 con uv). Sezioni:
[project]
  name = "nexus-eduvault"
  version = "0.1.0"
  requires-python = ">=3.12,<3.13"
[project.dependencies] → ogni voce della tabella §1.1 con la versione minima ESATTA della blueprint, niente di più, niente di meno. IN PIÙ aggiungi le seguenti dipendenze di ottimizzazione v3.0:
  - edge-tts>=6.1 (OPT-1: TTS narrazione FAD, gratuito, nessuna API key — SOSTITUISCE openai)
  - mutagen>=1.47 (OPT-4: calcolo durata MP3 generati da edge-tts)
  - pydantic-settings>=2.3 (OPT-2: gestione configurazione tipizzata con validazione all'avvio)
  - Jinja2>=3.1 (OPT-3: template engine per PDF dispensa)
[project.optional-dependencies.dev] → pytest, pytest-asyncio, pytest-cov, mypy, ruff, types-*
[tool.ruff] → line-length 100, target-version py312
[tool.mypy] → strict = true, plugins = ["pydantic.mypy"]
[tool.pytest.ini_options] → asyncio_mode = "auto"

NON includere librerie non presenti in §1.1 (eccetto le 4 dipendenze v3.0 sopra elencate). NON includere openai (TTS ora via edge-tts). Fermati e stampa: "pyproject.toml scritto. In attesa di 0.2."
```

### 0.2 — Prompt: `Dockerfile`

```text
Leggi BLUEPRINT.md §02 (Dockerfile esatto) e §07 (dipendenze sistema WeasyPrint e cairosvg).

COMPITO ATOMICO:
Scrivi `Dockerfile` esattamente come da BP §02.1 (NON Dockerfile.backend — la BP usa "Dockerfile"):
  - FROM python:3.12-slim
  - Installa dipendenze C per WeasyPrint + cairosvg + font
  - Copia assets/fonts/Montserrat/ e fa fc-cache
  - COPY pyproject.toml, pip install
  - COPY . .
  - CMD uvicorn

Stampa: "Dockerfile scritto. In attesa di 0.3."
```

### 0.3 — Prompt: `docker-compose.yml`

```text
Leggi BLUEPRINT.md §02.2 esattamente.

COMPITO ATOMICO:
Scrivi `docker-compose.yml` come da BP §02.2 con 4 servizi: backend, postgres (pgvector/pgvector:pg16), frontend, nginx. Postgres NON espone porta esterna (solo expose 5432 rete interna). Network e volumi come da BP.

Stampa: "docker-compose.yml scritto. In attesa di 0.4."
```

### 0.4 — Prompt: `app/main.py` minimo + dependencies + pool

<!-- FIX-7 APPLICATO: _job_semaphore NON va in dependencies.py. Resta in generation_service.py (BP §09). -->

```text
Leggi BLUEPRINT.md §02.4 (dependencies.py), §02.5 (main.py), §02.3 (connection pool).

COMPITO ATOMICO:
Crea `app/config.py` con classe Settings basata su **pydantic-settings v2** (OPT-2 v3.0). NON usare os.environ[] diretto — tutto passa per la classe Settings:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str  # postgresql://nexus_app:...@postgres:5432/nexus
    database_admin_url: str = ""

    # API Keys
    anthropic_api_key: str
    voyage_api_key: str
    brave_search_api_key: str = ""

    # Auth (BP §08.1 — chiave SINGOLA, tipo token nel payload)
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    jwt_refresh_expiry_days: int = 7

    # CORS
    frontend_url: str = "http://localhost:3000"

    # Pipeline
    pipeline_timeout: int = 1800
    llm_request_timeout: int = 120
    max_concurrent_jobs: int = 1

    # TTS (OPT-1: edge-tts — nessuna API key!)
    tts_voice: str = "it-IT-DiegoNeural"

    # Branding
    organization_name: str = "corsi8108"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

In TUTTI i moduli che accedono a variabili d'ambiente, usare `from app.config import settings` e accedere tramite `settings.jwt_secret`, `settings.anthropic_api_key`, ecc. MAI os.environ[] diretto (OPT-2).

Crea `services/dependencies.py` ESATTAMENTE come BP §02.4:
  - _pool, set_pool(), get_pool()
  - _voyage_client, set_voyage_client(), get_voyage_client()
  - _shutdown_event = asyncio.Event(), get_shutdown_event()
  - NIENTE semaforo qui. Il semaforo _job_semaphore vive in generation_service.py (BP §09.1, vincolo v2.0).

Crea `db/connection.py` come BP §02.3: create_pool() con asyncpg, min 5, max 20.

Crea `app/main.py` come BP §02.5:
  - FastAPI con startup/shutdown
  - set_pool(), set_voyage_client() in startup
  - CORSMiddleware con FRONTEND_URL
  - slowapi Limiter
  - Graceful shutdown con get_shutdown_event().set()

Stampa: "main.py, config.py, dependencies.py, connection.py scritti. In attesa di 0.5."
```

### 0.5 — Prompt: Endpoint `/health`

```text
Leggi BLUEPRINT.md §10.1 (health check).

COMPITO ATOMICO:
In `app/api/routes/health.py`: GET /health → {"status", "database", "disk_free_gb"} come BP §10.1.
Registra in main.py. Scrivi test in tests/integration/test_health.py. Esegui pytest.

Stampa: "/health funzionante. In attesa di 0.6."
```

### 0.6 — Prompt: Verifica E2E Sprint 0

```text
COMPITO ATOMICO:
Esegui: docker compose build → up -d → sleep 15 → ps → curl /health → logs tail.
Allega output. Se fallisce, fermati.

Stampa: "FASE 0 verificata end-to-end. Pronto per commit."
```

### Checklist Umana — fine FASE 0

```text
[ ] pyproject.toml include dipendenze BP §1.1 + edge-tts + pydantic-settings + Jinja2 + mutagen (OPT v3.0). NON include openai
[ ] Dockerfile ha dipendenze sistema per WeasyPrint+cairosvg
[ ] docker compose up → postgres + backend, healthcheck verde
[ ] curl /health → status ok, database connected
[ ] CORS origin ESPLICITO, mai wildcard
[ ] Pool asyncpg min=5 max=20 (in db/connection.py, NON db/pool.py)
[ ] dependencies.py contiene pool, voyage_client, shutdown_event (NO semaforo)
[ ] config.py usa pydantic-settings v2 con classe Settings (OPT-2). Nessun os.environ[] sparso
[ ] structlog JSON renderer attivo
[ ] pytest, mypy, ruff verdi
```

### Git — fine FASE 0

```bash
git checkout -b feat/phase0-infrastructure
git add .
git commit -m "feat(phase0): docker-compose + FastAPI skeleton + /health"
git tag v0.1.0-phase0
git push origin feat/phase0-infrastructure
```

---

<a id="fase-1"></a>
## FASE 1 — DATABASE, AUTH, MODELLI PYDANTIC (Sprint 1 Blueprint)

**Riferimenti BP:** §03 (Schema SQL), §04 (Contratti Pydantic), §08 (Auth JWT custom + bcrypt), §15 Sprint 1.
**Deliverable:** schema applicato, ruoli nexus_admin/nexus_app, audit log append-only, JWT login funzionante, seed admin.

### 1.1 — Prompt: Schema SQL `001_initial.sql`

<!-- FIX-6 APPLICATO: nessun source_hash. GAP-3 INTEGRATO: tabella audio_tracks + audio_manifest_path in courses. -->

```text
Leggi BLUEPRINT.md §03 INTERAMENTE.

COMPITO ATOMICO:
Riproduci in `db/migrations/001_initial.sql` lo schema ESATTO della BP §03. Niente refactor, niente colonne extra. Tabelle nell'ordine BP: users, brand_presets, regulations, regulation_chunks (vector 1024, HNSW), courses, approved_courses, generation_jobs, image_cache, audit_log.

IN PIÙ (GAP-3 — narrazione audio FAD), aggiungi DOPO image_cache e PRIMA di audit_log:

-- ────────────────────────────────────────────
-- TRACCE AUDIO (narrazione FAD per ogni slide)
-- ────────────────────────────────────────────
CREATE TABLE audio_tracks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    slide_index INT NOT NULL,
    narration_text TEXT NOT NULL,
    audio_path VARCHAR(500),
    duration_seconds DECIMAL(6,2),
    voice VARCHAR(50) DEFAULT 'it-IT-DiegoNeural',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audio_course ON audio_tracks(course_id);

E aggiungi alla tabella courses la colonna:
    audio_manifest_path VARCHAR(500),

Poi scrivi `db/migrations/setup_roles.sql` come da BP §03.2. REVOKE DELETE, UPDATE, TRUNCATE ON audit_log FROM nexus_app.

Stampa: "Migrations SQL scritte. In attesa di 1.2."
```

### 1.2 — Prompt: Modelli Pydantic Completi

```text
Leggi BLUEPRINT.md §04 INTERAMENTE (4 file: core.py, requests.py, knowledge.py, pipeline.py).

COMPITO ATOMICO:
Riproduci in 4 file separati ESATTAMENTE come BP §04:
  - models/core.py → TargetType, SlideDensity, SlideType, ChunkType (Enum)
  - models/requests.py → CourseRequest (aggiungi "audio" come opzione valida in outputs), CourseResponse
  - models/knowledge.py → NormativeChunk, StylePattern (con vincolo anti-avvelenamento)
  - models/pipeline.py → SlideContent (con body validator troncamento soft), ImageStrategy, ModuleSpec, PacingPlan, ModuleContent, CourseContext, GenerationReport

NexusPipelineState (TypedDict) va in agents/pipeline.py, NON qui.

Scrivi tests/unit/test_models.py con happy path + validation error per modelli con validator.

Esegui mypy --strict e pytest. Stampa: "Modelli Pydantic pronti. In attesa di 1.3."
```

### 1.3 — Prompt: Servizio Auth (JWT + bcrypt)

```text
Leggi BLUEPRINT.md §08 INTERAMENTE.

COMPITO ATOMICO:
In `services/auth_service.py`: hash_password, verify_password, create_access_token, create_refresh_token, decode_token — come BP §08.1. USA JWT_SECRET (singola chiave, BP). Distingui access/refresh tramite campo "type" nel payload.

In `api/dependencies.py`: get_current_user con check is_active (revoca implicita, BP §08.2), require_role factory.

In `api/routes/auth.py`: POST /api/auth/login, POST /api/auth/refresh (con check is_active), GET /api/users/me. Rate limit su login (BP §08.5).

Tests in tests/integration/test_auth.py.

Esegui pytest. Stampa: "Auth pronto. In attesa di 1.4."
```

### 1.4 — Prompt: Seed Admin

```text
Leggi BLUEPRINT.md §02.7 (seed.py).

COMPITO ATOMICO:
In `scripts/seed.py` come BP §02.7: crea admin + brand preset default. Usa DATABASE_ADMIN_URL. Idempotente.

Tests in tests/integration/test_seed.py.

Stampa: "Seed pronto. In attesa di 1.5."
```

### 1.5 — Prompt: Smoke Test FASE 1

```text
COMPITO ATOMICO:
Esegui: docker compose down -v → up -d → apply migrations → setup_roles → seed → login → /me → DELETE audit_log come nexus_app (DEVE FALLIRE).

Riporta TUTTI gli output. Stampa: "FASE 1 verificata. Pronto per commit."
```

### Checklist Umana — fine FASE 1

```text
[ ] 001_initial.sql riflette BP §03 + tabella audio_tracks (GAP-3)
[ ] courses ha colonna audio_manifest_path
[ ] HNSW index su regulation_chunks.embedding
[ ] totp_secret presente ma non usata (v1.1)
[ ] Ruolo nexus_app NON può DELETE audit_log
[ ] 4 file models/ come BP §04 (core, requests, knowledge, pipeline)
[ ] NexusPipelineState NON è nei models (va in agents/pipeline.py, FASE 3)
[ ] /api/auth/login funziona, JWT usa JWT_SECRET singola
[ ] is_active=false invalida token immediatamente
[ ] Rate limit su /api/auth/login attivo
[ ] pytest, mypy, ruff verdi
```

### Git — fine FASE 1

```bash
git checkout -b feat/phase1-db-auth
git add .
git commit -m "feat(phase1): schema SQL + audio_tracks, Pydantic models (4 files), JWT auth, seed"
git tag v0.2.0-phase1
git push origin feat/phase1-db-auth
```

---

<a id="fase-2"></a>
## FASE 2 — KNOWLEDGE BASE + COURSE_CATALOG + RAG (Sprint 2 Blueprint)

**Riferimenti BP:** §06, §13, §15 Sprint 2.
**Deliverable:** pipeline ingestion completa, chunking rule-based + LLM, embedding Voyage, query RAG semantica, COURSE_CATALOG validato.

> **Prerequisito hard:** PDF DM 388/2003 in `storage/pdfs/dm388_03.pdf`.

### 2.1 — Prompt: Estrazione e Parsing PDF

<!-- FIX-6 APPLICATO: rimosso source_hash -->

```text
Leggi BLUEPRINT.md §06.1.1 (Stadio 1 — Parsing con pdfplumber).

COMPITO ATOMICO:
In `services/ingestion_service.py`: funzione parse_regulation_pdf(pdf_path) come BP §06.1.1. Estrai testo con pdfplumber. Log strutturato.

Tests con dm388_03.pdf REALE.

Stampa: "Estrazione PDF pronta. In attesa di 2.2."
```

### 2.2 — Prompt: Chunking Ibrido

```text
Leggi BLUEPRINT.md §06.1.1 INTERAMENTE (Stadio 2 — chunking ibrido: ART_PATTERN, COMMA_PATTERN, ALLEGATO_PATTERN, normalize_for_coverage, chunk_structured_regulation, chunk_unstructured_regulation, extract_uncaptured_text, chunk_regulation con coverage check 70%).

COMPITO ATOMICO:
In `services/ingestion_service.py` (INLINE, non in file utils separato):
  - Tutte le funzioni di chunking come da BP §06.1.1 Stadio 2
  - ART_PATTERN con supporto -bis/-ter/-quater/...
  - Coverage check normalizzato con soglia 70%
  - Fallback paragrafo con overlap 1 frase
  - Deduplicazione via content_hash SHA-256

Tests con dm388_03.pdf.

Stampa: "Chunking pronto. In attesa di 2.3."
```

### 2.3 — Prompt: Classificazione + Embedding

```text
Leggi BLUEPRINT.md §06.1.1 Stadio 3 (classificazione LLM) e Stadio 4 (embedding Voyage, dedup, indicizzazione batch).

COMPITO ATOMICO:
In `services/ingestion_service.py`:
  - classify_chunk() con LLM come BP §06.1.1 Stadio 3
  - embed_batch() e voyage_embed_with_retry() come BP §06.1.1 Stadio 4
  - index_chunks() con dedup content_hash come BP
  - Usa get_voyage_client() da dependencies.py

In `services/dependencies.py`: assicurati che set_voyage_client/get_voyage_client siano presenti (fatto in FASE 0).

Tests con mock Voyage.

Stampa: "Classificazione + Embedding pronti. In attesa di 2.4."
```

### 2.4 — Prompt: COURSE_CATALOG

```text
Leggi BLUEPRINT.md §13 INTERAMENTE.

COMPITO ATOMICO:
In `config/catalog_config.py`: COURSE_CATALOG dict con i 6 tipi corso ESATTI dalla BP §13. HACCP con regional=True.

Tests: tutti i 6 tipi esistono, titoli moduli non vuoti, HACCP Campania valida.

Stampa: "COURSE_CATALOG pronto. In attesa di 2.5."
```

### 2.5 — Prompt: KnowledgeRepository + RAG

```text
Leggi BLUEPRINT.md §06.3 (KnowledgeRepository con resolve_slugs_to_ids, search_chunks con JOIN regionale, get_style_patterns).

COMPITO ATOMICO:
In `services/knowledge_repo.py` (NON rag_service.py):
  - Classe KnowledgeRepository come BP §06.3
  - resolve_slugs_to_ids() con validazione ValueError se slug mancanti
  - search_chunks() con JOIN su regulations.region (NULL-safe)
  - get_style_patterns() con ORDER BY certified_at DESC LIMIT 5

Tests integrazione con dm388_03.pdf ingerito.

Stampa: "KnowledgeRepository pronto. In attesa di 2.6."
```

### 2.6 — Prompt: Endpoint REST `/api/regulations`

```text
Leggi BLUEPRINT.md §10 (endpoint regulations).

COMPITO ATOMICO:
In `api/routes/regulations.py`:
  - POST /api/regulations/upload → admin only, pipeline ingestion
  - GET /api/regulations → paginato
  - GET /api/regulations/{id}/chunks → paginato
  - DELETE /api/regulations/{id} → soft-delete status='ABROGATA'

Rate limit. Authorization. Tests.

Stampa: "Endpoint /api/regulations pronto. Pronto per commit FASE 2."
```

### Checklist Umana — fine FASE 2

```text
[ ] DM 388/2003 ingerito con successo
[ ] coverage_check ≥ 70%
[ ] Dedup content_hash funzionante
[ ] Embedding voyage-3 dimensione 1024
[ ] HNSW index utilizzato (EXPLAIN ANALYZE)
[ ] COURSE_CATALOG ha 6 tipi corso
[ ] HACCP Campania valida, regione inesistente → errore
[ ] knowledge_repo.py (NON rag_service.py) con resolve_slugs + search_chunks
[ ] Chunking INLINE in ingestion_service.py (NO file utils/chunking.py separato)
[ ] Tutti test passano
```

### Git — fine FASE 2

```bash
git checkout -b feat/phase2-kb-rag
git add .
git commit -m "feat(phase2): ingestion, hybrid chunking (inline), Voyage embeddings, RAG, COURSE_CATALOG"
git tag v0.3.0-phase2
git push origin feat/phase2-kb-rag
```

---

<a id="fase-3"></a>
## FASE 3 — AGENTI LANGGRAPH + PACINGENGINE (Sprint 3 Blueprint)

<!-- FIX-1 APPLICATO: 2 nodi (research + content), NON 3. Production Builder è post-pipeline. -->
<!-- FIX-3 APPLICATO: NO circuit_breaker.py separato. Contatore inline nel content_agent. -->
<!-- FIX-8 + GAP-1 APPLICATI: PacingEngine con regola 1 slide / 30 secondi, DIAGRAM escluso dalla distribuzione v1.0. -->

**Riferimenti BP:** §05 (2 agenti Research + Content, checkpointing PostgreSQL), §06B (PacingEngine), §15 Sprint 3.
**Deliverable:** pipeline LangGraph a **2 nodi** eseguibile end-to-end, slide JSON, circuit breaker (contatore inline), checkpoint persistito, PacingEngine calibrato a 1 slide / 30 secondi.

### 3.1 — Prompt: State LangGraph + Checkpointer + Grafo (2 NODI)

```text
Leggi BLUEPRINT.md §05 (LangGraph: SOLO 2 nodi research + content, Production Builder è funzione POST-PIPELINE, NON un nodo).

COMPITO ATOMICO:
In `agents/pipeline.py` (UNICO file per state + grafo, come BP §05.2 e §05.3):
  1. NexusPipelineState(TypedDict) con TUTTI i campi BP §05.2 (course_request, brand_config, course_context, pacing_plan, completed_modules con operator.add, current_module_index, job_id, errors). NIENTE pptx_path/pdf_path nello state — il Production Builder è post-pipeline.
  2. create_pipeline(database_url) con:
     - graph.add_node("research", research_agent)
     - graph.add_node("content", content_agent)
     - graph.set_entry_point("research")
     - graph.add_edge("research", "content")
     - graph.set_finish_point("content")
     - checkpointer = AsyncPostgresSaver.from_conn_string(database_url)
     - return graph.compile(checkpointer=checkpointer)
  3. Il grafo ha ESATTAMENTE 2 NODI. NON aggiungere "finalize" o altri nodi.

Tests: tests/unit/test_graph_compile.py → assert graph compila, ha **2 nodi**, edges corretti.

Stampa: "Graph LangGraph compilato (2 nodi). In attesa di 3.2."
```

### 3.2 — Prompt: PacingEngine (regola 1 slide / 30 secondi)

<!-- GAP-1 INTEGRATO: SECONDS_PER_SLIDE = 30 (fisso). FIX-8: DIAGRAM rimosso dalla distribuzione v1.0. -->

```text
Leggi BLUEPRINT.md §06B INTERAMENTE (PacingEngine).

COMPITO ATOMICO:
In `services/pacing_engine.py` (NON agents/pacing_engine.py):

Implementa PacingEngine come BP §06B MA con questa CORREZIONE CRITICA sulla regola di pacing:

═══ VINCOLO METRICO v2.0 ═══
La regola fondamentale di distribuzione è: 1 SLIDE OGNI 30 SECONDI DI CORSO.
Questo è un impegno commerciale verso il cliente e un vincolo architetturale.

Nella formula di calcolo, SOSTITUISCI la media ponderata dei SECONDS_PER_TYPE con:

    SECONDS_PER_SLIDE = 30  # vincolo metrico fisso
    total_slides = int((total_seconds / SECONDS_PER_SLIDE) * multiplier)

Dove total_seconds = duration_hours * 3600 e multiplier è il DENSITY_MULTIPLIER.
Risultato atteso con densità STANDARD:
  - 1h → 120 slide
  - 4h → 480 slide
  - 8h → 960 slide
  - 16h → 1920 slide

La DISTRIBUTION (proporzioni dei tipi slide nel modulo) resta come BP §06B MA senza DIAGRAM in v1.0:
    DISTRIBUTION = {
        "CONTENT_TEXT": 0.50,
        "CONTENT_IMAGE": 0.22,
        "QUIZ": 0.12,
        "CASE_STUDY": 0.06,
        "RECAP": 0.10,
    }
    # DIAGRAM ESCLUSO in v1.0 (D-17). Se l'LLM lo genera spontaneamente, gestito dal fallback in FASE 4.

I titoli dei moduli vengono dal COURSE_CATALOG (semantici, BP §13).
Il body validator con troncamento soft rimane come BP §04.4.

Tests: tests/unit/test_pacing_engine.py:
  - 1h standard → esattamente 120 slide
  - 8h standard → esattamente 960 slide
  - 4h leggera → 480 * 0.8 = 384 slide
  - DIAGRAM non presente nella distribuzione

Stampa: "PacingEngine pronto (30s/slide). In attesa di 3.3."
```

### 3.3 — Prompt: Research Agent

```text
Leggi BLUEPRINT.md §05.4 INTERAMENTE (Research Agent con gate RAG, top_k dinamico, distribuzione chunk, validazione regionale).

COMPITO ATOMICO:
In `agents/research_agent.py` come BP §05.4:
  - research_agent(state) → dict
  - Usa get_pool() da dependencies
  - resolve_slugs_to_ids, query semantica (D-20), top_k = max(30, duration_hours * 10)
  - Gate RAG: < 5 chunk → ValueError
  - Filtro rilevanza MIN_RELEVANCE = 0.3
  - distribute_chunks_to_modules con keyword overlap + _rebalance_min + _rebalance_max
  - Validazione regionale per corsi con flag "regional"

Tests integrazione con DM 388/2003 ingerito.

Stampa: "Research Agent pronto. In attesa di 3.4."
```

### 3.4 — Prompt: Content Agent (con Circuit Breaker INLINE)

<!-- FIX-3 APPLICATO: NO file circuit_breaker.py separato. Contatore inline come BP §05.5. -->

```text
Leggi BLUEPRINT.md §05.5 INTERAMENTE (Content Agent con retry LLM, JSON parsing, circuit breaker inline) e §05.6 (prompt engineering Discente/Formatore).

COMPITO ATOMICO:

In `agents/prompts.py`: system prompt Discente + Formatore + build_module_prompt + build_previous_summary come BP §05.6.

In `agents/content_agent.py`:
  - content_agent(state) → dict come BP §05.5
  - call_llm() con tenacity retry (3 tentativi, exponential backoff)
  - parse_slides_json() con retry correttivo
  - Validazione SlideContent per ogni slide
  - CIRCUIT BREAKER INLINE (contatore, NON classe separata):
    failed_count = 0; if failed_count > total_modules * 0.5: raise RuntimeError("Circuit breaker")

NON creare file agents/circuit_breaker.py. NON creare classe ModuleCircuitBreaker.

Tests: mock Anthropic API, verifica circuit breaker apre su >50% failure.

Stampa: "Content Agent pronto. In attesa di 3.5."
```

### 3.5 — Prompt: Pipeline End-to-End (senza Production Builder)

```text
COMPITO ATOMICO:
In tests/integration/test_pipeline_e2e_no_build.py:
  - Ingest DM 388/2003 + seed
  - Costruisci initial_state esplicito (BP §05.2)
  - graph.ainvoke con asyncio.wait_for(timeout=PIPELINE_TIMEOUT_SECONDS)
  - Verifica: ≥ 1 modulo, ≥ N slide, checkpoint persistito

Esegui. Stampa: "Pipeline E2E (no build) funzionante. Pronto per commit FASE 3."
```

### Checklist Umana — fine FASE 3

```text
[ ] LangGraph: **2 nodi** (research, content), edge lineare (NON 3, NON finalize)
[ ] NexusPipelineState è TypedDict in agents/pipeline.py (non in models/)
[ ] Checkpointer PostgreSQL attivo
[ ] PacingEngine: 1h standard → 120 slide, 8h → 960 (regola 30s/slide)
[ ] PacingEngine: DIAGRAM NON nella distribuzione v1.0
[ ] PacingEngine in services/pacing_engine.py (NON agents/)
[ ] Distribuzione chunks ribilanciata (keyword overlap + min/max)
[ ] Body validator emette warning su troncamento
[ ] Research Agent: query SEMANTICA, threshold 0.3, gate 5 chunk
[ ] Content Agent: circuit breaker INLINE (contatore), NON classe separata
[ ] NO file agents/circuit_breaker.py nel progetto
[ ] Prompt differenziato per Formatore vs Discente
[ ] Retry tenacity su 429/500/529
[ ] asyncio.wait_for con timeout 1800s
[ ] GRANT su tabelle LangGraph per nexus_app
[ ] pytest tutti verdi
```

### Git — fine FASE 3

```bash
git checkout -b feat/phase3-agents
git add .
git commit -m "feat(phase3): LangGraph 2-node pipeline, PacingEngine 30s/slide, Research+Content agents"
git tag v0.4.0-phase3
git push origin feat/phase3-agents
```

---

<a id="fase-4"></a>
## FASE 4 — PRODUCTION BUILDER (PPTX / PDF / Image / SVG / Audio TTS) (Sprint 4 Blueprint)

<!-- GAP-3 INTEGRATO: sotto-fase 4.6 per Audio Service TTS narrazione FAD. -->

**Riferimenti BP:** §07 INTERAMENTE + estensione GAP-3 (Audio TTS).
**Deliverable:** dato un set di Slide JSON → output `corso.pptx`, `dispensa.pdf`, `audio/*.mp3`, `sync_manifest.json`, immagini in cache; tutto thread-safe via Semaphore(1) downstream.

> **Prerequisito hard:** template PPTX `assets/templates/nexus_master.pptx` calibrato manualmente (LAVORO UMANO 4-6 ore). Brand assets presenti.

### 4.1 — Prompt: `inspect_pptx_template.py`

```text
Leggi BLUEPRINT.md §07.3.

COMPITO ATOMICO:
In `scripts/inspect_pptx_template.py`: script CLI come BP §07.3 che ispeziona il template PPTX.
Output: report tabellare + JSON in `assets/templates/master_inspection.json`.

Stampa: "Template ispezionato. In attesa di 4.2."
```

### 4.2 — Prompt: SlideBuilder

```text
Leggi BLUEPRINT.md §07 (SlideBuilder: image_map con path locali, try/except, fallback placeholder).

COMPITO ATOMICO:
In `builders/slide_builder.py`: come BP. Riceve image_map dict[int, str] con path locali. Try/except su inserimento immagine, fallback testuale.

Tests con template minimale e slide mock.

Stampa: "SlideBuilder pronto. In attesa di 4.3."
```

### 4.3 — Prompt: Image Service (con sanitize_svg INLINE)

<!-- FIX-2 APPLICATO: sanitize_svg è INLINE in image_service.py, NON in utils/svg_sanitizer.py separato -->

```text
Leggi BLUEPRINT.md §07.0 INTERAMENTE.

COMPITO ATOMICO:
In `services/image_service.py`:
  - sanitize_svg() come funzione INLINE (BP §07.0, NON file separato)
  - _download_one_image() con Semaphore(5), cache DB, validazione Pillow
  - _render_diagram_sync() con cairosvg
  - prefetch_images() → dict[int, str] come BP §07.0

Tests: SVG malevolo → sanitizzato; immagine corrotta → scartata.

Stampa: "ImageService pronto. In attesa di 4.4."
```

### 4.4 — Prompt: PDF Builder (con Jinja2 — OPT-3 v3.0)

```text
Leggi BLUEPRINT.md §07.2 (PdfBuilder con WeasyPrint).

COMPITO ATOMICO:
In `builders/pdf_builder.py`: PdfBuilder con WeasyPrint MA usando **Jinja2** per il template HTML (OPT-3 v3.0).

NON usare f-string .format() per il template HTML. Invece:
  1. Crea il file `app/templates/dispensa.html` con template Jinja2:
     - Loop `{% for slide in slides %}` sui moduli e sulle slide
     - Condizionale `{% if slide.normative_ref %}` per riferimenti normativi
     - Condizionale per speaker_notes, quiz con opzioni
     - Variabili `{{ palette.primary }}`, `{{ palette.secondary }}` per colori brand
     - Copertina con titolo, normative, logo, data
     - Footer con numerazione pagine via `@page { @bottom-center { content: counter(page); } }`
  2. In PdfBuilder.__init__: carica `Environment(loader=FileSystemLoader("app/templates/"))` Jinja2
  3. In PdfBuilder.build: `template.render(course=..., slides=..., palette=...)` → poi `weasyprint.HTML(string=html).write_pdf(pdf_path)`

Il template deve produrre lo STESSO output strutturale del PDF_TEMPLATE della BP §07.2:
  - @page A4, margin 2cm
  - Font: 'Open Sans' body, 'Montserrat' headings
  - Sezioni per modulo con page-break
  - Classi .normative-ref, .quiz, .speaker-notes

Tests: slide mock → PDF generato con contenuto corretto.

Stampa: "PDF Builder Jinja2 pronto. In attesa di 4.5."
```

### 4.5 — Prompt: ProductionBuilder (Orchestratore Build)

```text
Leggi BLUEPRINT.md §07.1 (ProductionBuilder: memory check, disk check, asyncio.to_thread).

COMPITO ATOMICO:
In `builders/production_builder.py`: ProductionBuilder come BP §07.1.
  - check_memory_before_build() con psutil
  - check_disk_before_build()
  - Build: PPTX → validate → PDF → Audio (FASE 4.6 aggiungerà il passo audio) → cleanup
  - asyncio.to_thread() per operazioni sincrone
  - _cleanup_tmp() per file > 1 ora

In `builders/pptx_validator.py`: validazione post-build come BP.

Tests end-to-end con 20 slide mock.

Stampa: "ProductionBuilder pronto. In attesa di 4.6."
```

### 4.6 — Prompt: Audio Service — Narrazione TTS per FAD (edge-tts — OPT-1 v3.0)

<!-- GAP-3 INTEGRATO + OPT-1 APPLICATO: edge-tts sostituisce OpenAI TTS. Gratuito, nessuna API key. -->

```text
Leggi CLAUDE.md (REI-9 e OPT-1). NON cercare questa funzionalità nella BLUEPRINT — è un'estensione v2.0 documentata in questo Execution Plan per colmare il GAP-3 dell'audit commerciale (narrazione audio FAD promessa al cliente nel PDF §3.8 e §05).

ATTENZIONE: NON usare OpenAI TTS. Usare **edge-tts** (Microsoft Edge Neural TTS).
Motivazione (OPT-1 v3.0): gratuito, nessuna API key, nessun vendor lock-in, qualità eccellente per narrazione formativa in italiano. Il cliente C.F.P. Montessori non dovrà mantenere un account OpenAI post-consegna.

COMPITO ATOMICO:
In `services/audio_service.py`:

  - Classe `AudioService` con:
    - `__init__(self, voice: str)` → legge TTS_VOICE da settings (default: "it-IT-DiegoNeural"). NON serve parametro model (edge-tts non ha tier).
    - `async generate_narrations(slides: list[SlideContent], course_id: str, pool) -> dict`:
      1. Per ogni slide con speaker_notes non vuoto:
         - Costruisci testo di narrazione: se speaker_notes è presente usalo, altrimenti usa body della slide riformulato in tono discorsivo
         - Genera audio con edge-tts:
           ```python
           import edge_tts

           communicate = edge_tts.Communicate(narration_text, self.voice)
           await communicate.save(audio_path)
           ```
         - Calcola durata MP3 con mutagen:
           ```python
           from mutagen.mp3 import MP3
           audio_info = MP3(audio_path)
           duration_seconds = audio_info.info.length
           ```
         - Salva MP3 in `output/audio/{course_id}/slide_{index:04d}.mp3`
         - INSERT in tabella audio_tracks (course_id, slide_index, narration_text, audio_path, duration_seconds, voice)
      2. Genera manifesto sincronizzazione `output/audio/{course_id}/sync_manifest.json`:
         ```json
         {
           "course_id": "uuid",
           "total_tracks": N,
           "tracks": [
             {"slide_index": 0, "audio_file": "slide_0000.mp3", "duration_seconds": 12.5, "narration_text": "..."},
             ...
           ]
         }
         ```
      3. Salva path manifesto in courses.audio_manifest_path
      4. Return: dict con conteggio tracce generate e path manifesto

    - Concorrenza: Semaphore(3) per chiamate TTS parallele
    - Retry: tenacity con exponential backoff su errori HTTP/connessione
    - Timeout: 30s per singola generazione TTS
    - Fallback: se TTS fallisce per una slide, logga warning e continua (la slide resta senza audio)

Aggiorna `builders/production_builder.py` per includere la fase audio:
  - Dopo PDF build e prima di cleanup, aggiungi:
    ```python
    if "audio" in course.get("outputs", []):
        await ws_callback(job_id, 96, "Generazione narrazione audio...")
        from app.config import settings
        audio_service = AudioService(voice=settings.tts_voice)
        audio_result = await audio_service.generate_narrations(slides, course["id"], db)
    ```

Tests:
  - tests/unit/test_audio_service.py: mock edge_tts.Communicate, verifica che per 5 slide con speaker_notes genera 5 file e manifesto JSON valido
  - tests/unit/test_audio_fallback.py: mock edge_tts che fallisce su 1 slide → le altre 4 vengono generate, warning loggato

Stampa: "Audio Service edge-tts pronto. In attesa di 4.7."
```

### 4.7 — Prompt: Test E2E Build Sintetico (con Audio)

```text
COMPITO ATOMICO:
Crea `scripts/synth_build_test.py`:
  - 30 slide sintetiche con speaker_notes
  - Chiama ProductionBuilder.build_course con outputs=["pptx", "pdf", "audio"]
  - Verifica: PPTX esiste con 30 slide, PDF esiste, cartella audio/ esiste con MP3, sync_manifest.json valido
  - edge-tts non richiede API key, quindi il test audio funziona sempre (nessun skip condizionale)

Esegui. Stampa: "FASE 4 verificata. Pronto per commit."
```

### Checklist Umana — fine FASE 4

```text
[ ] Template master.pptx calibrato e versionato
[ ] inspect_pptx_template.py genera master_inspection.json
[ ] SlideBuilder: path locali, fallback placeholder
[ ] image_service: Semaphore(5), timeout 10s, Pillow validate, sanitize_svg INLINE (no file separato)
[ ] cairosvg renderizza SVG di test
[ ] **[v3.0 OPT-3] PDF builder usa Jinja2 template (templates/dispensa.html) + WeasyPrint**
[ ] PDF builder produce PDF con TOC, header/footer branded
[ ] ProductionBuilder: memory check + disk check + asyncio.to_thread
[ ] _cleanup_tmp funziona
[ ] **[v3.0 OPT-1] Audio Service: genera MP3 per slide via edge-tts (NON OpenAI)**
[ ] **[v3.0 OPT-1] Nessuna OPENAI_API_KEY nel .env**
[ ] **[v3.0 OPT-4] Durata MP3 calcolata con mutagen**
[ ] **[v2.0] sync_manifest.json prodotto e salvato in courses.audio_manifest_path**
[ ] **[v2.0] audio_tracks tabella popolata correttamente (voice default: it-IT-DiegoNeural)**
[ ] **[v2.0] Fallback: slide senza speaker_notes → skip audio (no crash)**
[ ] **[v2.0] Concorrenza audio: Semaphore(3) per TTS parallelo**
[ ] synth_build_test.py produce PPTX + PDF + audio/ (nessun skip condizionale — edge-tts non richiede API key)
[ ] pytest, mypy, ruff verdi
```

### Git — fine FASE 4

```bash
git checkout -b feat/phase4-production-builder
git add .
git commit -m "feat(phase4): SlideBuilder, ImageService, PdfBuilder (Jinja2), AudioService (edge-tts), ProductionBuilder"
git tag v0.5.0-phase4
git push origin feat/phase4-production-builder
```

---

<a id="fase-5"></a>
## FASE 5 — ORCHESTRAZIONE BACKEND + WEBSOCKET + REST (Sprint 5A Blueprint)

<!-- FIX-7 APPLICATO: semaforo vive in generation_service.py, non dependencies.py -->

**Riferimenti BP:** §09, §10, §15 Sprint 5A.
**Deliverable:** endpoint /api/courses, WebSocket progress, queue position, audit log, download audio.

### 5.1 — Prompt: `generation_service.py`

```text
Leggi BLUEPRINT.md §09 INTERAMENTE.

COMPITO ATOMICO:
In `services/generation_service.py`:
  - _job_semaphore = asyncio.Semaphore(1) QUI (BP §09, NON in dependencies.py)
  - PIPELINE_TIMEOUT_SECONDS da config
  - get_shutdown_event() da services/dependencies.py (D-18)
  - run_pipeline(job_id, course_id) come BP §09: acquisisce semaforo, wait_for con timeout
  - _run_pipeline_inner(job_id, course_id) come BP §09: carica corso, costruisce initial_state, invoca LangGraph, salva slide_contents_json, fingerprint PRIMA del build, poi chiama ProductionBuilder
  - build_normative_fingerprint() come BP §09
  - send_ws_progress() come BP §09
  - recover_interrupted_jobs() come BP §09.2

Tests con pipeline mockata.

Stampa: "generation_service pronto. In attesa di 5.2."
```

### 5.2 — Prompt: Endpoint `/api/courses`

```text
Leggi BLUEPRINT.md §10.

COMPITO ATOMICO:
In `api/routes/courses.py`:
  - POST /api/courses → avvia pipeline, ritorna {course_id, job_id, queue_position}
  - GET /api/courses → paginato, ownership-aware
  - GET /api/courses/{id} → dettaglio con fingerprint
  - POST /api/courses/{id}/certify → certifica corso (Livello 2)
  - GET /api/courses/{id}/download/{format} → PPTX, PDF, ZIP, audio (aggiungere "audio" come formato: scarica zip della cartella audio/)
  - DELETE /api/courses/{id} → soft-delete archived

Rate limit su POST. Tests.

Stampa: "Endpoint courses pronto. In attesa di 5.3."
```

### 5.3 — Prompt: WebSocket Progress Autenticato

```text
Leggi BLUEPRINT.md §08.8 (WebSocket con JWT, ownership check, get_job_progress).

COMPITO ATOMICO:
In `api/websocket.py`: come BP §08.8.

Tests: senza token → close; altro utente → close; legittimo → riceve progress.

Stampa: "WebSocket pronto. In attesa di 5.4."
```

### 5.4 — Prompt: Endpoint `/api/admin`

```text
Leggi BLUEPRINT.md §10 (admin endpoints).

COMPITO ATOMICO:
In `api/routes/admin.py` (auth: ADMIN only):
  - GET /api/admin/metrics → metriche pipeline da audit_log
  - GET /api/dashboard/stats → courses_count, regulations_count, l2_count
  - GET /api/brand-presets → lista preset branding
  - GET /api/catalog → COURSE_CATALOG

Tests: admin → 200; operatore → 403.

Stampa: "Endpoint admin pronto. In attesa di 5.5."
```

### 5.5 — Prompt: Smoke Test E2E Backend

```text
COMPITO ATOMICO:
Esegui pipeline completa: reset → migrations → seed → login → ingest dm388 → POST /api/courses → WebSocket → COMPLETED → download PPTX + PDF → GET /api/admin/metrics.

Riporta TUTTI gli output.

Stampa: "FASE 5 verificata. Pronto per commit."
```

### Checklist Umana — fine FASE 5

```text
[ ] generation_service usa _job_semaphore definito AL SUO INTERNO (NON da dependencies.py)
[ ] generation_service usa get_shutdown_event() da dependencies (D-18)
[ ] asyncio.wait_for con timeout 1800s
[ ] normative_fingerprint + source_chunk_ids salvati PRIMA del build
[ ] Recovery al boot: job bloccati → failed
[ ] queue_position calcolato
[ ] WebSocket autenticato JWT + ownership check
[ ] Polling fallback 30s documentato
[ ] GET /api/courses/{id}/download/audio → zip audio (v2.0 GAP-3)
[ ] Rate limiting su POST /api/courses
[ ] Audit log append-only verificato
[ ] pytest, mypy, ruff verdi
```

### Git — fine FASE 5

```bash
git checkout -b feat/phase5-orchestration-api
git add .
git commit -m "feat(phase5): generation_service, /api/courses + audio download, WebSocket, /api/admin"
git tag v0.6.0-phase5
git push origin feat/phase5-orchestration-api
```

---

<a id="fase-6"></a>
## FASE 6 — FRONTEND SHADCN-ADMIN + BRANDING C.F.P. MONTESSORI (Sprint 5B Blueprint, v4.0)

<!-- SWAP-1 v4.0: Base 44 eliminato. Frontend sviluppato internamente da Claude Code su template shadcn-admin. -->

**Riferimenti BP:** §10 (API REST + WebSocket), §01.2 (Stack Frontend: React/shadcn/Tailwind/Zustand).
**Deliverable:** applicazione frontend completa con 7 pagine operative, branding C.F.P. Montessori, cablaggio su tutti gli endpoint FastAPI §10 e WebSocket progress tracking. L'applicazione deve sembrare un software enterprise proprietario, non un template generico.

> **Prerequisiti hard:**
> - Node ≥ 20 installato e verificato
> - Backend FastAPI funzionante su `http://localhost:8000` (FASE 0-5 completate)
> - `curl http://localhost:8000/health` → verde
> - `curl http://localhost:8000/openapi.json` → JSON valido
> - Logo C.F.P. Montessori in `assets/brand/logo.png` (512×512) e `assets/brand/logo-light.png` (per dark mode)
> - Palette colori HEX del cliente (primario, secondario, accento) — dal CLIENT_INTAKE §4

### 6.1 — Prompt: Clone Template shadcn-admin

```text
Leggi CLAUDE.md (REI-1 e REI-11).

COMPITO ATOMICO:
1. Cancella `.gitkeep` da `frontend/`.
2. Esegui: `git clone https://github.com/satnaing/shadcn-admin.git frontend/`
3. Rimuovi la cartella `frontend/.git` (il template diventa parte del nostro repo, non un submodule).
4. Crea `frontend/INTEGRATION_NOTES.md` con:
   - Hash commit del template clonato
   - Data di clone
   - Regola: "Questo template è la BASE. Le modifiche avvengono per adattamento, non per sostituzione."
   - Link al repo originale per reference futura
5. NON eseguire `npm install` ancora.

Stampa: "shadcn-admin clonato. In attesa di 6.2."
```

### 6.2 — Prompt: Analisi Struttura Template + Inventario Componenti

```text
Leggi CLAUDE.md (REI-1, REI-11).

COMPITO ATOMICO:
Esplora `frontend/` in profondità. Produci un inventario COMPLETO in `frontend/INTEGRATION_NOTES.md` (aggiungi alla sezione esistente):

## Inventario Template shadcn-admin

### Struttura Directory
(output di `find frontend/src -type f -name "*.tsx" -o -name "*.ts" | head -80`)

### Pagine Esistenti
| Path | Descrizione | Riutilizzabile per Nexus? | Pagina Nexus target |
|---|---|---|---|
| src/pages/dashboard.tsx | Dashboard principale | Sì → Dashboard corsi | Dashboard |
| src/pages/auth/sign-in.tsx | Login form | Sì → Login | Login |
| src/pages/tasks.tsx | Lista task | Sì → Lista corsi | Dashboard |
| ... | ... | ... | ... |

### Componenti shadcn/ui Disponibili
(lista TUTTI i componenti in `src/components/ui/`)

### Layout e Navigazione
- Sidebar: path e struttura
- Header: path e struttura
- Route config: path e struttura

### Sistema di Temi
- CSS variables location: `src/index.css` o simile
- Tailwind config: `tailwind.config.ts`
- Dark mode: come gestito

NON modificare nessun file. Solo analisi.

Stampa: "Inventario completato. In attesa di 6.3."
```

### 6.3 — Prompt: Iniezione Brand C.F.P. Montessori (Visual Identity)

<!-- SWAP-5 v4.0: Branding injection esplicito -->

```text
Leggi CLAUDE.md (REI-1, REI-11) e `frontend/INTEGRATION_NOTES.md` (sezione "Sistema di Temi").
Leggi i materiali brand del cliente in `assets/brand/` (logo, palette).

COMPITO ATOMICO — BRANDING:
Applica l'identità visiva C.F.P. Montessori al template shadcn-admin. Intervieni SOLO sui file di configurazione globale, NON sulle singole pagine (quelle verranno dopo).

1. **Variabili CSS `:root`** (in `src/index.css` o equivalente):
   Sovrascrivi i colori del tema con la palette del cliente:
   ```css
   :root {
     --primary: <HEX primario C.F.P. Montessori convertito in HSL>;
     --primary-foreground: <contrasto calcolato>;
     --secondary: <HEX secondario>;
     --accent: <HEX accento>;
     /* Mantieni tutti gli altri token del template invariati */
   }
   ```

2. **tailwind.config.ts**:
   Estendi il tema con i colori brand:
   ```typescript
   theme: {
     extend: {
       colors: {
         brand: {
           primary: '<HEX>',
           secondary: '<HEX>',
           accent: '<HEX>',
         }
       }
     }
   }
   ```

3. **Logo e Favicon**:
   - Copia `assets/brand/logo.png` → `frontend/public/logo.png`
   - Copia `assets/brand/logo-light.png` → `frontend/public/logo-light.png` (se esiste)
   - Aggiorna il componente Sidebar per usare il logo del cliente al posto del placeholder
   - Aggiorna `favicon.ico` e `<title>` in `index.html` → "Nexus EduVault — C.F.P. Montessori"

4. **Titoli e Label**:
   - App name: "Nexus EduVault"
   - Sidebar header: logo + "Nexus EduVault"
   - Footer (se presente): "© C.F.P. Montessori — Powered by Axialoop"

Tests: `npm run dev` → verifica visivamente che i colori e il logo siano applicati.

Stampa: "Branding C.F.P. Montessori applicato. In attesa di 6.4."
```

### 6.4 — Prompt: Tipi TypeScript da OpenAPI

```text
COMPITO ATOMICO:
1. `cd frontend && npm install` (prima installazione dipendenze template)
2. `curl http://localhost:8000/openapi.json > src/lib/openapi.json`
3. `npx openapi-typescript src/lib/openapi.json -o src/lib/types.gen.ts`
4. Verifica che `types.gen.ts` contenga i tipi per: CourseRequest, CourseResponse, User, Regulation, BrandPreset

Stampa: "Tipi TypeScript generati da OpenAPI. In attesa di 6.5."
```

### 6.5 — Prompt: API Client + WebSocket Client

```text
Leggi BLUEPRINT.md §10 (TUTTI gli endpoint) e §08.8 (WebSocket).

COMPITO ATOMICO:
Crea due file:

1. `frontend/src/lib/api.ts` — Client HTTP tipizzato per TUTTI gli endpoint BP §10:
   ```typescript
   // Auth
   login(email, password) → POST /api/auth/login → {access_token, refresh_token}
   refresh(token) → POST /api/auth/refresh → {access_token}
   getMe() → GET /api/users/me → User

   // Courses
   createCourse(data: CourseRequest) → POST /api/courses → CourseResponse
   getCourses(page, filters) → GET /api/courses → paginated
   getCourse(id) → GET /api/courses/{id} → detail
   certifyCourse(id) → POST /api/courses/{id}/certify
   downloadCourse(id, format) → GET /api/courses/{id}/download/{format} → blob
   deleteCourse(id) → DELETE /api/courses/{id}

   // Regulations
   uploadRegulation(file) → POST /api/regulations/upload
   getRegulations(page) → GET /api/regulations → paginated
   getChunks(id, page) → GET /api/regulations/{id}/chunks → paginated
   deleteRegulation(id) → DELETE /api/regulations/{id}

   // Admin
   getMetrics() → GET /api/admin/metrics
   getDashboardStats() → GET /api/dashboard/stats
   getBrandPresets() → GET /api/brand-presets
   getCatalog() → GET /api/catalog
   ```

   Usa fetch nativo con interceptor per JWT (Authorization header), auto-refresh su 401.

2. `frontend/src/lib/ws.ts` — WebSocket client per progress tracking:
   ```typescript
   connectToJob(jobId, token, onProgress, onComplete, onError)
   // URL: ws://localhost:8000/ws/{jobId}?token={jwt}
   // Fallback: polling GET /api/courses/{id} ogni 30 secondi
   ```

Tests manuali: verifica che `api.ts` compila senza errori TypeScript.

Stampa: "API client e WebSocket client pronti. In attesa di 6.6."
```

### 6.6 — Prompt: Pagina Login

```text
Leggi CLAUDE.md (REI-1, REI-11) e `frontend/INTEGRATION_NOTES.md` (pagina auth/sign-in esistente nel template).

COMPITO ATOMICO:
Adatta la pagina di login del template per Nexus EduVault:
  - Logo C.F.P. Montessori centrato sopra il form
  - Campi: email + password (shadcn/ui Input)
  - Bottone "Accedi" (shadcn/ui Button, colore brand primary)
  - Gestione errori: toast per credenziali invalide
  - On success: salva JWT in localStorage, redirect a /dashboard
  - Titolo pagina: "Nexus EduVault — Accesso"

Usa `api.ts → login()`. NON inventare un design nuovo — adatta quello esistente nel template.

Stampa: "Login pronto. In attesa di 6.7."
```

### 6.7 — Prompt: Dashboard + Lista Corsi

```text
Leggi BLUEPRINT.md §10 e CLAUDE.md (REI-11).
Ispirazione pattern: Linear.app (lista con stati e badge colorati).

COMPITO ATOMICO:
Adatta la pagina dashboard del template per mostrare:

1. **Header Dashboard**: statistiche sintetiche (shadcn/ui Card):
   - Corsi totali, Corsi in generazione, Normative indicizzate, Corsi approvati (L2)
   - Dati da `GET /api/dashboard/stats`

2. **Lista Corsi** (shadcn/ui Table con DataTable pattern del template):
   - Colonne: Titolo, Tipo, Target (discente/formatore), Durata, Stato, Data, Azioni
   - Badge stato colorati: generating (giallo pulse), completed (blu), certified (verde), failed (rosso)
   - Filtri: per tipo, per stato, per target
   - Paginazione
   - Bottone "Nuovo Corso" → naviga a wizard
   - Azioni per riga: Scarica (PPTX/PDF/Audio), Dettaglio, Certifica (se reviewer), Elimina
   - Dati da `GET /api/courses`

3. **FAB o header action**: "Nuovo Corso" button prominente

Stampa: "Dashboard pronta. In attesa di 6.8."
```

### 6.8 — Prompt: Wizard Creazione Corso (6 Step)

```text
Leggi BLUEPRINT.md §10 (POST /api/courses, payload CourseRequest) e le Specifiche Funzionali §3.1 (Configurazione Guidata del Corso — 6 passaggi).
Ispirazione pattern: Stripe Checkout multi-step.

COMPITO ATOMICO:
Crea una pagina wizard a 6 step con progress indicator:

  Step 1 — Tipo Corso: Select da COURSE_CATALOG (`GET /api/catalog`). Al cambio, pre-popola normative.
  Step 2 — Destinatario: Radio group "Discente" / "Formatore" (shadcn/ui RadioGroup).
  Step 3 — Parametri: duration_hours (number input), region (select, default "NAZIONALE"), slide_density (select: leggera/standard/intensiva).
  Step 4 — Brand: Select brand preset (`GET /api/brand-presets`). Anteprima colori.
  Step 5 — Output: Checkbox group (pptx ✓, pdf ✓, audio ☐). Almeno uno obbligatorio.
  Step 6 — Conferma: Riepilogo di tutti i parametri. Stima slide (duration_hours × 120). Bottone "Genera Corso".

On submit: `POST /api/courses` → ricevi `{course_id, job_id}` → naviga a Progress Monitor.

Validazione Pydantic-aligned: course_type required, duration_hours > 0 e ≤ 16, almeno un output selezionato.

Stampa: "Wizard pronto. In attesa di 6.9."
```

### 6.9 — Prompt: Progress Monitor + Dettaglio Corso + Gestione Normative + Admin

```text
Leggi BLUEPRINT.md §10 e §08.8 (WebSocket).
Ispirazione: GitHub Actions (progress con fasi nominate), Vercel Deploy log.

COMPITO ATOMICO (4 pagine in un prompt — componenti piccoli):

**A) Progress Monitor** (`/courses/{id}/progress`):
  - Connessione WebSocket via `ws.ts → connectToJob()`
  - Barra progresso animata (shadcn/ui Progress)
  - Fasi nominate con icone: ⏳ Ricerca normativa → 📝 Generazione contenuti → 🏗️ Composizione PPTX → 📄 Generazione PDF → 🔊 Narrazione audio
  - Al completamento: redirect a Dettaglio Corso
  - Se errore: messaggio con possibilità di retry
  - Fallback polling 30s se WebSocket non disponibile

**B) Dettaglio Corso** (`/courses/{id}`):
  - Card con: titolo, tipo, target, durata, stato, data creazione
  - Sezione download: bottoni per PPTX, PDF, Audio ZIP (da `GET /api/courses/{id}/download/{format}`)
  - Fingerprint normativo: lista delle normative citate (espandibile)
  - Flusso approvazione: se utente = reviewer, bottone "Certifica" (`POST /api/courses/{id}/certify`)
  - Dati da `GET /api/courses/{id}`

**C) Gestione Normative** (`/regulations`):
  - Upload PDF con drag-and-drop (shadcn/ui + react-dropzone o nativo)
  - Lista normative: titolo, tipo, stato (VIGENTE/ABROGATA), data, regione
  - Dettaglio: lista chunk estratti con tipo e tag (paginata)
  - Soft-delete: bottone "Abroga" → `DELETE /api/regulations/{id}`
  - Solo admin vede upload e delete

**D) Admin** (`/admin`):
  - Metriche pipeline: tempo medio, slide totali, corsi generati (da `GET /api/admin/metrics`)
  - Gestione utenti: lista con ruolo e stato is_active
  - Brand presets: lista con preview palette

Stampa: "Tutte le pagine pronte. In attesa di 6.10."
```

### 6.10 — Prompt: Navigazione, Routing + Build Finale

```text
COMPITO ATOMICO:
1. Configura il router del template per le pagine Nexus:
   - `/` → redirect a `/dashboard` se autenticato, altrimenti `/login`
   - `/login` → pagina login
   - `/dashboard` → Dashboard + Lista Corsi
   - `/courses/new` → Wizard 6 step
   - `/courses/:id` → Dettaglio Corso
   - `/courses/:id/progress` → Progress Monitor
   - `/regulations` → Gestione Normative (admin only)
   - `/admin` → Admin panel (admin only)

2. Aggiorna la Sidebar del template:
   - 📊 Dashboard
   - ➕ Nuovo Corso
   - 📚 Normative (solo admin)
   - ⚙️ Admin (solo admin)
   - 👤 Profilo / Logout

3. Implementa route guard: redirect a /login se JWT assente o scaduto.

4. Esegui: `npm run build`
   - Se errori TypeScript → correggili
   - Se warning → documenta in INTEGRATION_NOTES.md

5. Esegui: `npm run dev` → verifica manuale:
   - Login → Dashboard → Nuovo Corso → tutti i 6 step → Conferma → Progress → Download

Stampa: "FASE 6 completata. Pronto per commit."
```

### Checklist Umana — fine FASE 6

```text
[ ] shadcn-admin clonato (non submodule), .git rimosso
[ ] INTEGRATION_NOTES.md con inventario componenti e hash commit
[ ] **[v4.0 SWAP-5] Branding applicato: colori C.F.P. Montessori in :root CSS + tailwind.config.ts**
[ ] **[v4.0 SWAP-5] Logo C.F.P. Montessori in sidebar e login**
[ ] **[v4.0 SWAP-5] Favicon e <title> aggiornati**
[ ] types.gen.ts generato da openapi.json — tipi corrispondono ai contratti Pydantic
[ ] api.ts copre TUTTI gli endpoint BP §10 + download audio
[ ] ws.ts: WebSocket primario + polling fallback 30s
[ ] Login funzionante con JWT (localStorage)
[ ] Dashboard: statistiche + lista corsi con badge stato
[ ] Wizard 6 step: tutti i campi CourseRequest coperti
[ ] Progress Monitor: WebSocket real-time con fasi nominate
[ ] Dettaglio Corso: download PPTX/PDF/Audio + fingerprint normativo
[ ] Gestione Normative: upload, lista, chunks, soft-delete
[ ] Admin: metriche, utenti, brand presets
[ ] Route guard: redirect a /login senza JWT
[ ] Sidebar navigazione con icone e ruoli
[ ] Dark mode funzionante (ereditato dal template)
[ ] `npm run build` passa senza errori
[ ] Smoke test E2E: Login → Wizard → Progress → Download → OK
```

### Git — fine FASE 6

```bash
git checkout -b feat/phase6-frontend-shadcn
git add .
git commit -m "feat(phase6): frontend shadcn-admin, branding C.F.P. Montessori, 7 pages, API/WS wiring"
git tag v0.7.0-phase6
git push origin feat/phase6-frontend-shadcn
```

---

<a id="fase-7"></a>
## FASE 7 — CERTIFICATION, AUDIT, METRICHE, E2E, DEPLOY (Sprint 6 Blueprint)

<!-- FIX-4 APPLICATO: rimossa generazione certificati PDF/QR. Solo certify_course + StylePatternExtractor come da BP §06.2. -->

**Riferimenti BP:** §06.2 (certification_service), §12, §14, §15 Pre-Deploy.
**Deliverable:** certification service (certify_course + StylePatternExtractor), audit log completo, metriche, backup, E2E, deploy.

### 7.1 — Prompt: Certification Service (StylePatternExtractor SOLO)

```text
Leggi BLUEPRINT.md §06.2 (certification_service.py: StylePatternExtractor deterministico + certify_course).

COMPITO ATOMICO:
In `services/certification_service.py`:
  - StylePatternExtractor deterministico come BP §06.2 — estrae SOLO metadati strutturali (avg_words_per_slide, preferred_slide_sequence, tone_register, recurring_section_titles, avg_quiz_per_module, preferred_image_ratio). MAI frasi, MAI testo normativo.
  - certify_course(course_id, reviewer_id, pool) come BP §06.2: estrae pattern, inserisce in approved_courses, aggiorna status='certified'.

NON generare certificati PDF. NON generare QR code. NON creare tabella certificates. Queste feature non sono nella BP v1.0.

Tests: tests/integration/test_certification.py: certifica un corso, verifica approved_courses popolato, pattern deterministico (2 run → stesso output).

Stampa: "Certification service pronto. In attesa di 7.2."
```

### 7.2 — Prompt: Audit & Cleanup

```text
Leggi BLUEPRINT.md §08.7 (Audit Log) e §12 (cleanup_old_images).

COMPITO ATOMICO:
Audit: applica INSERT audit_log in endpoint sensibili (login, ingest, create/delete course, certify, admin).

In cleanup: cleanup_old_images(pool) come BP §12.1. Schedula in main.py lifespan ogni 24h.

Tests.

Stampa: "Audit & cleanup pronti. In attesa di 7.3."
```

### 7.3 — Prompt: Testing E2E Completo

```text
COMPITO ATOMICO:
In tests/integration/test_e2e_full.py:
  - Ingest 3 normative reali (DM 388, DLgs 81/08, Reg CE 852/2004)
  - Crea 3 corsi diversi (incluso HACCP Campania)
  - Run pipeline, verifica PPTX + PDF + audio presenti
  - Certifica 1 corso → approved_courses popolato
  - Verifica EXPLAIN ANALYZE → HNSW index
  - Kill backend → restart → job FAILED
  - DELETE audit_log come nexus_app → fail

Esegui. Stampa: "E2E completo. In attesa di 7.4."
```

### 7.4 — Prompt: Backup & Ops

```text
Leggi BLUEPRINT.md §12.

COMPITO ATOMICO:
scripts/backup.sh, scripts/restore.sh, docs/OPERATIONS.md come da standard.

Stampa: "Backup & ops pronti. In attesa di 7.5."
```

### 7.5 — Prompt: Deploy su VPS

```text
COMPITO ATOMICO:
deploy/nginx.conf, deploy/docker-compose.prod.yml, deploy/install.sh, deploy/PRECHECK.md.

NON eseguire deploy automaticamente.

Stampa: "Deploy script pronti. FASE 7 completata."
```

### Checklist Umana — fine FASE 7

```text
[ ] certification_service: StylePatternExtractor deterministico (NO certificati PDF, NO QR)
[ ] certify_course inserisce in approved_courses (Livello 2)
[ ] Audit log su endpoint sensibili
[ ] cleanup_old_images schedulata ogni 24h
[ ] E2E: 3 corsi generati, PPTX + PDF + audio presenti
[ ] E2E: HACCP Campania → corretto
[ ] Recovery: kill → restart → job FAILED
[ ] DELETE audit_log nexus_app → fallisce
[ ] Pagination su /api/courses e /api/regulations
[ ] Soft-delete funzionante
[ ] PacingEngine: 1h → 120 slide (regola 30s/slide verificata)
[ ] LangGraph: 2 nodi (research + content), checkpoint persistito
[ ] Circuit breaker: contatore inline, NO classe separata
[ ] Audio: narrazione edge-tts generata per corsi con output "audio" (OPT-1, nessuna OPENAI_API_KEY)
[ ] Backup pg_dump + rsync testato
[ ] Nginx con CSP, HSTS
[ ] HTTPS via Let's Encrypt
[ ] Firewall 22/80/443
[ ] pytest, mypy, ruff verdi
```

### Git — fine FASE 7

```bash
git checkout -b feat/phase7-certification-deploy
git add .
git commit -m "feat(phase7): certification (StylePatternExtractor), audit, cleanup, E2E, deploy"
git tag v1.0.0-rc1
git push origin feat/phase7-certification-deploy

# Dopo merge in main + smoke test:
git checkout main && git pull
git tag v1.0.0 -m "Nexus EduVault Supreme Production Ready v1.0"
git push origin v1.0.0
```

---

<a id="qa-finale"></a>
## SEZIONE FINALE — HUMAN QA MASTER CHECKLIST PRE-GO-LIVE

> Da rivedere riga per riga prima di puntare DNS di corsi8108.it al VPS.

### Vincoli architetturali (BP §1.4)
```text
[ ] D-01 FastAPI (no Django/Flask)
[ ] D-02 Semaphore(1) in generation_service.py; mai 2+
[ ] D-03 No Supabase — PostgreSQL + JWT custom
[ ] D-04 LangGraph con checkpointing, 2 nodi (research + content)
[ ] D-05 python-pptx (no LibreOffice)
[ ] D-06 WeasyPrint (no wkhtmltopdf)
```

### Single source of truth
```text
[ ] BLUEPRINT.md presente e immutato
[ ] CLAUDE.md v4.0 con REI-1 (shadcn-admin), REI-11 (UI Quality), sezione "Architettura Pipeline" e sezione "Ottimizzazioni v3.0"
[ ] Nessuna funzione inventata fuori da BP (grep TODO/FIXME → 0 critici)
```

### Sicurezza
```text
[ ] CORS origin esplicito, mai *
[ ] JWT_SECRET (singola chiave) ≥ 64 byte
[ ] bcrypt password hashing
[ ] is_active check su ogni request
[ ] Rate limit su login, courses POST
[ ] Audit log append-only (nexus_app: no UPDATE/DELETE)
[ ] SVG sanitizer INLINE in image_service.py
[ ] Immagini validate con Pillow
[ ] CSP headers Nginx
[ ] HTTPS forzato
[ ] Firewall 22/80/443
[ ] Secrets in .env mai committati
[ ] Nessun os.environ[] diretto nel codice — tutto via pydantic-settings (OPT-2)
[ ] Settings validati all'avvio: crash-fast se variabile obbligatoria mancante
[ ] Nessuna OPENAI_API_KEY nel .env (OPT-1 — edge-tts non la richiede)
```

### Frontend = shadcn-admin + Branding (v4.0 SWAP)
```text
[ ] shadcn-admin clonato, .git rimosso, INTEGRATION_NOTES.md presente
[ ] Branding C.F.P. Montessori: colori in :root CSS + tailwind.config.ts + logo in sidebar
[ ] 7 pagine operative: Login, Dashboard, Wizard, Progress, Dettaglio, Normative, Admin
[ ] types.gen.ts allineato a openapi.json
[ ] api.ts copre TUTTI gli endpoint BP §10 + audio download
[ ] ws.ts: WebSocket primario + polling fallback 30s
[ ] Route guard: JWT assente → redirect /login
[ ] npm run build passa senza errori
[ ] Dark mode funzionante
[ ] L'applicazione NON sembra un template generico — identità C.F.P. Montessori riconoscibile
```

### Performance & robustezza
```text
[ ] Corso 8h → 960 slide (regola 30s/slide)
[ ] Generato in < 15 minuti
[ ] Pipeline timeout 30 min forzato
[ ] Circuit breaker (contatore inline) funzionante
[ ] Recovery: nessun job orfano dopo kill
[ ] Backup giornaliero testato
```

### Audio TTS — edge-tts (v3.0 OPT-1)
```text
[ ] Audio Service usa edge-tts, NON OpenAI
[ ] Voce italiana: it-IT-DiegoNeural (o altra voce it-IT-* configurata in settings.tts_voice)
[ ] Nessuna OPENAI_API_KEY nel .env di produzione
[ ] MP3 generati per ogni slide con speaker_notes
[ ] Durata MP3 calcolata con mutagen (NON stimata)
[ ] sync_manifest.json prodotto per ogni corso con output "audio"
[ ] audio_tracks tabella DB popolata con voice = 'it-IT-DiegoNeural'
[ ] GET /api/courses/{id}/download/audio funzionante
[ ] Fallback: slide senza notes → skip (no crash)
[ ] Retry edge-tts su errori HTTP/connessione
```

### Cliente e dominio
```text
[ ] corsi8108.it punta al VPS
[ ] SSL valido > 60 giorni
[ ] Admin bootstrap loggato, password cambiata
[ ] PDF normativi caricati
[ ] Template PPTX brandizzato calibrato
[ ] Almeno 2 corsi generati e approvati dal cliente
```

### Documentazione
```text
[ ] docs/OPERATIONS.md
[ ] docs/CLIENT_INTAKE_TRACKING.md aggiornato
[ ] Credenziali admin in password manager
[ ] Procedura onboarding utenti
```

---

## APPENDICE A — REGOLE PRATICHE PER L'OPERATORE UMANO (axialoop)

1. **Apri Claude Code una sessione per Fase.** Mai due Fasi nella stessa.
2. **Tieni questo documento in split-screen** mentre lavori in VS Code.
3. **Copia il prompt esatto, non parafrasare.** I prompt sono stati cesellati per evitare ambiguità.
4. **Dopo ogni risposta di Claude Code:** `git status` + `git diff` per vedere cosa ha toccato. Se modifica file fuori dal suo scope, fermalo.
5. **Se Claude Code dice "GAP rilevato":** non insistere. Rileggi la sezione BP citata.
6. **Se Claude Code allucina:** chiudi sessione, riapri, rilancia con "Leggi CLAUDE.md. Hai inventato X. Mostra dove la BP la definisce o dichiara GAP."
7. **Mai saltare le checklist umane.**
8. **I pattern del template shadcn-admin sono la guida.** Se Claude Code propone un design che rompe la coerenza visiva del template, rispondi "REI-11 — mantieni i pattern del template."
9. **Commit & push alla fine di ogni Fase.** Mai accumulare.
10. **Tag dopo ogni Fase.** Rende triviale il rollback.

---

## APPENDICE B — MAPPATURA COMPLETA BP → FASI (v4.0)

| Sezione Blueprint | Contenuto | Fase di implementazione |
|---|---|---|
| §00 Executive Summary | Principi, parametri, feature differite v1.1 | Tutte (riferimento) |
| §01.1 Stack Backend | Librerie + versioni (+ edge-tts, pydantic-settings, Jinja2, mutagen — OPT v3.0) | FASE 0 (pyproject.toml) |
| §01.2 Stack Frontend | React/shadcn/Tailwind/Zustand — **implementato su template shadcn-admin** | FASE 6 (sviluppo locale) |
| §01.3 Infrastruttura | Docker, Nginx, VPS, SSL | FASE 0, FASE 7 |
| §01.4 Decisioni D-01..D-20 | Vincoli architetturali | Tutte (REI in CLAUDE.md) |
| §02 Infrastruttura | Compose, pool, dependencies, main | FASE 0 |
| §03 Schema DB | Tabelle + indici + ruoli + **audio_tracks** | FASE 1 |
| §04 Contratti Pydantic | 4 file: core, requests, knowledge, pipeline | FASE 1 |
| §05 Agenti LangGraph | Research + Content (**2 nodi**), state TypedDict, checkpointing | FASE 3 |
| §06 Knowledge Base | Ingestion, chunking ibrido (inline), embedding, RAG | FASE 2 |
| §06.2 Livello 2 + StylePatternExtractor | certification_service (**no certificati PDF**) | FASE 7 |
| §06B PacingEngine | Distribuzione **30s/slide**, no DIAGRAM v1.0 | FASE 3 |
| §07 Production Builder | SlideBuilder, ImageService (svg inline), PDF (Jinja2), **AudioService edge-tts** | FASE 4 |
| §08 Auth | JWT custom + bcrypt, **JWT_SECRET singolo** | FASE 1 |
| §09 Orchestrazione | wait_for, **semaforo in generation_service.py**, shutdown, recovery | FASE 5 |
| §10 API REST + WebSocket | Endpoint + WS + **download audio** | FASE 5 + FASE 6 |
| §12 Deploy + Cleanup | Nginx, backup, cleanup_old_images | FASE 7 |
| §13 COURSE_CATALOG | 6 tipi corso, HACCP regionale | FASE 2 |
| §14 Testing | Strategia test | FASE 7 |
| §15-§16 Checklist + Piano Sprint | Riferimento trasversale | Tutte |

---

**Fine del NEXUS EDUVAULT — SUPREME MASTER EXECUTION PLAN & PROMPT BOOK v4.0.**

*Questo documento è autosufficiente. Integra tutte le correzioni dei FIX-1 a FIX-8 dell'audit tecnico, il vincolo metrico 30s/slide (GAP-1), la narrazione audio TTS (GAP-3) dell'audit commerciale, le ottimizzazioni OPT-1 (edge-tts), OPT-2 (pydantic-settings), OPT-3 (Jinja2 PDF), OPT-4 (mutagen) dell'audit BaaS & Open-Source, e il frontend swap SWAP-1 a SWAP-5 (da Base 44 a shadcn-admin con branding C.F.P. Montessori). Da tenere aperto in VS Code accanto a Claude Code per tutta la durata dello sviluppo (stimata: 6-9 settimane di lavoro umano in solitaria + agente).*
