# Handoff to PHASE 6 — Nexus EduVault

**Data handoff:** 2026-05-24
**Sessione che consegna:** Claude Opus 4.7 (VS Code extension)
**Fine ciclo:** Step A + B + C + FASE 0 + FASE 1 + FASE 2 + FASE 3 + FASE 4 + FASE 5 tutte chiuse ✅ (FASE 5 🟡 parziale su steps live, vedi sezione 4)
**Da iniziare:** FASE 6 — Frontend shadcn-admin + Branding (Sprint 5B)

> **Per la sessione che riceve.** Questo documento è il briefing operativo che la blueprint, il Master Plan, il Tracker e l'HANDOFF_PHASE2 da soli **non** ti possono dare. Contiene lo stato post-FASE-5, i gotcha che si sono accumulati nelle FASI 2-5, l'inventario reale dei file backend, la mappa skill/MCP per FASE 6 (la più frontend-pesante del progetto), e le risorse mancanti per chiudere le pendenze. Leggilo subito dopo CLAUDE.md e prima di scrivere qualsiasi codice. L'hook SessionStart in `.claude/settings.json` te lo elenca tra i file obbligatori.

---

## 1. Stato attuale del repo (snapshot 2026-05-24)

### Branch e tag (tutti pushati su origin)

| Branch | Tag | Note |
|---|---|---|
| `feat/phase0-infrastructure` | `v0.1.0-phase0` | docker-compose + FastAPI skeleton + /health |
| `feat/phase1-db-auth` | `v0.2.0-phase1` | schema SQL + JWT auth + seed |
| `feat/phase2-kb-rag` | `v0.3.0-phase2` | ingestion, chunking, RAG, COURSE_CATALOG |
| `feat/phase3-agents` | `v0.4.0-phase3` | LangGraph 2-node + PacingEngine + Research+Content agents |
| `feat/phase4-production-builder` | `v0.5.0-phase4` | SlideBuilder + PdfBuilder + ImageService + AudioService + ProductionBuilder + synth E2E |
| `feat/phase5-orchestration-api` | `v0.6.0-phase5` | generation_service + /api/courses + WebSocket + /api/admin + polling-fallback doc |

**Branch corrente:** `feat/phase5-orchestration-api` (working tree clean).
**Modello multi-branch:** ogni FASE = branch + tag, lineari (phase5 contiene phase4 contiene phase3...), fast-forward, zero merge conflict atteso. Quando vorrai mergere in `main`, basta 1 PR finale o uno per fase a tua scelta.

### Cosa esiste oggi (backend completo)

