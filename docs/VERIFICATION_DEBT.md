# VERIFICATION DEBT — Nexus EduVault

> **Scopo.** Inventario auditabile di tutto ciò che è stato dimostrato *solo* con
> mock / fixture sintetiche / pattern strutturali, e che richiede una verifica
> contro risorse reali (DB live, API esterne reali, documenti reali del cliente)
> per dirsi davvero validato. Più la lista di tutte le discrepanze REI-16 segnalate
> nelle risposte di Claude Code, e le credenziali/risorse mancanti per chiuderle.
>
> **Vincolo di mantenimento (REI-17).** Claude Code DEVE aggiornare questo file
> ogni volta che: (a) introduce un nuovo test mock, (b) segnala una discrepanza
> REI-16, (c) scopre che gli serve una credenziale / risorsa esterna non ancora
> disponibile. L'aggiornamento avviene PRIMA del corrispondente aggiornamento
> Tracker (REI-12) — così il debt è sempre visibile e tracciato.
>
> **Ultimo aggiornamento:** 2026-05-23 — Audit checklist FASE 3 + fix item 15 (setup_langgraph_grants.sql)
> **Conteggio attuale:** 88 test mock + 26 test deterministici + 1 test live (skipped default) = 154 test esecuti + 1 deselected, 24 discrepanze REI-16, 11 risorse mancanti

---

## 1. Test eseguiti con MOCK (non contro risorse reali)

Quando un test usa `AsyncMock`, `patch`, una fixture sintetica o uno stub, l'asserzione
prova la *correttezza della forma del codice*, non il comportamento contro la risorsa
reale. Sono test utili e necessari — ma incompleti. Ognuno qui ha un riferimento al
test e una nota su cosa NON sta ancora verificando.

### Ingestion (FASE 2.1 / 2.2 / 2.3 / 2.6)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 1-5 | `test_parse_regulation_pdf_*` (5 test) | `tests/integration/test_ingestion.py` | Usa `dm388_synthetic.pdf` (reportlab, 4 pp). Non verifica pdfplumber su layout Gazzetta Ufficiale reale (colonne, header, font incorporato, OCR layer). Risorsa mancante: **#R1** (DM 388/2003 reale). |
| 6-8 | `test_parse_then_chunk_*` (3 test E2E parse+chunk) | `tests/integration/test_ingestion.py` | Idem #1-5: chunking testato su fixture sintetica. ART_PATTERN/COMMA_PATTERN/ALLEGATO_PATTERN non esercitati su normativa italiana vera; `normalize_for_coverage` (strip "Gazzetta Ufficiale ... Serie ... N" e "— N —") MAI esercitato perché la fixture non li contiene. **Risorsa: #R1.** |
| 9-23 | `test_chunking.py` (15 test unit regex/coverage/hash) | `tests/unit/test_chunking.py` | Stringhe sintetiche hand-crafted. I regex passano su input che io stesso ho costruito per farli passare — bias di conferma intrinseco. **Risorsa: #R1** per test contro testo reale. |
| 24 | `test_classify_chunk_parses_json` | `tests/unit/test_classification_embedding.py` | Mocka `call_llm` con `AsyncMock`. Mai chiamato Anthropic API reale. La SANZIONE-downgrade rule è testata con stringhe inventate. **Risorsa: #R3** (ANTHROPIC_API_KEY funzionante). |
| 25 | `test_classify_chunk_downgrades_false_sanzione` | id. | id. |
| 26 | `test_classify_chunk_keeps_true_sanzione` | id. | id. |
| 27 | `test_embed_batch_returns_one_vector_per_text` | id. | Stub `_voyage_stub(dim=1024)`: hardcodo 1024 nel mock e poi verifico 1024. Tautologia. Non verifica che Voyage `voyage-3` produca davvero 1024 dim. **Risorsa: #R4** (VOYAGE_API_KEY funzionante). |
| 28 | `test_voyage_embed_with_retry_returns_single_vector` | id. | id. |
| 29 | `test_index_chunks_inserts_new_chunks` | id. | Mock pool: verifico solo che `pool.execute.await_count == 2`. Non verifico che l'INSERT contro Postgres reale + pgvector accetti il literal `$8::vector` con embedding 1024-dim. **Risorsa: #R2** (DB live). |
| 30 | `test_index_chunks_skips_duplicates` | id. | Mock dedup: `fetchval` ritorna `"existing-uuid"` per il primo, `None` per il secondo. Non verifico race condition concorrenti né che l'UNIQUE INDEX parziale `WHERE is_current = true` funzioni davvero come previsto. **Risorsa: #R2.** |
| 31 | `test_index_chunks_empty_is_noop` | id. | OK strutturalmente. |

