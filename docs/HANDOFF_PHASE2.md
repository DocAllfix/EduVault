# Handoff to PHASE 2 — Nexus EduVault

**Data handoff:** 2026-05-23
**Sessione che consegna:** Claude Opus 4.7 (VS Code extension)
**Fine ciclo:** Step A + B + C + FASE 0 + FASE 1 tutte chiuse ✅
**Da iniziare:** FASE 2 — Knowledge Base + COURSE_CATALOG + RAG

> **Per la sessione che riceve.** Questo documento è il briefing operativo che la blueprint, il Master Plan e il Tracker da soli **non** ti possono dare. Contiene le decisioni applicate finora, i 5 gotcha ricorrenti, lo stato runtime del repo e la mappa skill per i 6 prompt di FASE 2. Leggilo subito dopo CLAUDE.md e prima di scrivere qualsiasi codice. L'hook SessionStart te lo elenca esplicitamente.

---

## 1. Stato attuale del repo (snapshot 2026-05-23)

### Cosa è verde e committato

- Branch: `feat/phase0-infrastructure` su origin (tag `v0.1.0-phase0`)
- Storia: 4 commit (`d552d04` step-A → `f88cd79` step-B → `f3e39df` step-C → `3fde134` phase-0)
- FASE 1 verificata **ma non ancora committata** (vedi sezione 3)

### Cosa è verde non-committato (FASE 1)

| File | Status |
|---|---|
| `app/db/migrations/001_initial.sql` | 10 tabelle BP §03 + GAP-3 (audio_tracks, audio_manifest_path), applicato live OK |
| `app/db/migrations/setup_roles.sql` | nexus_app + REVOKE su audit_log verificato (3/3 forbidden ops bloccate) |
| `app/models/{core,requests,knowledge,pipeline}.py` | 4 file BP §04 + outputs whitelist con 'audio' (GAP-3) |
| `app/services/auth_service.py` | JWT singolo + bcrypt + decode |
| `app/api/dependencies.py` | get_current_user (revoca implicita) + require_role + **limiter shared instance** |
| `app/api/routes/auth.py` | /login (rate-limited 10/min) + /refresh + /users/me |
| `app/services/dependencies.py` | + alias `VoyageClient = Any` aggiunto per mypy |
| `app/main.py` | Limiter importato da api.dependencies; auth router registrato |
| `app/services/generation_service.py` | **stub** (REI-15 — sarà sostituito in FASE 5) |
| `scripts/seed.py` | seed(pool) factored per testability; idempotente verificato |
| `tests/integration/test_health.py` | 4 test ✅ |
| `tests/integration/test_auth.py` | 15 test ✅ |
| `tests/integration/test_seed.py` | 6 test ✅ |
| `tests/unit/test_models.py` | 19 test ✅ |
| `pyproject.toml` | + `uvicorn[standard]`, `pyjwt`, mypy overrides per asyncpg/voyageai |
| `Dockerfile` | pin `python:3.12-slim-bookworm` + COPY app/ pre pip install |
| `docker-compose.yml` | profili: `core` (backend+postgres) sempre on, `full` (frontend+nginx) opt-in |
| `nginx.conf` | reverse proxy stub (riusato in FASE 6/7) |
| `.env.example` | aggiornato a BP §02.6 (DATABASE_URL composto, POSTGRES_ADMIN_PASSWORD/APP_PASSWORD) |
| `CLAUDE.md` | + REI-14 (PLAYBOOK), REI-15 (codegraph auto-reindex) |
| `.claude/settings.json` | hook SessionStart elenca i file da leggere (incl. questo) |
| `.claude/skills/` | 21 skill (impeccable, ckm:*, karpathy, frontend-design, 6 langchain/langgraph, 6 cdt-*) |
| `.mcp.json` | 6 MCP server (github, shadcn, playwright, postgres restricted, codegraph, chrome-devtools) |
| `docs/SKILLS_PLAYBOOK.md` + `docs/SKILLS_PER_PHASE_CHEATSHEET.md` | mappa skill per ogni prompt |
| `docs/TOOLBELT.md` + `INSTALLED_TOOLBELT.md` | stato installato vs raccomandazioni |
| `NEXUS_EDUVAULT_Project_Status_Tracker.md` | tutte le righe FASE 0+1 → ✅ con note |

### Stato runtime locale (NON in git)