```
app/
├── api/
│   ├── routes/
│   │   ├── admin.py            (FASE 5.4 — 4 endpoint admin-only)
│   │   ├── auth.py             (FASE 1.3)
│   │   ├── courses.py          (FASE 5.2 — 6 endpoint + download audio)
│   │   ├── health.py           (FASE 0.5)
│   │   └── regulations.py      (FASE 2.6)
│   ├── dependencies.py         (get_current_user, require_role, limiter shared)
│   └── websocket.py            (FASE 5.3 — /ws/jobs/{id})
├── agents/
│   ├── content_agent.py        (FASE 3.4 — LLM + JSON + circuit breaker INLINE)
│   ├── pipeline.py             (FASE 3.1 — LangGraph 2 nodi @asynccontextmanager)
│   ├── prompts.py              (FASE 3.4 — Discente/Formatore)
│   └── research_agent.py       (FASE 3.3 — RAG + distribute chunks)
├── builders/
│   ├── pdf_builder.py          (FASE 4.4 — Jinja2 + WeasyPrint, lazy import)
│   ├── pptx_validator.py       (FASE 4.5 — count check)
│   ├── production_builder.py   (FASE 4.5 — orchestratore con guards)
│   └── slide_builder.py        (FASE 4.2 — image fallback testuale)
├── db/
│   ├── connection.py           (FASE 0.4 — pool asyncpg)
│   └── migrations/
│       ├── 001_initial.sql     (10 tabelle)
│       ├── setup_roles.sql     (nexus_app + REVOKE audit_log)
│       └── setup_langgraph_grants.sql  (post-startup — non ancora eseguito #R11)
├── models/
│   ├── core.py                 (enum SlideType, SlideDensity, TargetType, ChunkType)
│   ├── knowledge.py            (NormativeChunk, StylePattern)
│   ├── pipeline.py             (SlideContent, ModuleSpec, PacingPlan, ImageStrategy, GenerationReport)
│   └── requests.py             (CourseRequest, CourseResponse)
├── services/
│   ├── audio_service.py        (FASE 4.6 — edge-tts, NO OpenAI)
│   ├── auth_service.py         (FASE 1.3 — JWT + bcrypt)
│   ├── certification_service.py (FASE 5.2 MINIMUM — sostituito in FASE 7.1)
│   ├── dependencies.py         (get_pool, get_voyage_client, get_shutdown_event)
│   ├── generation_service.py   (FASE 5.1 — _job_semaphore, run_pipeline)
│   ├── image_service.py        (FASE 4.3 — sanitize_svg INLINE, Semaphore(5))
│   ├── ingestion_service.py    (FASE 2.1-2.3 — parse+chunk+classify+embed)
│   ├── knowledge_repo.py       (FASE 2.5 — RAG hybrid filter)
│   └── pacing_engine.py        (FASE 3.2 — 30s/slide, FIX-8 5 tipi)
├── templates/
│   └── dispensa.html           (FASE 4.4 + audit FASE 4 — TOC + header brand)
├── config.py                   (pydantic-settings v2, OPT-2)
└── main.py                     (startup pool + voyage + recovery; shutdown event)

scripts/
├── create_pptx_template.py     (stub — usato per generare template prima della calibrazione umana)
├── inspect_pptx_template.py    (FASE 4.1 — CLI report + JSON dump)
├── seed.py                     (FASE 1.4 — admin + default brand preset)
└── synth_build_test.py         (FASE 4.7 — E2E 30 slide mock, ESEGUITO LIVE IN DOCKER)

tests/
├── unit/                       (test_models, test_chunking, test_pacing_engine,
│                                test_catalog, test_classification_embedding,
│                                test_graph_compile, test_audio_service, test_audio_fallback)
└── integration/                (test_health, test_auth, test_seed, test_ingestion,
                                 test_knowledge_repo, test_regulations, test_research_agent,
                                 test_content_agent, test_pipeline_e2e_no_build,
                                 test_slide_builder, test_image_service, test_pdf_builder,
                                 test_production_builder, test_generation_service,
                                 test_courses, test_websocket, test_admin)

docs/
├── CLIENT_INTAKE_QUESTIONNAIRE.md
├── CLIENT_INTAKE_TRACKING.md
├── HANDOFF_PHASE2.md           (storico)
├── HANDOFF_PHASE6.md           (questo file)
├── POLLING_FALLBACK.md         (FASE 5 audit fix item 8)
├── SKILLS_PER_PHASE_CHEATSHEET.md
├── SKILLS_PLAYBOOK.md
├── TOOLBELT.md
└── VERIFICATION_DEBT.md        (58 discrepanze D1-D58, 13 risorse mancanti, ~250 test mock)
```

### Test count attuale

- **315 pytest passed** + 1 deselected (live test FASE 3.5)
- **mypy --strict** verdi su 43 source files
- **ruff** verdi project-wide
- **1 synth E2E** verde in Docker (FASE 4.7)
- **1 smoke E2E parziale** live in Docker (FASE 5.5 — steps 1-6 verdi, 7-9 BLOCKED-UPSTREAM)
- **2 audit checklist** (FASE 4 e FASE 5) completati con fix applicati

### Stato runtime locale (NON in git, da rebuildare in nuova sessione se serve)

- `.env` reale in root (gitignored). Contiene `ANTHROPIC_API_KEY` **non valida** (401 invalid x-api-key live confermato), `VOYAGE_API_KEY` non testata, `JWT_SECRET` 128 hex, `POSTGRES_*_PASSWORD` 64 hex, `BRAVE_SEARCH_API_KEY` (non testata)
- Container Docker probabilmente DOWN (li avevamo abbattuti con `docker compose down -v` in FASE 5.5). Verificare con `docker compose ps`. Per FASE 6 (frontend) il backend deve essere up: `docker compose up -d` + applicare migrations + setup_roles + seed (sequenza in sezione 3 di questo doc).
- Codegraph index probabilmente aggiornato all'ultimo reindex post-FASE 5 (verificato in FASE 5.4)

