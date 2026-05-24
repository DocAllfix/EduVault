# NEXUS EDUVAULT — PROJECT STATUS TRACKER & MODEL STRATEGY

**Progetto:** Nexus EduVault v1.0  
**Cliente:** C.F.P. Montessori  
**Fornitore:** Axialoop di Di Lonardo Alessandro  
**Riferimento:** Execution Plan v4.0 + Blueprint v7.0  
**Ultimo aggiornamento:** 2026-05-24 (**Audit checklist FASE 5 COMPLETO** ✅ — 12 item verificati. 11 ✅ verdi + 1 ❌→✅ FIX (item 8: polling fallback 30s NON era documentato → creato `docs/POLLING_FALLBACK.md` con contratto WS+REST + pseudo-code frontend FASE 6.9 + rate limit + stati terminali). Item 11 audit_log append-only verificato LIVE in Docker (3/3 forbidden ops bloccate come nexus_app, INSERT/SELECT OK). Item 9 ZIP audio verificato LIVE nello smoke 5.5 (1.4MB / 31 file). FASE 5 backend completamente WIRED-UP, auditata e documentata. Per chiusura E2E live restano #R1+#R3+#R4 (PDF reale + Anthropic+Voyage keys valide). 315/315 verdi project-wide.)  

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
| B.1 | Analisi ambiente locale | **S** | Comandi shell + report tabellare | ✅ | 2026-05-23 | ENV_REPORT.md generato. Tutto conforme BP §1.1, solo psql client mancante (non bloccante). |
| B.2 | Ricerca MCP/Skills/Estensioni | **S** | Web search + filtro, no ragionamento architetturale | ✅ | 2026-05-23 | docs/TOOLBELT.md v1 → v2 (con frontend-design, langchain-skills, Impeccable, UI/UX Pro Max, shadcn skill, Vercel guidelines; styled-components scartato con motivo). |
| B.3 | Installazione selettiva | **S** | Esecuzione comandi uno per uno | ✅ | 2026-05-23 | **21 skill + 1 slash command + 6 MCP + 12 estensioni VS Code installati.** Skill: 7 design (impeccable + ckm:*) + karpathy-guidelines + frontend-design (Anthropic) + 6 langchain/langgraph + 6 chrome-devtools (cdt-*). Slash command: /code-review (Anthropic ufficiale). MCP: github, shadcn, playwright, postgres-restricted, codegraph, chrome-devtools. Plugin Anthropic ufficiali estratti manualmente dai loro repo sorgenti perché /plugin non funziona nell'estensione VS Code (bug noto #8569/#8590/#58556). Aggiunto REI-15 (auto-reindex codegraph). superpowers@obra rimandato a post-FASE 1. |

### STEP C — Questionario Cliente

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| C.1 | Stesura questionario | **S** | Template strutturato da spec | ✅ | 2026-05-23 | docs/CLIENT_INTAKE_QUESTIONNAIRE.md — 8 sezioni in italiano, ancorate a BP §00/§06/§13 (6 tipi corso + HACCP regionale Campania) + REI-13 (dominio TBD), 4 sezioni bloccanti go-live esplicitate. |
| C.2 | Tracking ricezione materiali | **S** | Tabella Markdown semplice | ✅ | 2026-05-23 | docs/CLIENT_INTAKE_TRACKING.md — 27 item allineati al questionario (1.1→8.3 + voce semantica "5 VPS"), 4 bloccanti go-live evidenziati, path convention da BP §14.1, stati ⏳/🔄/✅/❌/⚪. |

---

## FASI DI SVILUPPO

### FASE 0 — Infrastruttura (Sprint 0)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 0.1 | `pyproject.toml` | **S** | Copia tabella dipendenze da BP §1.1, meccanico | ✅ | 2026-05-23 | 22 runtime deps (BP §1.1 verbatim) + 4 OPT v3.0 (edge-tts/mutagen/pydantic-settings/Jinja2); openai assente. |
| 0.2 | `Dockerfile` | **S** | Copia da BP §02.1 con adattamento minimo | ✅ | 2026-05-23 | BP letterale + pin a bookworm (libgdk-pixbuf2.0-dev trixie-removed) + COPY app/ pre pip install (hatchling). |
| 0.3 | `docker-compose.yml` | **S** | Copia da BP §02.2, 4 servizi | ✅ | 2026-05-23 | 4 servizi BP §02.2 + profile "full" su frontend/nginx (PHASE 6+). postgres expose-only. |
| 0.4 | `main.py` + `config.py` + `dependencies.py` + `connection.py` | **S** | BP fornisce codice esatto, pydantic-settings è boilerplate | ✅ | 2026-05-23 | OPT-2 (Settings) ovunque, zero os.environ[]. Lazy import generation_service (FASE 5). |
| 0.5 | Endpoint `/health` | **S** | Endpoint banale, 20 righe | ✅ | 2026-05-23 | BP §10.1 via APIRouter, get_pool() centralizzato, fallback disk path host-friendly. 4 test integration verdi. |
| 0.6 | Verifica E2E Sprint 0 | **S** | Comandi docker + curl | ✅ | 2026-05-23 | docker compose build+up OK; /health → {"status":"ok","database":"connected","disk_free_gb":948.9} HTTP 200. Tag v0.1.0-phase0. |

**Stima costo FASE 0:** ~$2-4 (100% Sonnet)

---

### FASE 1 — Database, Auth, Modelli Pydantic (Sprint 1)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 1.1 | Schema SQL `001_initial.sql` | **S** | Copia da BP §03, SQL dichiarativo | ✅ | 2026-05-23 | BP §03 letterale + GAP-3 (audio_tracks dopo image_cache; courses.audio_manifest_path). 10 tabelle, HNSW, GIN. Applicato live: zero errori. |
| 1.2 | Modelli Pydantic (4 file) | **S** | Copia da BP §04, Pydantic boilerplate con validator | ✅ | 2026-05-23 | BP §04 letterale + outputs=audio whitelist + fix lookup enum nel body validator. 19 unit test verdi. |
| 1.3 | Servizio Auth (JWT + bcrypt) | **S** | BP §08 fornisce codice esatto, logica lineare | ✅ | 2026-05-23 | BP §08 + OPT-2 (settings) + karpathy-guidelines (assumptions A1-A14 dichiarate). pyjwt aggiunta. Limiter shared in api/dependencies. 15 integration test verdi (login, refresh, /me, type-check, is_active, no-enum). |
| 1.4 | Seed admin | **S** | Script semplice, idempotente | ✅ | 2026-05-23 | BP §02.7 + OPT-2 + structlog. Refactored seed(pool) per testabilità. 6 unit test (incl. idempotenza split admin/brand). |
| 1.5 | Smoke test FASE 1 | **S** | Comandi sequenziali di verifica | ✅ | 2026-05-23 | E2E live: down -v → up → migrations (10 tables) → setup_roles (nexus_app + REVOKE) → seed + idempotenza → login → /me (admin, is_active) → DELETE/UPDATE/TRUNCATE audit_log come nexus_app TUTTI permission_denied. .env rigenerato con hex (no padding =). codegraph reindex eseguito (115 file, 1415 nodi, REI-15). |

**Stima costo FASE 1:** ~$3-5 (100% Sonnet)

---

### FASE 2 — Knowledge Base + COURSE_CATALOG + RAG (Sprint 2)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 2.1 | Estrazione e Parsing PDF | **S** | pdfplumber wrapper semplice | ✅ | 2026-05-23 | BP §06.1.1 Stadio 1 letterale + accetta str/PathLike + FileNotFoundError esplicito. 5 integration test verdi (real PDF preferred, synthetic fixture fallback). 49/49 test totali, mypy/ruff verdi. Codegraph reindex eseguito (REI-15 trigger d). **NOTA:** PDF reale dm388_03.pdf ancora mancante in storage/pdfs/ — fixture sintetica reportlab in tests/fixtures/pdfs/dm388_synthetic.pdf (4 pagine, Art. 1/2/2-bis/Allegato I). 2.2 chunking richiederà il PDF reale per validare coverage regex su testo gazzettiero. |
| 2.2 | Chunking Ibrido | **O** | ⚠️ Logica custom complessa: regex normative italiane (ART_PATTERN, COMMA_PATTERN, ALLEGATO_PATTERN), coverage check, fallback, dedup. Il cuore differenziante del prodotto. Errori qui si propagano a cascata. | ✅ | 2026-05-23 | BP §06.1.1 Stadio 2 letterale inline in ingestion_service.py (no utils/ separato). 8 entità: ART_PATTERN (-bis..-decies), COMMA_PATTERN, ALLEGATO_PATTERN, normalize_for_coverage, chunk_structured/unstructured_regulation, extract_uncaptured_text, chunk_regulation (coverage 70%) + compute_content_hash SHA-256. Alias Chunk=dict[str,str\|None] (no TypedDict per CLAUDE.md). 18 test (15 unit regex/coverage/hash + 3 E2E PDF). 67/67 totali, mypy/ruff verdi. karpathy applicato. **NOTA: testato SOLO su fixture sintetica — coverage regex su PDF gazzettiero reale ancora da validare (PDF mancante).** |
| 2.3 | Classificazione + Embedding | **S** | API call + batch processing, logica lineare | ✅ | 2026-05-23 | BP §06.1.1 Stadio 3+4 inline. classify_chunk (LLM + downgrade SANZIONE rule-based), embed_batch/voyage_embed_with_retry (Voyage voyage-3, get_voyage_client da dependencies), index_chunks (batch 50 + dedup content_hash). **GAP sequenza:** call_llm (BP §05.5, normalmente in content_agent FASE 3.4) definito QUI con anthropic+tenacity per sbloccare 2.3 — FASE 3.4 lo importerà da ingestion_service (deciso con utente). OPT-2: timeout da settings.llm_request_timeout. 8 test mock Voyage/Anthropic. 75/75 totali, mypy/ruff verdi. dependencies.py invariato (set/get_voyage_client già FASE 0). |
| 2.4 | COURSE_CATALOG | **S** | Dizionario Python statico da BP §13 | ✅ | 2026-05-23 | config/catalog_config.py: 6 tipi corso verbatim BP §13 (sicurezza generale/specifica basso, primo soccorso B/C, antincendio L1, HACCP addetto, preposti). HACCP regional=True (unico regionale v1.0). Type hint dict[str,dict[str,object]] (no TypedDict). Import `from config.catalog_config import COURSE_CATALOG` (namespace package, no __init__). 8 test (6 tipi, titoli/regs/moduli non vuoti, HACCP regionale, bounds ore). 83/83 totali, mypy/ruff verdi. |
| 2.5 | KnowledgeRepository + RAG | **O** | ⚠️ Query vettoriale con JOIN regionale NULL-safe, filtro rilevanza, pattern complesso. Errori producono corsi con contenuto errato. | ✅ | 2026-05-23 | services/knowledge_repo.py (NON rag_service.py) BP §06.3: resolve_slugs_to_ids (ValueError su slug mancanti), search_chunks (JOIN regulations.region NULL-safe, relevance_score = 1 - cosine, ORDER BY <=>, LIMIT top_k), get_style_patterns (ORDER BY certified_at DESC LIMIT 5). Helper _to_pgvector: embedding list→literal '[...]' perché asyncpg non ha codec vector (segnalato REI-16). langchain-rag skill applicata (filtro ibrido vector+scalar su pgvector, NON retriever astratto; embedding voyage-3/1024 coerente index↔query). 9 test su mock pool (gotcha #4 — DB live in E2E). 92/92 totali, mypy/ruff verdi. |
| 2.6 | Endpoint REST `/api/regulations` | **S** | CRUD standard con rate limit | ✅ | 2026-05-23 | api/routes/regulations.py BP §10: POST /upload (require_role admin + rate 3/min §08.5 + UploadFile/Form → ingest_regulation_file), GET / (paginato page/per_page), GET /{id}/chunks (paginato), DELETE /{id} (soft-delete UPDATE status='ABROGATA', 404 se assente). Router registrato in main.py. ingest_regulation_file (orchestratore Stage 1-4, scope deciso con utente) + fix embedding→$N::vector literal in index_chunks. 8 test (authz operator→403, paginazione LIMIT/OFFSET, soft-delete, upload mock). 100/100 totali, mypy/ruff verdi. |

**Stima costo FASE 2:** ~$8-12 (4 Sonnet + 2 Opus)

---

### FASE 3 — Agenti LangGraph + PacingEngine (Sprint 3)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 3.1 | State LangGraph + Grafo (2 nodi) | **S** | BP §05.2-§05.3 fornisce codice esatto, pattern LangGraph standard | ✅ | 2026-05-23 | app/agents/pipeline.py: NexusPipelineState TypedDict (8 campi BP §05.2 letterali, no pptx/pdf — FIX-1) con operator.add reducer su completed_modules+errors. create_pipeline @asynccontextmanager (D18: AsyncPostgresSaver.from_conn_string è acm in langgraph-checkpoint-postgres 3.1.0). Grafo: research+content via set_entry_point/add_edge/set_finish_point BP §05.3 letterale. 2 NODI, no Production Builder. Stub research_agent/content_agent (impl 3.3/3.4). Lazy import per evitare ciclo (D20). pyproject + langgraph-checkpoint-postgres + psycopg[binary] (D21). 7 test compile (TypedDict shape, no campi vietati, reducer, 2 nodi, edge lineari, checkpointer wired, acm signature) — mock InMemorySaver, Postgres MAI live (#R2). 108/108 totali, mypy/ruff verdi. langgraph-fundamentals + langgraph-persistence skill applicate (REI-14). |
| 3.2 | PacingEngine (30s/slide) | **S** | Calcolo matematico deterministico, formula chiara | ✅ | 2026-05-23 | app/services/pacing_engine.py (NON agents/) BP §06B + GAP-1+FIX-8 v2.0. SECONDS_PER_SLIDE=30 fisso (D22 sostituisce media ponderata BP), DISTRIBUTION 5 tipi senza DIAGRAM (D23 FIX-8), DENSITY_MULTIPLIER 0.8/1.0/1.25, SLIDES_PER_MODULE_TARGET=40. Per-modulo: l'ultimo tipo assorbe il resto (somma=slide_count). module_titles dal COURSE_CATALOG con fallback "Modulo N". 17 test deterministici PURI (zero mock, zero I/O): 1h→120, 4h→480, 8h→960, 16h→1920 slide; densità leggera 4h→384, intensiva→600; DIAGRAM assente dovunque; distribuzione somma a slide_count per ogni modulo; min 2 moduli; titoli catalog vs fallback. 125/125 totali, mypy/ruff verdi. **PacingEngine è uno dei rari componenti SENZA verification debt** (#R0 non applicabile). |
| 3.3 | Research Agent | **O** | ⚠️ Orchestrazione complessa: query semantica, top_k dinamico, gate RAG, distribuzione chunk con keyword overlap, ribilanciamento min/max. Molte edge case. | ✅ | 2026-05-23 | app/agents/research_agent.py BP §05.4 letterale. Helpers: _keyword_overlap, _rebalance_min/max, distribute_chunks_to_modules (round-robin se <3*moduli chunks, altrimenti semantic overlap + rebalance min(3)/max(avg+5)). Pipeline: resolve_slugs→regional guard (HACCP+NAZIONALE→ValueError, IMPLEMENTA item 7 checklist FASE 2 che D17 segnalava appartenere a FASE 3 → DEBITO CHIUSO)→query semantica D-20 (title+default_modules)→voyage_embed→search_chunks(top_k=max(30, durata*10))→gate <5→filtro MIN_RELEVANCE 0.3→pacing con titoli catalog→distribute→get_style_patterns. Return dict {course_context, pacing_plan} (langgraph fix-state-must-return-dict). 13 test (7 helpers det. + 6 mock flow). 138/138 totali, mypy/ruff verdi. D24: aggiunto config/__init__.py per mypy. langgraph-fundamentals + langchain-rag skill (REI-14). |
| 3.4 | Content Agent + Circuit Breaker | **O** | ⚠️ La sotto-fase più complessa del progetto: chiamate LLM con retry, parsing JSON robusto, circuit breaker inline, prompt engineering differenziato Discente/Formatore. Errori = corsi illeggibili. | ✅ | 2026-05-23 | app/agents/prompts.py BP §05.6 letterale (SYSTEM_PROMPT_DISCENTE/FORMATORE + build_content_system_prompt + build_module_prompt diff. formatore + build_previous_summary). app/agents/content_agent.py BP §05.5 letterale: parse_slides_json (fence strip + json.loads + retry correttivo), content_agent iterates pacing.modules[start_index:], call_llm via retry tenacity, circuit breaker INLINE failed_count: int (FIX-3 — NO class). D10 CHIUSO: import call_llm da ingestion_service (no duplicazione). Reducer-friendly return {completed_modules:[...], current_module_index:N} (langgraph fix-state-must-return-dict). 14 test: parser+prompts deterministici, happy path 3 moduli, corrective retry, breaker trip>50%/no-trip=50%, meta-test grep FIX-3. 152/152 totali, mypy/ruff verdi. karpathy-guidelines + langgraph-fundamentals skill applicate (REI-14). |
| 3.5 | Pipeline E2E (senza build) | **S** | Test di integrazione, non logica nuova | ✅ | 2026-05-23 | tests/integration/test_pipeline_e2e_no_build.py. **Approccio mock+live deciso con utente** (D25): test PRIMARIO mockato (6 dipendenze patched simultanee: AsyncPostgresSaver→InMemorySaver, KnowledgeRepository.resolve/search/style, voyage_embed, call_llm) — verifica ainvoke 2-nodi, reducer operator.add accumula completed_modules, checkpoint scritto (graph.aget_state), asyncio.wait_for(timeout). Test SECONDARIO timeout: nodo hang 5s vs timeout 0.1s → asyncio.TimeoutError. Test LIVE skeleton @pytest.mark.live (skip default, eseguibile `pytest -m live` quando #R1+#R2+#R3+#R4 disponibili). 154/154 mocked verdi + 1 deselected. mypy/ruff verdi. codegraph reindex. |

**Stima costo FASE 3:** ~$10-15 (3 Sonnet + 2 Opus)

---

### FASE 4 — Production Builder (Sprint 4)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 4.1 | `inspect_pptx_template.py` | **S** | Script CLI di ispezione, output report | ✅ | 2026-05-23 | scripts/inspect_pptx_template.py: argparse `--template-path` / `--output-json`, dataclass-driven (ShapeInfo/LayoutInfo/InspectionReport), enumera slide_layouts ed estrae idx/name/shape_type/placeholder_type/posizione in EMU+inches. Output: report tabellare stdout + JSON in `assets/templates/master_inspection.json`. Exit 1 con messaggio chiaro se template assente (LAVORO UMANO #R8). Smoke test su `.pptx` default OK (11 layout/58 shape rilevati, JSON valido). D28 (struttura inspector dedotta dal contesto BP §07.3). #R10 chiuso: deps FASE 4 installate localmente. `pptx`/`pptx.*` aggiunti a mypy overrides. mypy/ruff verdi, 154/154 verdi. |
| 4.2 | SlideBuilder | **O** | ⚠️ Manipolazione python-pptx con layout complessi, posizionamento pixel, inserimento immagini con fallback, gestione template multi-layout. Richiede comprensione visiva della struttura PPTX. | ✅ | 2026-05-23 | `app/builders/slide_builder.py` SYNC (REI-3: Semaphore in FASE 5.1). Layout map `SlideType→idx` default BP §07.3 (0-7) override per-instance. Helper placeholder lookup by type (TITLE/BODY/PICTURE/SUBTITLE/OBJECT). Image insert try/except → fallback "[Immagine non disponibile]" (BP §07.1 line 2304-2312). `_is_local_path` rigetta URL (invariante BP line 2148). Quiz con 4 opzioni A-D + marker ✓. BuildReport dataclass per diagnostics. Output `{out}/{id}_corso.pptx`. 22 test su template sintetico (default python-pptx, generato in-process). D29 (BP §07.1 non dà classe), D30 (path app/builders/ vs prompt builders/). 176/176 verdi, mypy/ruff verdi. **#R8 ancora aperto** (template umano per validare layout BP §07.3 reali). |
| 4.3 | Image Service + sanitize_svg | **S** | BP fornisce codice esatto, pattern async con semaforo | ✅ | 2026-05-23 | `app/services/image_service.py` BP §07.0 verbatim: `sanitize_svg()` INLINE (FIX-2, 4 regex DOTALL su script/foreignObject/remote-xlink/event-handler); `_download_one_image()` async con Semaphore(5), cache DB query/usage_count, Pillow `load()` strict, guard 5MB; `_render_diagram_sync()` cairosvg 1200×800 (sanitize PRIMA del rendering); `prefetch_images()` con shared httpx client + asyncio.gather. 22 test (7 sanitize_svg deterministici + 5 download + 4 render + 5 prefetch + 1 meta-test FIX-2). D31 (bug BP `'web_tasks' in dir()`), D32 (dict typing), D33 (assert query_url not None). `cairosvg`/`cairosvg.*` in mypy overrides. 198/198 verdi, mypy/ruff verdi. |
| 4.4 | PDF Builder (Jinja2 + WeasyPrint) | **S** | Template HTML/CSS + rendering, logica lineare | ✅ | 2026-05-23 | `app/builders/pdf_builder.py` + `app/templates/dispensa.html` BP §07.2 + OPT-3 v3.0: Jinja2 sostituisce `str.format()`. Template con loop modules/slides, condizionali normative_ref/speaker_notes/quiz, copertina+page counter, palette brand iniettata, autoescape ON. PdfBuilder SYNC; `render_html()` esposto per test deterministici. Lazy import weasyprint (D34: GTK runtime Windows). 24 test (4 group puri + 2 constructor + 12 render_html Jinja2 + 4 build mockato + 1 escaping + 1 meta-test OPT-3 AST D35). D36: path `app/builders/`. `weasyprint`/`weasyprint.*` in mypy overrides. Nuova risorsa **#R12** (GTK runtime locale per validare PDF binario reale; workaround stub `sys.modules['weasyprint']=MagicMock()` nei test). 222/222 verdi, mypy/ruff verdi. |
| 4.5 | ProductionBuilder (orchestratore) | **S** | Composizione di moduli già pronti, pattern semplice | ✅ | 2026-05-23 | `app/builders/production_builder.py` + `app/builders/pptx_validator.py` BP §07.1 verbatim, karpathy applicato (zero recovery extra). `check_memory_before_build` (psutil, 60% threshold), `check_disk_before_build` (1GB min). ProductionBuilder.build async orchestratore: memory→disk→PPTX(to_thread)→validate→PDF(to_thread)→`_cleanup_tmp`(>1h)→`_build_report`. Progress 87/92/95 BP literal. PptxValidator carica .pptx + count check. 15 test (4 guard, 3 validator REAL pptx, 1 E2E 20 slide mock + 2 propagation/fail-fast, 2 cleanup, 3 meta REI-3/BP constants). D37 (PptxValidator minimum), D38 (path), D39 (top-level GenerationReport). `psutil`/`psutil.*` in mypy overrides. 237/237 verdi project-wide, mypy/ruff verdi. |
| 4.6 | Audio Service (edge-tts) | **S** | API async semplice, pattern identico a image_service | ✅ | 2026-05-23 | `app/services/audio_service.py` GAP-3 + OPT-1 edge-tts (NO OpenAI). Schema audio_tracks verificato da 001_initial.sql (D42, MCP postgres non esposto in sessione). `generate_narrations()`: Semaphore(3) + tenacity 3-retry exp + wait_for 30s, MP3 in `output/audio/{course_id}/slide_NNNN.mp3`, durata via mutagen, INSERT audio_tracks + UPDATE courses.audio_manifest_path, manifest JSON con `{course_id,total_tracks,tracks:[...]}`. Fallback per-slide (BP §07.1 invariante). ProductionBuilder esteso con tappa audio condizionata su `course["outputs"]` (progress 96, import lazy). D40 (body fallback senza LLM rephrase: karpathy #2), D41 (path), D42 (schema da migration). Nuova risorsa **#R13** (Edge TTS endpoint). 9 test (6 happy path + 3 fallback con cleanup file parziale + timeout). 246/246 verdi, mypy/ruff verdi project-wide. |
| 4.7 | Test E2E Build sintetico | **S** | Script di test, non logica nuova | ✅ | 2026-05-24 | `scripts/synth_build_test.py` CLI E2E: 30 slide mock + 3 moduli + outputs=["pptx","pdf","audio"]. Self-supplies template sintetico + `_FakePool` stub (no #R2). Guard `_check_weasyprint_available()` exit 2 con istruzioni Docker se GTK mancante. Verifica PPTX 30 slide + PDF esiste + audio MP3 + manifest JSON. **Eseguito con SUCCESSO IN DOCKER** (eduvault-backend, 2026-05-24): 30 slide + PDF + 30 MP3 it-IT-DiegoNeural REALI da edge-tts + manifest in ~10s. D43 (build/build_course), D44 (python-multipart pre-esistente), D45 (Docker rebuild). 246 pytest verdi + 1 synth E2E green. **FASE 4 INTERA COMPLETATA: 7/7 sotto-fasi ✅.** |

**Stima costo FASE 4:** ~$6-10 (6 Sonnet + 1 Opus)

---

### FASE 5 — Orchestrazione Backend + WebSocket + REST (Sprint 5A)

| # | Sotto-fase | Modello | Motivazione | Stato | Data | Note |
|---|---|---|---|---|---|---|
| 5.1 | `generation_service.py` | **O** | ⚠️ Cuore dell'orchestrazione: semaforo, timeout globale, pipeline inner con costruzione initial_state, fingerprint, telemetria. Molte parti mobili interconnesse. | ✅ | 2026-05-24 | `app/services/generation_service.py` BP §09 verbatim. `_job_semaphore=Semaphore(1)` QUI (REI-3 + FIX-7). `PIPELINE_TIMEOUT_SECONDS = settings.pipeline_timeout` (OPT-2 D47). `send_ws_progress` (UPDATE progress_percent+current_step). `build_normative_fingerprint` (refs dedup + chunk_count + ISO timestamp). `run_pipeline` wrapper async with semaforo + asyncio.wait_for + 3 except (TimeoutError→'failed', CancelledError→'cancelled' + re-raise D51, Exception→'failed' truncate 500ch). `_run_pipeline_inner`: fetchrow course+brand → initial_state 8 campi BP §05.2 → status='research' → async with create_pipeline (D49) → ainvoke con cast (D50) → slide_contents_json + fingerprint + chunk_ids PRIMA del build → status='building' → prefetch_images → ProductionBuilder.build(db=pool D52) → status='completed' + INSERT audit_log pipeline_metrics. `recover_interrupted_jobs` BP §09.2: UPDATE status='failed' WHERE status IN (research/content/building). 17 test (3 invarianti REI/FIX/OPT + 3 fingerprint puri + 1 ws + 1 happy path + 3 failure paths + 1 ordering fingerprint-before-build + 2 recover + 3 meta). D47-D52 segnalate. 270/270 verdi, mypy/ruff verdi project-wide, codegraph reindex. |
| 5.2 | Endpoint `/api/courses` | **S** | CRUD + download, pattern standard FastAPI | ✅ | 2026-05-24 | `app/api/routes/courses.py` BP §10: POST (rate 5/min BP §10.4, pacing estimate, queue_position via COUNT generation_jobs, INSERT course+job, fire-and-forget `asyncio.create_task(run_pipeline)`), GET paginato ownership-aware (admin tutti, operator solo `created_by=me`) + filtro status, GET/{id} con fingerprint JSON parse + 404/403, POST/{id}/certify (reviewer/admin → `certify_course`), GET/{id}/download/{pptx,pdf,zip,audio} (StreamingResponse ZIP in-memory, "audio" zippa cartella MP3 + manifest), DELETE soft-delete archived. `certification_service.py` MINIMUM (D53: FASE 7.1 lo sostituirà BP §06.2 verbatim). 19 test (unauth/queue position/invalid outputs/ownership SQL admin vs operator/status filter/404-403-200/certify role+ValueError→400/download tutti i 4 fmt + missing path 404 + invalid 400/delete owner vs non-owner). Router registrato in main.py. 289/289 verdi, mypy/ruff verdi project-wide, codegraph reindex. |
| 5.3 | WebSocket progress autenticato | **S** | BP §08.8 fornisce codice esatto, pattern asincrono | ✅ | 2026-05-24 | `app/api/websocket.py` BP §08.8 verbatim + 3 fix REI/security: WS `/ws/jobs/{job_id}?token=...` con JWT decode → close 4001 invalid/refresh (D56), JOIN courses-jobs per ownership → close 4004/4003 (admin/reviewer = qualunque job, operator = solo `created_by=me`), loop `send_json + sleep(1)` fino a TERMINAL_STATES `{completed,failed,cancelled}` (D55 estende BP per coerenza con FASE 5.1 D51). `get_job_progress(job_id)` riusabile per polling fallback con UUID conversion + try/except → not_found su UUID malformato (D54 fix bug BP). Router registrato in main.py. 14 test (3 get_job_progress puri + 3 auth failures incl. refresh-token reject + 3 ownership 4004/4003 + 4 happy paths admin/operator/multi-frame/failed + 1 meta). 303/303 verdi, mypy/ruff verdi project-wide, codegraph reindex. |
| 5.4 | Endpoint `/api/admin` | **S** | Query aggregate semplici | ✅ | 2026-05-24 | `app/api/routes/admin.py` BP §10: 4 endpoint admin-only (D57). GET /api/admin/metrics aggrega `audit_log WHERE action='pipeline_metrics'` su `?days=N` (1-365, default 7) → total_runs/avg_elapsed_seconds/avg_slides/total_images_resolved/period_days, gestisce sia JSONB dict che str (asyncpg codec variance). GET /api/dashboard/stats → COUNT su courses/regulations/approved_courses con guard NULL→0. GET /api/brand-presets → SELECT ORDER BY is_default DESC, name + parsing palette JSON-or-dict. GET /api/catalog → ritorna COURSE_CATALOG (6 tipi BP §13). Router registrato in main.py. 12 test (per endpoint: admin OK + operator 403; metrics: empty + mixed payload + invalid days 422; dashboard: null counts; brand-presets: default first + palette dict/str; catalog: 6 keys; unauth surface su tutti). 315/315 verdi, mypy/ruff verdi project-wide, codegraph reindex. |
| 5.5 | Smoke test E2E backend + Audit checklist | **S** | Verifica sequenziale, no logica nuova | 🟡 | 2026-05-24 | **E2E PARZIALE eseguito live**. Steps 1-6 verdi: down -v → build → up → migrations (10 tabelle) → setup_roles con sed sub password → seed (admin+brand) → restart backend → /health OK → login admin → /me. Step 7-9 (ingest dm388 + POST /api/courses + WS): **BLOCKED-UPSTREAM** da #R1 (PDF reale assente, solo synthetic) + #R3 (ANTHROPIC_API_KEY restituisce 401 invalid x-api-key live confermato) + #R4 (VOYAGE non testato ma stessa categoria). Fallback surrogate (deciso con utente): synth_build_test re-eseguito in Docker (30 slide + PDF 25KB + 30 MP3 reali edge-tts), poi INSERT manuale di 1 corso completed in DB → tutti i 4 download REST testati REAL (PPTX 89496B, PDF 25465B, ZIP 69183B, audio ZIP 1.4MB con 30 MP3+manifest) + tutti i 4 admin endpoint REST testati REAL (metrics→0 runs, dashboard→1+1+0, brand-presets→default, catalog→6 keys). D58 (ingest non transazionale). **Audit checklist FASE 5 completo (12 item)**: 11 ✅ + 1 FIX item 8 (polling fallback doc in `docs/POLLING_FALLBACK.md`). Item 11 audit_log append-only verificato LIVE in Docker. **Per chiusura completa servono #R1+#R3+#R4 risolti** (utente deve fornire PDF reale + API keys valide). |

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