- `.env` reale presente in root (gitignored). Password **hex** (non base64 — vedi gotcha #2). Lunghezze: JWT 128, postgres 64, bootstrap 32.
- Container Docker **up**: `eduvault-postgres-1` healthy, `eduvault-backend-1` up
- DB postgres `nexus` ha: 10 tabelle, 1 admin user (`admin@nexus-eduvault.local`, role=admin, is_active=true), 1 default brand preset, 1 riga in audit_log (residuo dello smoke test 1.5)
- Ruolo `nexus_app` creato in DB con password reale (sed-substituted al runtime, NON salvata nel .sql)
- Codegraph index aggiornato: 115 file, 1415 nodi (corrente al 1.5)

---

## 2. I 5 gotcha critici (NON sbagliare di nuovo)

### Gotcha #1 — `os.environ[]` è VIETATO ovunque in `app/`
BP è scritta con `os.environ["..."]` ovunque (es. §02.5 voyage api key, §02.7 seed). **Non copiare letterale**: REI-14/OPT-2 impone `from app.config import settings` + `settings.<campo>`. Il `Settings` ha già: `database_url`, `database_admin_url`, `anthropic_api_key`, `voyage_api_key`, `brave_search_api_key`, `jwt_secret`, `jwt_algorithm`, `jwt_expiry_minutes`, `jwt_refresh_expiry_days`, `frontend_url`, `pipeline_timeout`, `llm_request_timeout`, `max_concurrent_jobs`, `tts_voice`, `organization_name`, `admin_bootstrap_email`, `admin_bootstrap_password`. **Se ti serve una variabile non listata, AGGIUNGILA al Settings PRIMA di usarla.**

### Gotcha #2 — Password `.env` SOLO hex (no `openssl rand -base64`)
La prima generazione (Step 0.5) usava `openssl rand -base64 32` che produce stringhe con `=` di padding + occasionale newline interno. Su Windows con CRLF questo spacca `docker compose` con `unexpected character "@" in variable name`. **Regola:** sempre `openssl rand -hex N | tr -d '\r\n'`. Tutto in `.env` ora è hex.

### Gotcha #3 — voyageai / asyncpg non hanno `py.typed`
Mypy --strict si lamenta di `voyageai.AsyncClient` e `asyncpg.Pool` come "not exported / not typed". Pattern già applicato in `services/dependencies.py`: `VoyageClient = Any` come alias. `[[tool.mypy.overrides]]` nel pyproject ha già `ignore_missing_imports = true` per entrambi. **Se aggiungi un'altra lib senza `py.typed`, aggiungila lì.**

### Gotcha #4 — Il container Docker non vede modifiche al codice senza rebuild
`docker compose up -d` ricicla l'immagine. Dopo ogni modifica a `app/*.py` per testare LIVE serve `docker compose build backend && docker compose up -d backend`. I test pytest **invece** girano in locale contro mock — sempre OK.

### Gotcha #5 — `print()` è vietato (REI-7)
La BP usa `print("✓ Admin creato")` in seed.py. Sostituire SEMPRE con `structlog.get_logger().info(...)`. `configure_logging()` è già in `app/config.py` e viene chiamato da `main.startup()`.

---

## 3. Cosa fare PRIMA del primo prompt di FASE 2

### Bloccante #1 — Commit FASE 1
La FASE 1 è verificata ma NON committata. Sequenza (chiedimi se vuoi che li lanci io):
```
git checkout -b feat/phase1-db-auth
git add .
git commit -m "feat(phase1): schema SQL + audio_tracks, Pydantic models (4 files), JWT auth, seed"
git tag v0.2.0-phase1
git push origin feat/phase1-db-auth
```

### Bloccante #2 — Verificare PDF DM 388/2003 in `storage/pdfs/`
FASE 2 prompt 2.1 ha **prerequisito hard** documentato nel Master Plan riga 982:
> "PDF DM 388/2003 in `storage/pdfs/dm388_03.pdf`"

Al 2026-05-23, `storage/pdfs/` contiene solo `.gitkeep`. **Senza questo PDF il prompt 2.2 (chunking) non può testare nulla di reale.** Il PDF è citato nel `CLIENT_INTAKE_QUESTIONNAIRE.md` punto 2.3, marcato come "TEST chunking minimo (4 pagine, BP §16 punto 3)". Va scaricato da gazzettaufficiale.it o normattiva.it e committato (o aggiunto via `.gitignore` se preferisci tenerlo locale).

### Soft — Container Docker
Lo stato runtime locale ha postgres con schema applicato e seeded. **Se la nuova sessione vuole partire pulita** per FASE 2: `docker compose down -v && docker compose up -d` + riapplica migrations + setup_roles + seed (sequenza già rodata nello smoke test 1.5 — vedi messaggio "1.5" della sessione precedente). **Se invece vuoi continuare** sullo stato attuale, il DB è già pronto per testare ingestion in 2.1.

---

## 4. Skill/MCP per i 6 prompt FASE 2

Riferimento autoritativo: `docs/SKILLS_PER_PHASE_CHEATSHEET.md`. Estratto operativo per la FASE 2:

| Prompt | Tipo task | Skill da pre-pendere |
|---|---|---|
| **2.1** Parsing PDF | deterministico (pdfplumber) | nessuna |
| **2.2** Chunking ibrido | alto rischio over-engineering (regex pattern + soglie + fallback) | `karpathy-guidelines` → riga esatta in CHEATSHEET §2.2 |
| **2.3** Classify + embed | integrazione Anthropic + Voyage | nessuna |
| **2.4** COURSE_CATALOG | copia da BP §13 | nessuna |
| **2.5** KnowledgeRepository + RAG | JOIN regionale NULL-safe + top_k dinamico | `langchain-rag` → riga in CHEATSHEET §2.5 |
| **2.6** Endpoint /api/regulations | CRUD REST | nessuna |

**Postgres MCP** è disponibile in modalità restricted. È utile per verificare lo schema reale durante 2.1-2.5 prima di scrivere query SQL. Auto-attivo se la nuova sessione lo chiama esplicitamente — io NON l'ho usato in FASE 1 perché ho preferito `docker exec psql` (più veloce, stessa cosa).

**Codegraph MCP** è ora utile: ci sono 115 file Python indicizzati. Quando si toccherà `services/knowledge_repo.py` o `models/knowledge.py`, `codegraph_callers` ridurrà i Grep di esplorazione.

---

## 5. Sequenza prompt attesi per FASE 2

Dal Master Plan §FASE 2 (righe 977-1106). La nuova sessione li riceverà uno alla volta da te. Eccoli in ordine, ognuno con il pre-fix skill se serve (dal CHEATSHEET):

| # | Prompt | Output atteso |
|---|---|---|
| 2.1 | Parsing PDF (`parse_regulation_pdf`) | `app/services/ingestion_service.py` parziale + test su dm388 |
| 2.2 | Chunking ibrido (regex + LLM fallback) | stesso file esteso + test coverage ≥70% |
| 2.3 | Classify + embed (Anthropic + Voyage) | stesso file completo |
| 2.4 | COURSE_CATALOG | `config/catalog_config.py` con 6 corsi BP §13 |
| 2.5 | KnowledgeRepository + RAG | `app/services/knowledge_repo.py` |
| 2.6 | /api/regulations endpoints | `app/api/routes/regulations.py` + commit FASE 2 |

Fine FASE 2 → branch `feat/phase2-kb-rag` + tag `v0.3.0-phase2` (vedi Master Plan riga 1098).

---

## 6. Decisioni architetturali permanenti (non rinegoziabili)

Repetute qui per evidenza alla nuova sessione — sono già in CLAUDE.md ma vale la pena ribadirle perché FASE 2 le toccherà tutte:

- **REI-3** `Semaphore(1)` per python-pptx — non rilevante per FASE 2, ma il pattern si applica anche al **Voyage embed batch** (rate limit lato API, non concorrenza locale)
- **REI-13** dominio non deciso → nei test usare `nexus-eduvault.local` o placeholder, MAI `corsi8108.it`
- **REI-14** prima di ogni prompt non banale → leggi `SKILLS_PLAYBOOK.md`/`CHEATSHEET.md`
- **REI-15** dopo ogni grossa modifica a `app/` → reindex `npx @colbymchenry/codegraph index`
- **FIX-2** sanitize_svg INLINE (rilevante in FASE 4, non FASE 2)
- **FIX-6** `source_hash` NON esiste nel nostro schema (rimosso dalla BP) — se la BP §06 lo cita, ignora
- **STyled-components SCARTATO** (per FASE 6, ma utile sapere se la BP suggerisce altrimenti)
- **Base44 SUPERATO** da shadcn-admin (rilevante FASE 6)

---

## 7. Numeri di test correnti (smoke per la nuova sessione)

Quando la nuova sessione apre per la prima volta, eseguire:
```
python -m pytest -q
python -m mypy --strict app/ scripts/
python -m ruff check app/ scripts/ tests/
```
**Risultato atteso:** 44 test passed (4 health + 19 models + 15 auth + 6 seed), mypy "Success no issues in 42 source files", ruff "All checks passed". Se uno qualsiasi di questi 3 è rosso → **STOP e investigare** prima di iniziare FASE 2 (qualcosa è stato toccato non documentato).

---

## 8. Riferimento agli artefatti chiave (link clickabili VS Code)

- Costituzione: [CLAUDE.md](../CLAUDE.md)
- Master Plan FASE 2: [NEXUS_EDUVAULT_Supreme_Master_Execution_Plan_v4_0.md riga 977](../NEXUS_EDUVAULT_Supreme_Master_Execution_Plan_v4_0.md)
- Blueprint §06 (ingestion + RAG): [NEXUS_EDUVAULT_Blueprint_v7.0_FINAL.md riga 1505](../NEXUS_EDUVAULT_Blueprint_v7.0_FINAL.md)
- Blueprint §13 (COURSE_CATALOG): riga 3040
- Tracker (stato): [NEXUS_EDUVAULT_Project_Status_Tracker.md](../NEXUS_EDUVAULT_Project_Status_Tracker.md)
- Skill playbook: [SKILLS_PLAYBOOK.md](SKILLS_PLAYBOOK.md)
- Skill per prompt: [SKILLS_PER_PHASE_CHEATSHEET.md](SKILLS_PER_PHASE_CHEATSHEET.md)
- Toolbelt installato: [INSTALLED_TOOLBELT.md](../INSTALLED_TOOLBELT.md)

---

**Fine del documento di handoff. La nuova sessione che legge questo è ora al corrente di tutto ciò che la sessione precedente ha imparato che non era già nei file standard.**