---

## 2. I 7 gotcha critici accumulati (NON sbagliare di nuovo)

> I primi 5 sono ereditati da HANDOFF_PHASE2. I 6-7 sono nuovi delle FASI 4-5.

### Gotcha #1 — `os.environ[]` è VIETATO ovunque in `app/`
Vedi HANDOFF_PHASE2.md sezione 2. Pattern: `from app.config import settings` + `settings.<campo>`. Se aggiungi un campo, dichiaralo nel `Settings` di `app/config.py` prima di usarlo.

### Gotcha #2 — Password `.env` solo hex (no base64)
Vedi HANDOFF_PHASE2.md. `openssl rand -hex N | tr -d '\r\n'` su Windows con CRLF.

### Gotcha #3 — Librerie senza `py.typed` → mypy override
Override già esistente in `pyproject.toml`: `asyncpg, voyageai, pptx, cairosvg, weasyprint, psutil`. Se aggiungi un'altra lib senza stubs, aggiungila lì.

### Gotcha #4 — Container Docker NON vede modifiche al codice senza rebuild
`docker compose up -d` ricicla l'immagine. Dopo qualunque modifica a `app/*.py` o nuovo file in `scripts/`/`tests/`, per testare LIVE serve `docker compose build backend && docker compose up -d backend`. **D45 lo conferma in FASE 4.7**: il primo run di `synth_build_test` falliva perché l'immagine era pre-FASE-4. I test pytest **locali** vanno comunque, perché girano contro mock.

### Gotcha #5 — `print()` vietato, usa `structlog`
Vedi HANDOFF_PHASE2.md. `configure_logging()` chiamato in `main.startup()`.

### Gotcha #6 (NUOVO FASE 4) — WeasyPrint richiede GTK runtime sul host
**#R12 documentata.** Su Windows l'import top-level di `weasyprint` fallisce con `OSError: cannot load library 'libgobject-2.0-0'`. Soluzione attuale:
- `pdf_builder.py` fa lazy import (`import weasyprint` dentro `build()`, non al top-level)
- I test mockano `sys.modules['weasyprint'] = MagicMock()` prima di importare pdf_builder
- Per validare PDF binario reale → eseguire in Docker (Dockerfile FASE 0 ha `libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev`)
- Stesso pattern ereditato da `production_builder.py` e `generation_service.py` che lo importano transitivamente

### Gotcha #7 (NUOVO FASE 4-5) — `python-multipart` non era in deps
**D44 documentata.** FastAPI 0.111+ non lo include più transitivamente; serve esplicito quando endpoint usano `UploadFile + Form` (es. `regulations.py` upload). Già aggiunto a `pyproject.toml` post-FASE-4. **Se aggiungi nuovi upload endpoint, è già OK.**

### Gotcha #8 (potenziale FASE 6) — CORS
`app/main.py` ha attualmente `CORSMiddleware` con un origin (vedi `settings.frontend_url`). Per il dev del frontend con Vite/Next su `http://localhost:5173` o `:3000`, dovrai assicurarti che `FRONTEND_URL` in `.env` matchi. **REI-10**: mai wildcard `*`.

---

## 3. Cosa fare PRIMA del primo prompt di FASE 6

### Bloccante #1 — Niente (in teoria)
FASE 6 è frontend puro su `frontend/`. Non tocca backend. Il backend può restare DOWN finché non serve l'integrazione vera (prompt 6.4 OpenAPI types, 6.5 client REST/WS).

### Soft — Risorse residue per chiudere il debt
Vedi sezione 5 di questo doc. Per chiudere ✅ FASE 5 (oggi 🟡), servono #R1+#R3+#R4 — non bloccanti per iniziare FASE 6.

