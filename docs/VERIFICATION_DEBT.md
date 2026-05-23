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
> **Ultimo aggiornamento:** 2026-05-23 — fine FASE 2 + REI-17 introdotta
> **Conteggio attuale:** 60 test mock, 17 discrepanze REI-16, 9 risorse mancanti

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
| D10 | 2.3 | `call_llm` definito in `ingestion_service.py` invece che `content_agent.py` | GAP di sequenza (2.3 < 3.4). Deciso con utente: opzione "minimale in ingestion". FASE 3.4 dovrà importarlo da qui. | accettato, **azione richiesta in FASE 3.4** |
| D11 | 2.3 | BP `timeout=120.0` hardcoded, io `settings.llm_request_timeout` | OPT-2 (no env hardcoded); valore default identico | accettato |
| D12 | 2.3 | `classify_chunk -> dict[str, object]`, `index_chunks` con `pool: object` | mypy strict; runtime invariato | accettato |
| D13 | 2.5 | Helper `_to_pgvector` aggiunto (BP passa `query_embedding` grezzo) | asyncpg non ha codec vector; literal `[a,b,c]` + `::vector` è interop standard. **Da validare contro DB live.** | **debito aperto — #R2** |
| D14 | 2.5 | Test su mock pool invece di "integrazione con dm388 ingerito" come dice il prompt | Gotcha #4 HANDOFF: pytest su mock; integration vera in E2E (mai eseguita) | **debito aperto — #R1 + #R2** |
| D15 | 2.5 | `pool: asyncpg.Pool` tipizzato (BP non tipizza) | mypy strict | accettato |
| D16 | 2.6 | `ingest_regulation_file()` orchestratore non verbatim BP | BP §10 dà solo firma endpoint. Composto Stage 1-4. Deciso con utente. Tocca `index_chunks` 2.3 (retroattivo) per fix `$N::vector`. | accettato |
| D17 | 2.6 / audit post-FASE-2 | Checklist FASE 2 item 7 "regione inesistente → errore" non implementabile in `knowledge_repo` (BP §06.3 non valida) — la validazione vive in `research_agent` BP §05.4 (FASE 3.3) | Documentato nel docstring + test `test_search_chunks_unknown_region_does_not_raise`; **la checklist FASE 2 contiene un item che logicamente appartiene a FASE 3** | flagged — possibile errore Master Plan |

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

---

## 4. Action items prioritizzati

### Sblocco immediato (sotto controllo dell'utente)

1. **[#R1]** Scaricare DM 388/2003 in `storage/pdfs/dm388_03.pdf` → sblocca D4, D9, test 1-23, parziale validazione item 1 checklist.
2. **[#R3 + #R4]** Confermare che le API key in `.env` sono valide e con budget → sblocca test reali Anthropic/Voyage.
3. **[#R2]** Decisione: introduciamo un marker `@pytest.mark.live` per test contro DB Docker? (proposta mia, non BP) — se sì lo aggiungo io, scrivo i live test minimi.

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
| **TOTALE** | **101** | **101** | **~15 senza debt** | **~86 con debt** |

> Lettura: il 100% dei test passa contro mock. ~85% ha un debito di verifica
> reale aperto. Nessun test del progetto, ad oggi (fine FASE 2), ha mai
> esercitato Postgres+pgvector live, Anthropic API live, Voyage API live, o
> un PDF normativo italiano vero.

---

*Mantieni questo documento come livello primario di trasparenza tecnica.
Se sparisce o smette di essere aggiornato, l'audit del progetto perde la sua
unica fonte sulla qualità effettiva (mock vs reale) dei test.*