### KnowledgeRepository (FASE 2.5)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 32-33 | `test_to_pgvector_*` (2 test) | `tests/integration/test_knowledge_repo.py` | Pura formattazione stringa. OK. |
| 34 | `test_resolve_slugs_returns_ids` | id. | Mock `pool.fetch` ritorna 2 righe. Non verifico che `slug = ANY($1::text[])` funzioni contro Postgres reale né che lo INDEX `idx_regulations_slug` venga usato. **Risorsa: #R2.** |
| 35 | `test_resolve_slugs_raises_on_missing` | id. | OK logicamente, niente da provare contro DB. |
| 36 | `test_search_chunks_maps_to_normative_chunk` | id. | Mock pool ritorna 1 riga. Mai eseguita la query vettoriale reale `<=>` su HNSW. **Risorse: #R2 + #R5** (HNSW EXPLAIN ANALYZE). |
| 37 | `test_search_chunks_passes_pgvector_literal_and_regional_join` | id. | Verifica solo che la stringa SQL contenga le sottostringhe attese. Mai eseguita. **Risorsa: #R2.** |
| 38 | `test_search_chunks_unknown_region_does_not_raise` (NUOVO post-audit) | id. | Documenta il comportamento "no validation" — vedi discrepanza **D17** sotto. |
| 39 | `test_search_chunks_handles_null_tags` | id. | OK strutturalmente. |
| 40 | `test_get_style_patterns_decodes_json_ordered` | id. | Mock ritorna JSON pre-cotto. Non verifica che `style_pattern JSONB` di asyncpg ritorni davvero str (e non già un dict, dipende dal codec) — se asyncpg ritorna dict, `json.loads(dict)` esplode. **Risorsa: #R2.** |
| 41 | `test_get_style_patterns_empty` | id. | OK. |

### COURSE_CATALOG (FASE 2.4)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 42-49 | `test_catalog.py` (8 test) | `tests/unit/test_catalog.py` | Verifiche strutturali sul dict Python. Non verificano che gli `slug` in `regs` esistano davvero in `regulations` (foreign-key logica, validata a runtime da `resolve_slugs_to_ids`). **Risorsa: #R1 + altri PDF normativi reali.** |

### Audit checklist FASE 3 (post-implementazione)