### Soft — Rebuild Docker quando serve il backend live
Se il prompt 6.4 (OpenAPI → TypeScript types) richiede backend up:
```bash
docker compose up -d              # postgres + backend
# se nexus_app role non esiste (volume vergine):
docker compose stop backend
docker exec -i eduvault-postgres-1 psql -U nexus_admin -d nexus < app/db/migrations/001_initial.sql
APP_PASS=$(grep "^POSTGRES_APP_PASSWORD=" .env | cut -d= -f2- | tr -d '\r\n')
sed "s/CHANGE_ME_APP_64_CHARS/$APP_PASS/" app/db/migrations/setup_roles.sql | docker exec -i eduvault-postgres-1 psql -U nexus_admin -d nexus
docker compose up -d backend
docker compose exec -T backend python scripts/seed.py
# /health → 200, /docs → swagger UI
```

---

## 4. Stato FASE 5 — perché è 🟡 (non ✅)

Nello smoke E2E FASE 5.5 abbiamo eseguito LIVE in Docker:
- ✅ Steps 1-6: reset → migrations → setup_roles → seed → login admin → /me. Tutto verde.
- ❌ Steps 7-9: ingest dm388 → POST /api/courses → WebSocket progress. **BLOCKED-UPSTREAM:**
  - `ANTHROPIC_API_KEY` nel `.env` ritorna `401 invalid x-api-key` (6 retry tenacity, classify_chunk fallisce)
  - `VOYAGE_API_KEY` non testata ma probabilmente stesso problema
  - `storage/pdfs/dm388_03.pdf` è solo `dm388_synthetic.pdf` 4.9KB (#R1)

**Surrogate verde:** abbiamo rieseguito `synth_build_test` in Docker (30 PPTX + PDF 25KB + 30 MP3 reali + manifest) e inserito 1 corso completed manualmente in DB → testato REAL i 4 download REST (PPTX 89KB, PDF 25KB, ZIP 69KB, audio ZIP 1.4MB con 31 file) + tutti i 4 admin endpoint REST.

**Audit checklist FASE 5 (12 item):** 11 ✅ + 1 FIX (item 8 polling fallback documentato in `docs/POLLING_FALLBACK.md`). Item 11 audit_log append-only verificato LIVE in Docker (3/3 forbidden ops bloccate come `nexus_app`).

**Per chiudere ✅ FASE 5** serve solo che l'utente fornisca le 3 risorse #R1+#R3+#R4 e ri-eseguire steps 7-9.

---

## 5. Skill/MCP per i 10 prompt FASE 6

Riferimento autoritativo: `docs/SKILLS_PER_PHASE_CHEATSHEET.md` sezione FASE 6 (righe ~225-310). **FASE 6 è la fase più skill-pesante del progetto** — la regola design top-down (SKILLS_PLAYBOOK §7) è obbligatoria.

| Prompt | Tipo task | Skill da pre-pendere |
|---|---|---|
| **6.1** Clone template shadcn-admin | git clone | nessuna |
| **6.2** Inventario componenti | find + markdown | nessuna |
| **6.3** Branding C.F.P. Montessori | CSS vars + Tailwind config | `ckm:design-system` + `ckm:brand` (riga in CHEATSHEET §6.3) |
| **6.4** Tipi TS da OpenAPI | npx openapi-typescript | nessuna |
| **6.5** API Client + WebSocket Client | fetch tipizzato | nessuna |
| **6.6** Pagina Login | prima vera pagina UI | **WORKFLOW TOP-DOWN** (riga in CHEATSHEET §6.6: frontend-design → ckm:ui-styling → impeccable self-audit → shadcn MCP) |
| **6.7** Dashboard + Lista Corsi | DataTable + stats cards | stesso 6.6 + enfasi `impeccable` (badge stato) |
| **6.8** Wizard 6-step | pagina più complessa del frontend | stesso 6.6 + `ckm:design-system` (progress indicator) |
| **6.9** Progress + Dettaglio + Normative + Admin (4 pagine) | volume alto | stesso 6.6 + enfasi `impeccable` (4 audit) |
| **6.10** Navigazione, routing, build | router + build verification | `cdt-chrome-devtools` + MCP `chrome-devtools` |

**MCP critici per FASE 6:**
- **shadcn MCP** (`mcp__shadcn__*`) — auto-attivo quando `frontend/components.json` esiste. Per API esatte dei componenti.
- **chrome-devtools MCP** (`mcp__chrome-devtools__*`) — per 6.10 (verifica visuale post-build, Core Web Vitals)
- **playwright MCP** — per E2E browser test in FASE 7
- **postgres MCP restricted** — meno utile in FASE 6 ma resta a disposizione

**REI-1 + REI-11 obbligatorio**: frontend = template shadcn-admin clonato (non Base44). Pixel-perfect quality. Solo componenti shadcn/ui esistenti. Spacing uniforme (gap-4, p-6), tipografia gerarchica (text-2xl titoli, text-sm caption).

---

## 6. Sequenza prompt attesi per FASE 6

Dal Master Plan §FASE 6 (righe ~1500-1700). 10 prompt:

| # | Prompt | Output atteso |
|---|---|---|
| 6.1 | Clone shadcn-admin | `frontend/` con template clonato e pulito |
| 6.2 | Inventario | `docs/FRONTEND_INVENTORY.md` |
| 6.3 | Branding | `frontend/src/index.css` + `tailwind.config.ts` modificati + logo |
| 6.4 | Tipi TypeScript | `frontend/src/types/api.ts` generato da OpenAPI |
| 6.5 | API + WS Client | `frontend/src/lib/api.ts` + `frontend/src/lib/ws.ts` |
| 6.6 | Login page | `frontend/src/pages/Login.tsx` |
| 6.7 | Dashboard + Lista Corsi | `frontend/src/pages/Dashboard.tsx` + `Courses.tsx` |
| 6.8 | Wizard 6-step | `frontend/src/pages/CreateCourse.tsx` |
| 6.9 | Progress + Dettaglio + Normative + Admin | 4 file `frontend/src/pages/*.tsx` |
| 6.10 | Routing + build | router config + verifica E2E con chrome-devtools |

Fine FASE 6 → branch `feat/phase6-frontend` + tag `v0.7.0-phase6`.

---

## 7. Risorse residue (`docs/VERIFICATION_DEBT.md` §3)

| ID | Cosa serve | Bloccante per | Stato |
|---|---|---|---|
| **#R1** | PDF DM 388/2003 reale | E2E ingest live | ⏳ utente deve fornire |
| **#R2** | Postgres pgvector live (Docker) | live integration tests | ✅ disponibile (rebuild quando serve) |
| **#R3** | ANTHROPIC_API_KEY valida | classify_chunk + content_agent live | ❌ chiave attuale → 401 |
| **#R4** | VOYAGE_API_KEY valida | embed + search live | ⏳ non testata, probabilmente 401 |
| **#R5** | EXPLAIN ANALYZE su HNSW | item 5 FASE 2 checklist | dipende #R1+#R3+#R4 |
| **#R6** | BRAVE_SEARCH_API_KEY valida | image_service download reali | non testata |
| **#R7** | Logo + palette + font C.F.P. Montessori | FASE 6.3 branding | ⏳ utente deve fornire |
| **#R8** | Template PPTX brandizzato (LAVORO UMANO 4-6h) | FASE 4 validazione layout BP §07.3 | ⏳ utente |
| **#R9** | Accordo Stato-Regioni 2011 + altri PDF normativi | validazione COURSE_CATALOG | ⏳ utente |
| **~~#R10~~** | ~~FASE 4 deps locali~~ | — | ✅ CHIUSO |
| **#R11** | Eseguire `setup_langgraph_grants.sql` post primo startup live | item 15 checklist FASE 3 | pending utente |
| **#R12** | GTK runtime locale per WeasyPrint | PDF binario reale su host | ✅ workaround Docker |
| **#R13** | Microsoft Edge TTS endpoint | MP3 reali via edge-tts | ✅ disponibile con internet |

**Per FASE 6 (frontend) servono soprattutto #R7 (branding) prima del prompt 6.3.** Le altre risorse sono per ri-verifica live di FASI precedenti.

---

## 8. Smoke test eseguiti (audit trail)

| Smoke | Quando | Esito | Risorse usate |
|---|---|---|---|
| FASE 1.5 manuale | 2026-05-23 | ✅ verde | DB live + admin login + audit_log REVOKE |
| FASE 3.5 mocked | 2026-05-23 | ✅ 154/154 | mock 6 dipendenze |
| FASE 3.5 live skel | mai eseguito | skipped | #R1+#R2+#R3+#R4 |
| FASE 4.7 synth_build_test in Docker | 2026-05-23 | ✅ 30 PPTX + PDF + 30 MP3 reali | edge-tts reale + GTK Docker |
| Audit FASE 4 + ri-run synth con TOC/header | 2026-05-24 | ✅ PDF 25KB con TOC funzionante | GTK Docker |
| FASE 5.5 smoke E2E live | 2026-05-24 | 🟡 1-6 verdi, 7-9 blocked, surrogate verde | DB live + 4 download REST REAL + 4 admin REST REAL |
| Audit FASE 5 + audit_log append-only live | 2026-05-24 | ✅ 11/12 + 1 FIX polling-doc | DB live |

**Tutti i risultati granulari documentati in `docs/VERIFICATION_DEBT.md`** (D1-D58, ~250 test count by category).

---

## 9. Decisioni architetturali permanenti (rinfresco)

REI inviolabili in [CLAUDE.md](../CLAUDE.md):
- **REI-1** shadcn-admin (no Base44). **REI-11** UI pixel-perfect.
- **REI-3** Semaphore(1) per python-pptx. **Vive in `generation_service.py`** (FIX-7 v2.0, verificato in FASE 5.1 + meta-test).
- **REI-4** no Supabase, no cloud auth.
- **REI-5** no invenzioni fuori blueprint. **REI-16** prompt vs BP → segnala discrepanza + applica prompt.
- **REI-7** codice EN, risposte umane IT.
- **REI-10** sicurezza by default: no CORS wildcard, rate limit, audit log append-only, sanitize SVG, Pillow.verify, JWT is_active check.
- **REI-12** Tracker aggiornato prima del commit. **REI-17** VERIFICATION_DEBT aggiornato prima del Tracker.
- **REI-13** dominio non deciso (FASE 7).
- **REI-14** prima di task non triviali, consulta SKILLS_PLAYBOOK/CHEATSHEET.
- **REI-15** codegraph reindex automatico ai 4 trigger.
- **OPT-1** edge-tts no OpenAI. **OPT-2** pydantic-settings. **OPT-3** Jinja2 per PDF.

Vincoli pipeline v2.0:
- LangGraph 2 nodi ESATTI (research + content). Production Builder POST-pipeline.
- Circuit breaker INLINE in content_agent (FIX-3, meta-test guard).

---

## 10. Riferimento agli artefatti chiave (link clickabili VS Code)

- Costituzione: [CLAUDE.md](../CLAUDE.md)
- Blueprint v7.0 FINAL: [NEXUS_EDUVAULT_Blueprint_v7.0_FINAL.md](../NEXUS_EDUVAULT_Blueprint_v7.0_FINAL.md)
- Master Plan v4.0: [NEXUS_EDUVAULT_Supreme_Master_Execution_Plan_v4_0.md](../NEXUS_EDUVAULT_Supreme_Master_Execution_Plan_v4_0.md)
- Tracker: [NEXUS_EDUVAULT_Project_Status_Tracker.md](../NEXUS_EDUVAULT_Project_Status_Tracker.md)
- Verification Debt: [VERIFICATION_DEBT.md](VERIFICATION_DEBT.md)
- Skill playbook: [SKILLS_PLAYBOOK.md](SKILLS_PLAYBOOK.md)
- Skill per prompt: [SKILLS_PER_PHASE_CHEATSHEET.md](SKILLS_PER_PHASE_CHEATSHEET.md)
- Polling fallback (NUOVO FASE 5): [POLLING_FALLBACK.md](POLLING_FALLBACK.md)
- Handoff PHASE 2 (storico): [HANDOFF_PHASE2.md](HANDOFF_PHASE2.md)
- Toolbelt installato: [INSTALLED_TOOLBELT.md](../INSTALLED_TOOLBELT.md)

---

**Fine del documento di handoff. La nuova sessione che legge questo è ora al corrente di tutto ciò che le 6 sessioni precedenti (Step A-C + FASI 0-5) hanno imparato che non era già nei file standard.**