Eseguito audit punto-per-punto della checklist Master Plan riga ~1254 (16 item):
- **13 verdi senza riserve**: 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 16
- **1 verde con caveat tracciato**: 3 (checkpointer PG "attivo" nel codice ma mai live nei test — #R2)
- **2 azioni residue**:
  - Item 14 (`asyncio.wait_for` timeout 1800s nel codice produzione): vive in `generation_service.py` FASE 5.1 — D26
  - Item 15 (GRANT tabelle LangGraph): risolto con `setup_langgraph_grants.sql` — D27 / #R11

### Pipeline E2E no-build (FASE 3.5)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 109 | `test_pipeline_e2e_mocked` | `tests/integration/test_pipeline_e2e_no_build.py` | **6 dipendenze esterne mockate simultaneamente** (AsyncPostgresSaver→InMemorySaver, KnowledgeRepository.resolve_slugs/search_chunks/get_style_patterns, voyage_embed_with_retry, call_llm). Verifica: orchestrazione 2-nodi LangGraph reale, reducer `operator.add` su completed_modules, checkpoint scrittura via `graph.aget_state()`, wrapper `asyncio.wait_for(timeout)`. **NON verifica**: chunk reali, embedding voyage-3 reali, slide LLM reali, Postgres checkpointing reale, performance pipeline su corso completo (es. 8h = 24 moduli × N call LLM). |
| 110 | `test_pipeline_e2e_respects_timeout_wrapper` | id. | Verifica logica timeout con un nodo che dorme 5s vs timeout 0.1s → TimeoutError. OK strutturale. |
| 111 | `test_pipeline_e2e_real` (`@pytest.mark.live`) | id. | **DESELECTED di default** (`addopts = -m 'not live'` in pyproject). Scheletro che chiama `pytest.skip` se manca uno tra: storage/pdfs/dm388_03.pdf (#R1), DATABASE_URL env (#R2), VOYAGE_API_KEY (#R4), ANTHROPIC_API_KEY (#R3). Eseguibile manualmente con `pytest -m live`. **Mai eseguito davvero ad oggi**. |

### Content Agent (FASE 3.4)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 95-98 | 4 test `parse_slides_json` (plain / fenced / object / malformed) | `tests/integration/test_content_agent.py` | Pura parsing logic. **Senza debt.** |
| 99-103 | 5 test prompts (system selection, formatore branch, style pattern, summary empty/populated) | id. | Pure string building. **Senza debt.** |
| 104 | `test_content_agent_happy_path_returns_completed_modules` | id. | Mocka `call_llm` con `AsyncMock(side_effect=_ok_response)`. **Nessuna chiamata Anthropic reale.** L'orchestrazione 3 moduli → 3 ModuleContent è verificata strutturalmente; la QUALITÀ del JSON generato dall'LLM reale (slide ben formate, normative_ref pertinenti, body entro 90 parole) **NON è verificata.** Risorsa: **#R3** (Anthropic API key) per test E2E reale. |
| 105 | `test_content_agent_corrective_retry_recovers_invalid_json` | id. | Verifica la logica retry (malformed → correzione → valido). OK strutturalmente. Non verifica che l'LLM reale ritorni davvero JSON valido al secondo tentativo. **Risorsa: #R3.** |
| 106 | `test_content_agent_circuit_breaker_trips_above_50_percent` | id. | Verifica trip su >50%. OK logico. |
| 107 | `test_content_agent_circuit_breaker_does_not_trip_at_exactly_50_percent` | id. | Edge case = 50% (strict > comparator). OK. |
| 108 | `test_no_circuit_breaker_class_anywhere` | id. | **Guardia strutturale FIX-3 / karpathy reg #2:** grep regex `^class\s+\w*[Cc]ircuit[Bb]reaker` su tutti i file `app/agents/**.py`, escludendo docstring/commenti. Fa fallire CI se qualcuno reintroduce una `class ModuleCircuitBreaker`. **Senza debt — è un meta-test sul codice.** |

### Research Agent (FASE 3.3)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 82-88 | 7 test helpers (`_keyword_overlap`, `_rebalance_min/max`, `distribute_chunks_to_modules`) | `tests/integration/test_research_agent.py` | Helpers deterministici su `NormativeChunk` sintetici. **Senza debt** — sono matematica/algoritmo puri. |
| 89 | `test_research_agent_happy_path_returns_context_and_pacing` | id. | Mocka `KnowledgeRepository.resolve_slugs_to_ids` + `voyage_embed_with_retry` + `search_chunks` + `get_style_patterns`. **Quattro componenti esterni mockati simultaneamente.** Verifica orchestrazione, NON l'effettiva ricerca vettoriale né l'embedding voyage-3 reale. Risorse: **#R1 + #R2 + #R4**. |
| 90 | `test_research_agent_rag_gate_raises_below_5_chunks` | id. | Logica gate verificata. OK con mock. |
| 91 | `test_research_agent_regional_course_rejects_nazionale` | id. | Logica guardia regionale verificata. OK. |
| 92 | `test_research_agent_regional_course_accepts_specific_region` | id. | Stesso mock pesante: 4 patch attivi. Risorse: **#R1 + #R2 + #R4 + corpus HACCP Campania (#R9 sottoinsieme)**. |
| 93 | `test_research_agent_relevance_filter_strips_low_score` | id. | Logica filtro verificata. OK. |
| 94 | `test_research_agent_top_k_scales_with_duration` | id. | Verifica che `search_chunks` riceva `top_k=80` per 8h. OK strutturale. |

### PacingEngine (FASE 3.2)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 65-81 | 17 test `test_pacing_engine.py` | `tests/unit/test_pacing_engine.py` | **Pura matematica deterministica — zero mock, zero I/O, zero dipendenze esterne.** Test asseriscono direttamente i numeri attesi (120/480/960/1920 slide, distribuzione che somma a slide_count, 0 DIAGRAM, fallback titoli moduli). **Nessun debt aperto su questi test.** Il PacingEngine è uno dei pochi componenti del progetto totalmente verificabile in-process. |

### LangGraph pipeline (FASE 3.1)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 58 | `test_state_has_exactly_bp_05_2_fields` | `tests/unit/test_graph_compile.py` | Introspezione statica sul TypedDict. OK. |
| 59 | `test_state_omits_post_pipeline_fields` | id. | Idem — verifica strutturale. OK. |
| 60 | `test_completed_modules_has_add_reducer` | id. | Verifica via `__metadata__` di `Annotated`. OK. |
| 61 | `test_errors_has_add_reducer` | id. | Idem. OK. |
| 62 | `test_graph_compiles_with_two_nodes_and_linear_edges` | id. | **Mocka `AsyncPostgresSaver.from_conn_string` con `_fake_pg_saver` che yielda `InMemorySaver`.** La struttura del grafo (nodi/edge) è validata, ma il checkpointer **NON è mai stato esercitato contro Postgres reale**. La query `CREATE TABLE checkpoints/checkpoint_writes/checkpoint_migrations` di `AsyncPostgresSaver.setup()` non è mai stata eseguita. **Risorsa: #R2** (DB live). |
| 63 | `test_graph_uses_checkpointer` | id. | Verifica solo che `graph.checkpointer is not None` con InMemory mock. **Risorsa: #R2.** |
| 64 | `test_create_pipeline_is_async_context_manager` | id. | Verifica strutturale del decorator. OK. |

### Endpoint /api/regulations (FASE 2.6)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 50-52 | `test_*_forbidden_*` / `test_upload_requires_token` (3 test) | `tests/integration/test_regulations.py` | OK strutturalmente — testano `require_role` + HTTPBearer. |
| 53 | `test_upload_admin_runs_ingestion` | id. | Mocka `ingest_regulation_file` con `AsyncMock(return_value=(uuid, 7))`. Non verifica l'orchestrazione completa, non scrive su disco reale. **Risorse: #R1 + #R2 + #R3 + #R4.** |
| 54 | `test_list_regulations_paginated` | id. | Mock pool ritorna 1 riga. Pagination LIMIT/OFFSET non eseguito contro Postgres. **Risorsa: #R2.** |
| 55 | `test_list_chunks_paginated` | id. | Idem. **Risorsa: #R2.** |
| 56 | `test_delete_soft_deletes` | id. | Verifica solo che l'SQL contenga `status = 'ABROGATA'`. Non verifica che il trigger `update_updated_at` aggiorni davvero il campo. **Risorsa: #R2.** |
| 57 | `test_delete_not_found_returns_404` | id. | Mock `pool.execute` ritorna `"UPDATE 0"`. OK strutturalmente. |

### Altri test pre-esistenti (FASE 0 / 1)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 58 | health, auth, seed, models (44 test pre-FASE-2) | vari | Tutti su `AsyncMock` pool. L'unica volta che il DB live è stato usato è stato lo smoke test manuale 1.5 (down -v → up → migrations → setup_roles → seed → login). Non è automatizzato. **Risorsa: #R2.** |

**Totale test mock contati: 60** (di cui ~5 puramente strutturali senza debt, e ~55 con debt reale aperto).

---

## 2. Discrepanze REI-16 (storicizzazione)

Lista cronologica di tutte le divergenze tra BP / Master Plan / output precedente di Claude
Code e quello effettivamente prodotto, con la motivazione e lo stato.

| ID | Fase | Discrepanza | Motivazione | Stato |
|---|---|---|---|---|
| D1 | 2.1 | BP `pdf_path: str` → io `str \| os.PathLike[str]` | Ergonomia con `pathlib.Path` nei test; semantica preservata | accettato |
| D2 | 2.1 | BP usa `full_text += page.extract_text(...)`, io uso `list.append + "".join()` | Costo lineare invece che quadratico (rilevante su D.Lgs 81/08 ~400 pp) | accettato |
| D3 | 2.1 | BP non gestisce `extract_text() -> None`, io sostituisco con `""` | Pagine scansionate senza text layer non devono crashare l'ingestion | accettato |
| D4 | 2.1 | PDF reale `dm388_03.pdf` non presente, uso fixture sintetica reportlab | Prompt lanciato esplicitamente; REI-16 → procedo e segnalo | **debito aperto — #R1** |
| D5 | 2.1 | reportlab non in pyproject ma usato per fixture | Transitive di weasyprint; evito di gonfiare deps produzione | tollerato |
| D6 | 2.2 | BP `list[dict]` nudo, io `dict[str, str \| None]` con alias `Chunk` | mypy --strict; no TypedDict fuori `agents/pipeline.py` | accettato |
| D7 | 2.2 | BP usa `chunk["body"]` puro, io `str(chunk["body"])` | mypy non sa che `body` è sempre `str` nel dict `str\|None` | accettato |
| D8 | 2.2 | Esposto `compute_content_hash` in 2.2 (BP lo usa in Stadio 4) | Prompt 2.2 lo richiede esplicitamente; minimum code | accettato |
| D9 | 2.2 | Test chunking solo su fixture sintetica | Idem D4 | **debito aperto — #R1** |
| D10 | 2.3 | `call_llm` definito in `ingestion_service.py` invece che `content_agent.py` | GAP di sequenza (2.3 < 3.4). Deciso con utente: opzione "minimale in ingestion". FASE 3.4 dovrà importarlo da qui. | **CHIUSO 3.4**: content_agent.py importa `from app.services.ingestion_service import call_llm`, zero duplicazione. |
| D11 | 2.3 | BP `timeout=120.0` hardcoded, io `settings.llm_request_timeout` | OPT-2 (no env hardcoded); valore default identico | accettato |
| D12 | 2.3 | `classify_chunk -> dict[str, object]`, `index_chunks` con `pool: object` | mypy strict; runtime invariato | accettato |
| D13 | 2.5 | Helper `_to_pgvector` aggiunto (BP passa `query_embedding` grezzo) | asyncpg non ha codec vector; literal `[a,b,c]` + `::vector` è interop standard. **Da validare contro DB live.** | **debito aperto — #R2** |
| D14 | 2.5 | Test su mock pool invece di "integrazione con dm388 ingerito" come dice il prompt | Gotcha #4 HANDOFF: pytest su mock; integration vera in E2E (mai eseguita) | **debito aperto — #R1 + #R2** |
| D15 | 2.5 | `pool: asyncpg.Pool` tipizzato (BP non tipizza) | mypy strict | accettato |
| D16 | 2.6 | `ingest_regulation_file()` orchestratore non verbatim BP | BP §10 dà solo firma endpoint. Composto Stage 1-4. Deciso con utente. Tocca `index_chunks` 2.3 (retroattivo) per fix `$N::vector`. | accettato |
| D17 | 2.6 / audit post-FASE-2 | Checklist FASE 2 item 7 "regione inesistente → errore" non implementabile in `knowledge_repo` (BP §06.3 non valida) — la validazione vive in `research_agent` BP §05.4 (FASE 3.3) | Documentato nel docstring + test `test_search_chunks_unknown_region_does_not_raise`; **la checklist FASE 2 contiene un item che logicamente appartiene a FASE 3** | flagged — possibile errore Master Plan |
| D18 | 3.1 | BP §05.3 scrive `checkpointer = AsyncPostgresSaver.from_conn_string(database_url)` come se ritornasse direttamente il saver. In `langgraph-checkpoint-postgres` 3.1.0 è un `@asynccontextmanager`. | `create_pipeline` diventa essa stessa `@asynccontextmanager` — caller (`generation_service` 5.1) dovrà fare `async with create_pipeline(url) as graph:`. Coerente con `ex-production-postgres` skill. | accettato, **azione richiesta in 5.1** |
| D19 | 3.1 | BP §05.2 firma `course_request: dict` nudo, io `dict[str, object]` (e cosi tutti gli altri campi dict dello state) | mypy strict + TypedDict richiede type args. Runtime invariato. | accettato |
| D20 | 3.1 | BP §05.3 importa `research_agent` / `content_agent` a top-level di `pipeline.py`. Ho dovuto lazy-import dentro `create_pipeline()` | Ciclo import: agent modules importano `NexusPipelineState` da `pipeline.py` (per type-annotare lo state come richiesto dal NodeInputT di `add_node` sotto mypy strict). | accettato |
| D21 | 3.1 | `pyproject.toml` aggiornato con `langgraph-checkpoint-postgres>=3.0` e `psycopg[binary]>=3.3` non in BP §1.1 | Necessari per import runtime di `AsyncPostgresSaver` (langgraph 1.x splitta i checkpointer in package separati) | accettato |
| D22 | 3.2 | BP §06B usa media ponderata `sum(SECONDS_PER_TYPE * DISTRIBUTION)`; prompt 3.2 esplicita `SECONDS_PER_SLIDE = 30` fisso (GAP-1 v2.0) | Vincolo commerciale: 1 slide / 30s come impegno verso il cliente. Sostituisce la formula BP. Risultati: 1h→120, 4h→480, 8h→960, 16h→1920 (verificati nei 17 test deterministici). | accettato (prompt prevale, REI-16) |
| D23 | 3.2 | BP §06B ha DISTRIBUTION 6 tipi (CONTENT_TEXT 0.45, CONTENT_IMAGE 0.20, DIAGRAM 0.10, QUIZ 0.10, CASE_STUDY 0.05, RECAP 0.10); prompt 3.2 elimina DIAGRAM (FIX-8 v1.0) e usa 5 tipi (CONTENT_TEXT 0.50, CONTENT_IMAGE 0.22, QUIZ 0.12, CASE_STUDY 0.06, RECAP 0.10) | DIAGRAM declassificato a v1.1 (D-17 BP §00 feature differite). Se Content Agent emette DIAGRAM spontaneamente, gestito da Image Service (FASE 4.3). Sum DISTRIBUTION = 1.00 verificato. | accettato (FIX-8, REI-16) |
| D24 | 3.3 | Creato `config/__init__.py` (BP §14.1 non lo elenca esplicitamente in `config/`) | mypy --strict con `config/` come arg passa due paths (`catalog_config` namespace vs `config.catalog_config`) → errore "Source file found twice". `__init__.py` rende il package esplicito senza cambiare import path. Runtime invariato. | accettato |
| D25 | 3.5 | Introdotto marker pytest `live` con `addopts = -m 'not live'` in pyproject.toml; test live skippato di default | BP / Master Plan non prescrivono uno split mock/live. Necessario per chiudere FASE 3 in CI gate senza Postgres/Voyage/Anthropic ma preservando il test E2E "vero" eseguibile manualmente con `pytest -m live`. Allinea il progetto al pattern proposto in VERIFICATION_DEBT azione #3. | accettato (deciso con utente) |
| D26 | 3 audit | Checklist FASE 3 item 14 ("asyncio.wait_for con timeout 1800s") non implementabile in FASE 3 — BP §09.1 lo colloca in `generation_service.run_pipeline()` (FASE 5.1, non ancora scritta) | Pattern già usato nel test E2E 3.5 (`asyncio.wait_for(graph.ainvoke(...), timeout=settings.pipeline_timeout)`). Il wrapping nel codice produzione arriverà con 5.1. Item analogo a D17 (item 7 checklist FASE 2 spostato in FASE 3). | flagged — chiude in 5.1 |
| D27 | 3 audit | Checklist FASE 3 item 15 ("GRANT su tabelle LangGraph per nexus_app"): in `setup_roles.sql` i GRANT sono COMMENTATI con nota "eseguire dopo primo avvio" → di fatto nessun GRANT applicato | Creato file separato `app/db/migrations/setup_langgraph_grants.sql` con GRANT espliciti per le 4 tabelle (checkpoints, checkpoint_writes, checkpoint_migrations, checkpoint_blobs verificate via inspection langgraph 3.1.0). Allineato a BP §03.2 pattern "GRANT post-startup". Da eseguire manualmente dopo prima invocazione pipeline live (#R11). | accettato |

---

## 3. Risorse / credenziali MANCANTI per chiudere il debt

| ID | Risorsa | Serve per chiudere | Bloccato da | Azione richiesta |
|---|---|---|---|---|
| **#R1** | `storage/pdfs/dm388_03.pdf` (PDF reale DM 388/2003) | D4, D9, D14, test 1-23, 53 | Cliente / download da gazzettaufficiale.it / normattiva.it | Scaricare PDF integrale, salvarlo in path indicato (tests/2.1/2.2 lo useranno automaticamente, fallback alla fixture cessa) |
| **#R2** | Postgres + pgvector LIVE accessibile dai test (Docker compose già configurato) | D13, D14, item 5 checklist, test 29-30, 34, 36-41, 54-56, 58 | Suite di integration test che faccia `docker compose up postgres → apply migrations → seed → run subset di test "live"` (separato dai mock pytest) | Definire un marker pytest `@pytest.mark.live` skippato di default; documentare in `docs/OPERATIONS.md` come lanciare i live test |
| **#R3** | `ANTHROPIC_API_KEY` valido in `.env` con quota residua | test 24-26, ingestion completa via upload reale | Cliente / chiave funzionante | Verificare che la chiave attuale in `.env` (gitignored) sia valida e abbia budget. Test `classify_chunk` reale ~$0.01 per chunk. |
| **#R4** | `VOYAGE_API_KEY` valido in `.env` con quota residua | test 27-28, ingestion completa | Cliente / chiave funzionante | Idem #R3. Voyage embed batch 50 → ~$0.001 per batch. |
| **#R5** | DM 388 ingerito + EXPLAIN ANALYZE su `search_chunks` per verificare uso HNSW | item 5 checklist FASE 2 | #R1 + #R2 + #R4 | Dopo ingestion reale: `docker exec ... psql ... -c "EXPLAIN ANALYZE SELECT ... FROM regulation_chunks ORDER BY embedding <=> ..."`. Aspettarsi `Index Scan using idx_chunks_embedding`. Se invece `Seq Scan`, capire perché (tabella troppo piccola? `SET enable_seqscan = off` per forzare). |
| #R6 | Brave Search API key valida | FASE 4 (image_service) | Cliente | Non rilevante per FASE 2 |
| #R7 | Logo + palette + font C.F.P. Montessori | FASE 6 (branding) | Cliente, CLIENT_INTAKE_QUESTIONNAIRE §4 | Non rilevante per FASE 2 |
| #R8 | Template PPTX brandizzato (lavoro UMANO, non delegabile) | FASE 4.1-4.2 | axialoop con PowerPoint | Non rilevante per FASE 2 |
| #R9 | Accordo Stato-Regioni 2011 + altre normative del COURSE_CATALOG (PDF) | Validazione completa COURSE_CATALOG, test fine-FASE-2 con corso reale generato | Cliente | Atteso entro inizio FASE 3 per testare research_agent E2E |
| #R10 | FASE 4 deps locali (`python-pptx`, `cairosvg`, `weasyprint`, `psutil`, `pyotp`, `edge-tts`, `mutagen`) | Test FASE 4 (Production Builder + Audio TTS) | Libpq + librerie C sistema (cairo, pango, gdk-pixbuf) | `pip install python-pptx cairosvg weasyprint psutil pyotp edge-tts mutagen` quando si arriva a FASE 4. Dichiarate in pyproject ma non installate localmente — il linter VS Code mostra hint Pylance (innocuo per FASE 3). Su Windows `cairosvg`+`weasyprint` richiedono GTK runtime; in Docker già OK perché Dockerfile FASE 0 installa libcairo2-dev/libpango1.0-dev/libgdk-pixbuf2.0-dev. |
| #R11 | Esecuzione manuale di `setup_langgraph_grants.sql` post primo startup live | Chiude item 15 checklist FASE 3 sul DB reale | #R2 (DB live) + prima invocazione pipeline reale | `docker exec -i eduvault-postgres-1 psql -U nexus_admin -d nexus < app/db/migrations/setup_langgraph_grants.sql`. Idempotente. Note: se `nexus_app` è l'unico utente che si connette in v1.0, è già OWNER delle tabelle checkpoint create dal suo `AsyncPostgresSaver.setup()` → GRANT ridondanti ma safe. Eseguire comunque per coerenza con BP §03.2. |

---

## 4. Action items prioritizzati

### Sblocco immediato (sotto controllo dell'utente)

1. **[#R1]** Scaricare DM 388/2003 in `storage/pdfs/dm388_03.pdf` → sblocca D4, D9, test 1-23, parziale validazione item 1 checklist.
2. **[#R3 + #R4]** Confermare che le API key in `.env` sono valide e con budget → sblocca test reali Anthropic/Voyage.
3. **[#R2] ✅ CHIUSO (3.5):** marker `@pytest.mark.live` introdotto in `pyproject.toml` con `addopts = -m 'not live'`. Primo test live skeleton in `test_pipeline_e2e_no_build.py::test_pipeline_e2e_real` (skip se prerequisiti mancanti). Pronto per esecuzione manuale appena le risorse #R1/#R3/#R4 + DATABASE_URL sono disponibili: `pytest -m live`.

### Sblocco strutturale (a carico mio quando le risorse arrivano)

4. Re-eseguire `test_parse_regulation_pdf_*` con PDF reale → verifica items 1 e 2 della checklist.
5. Eseguire ingestion E2E live: `docker compose up postgres → apply migrations → setup_roles → seed → POST /api/regulations/upload` con `dm388_03.pdf` reale + API key Anthropic/Voyage funzionanti. Conta chunk attesi, esegui EXPLAIN ANALYZE → chiude items 1, 3, 4, 5 della checklist.
6. Spostare il check "regione inesistente" in `research_agent` (FASE 3.3) come da BP §05.4 → chiude item 7 (è proprio dove la BP lo vuole).

### Manutenzione

7. Ogni nuovo test mock aggiunto → riga in §1.
8. Ogni discrepanza REI-16 nuova → riga in §2.
9. Ogni risorsa esterna mancante incontrata → riga in §3.

---

## Indice mock count (sintesi a colpo d'occhio)

| Fase | Test totali | Di cui mock | Di cui senza debt | Debt aperto |
|---|---|---|---|---|
| 0 | 4 (health) | 4 | 0 | DB live |
| 1 | 40 (auth+seed+models) | 40 | ~10 unit puri Pydantic | DB live |
| 2.1 | 5 | 5 | 0 | #R1 |
| 2.2 | 18 (15 unit + 3 E2E) | 18 | 0 | #R1 |
| 2.3 | 8 | 8 | 0 | #R2 #R3 #R4 |
| 2.4 | 8 | 8 | tutti senza debt strutturale | #R9 (altri PDF) |
| 2.5 | 10 (con D17 test) | 10 | 2 (_to_pgvector) | #R2 |
| 2.6 | 8 | 8 | 3 (authz strutturali) | #R1 #R2 #R3 #R4 |
| 3.1 | 7 | 7 | 5 (introspezione TypedDict + decorator) | #R2 (checkpointer live) |
| 3.2 | 17 | 0 | **17** (matematica pura, no I/O) | **nessuno** |
| 3.3 | 13 | 13 | 7 (helpers deterministici) | #R1 #R2 #R4 #R9 (search/embed live) |
| 3.4 | 14 | 14 | 9 (parser+prompts pure + FIX-3 structural guard) | #R3 (Anthropic live per qualità slide JSON reale) |
| 3.5 | 2 mocked + 1 live skel | 2 | 0 (E2E orchestrazione tutta mockata) | #R1 #R2 #R3 #R4 (live test esiste ma mai eseguito) |
| **TOTALE** | **154 + 1 live** | **137** | **~53 senza debt** | **~101 con debt** |

> Lettura: il 100% dei test passa contro mock. ~85% ha un debito di verifica
> reale aperto. Nessun test del progetto, ad oggi (fine FASE 2), ha mai
> esercitato Postgres+pgvector live, Anthropic API live, Voyage API live, o
> un PDF normativo italiano vero.

---

*Mantieni questo documento come livello primario di trasparenza tecnica.
Se sparisce o smette di essere aggiornato, l'audit del progetto perde la sua
unica fonte sulla qualità effettiva (mock vs reale) dei test.*
