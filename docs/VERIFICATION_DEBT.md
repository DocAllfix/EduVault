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
> **Ultimo aggiornamento:** 2026-06-02 (4 fix UX coerenti post-F10 base: D-224 X chiusura tour driver.js (richiede onCloseClick handler esplicito v1.4), D-225 tabella corsi archiviati separata collassabile sotto la tabella principale (filtro client-side via TanStack select + query indipendente), D-226 hard delete endpoint `/courses/{id}/hard` con gate status=archived (cleanup FK manuale per generation_jobs + approved_courses, transazione atomica) + bottone "Elimina definitivamente" rosso in ArchivedCoursesSection, D-227 closeButton prop su Sonner Toaster (X nativa). Commit 4cef755. STORICO: F10 onboarding implementato + verificato in prod — D-223: sistema contestuale "Stripe Dashboard"-style con OnboardingBanner slim + HelpButton `?` topbar + LabelWithHelp tooltip always-available + 11 tour file `driver.js`. Stack ~10KB gzip, brand-coordinato rosa CFP. Verifica prod 13:02 UTC: dashboard banner + spotlight ring step 1/4 → step 2/4 OK, Course Studio 7 data-tour markers, LabelWithHelp `?` su Note relatore + Riferimento normativo. Fix StudioTopBar (Course Studio non usa shadcn Header standard). Commit e350b84 + 272d46e. STORICO: F-NEXT Fase 3 chiusa: sample-read PPTX render fidelity 10 slide tipiche corso `bffd7e42` ha rivelato 2 bug strutturali. **D-221** [PptxCanvasRenderer client-side bypassato in prod perché `last_rebuilt_at=NULL` su prima generazione → fallback PNG dispensa testo-only → fidelity ~4%]: fix `generation_service.py:660` popola `last_rebuilt_at=NOW()` + migration `015` backfill corsi storici (commit f599af4). Verifica prod 12:04 UTC: PptxCanvasRenderer attivo, slide 1 MODULE_OPEN fidelity passa da ~0% a ~95% (matching shape `nx_accent_v + nx_module_num + nx_module_underline + nx_module_title`). **D-222** [striscia rosa verticale nelle QUIZ slide: `slide_builder_v2.py:632` scriveva "Risposta corretta: A" 21 chars dentro shape 23×23 px → wrap char-per-char in verticale]: fix testo vuoto + sposto shape fuori slide a -100000 EMU (commit c495d4b). Quiz slide ora pulite per generazioni future; corsi esistenti richiedono click Rigenera. D-218 sample-read 60 slide M0 A/B test hard filter (3.3%→16.7% core stretto, cluster D.Lgs Titolo III Attrezzature eliminato, nuovo cluster Classificazione incendi creato, flag `V2_B3_STRONG_DOMINANCE_ENABLED=true` lasciato attivo). D-219 endpoint `POST /api/admin/users` aggiunto fuori piano per credenziali cliente (commit 57e8e90). D-220 onboarding tour multi-pagina "F10" non era in piano, da pianificare. STORICO: 2026-06-01 F-PERF 3 fasi: FASE 1 image dedup intra-corso `MAX_LIBRARY_REUSE=3` verificata su corso `af08e1d1` 4h Antincendio L1 — max usage per immagine 3x vs 30x baseline (commit 29a306d). FASE 2 Azure Speech opt-in dependency `azure-cognitiveservices-speech>=1.40` aggiunta in pyproject (commit 764973f) + Railway env vars `V2_AUDIO_PROVIDER_AZURE=true` + `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION=westeurope` configurati. FASE 3 ridotta a Scenario E parametrico: `_BATCH_SIZE 10→15` in `ingestion_service.py:623` (commit dc7e854) — parallelizzazione batch intra-modulo scartata per non sommare 5% degrado titolo regredito sopra 20% on-topic core gia rotto. Risorsa Azure OpenAI Italy North gpt-4.1-mini Global Standard 46M TPM configurata su nuovo endpoint `https://edu-llm-vault.openai.azure.com/` (sostituisce endpoint Foundry sbagliato che causava HTTP 400 BadRequest e fallback fallito a tutta la chain). LLM_PROVIDER=azure_openai primary. D-200 registrato (bias velocita-su-qualita-non-misurata in sessione lunga + lezione metodologica D-183 estesa). D-201 registrato (scope FASE 3 ridotto da multi-strategy a parametro singolo per preservare diagnostica pulita). SAMPLE-READ DISCIPLINATO corso `af08e1d1` M0 "MODULO 1 Principi della combustione" su 30 slide: **on-topic core 20% (6/30)**, pattern voce-to-slide drift identico a H8 baseline. Nessun commit ulteriore proposto al cliente come "qualita invariata" — verita: tempi piu rapidi (con E deployato), qualita NON ancora dove vogliamo. Rollback H8b verificato (`V2_B3_STRONG_DOMINANCE_ENABLED=false`). Pivot lavoro a cure qualita reali (skeleton lock + cap 6 + filtro top_section hard) NON ancora avviato — registrato come prossimo step. STORICO: 2026-05-31 — F8 CLEANUP A/B PER FAMIGLIA scaffolding chiuso. Backend `app/config.py`: 3 nuovi flag per-family `v2_drop_{segnaletica,prevenzione_generale,incidenti_preposti}_enabled` (default True = safety-net D10). `app/agents/research_agent.py`: gate per-family su 3 `_DROP_PATTERN_*` esistenti (Segnaletica linea ~830, M1 Prevenzione linea ~895, M3 Incidenti linea ~950). Quando flag=False su Railway env, drop-pattern skip + log structured `*_skipped_f8`. Promozione "rimozione fisica" pattern dopo approval cliente per famiglia. Tests 6/6 PASS (`test_f8_drop_list_gates.py`: existence, default True safety-net, env override pydantic-settings v2, indipendenza flag, regex compile sanity). mypy clean su nuovi flag/gate. **TOTALE post-MVP unit tests: 52/52 PASS** (F5: 20 + F6: 14 + F7: 12 + F8: 6). D-189 in DEBT (scope ridotto da A/B test full a scaffolding; copre 80% valore D10). STORICO: F7 AZURE SPEECH chiuso opt-in path. Backend: `app/services/ssml.py` con `(PAUSE Ns)→<break time="Ns"/>` SSML converter (12/12 unit test PASS: case insensitive, opt-s suffix, xml-escape, cap MAX_BREAKS=10, time-cap 10s). `app/services/audio_service.py` aggiornato con `_azure_tts_save` async wrapper Azure SDK (gated import, fallback automatico a edge-tts se package mancante o errore Azure). Selector flag-based: `settings.v2_audio_provider_azure AND azure_speech_key` → Azure; default → edge-tts (free). INSERT audio_tracks ora popola `provider` column (migration 012). Endpoint `/audio/{idx}/info` espone {provider, voice, duration_seconds} per UI badge. Frontend: `audio-player.tsx` con TanStack useQuery `audio-info` + Badge "Azure" brand-secondary signal premium quality (Sparkles icon). tsc -b strict + vite build CLEAN 4.66s. D-188 in DEBT (Azure opt-in vs piano "primary"; azure-cognitiveservices-speech dep opzionale, da aggiungere a `[tts-azure]` group quando cliente fornisce key). 46/46 unit test post-MVP PASS (F5: 20 + F6: 14 + F7: 12). STORICO: F6 CHAT STUDIO chiuso end-to-end backend+frontend. Su richiesta esplicita utente le 3 feature richieste consegnate: (a) memoria conversation cross-session via DB persistence + sliding window 12 msg in context LLM, (b) streaming SSE via instructor `create_partial` + frontend fetch+ReadableStream parser SSE + typing-effect cursor pulse, (c) prompt-caching-friendly structure (system prompt stabile + slide_context separato + history alternati user/assistant → Anthropic auto-cache via prefix invariato + Azure prompt_cache_key implicito). Scope F6: chat ancorata SLIDE (vincolo D7), NO tool-use multi-tool agente, NO chat libera per-corso. Backend: `app/services/chat_service.py` (chat_turn + chat_turn_stream + get_or_create_conversation + insert_message + list_messages + mark_message_applied), 3 endpoint REST in `courses.py` (`GET /chat/history`, `POST /chat` SSE rate 30/min, `POST /chat/messages/{id}/apply` idempotent). Frontend: `ChatPanel` con SSE parser manuale (fetch+ReadableStream — EventSource NO support Bearer Authorization), MessageBubble bubble user vs assistant + Anchor chip "Slide #N" cross-slide + patch preview con diff (title/body/notes) + Apply/Applicato badge. Integration: Tabs Quality/Chat nel right rail Course Studio (default Quality per non disturbare F4 workflow). Test 14/14 PASS (memory window, sliding skip tool/system, get_or_create conv hit/miss, insert+list roundtrip, idempotency 200/409/404). tsc -b strict + vite build CLEAN 4.45s. D-187 in DEBT. STORICO: F5 IMAGE LIBRARY + DIAGRAM ROUTER chiuso backend — 3/4 step verdi (.1+.2+.3+.4); tests 20/20 PASS (test_embeddings 9 + test_diagram_router 11). Backend nuovo: `app/services/embeddings.py` (voyage-multimodal-3 image/text), `app/services/image_library_service.py` (k-NN cosine + GIN fallback), `app/services/diagram_router.py` (7 SVG heuristic ≥0.5 confidence), `app/db/migrations/011_image_library_unique.sql`, 2 endpoint REST (`/image/library/search` rate 60/min + `/api/admin/images/library` paginato). Integration: cascade tier-0 library in `image_service._resolve_query_urls._one` PRIMA di Pexels (transparent: pool=None → skip; threshold 0.30); usage_count++ best-effort. Frontend `image-picker.tsx` riscritto con shadcn Tabs Library/Web default Library, LibraryCard con hover license chip + score badge + Tooltip attribution. tsc -b strict + vite build CLEAN 7.11s. Discrepanze D-184 (cascade ordering invertito Pexels→Library), D-185 (seed scope ridotto: NO scraping auto, manifest manuale), D-186 (8 SVG nuovi + ISO7010 posticipati). Sequenza skill applicata REI-14: [DS] no token nuovi → [FD] brief in commento file → [IMP] mantieni Dialog + add Tabs → [UIS] grid 4-col + hover overlay + brand-primary score chip → [SHA] Tabs+Badge+Tooltip riusati. STORICO: F1 CATALOG UI ADMIN chiuso — backend `catalog_service.py` + 6 endpoint admin (`/api/admin/catalog/{summary,list,detail,update,approve,unapprove,bulk-approve}`) + frontend `/admin/catalog` con tabella shadcn + summary cards + filtri + bulk approve + dialog dettaglio moduli + CTA dalla pagina Admin. mypy clean, tsc clean, vite build verde 5.57s. Discrepanza D-183 registrata (scope MVP ridotto: solo UI review+approve dei 44 entries esistenti, scraping script + research_agent branch posticipati a post-flip flag `v2_catalog_from_db`). Commit 86eeca8 push deploy SUCCESS. **MVP gate residuo**: 0 — tutti i pezzi (rollback H8b + F4/F4b + F9 + F3 + F3.AI + F1) completati). PRECEDENTE: 2026-05-31 — F3.AI implementata (richiesta utente): rename "Approva scheletro"→"Approva struttura", 3 azioni LLM per-voce (rephrase/operational/alternatives) + free-text "Chiedi all'AI" per-modulo. Backend: `app/services/skeleton_ai_edit_service.py` + 2 endpoint courses.py (rate-limited, pure-proposal). Frontend: `skeleton-ai-edit.tsx` con DiffAcceptDialog + AlternativesDialog + ModuleAiPrompt integrati in skeleton-review.tsx. Discrepanza D-182 registrata (plan §F3 dichiarava edit MANUALE, chat NL demandata a F6 D7 — prompt utente prevale REI-16). mypy clean sui nuovi file, tsc clean. **PULIZIA POST-B4 COMPLETA pre-H8 (storico): D-161 + D-177 + D-178 V1.5 chiusi end-to-end (D-175 false positive, V1 saltato per disciplina anti-curatela). 163/163 test PASS, mypy/ruff clean, backfill prod applicato (accordo_2011 effective_until + 13 chunks external_reference). Patologia slide 67 ANT L1 ("Decreto ministeriale 3 agosto 2015") riconosciuta da V1.5 nei test logici. Tempi consuntivi totali: ~3 ore vs stima B2 originale 3-3.5 giorni. Razionale tempo: D-175 false positive (no fix), D-161/D-177/D-178 V1.5 hanno pattern stabilito da precedenti metodologici (D-168 filter al join, B3 metadata+backfill). D-180 registrato (chunk_id → DB lookup gate per diagnosi nx_normative_ref). D-181-bis backlog (display_citations field strutturato post-E2E controllo). Prossimo: E2E ANT L1 finale + sample-read insieme + semaforo H8.**

**ANALISTA SIGN-OFF E2E HACCP (2026-05-30) — D3 universale, due osservazioni a verbale:**
- **(a) pura DIMOSTRATA UNIVERSALE**: 4 audit + 1 E2E + verifica indipendente sul render (pattern più larghi: Coordinatore CSE/CSP, fascicolo opera, POS, antincendio, primo soccorso, edilizia/cantiere/amianto, DPI industriali) → tutti zero, 1 falso positivo verificato (slide 279 "preposto" = significato generico HACCP "responsabile di settore", non riferimento al corso Preposti). Cross-corso reale = zero su 336 slide. **D3 production-ready come fondazione, non era fortuna 81/08.**
- **D-169 [a mio carico]**: ogni nuovo stato semantico del flusso DEVE essere accompagnato da migration CHECK constraint nel suggerimento iniziale, non scoperto in E2E. Stessa famiglia di D-162/163 (cura applicata al livello giusto). Per D3 avrei dovuto suggerire migration 007 al momento di definire `skeleton_pending` come stato nel modello, non dopo che CheckViolationError ha colpito.
- **D-169-bis [audit richiesto pre-ground-truth]**: D-168 quasi certamente NON è l'unico filtro silenzioso. Scrematura veloce di tutti i `WHERE` di filtraggio in `knowledge_repo.search_chunks` + altre query retrieval/recall: filtri su region (D-168, fixing), language (possibile multilinguismo Reg CE?), regulation_type, effective_date, status. Non per fixare tutto: per **listare i filtri attivi e razionale aggiornato**, evitando di scoprire D-170/171/172 uno a uno durante la calibrazione. Mezza giornata.

**DIRETTIVE FINALI ANALISTA POST-E2E (2026-05-30):**
1. **Fix D-168 PRIMA del ground-truth**, confermato. Argomentazione: soglie relative su distribuzioni che includono caso BM25-only producono parametri sbilanciati. Post-fix: retrieval di prova HACCP M3 voce 1 atteso top_score >0.6 (corpus c'è, 147 chunk Reg CE 852).
2. **Audit D-169-bis** stessa finestra del fix D-168.
3. **Ground-truth = 5 moduli, non 4** (regimi distinti):
  - GEN M1 = regime denso, corpus saturo (top 0.99, media 0.75)
  - GEN M2 = regime cross-titolo intra-corpus (da misurare)
  - PRE M3 = regime sparso, corpus moderato (top 0.64, media 0.10)
  - ANT M0 = regime sparso post-ingestione (top 0.81, media 0.11)
  - **HACCP M2 = regime EUROPEA post-D-168** (da misurare, dovrebbe assomigliare a GEN/PRE per densità)
4. **Classificazione IN COPPIA**: io mando i top-30 grezzi di 1 voce per modulo (150 chunk totali), io faccio una prima classificazione on-topic/adjacent legittimo/off-topic chiaro con motivazione testuale per i non ovvi, analista rivede e corregge dove l'esperto-utente del cliente avrebbe deciso diversamente. Da 4-6h a 1-2h in coppia; classificazione esplicita in tabella diventa oracolo ricalibrabile in futuro.

**D-169** [a mio carico, 2026-05-30]: mancata migration 007 al momento di definire skeleton_pending. Pattern preventivo: ogni nuovo stato semantico del flusso (status) deve essere accompagnato da migration CHECK constraint nel suggerimento iniziale, non scoperto in E2E. Discovery via CheckViolationError costo: 1 ciclo HACCP perso + debug + applicazione migration prod. Lezione: stessa famiglia di D-162/163 (cura applicata al livello giusto).

**D-169-bis** [analista, 2026-05-30, audit pre-ground-truth]: scrematura tutti i `WHERE` di filtraggio in query retrieval/recall (knowledge_repo.search_chunks, recall_hybrid BM25 corpus load, kg_1hop hydration). Listare ogni filtro attivo + razionale aggiornato. Evitare di scoprire D-170/171/172 silenziosamente durante calibrazione B2. Filtri da auditare: region, language, regulation_type, effective_date, status, is_current. Output: tabella `{file:linea, filtro_SQL, razionale_documentato, conformità_intent}`.

### D-169-bis AUDIT — tabella filtri silenziosi nelle query retrieval/recall (2026-05-30)

**Schema rilevante (fonte: `001_initial.sql` + `005_v2_foundation.sql`):**
- `regulations`: `id, title, type, issuing_body, issue_date, effective_date, region, status('VIGENTE'|'ABROGATA'|'MODIFICATA'), slug`. **NESSUNA colonna `language`** → il rischio "filtri multi-lingua" è teorico, non applicabile (non esiste filtro impostabile).
- `regulation_chunks`: `id, regulation_id, article, paragraph, hierarchy_path, body, chunk_type, tags, embedding, content_hash, is_current(bool)`.
- `regulation_chunk_edges`: `id, src_chunk_id, dst_chunk_id, kind, weight, source('deterministic'|'llm_verified'), extraction_context`.

**Filtri attivi in retrieval/recall (esclude write-paths e dashboard count):**

| File:linea | Filtro SQL | Razionale documentato | Conformità intent |
|------------|-----------|----------------------|-------------------|
| `knowledge_repo.py:41` | `regulations WHERE status = 'VIGENTE'` (in `resolve_slugs_to_ids`) | Non genero corsi su normativa ABROGATA/MODIFICATA. | **OK**. Architetturale corretto: ABROGATA → fonte non efficace; MODIFICATA dovrebbe essere transient di backfill. Da rivedere SE in futuro si vuole supportare citazione storica di norma abrogata (raro in safety formativa). |
| `knowledge_repo.py:90` | `rc.regulation_id = ANY($2::uuid[])` (in `search_chunks`) | Parametrico: filtra ai regulations del catalog entry del corso. | **OK**. Filtro parametrico voluto, niente leakage cross-corso. |
| `knowledge_repo.py:91` | `rc.is_current = true` (in `search_chunks`) | Esclude chunk superseded da re-ingestione. | **OK con caveat**. Pattern de-duplicazione: re-ingestione marca i vecchi `is_current=false`. **DA TENERE OCCHIO**: se il delta-update marca by-mistake `is_current=false` su chunk validi → recall_size cala silenziosamente. Verificare almeno 1 volta in audit periodico che `COUNT(WHERE is_current=true) ≈ N_chunk_attesi`. |
| `knowledge_repo.py:92-93` | `r.region IN ('NAZIONALE','EUROPEA') OR r.region = $3::text` (post D-168 fix) | NAZIONALE = legge italiana applicabile ovunque; EUROPEA = Reg. CE/UE direttamente applicabili senza recepimento; region-specific solo se richiesta. | **OK post-fix D-168**. Audit chiuso su region. |
| `retrieval_v2.py:255-256` | `regulation_chunks WHERE regulation_id = ANY($1) AND is_current = true` (in `recall_hybrid` per caricare body BM25) | Carica il corpus BM25 in-memory per la stessa scope di regulation della query. | **OK con caveat D-168-bis**: questa query **non filtra per region** (BM25 lato Python non lo fa, e ha senso perché regulation_id è già limitato dal catalog entry). **Ma è proprio per questo che D-168 è stato compensato silenziosamente** — BM25 trovava i chunk Reg CE 852 dove cosine non li vedeva. Nessuna correzione richiesta: BM25 deve attingere a tutto il corpus delle regulation_ids; il filtro region è semanticamente errato a questo livello. |
| `retrieval_v2.py:310` | `regulation_chunks WHERE rc.id = ANY($1) AND rc.is_current = true` (idratazione chunk vincitori BM25 in `recall_hybrid`) | Idrata i chunk emersi via BM25 che non sono in cosine_chunks. | **OK**. Filtro id-based + is_current coerente con knowledge_repo. |
| `retrieval_v2.py:500` | `regulation_chunk_edges WHERE src_chunk_id = ANY($1) AND source = 'deterministic'` (in `expand_via_kg_1hop`) | F2.8 VAA-b: solo edge deterministici (regex citazione + gerarchia parsata). Gli edge `llm_verified` esistono ma sono esclusi dal 1-hop traversal per qualità (rumore residuo amplificato in dedup). | **OK con flag**. Comportamento intenzionale dietro feature flag `kg_traversal_enabled`. Se in futuro A/B mostra beneficio degli `llm_verified` in 1-hop, riattivabile via parametro. |
| `retrieval_v2.py:533` | `regulation_chunks WHERE id = ANY($1) AND is_current = true` (idratazione destinazioni edge KG 1-hop) | Idrata chunk destinazione degli edge seguiti. | **OK**. |
| `graph_service.py:145, 304, 455, 522, 672` | `regulation_chunks WHERE regulation_id = $1 AND is_current = true` (load chunk in `_ChunkResolver`, sibling extraction, llm_edges candidates, body fetch, deterministic extraction) | Caricamento corpus per estrazione edge. | **OK**. Scope strict per regulation. |
| `content_agent.py:187` | `regulation_chunks WHERE id = ANY($1)` (lookup `citation_label` per chunk in slide) | Solo `id = ANY`, **niente `is_current`** | **CONSIDERARE**: se uno chunk usato in retrieval è poi marcato `is_current=false` da re-ingestione, citation_label resta lookup-abile (dato che il filtro non c'è). Per il momento OK perché il chunk_id arriva da `relevance_score` calcolato up-stream con `is_current=true`. Race-condition teorica (re-ingestione mid-pipeline) ma non vissuta nei demo. Annotato come pattern, non fix. |
| `generation_service.py:499-500, 510-511` | `regulation_chunks WHERE id = ANY($1) [+SUBSTRING regulation_id prefix]` (citation post-build) | Lookup citation_label e short_title per slide finali. Senza `is_current=true`. | **OK**: stesso ragionamento di content_agent — l'id è di chunk già usato up-stream. |

**Conclusione audit D-169-bis (2026-05-30):**
- **Filtri sospetti rimasti: 0** — tutti i filtri di retrieval/recall hanno razionale aggiornato e nessun altro produce uno scarto silenzioso analogo a D-168.
- **Filtri `is_current=true` da osservare**: la disciplina di marcatura `is_current` in `ingestion_service.delta_update` rimane il punto di vulnerabilità più probabile per silent drop. Non è materia di fix preventivo: è da osservare nel monitoring (`cosine_size` vs `bm25_size` divergenze inattese).
- **Race condition citation_label**: pattern teorico, non fix preventivo. Tracciabile se mai succederà.
- **Nessun filtro su `language` esistente né impostabile** — schema senza colonna language. Il rischio era teorico.
- **D-169-bis CHIUSO**: nessun D-170/171/172 emerso. Procedere col ground-truth.

### D-168 VERIFICA POST-FIX HACCP M3 voce 1 (2026-05-30, via TCP proxy zephyr:11820)

**Setup**: course HACCP E2E (`309ea418`), M3 "Autocontrollo e documentazione", voce 1 `Fondamenti normativi dell'autocontrollo HACCP` (retrieval_query: "normativa italiana e comunitaria che disciplina l'obbligo di autocontrollo secondo HACCP e i riferimenti del D.Lgs 81/08"), region=LOMBARDIA.

**Risultato tecnico — fix funziona, retrieval bilanciato:**
- `cosine_size`: **0 → 147** ✅ (Reg CE 852/2004 region=EUROPEA ora entra nel cosine search)
- `bm25_size`: 105
- `fused_size`: 147 (RRF k=60)
- Tempo recall: 31 ms

**Risultato qualitativo — top_score NON è risalito:**
- `top_score rerank Cohere`: 0.367 pre-fix → **0.339 post-fix** (delta -0.028, dentro jitter Cohere ±0.05)
- Distribuzione top-30 post-fix: max=0.339, min=0.037, **media=0.084** (regime piatto basso)
- `under_alert_threshold (0.45)`: **still true**
- Atteso `>0.6` (era la mia ipotesi prima del test): **NO**

**Diagnosi: il fix D-168 era doveroso ma NON è la causa del top_score basso HACCP.**

Il D-168 ha riparato un fallimento silenzioso (cosine completamente azzerato per regulations EUROPEA → recall degradato a BM25-only invisibile). Quel fix era strutturale e va tenuto.

Ma la diagnosi più approfondita ora mostra che il top_score basso su HACCP M3 voce 1 ha **due cause distinte sovrapposte:**

1. **DLGS_193_2007 NON è in DB**: il slug `dlgs_193_2007` non risolve (`Regulations risolte: 1` invece di 2 — solo `reg_ce_852_2004`). Il D.Lgs 193/2007 è proprio il decreto italiano che recepisce e dà attuazione al Reg CE 852/2004 sull'igiene alimentare. È **probabilmente il chunk più rilevante** per "normativa italiana che disciplina l'obbligo di autocontrollo HACCP" e manca dall'ingestione. **Annotato come #R14** [risorsa esterna mancante: ingestire D.Lgs 193/2007]. NON bloccante per la calibrazione B2 perché il regime "low-confidence-uniformly" che vediamo qui *è esso stesso* un regime valido di calibrazione (forse il più stringente).

2. **Cohere rerank sul corpus Reg CE 852 da solo è genuinamente low-confidence** per la query specifica: il top-30 mostra `Allegato I del trattato`, `Art. 251 Direttiva modificata 1882/2003`, `Art. 5 principi HACCP`, `Art. 18 igiene operativa` — tutti pezzi del Reg CE 852 *generali*, non specificamente sulla *normativa* dell'autocontrollo (perché quel concetto vive in 852 implicito + nel 193/2007 esplicito, che manca).

**Implicazioni per B2 calibrazione (5 moduli):**
- GEN M1: regime denso (top 0.99, media 0.75)
- GEN M2: regime cross-titolo intra-corpus (da misurare)
- PRE M3: regime sparso, corpus moderato (top 0.64, media 0.10)
- ANT M0: regime sparso post-ingestione (top 0.81, media 0.11)
- **HACCP M2/M3: regime LOW-CONFIDENCE-UNIFORMLY (top 0.34, media 0.08)** — nuovo regime emerso, è esso stesso utile per calibrazione perché copre il caso "corpus limitato + topic specialistico + Cohere senza confidenza alta su nulla".

La soglia RELATIVA su HACCP M3 (`< max - delta`) avrà comportamento interessante: max basso (0.339) + media bassa (0.084) → `delta` piccolo (es. 0.1) lascerebbe passare i primi ~6-8 chunk. Se ground-truth manuale dice che SONO on-topic (Art. 5 principi HACCP, Art. 18 igiene operativa, Allegato II requisiti), la soglia funziona; se NO, è regime che richiede `delta` percentile-based invece di assoluto.

**#R14** [risorsa esterna mancante, 2026-05-30]: ingestire D.Lgs 193/2007 (decreto italiano di attuazione Reg CE 852/2004). Senza, ogni corso HACCP italiano avrà retrieval normativo-italiano incompleto. Non bloccante per D3 (lo skeleton è clean, le slide finali citano Reg CE 852 correttamente), non bloccante per B2 (il regime HACCP è utile come tale per calibrazione). Bloccante per QUALITÀ HACCP finale al cliente — il 193/2007 è citato in ogni manuale HACCP italiano serio.

**Conclusione STEP 3 (D-168 verifica)**: fix tecnico chiuso (cosine_size=147 ≠ 0). Top_score basso non è artefatto del bug, è regime reale del corpus. Procedere col ground-truth a 5 moduli; l'ordine di priorità non cambia.

### STEP 4 ESTRAZIONE (2026-05-30) — 2 scoperte che cambiano il regime di calibrazione

Eseguito `scripts/extract_groundtruth_5moduli.py` (TCP proxy zephyr:11820). Risultati:

| Modulo | top_score | media | n | Note |
|--------|-----------|-------|---|------|
| GEN M1 v1 (già) | 0.994 | 0.747 | 30 | denso saturo |
| **GEN M2 v1 (estratto oggi)** | **0.988** | **0.468** | 30 | **NON cross-titolo-sparso come ipotizzato — è DENSO** |
| PRE M3 v1 (già stress) | 0.642 | 0.099 | 30 | sparso, on-topic in fondo |
| ANT M0 v1 (già stress) | 0.814 | 0.114 | 30 | sparso post-DM 03/09 |
| **HACCP M2 v1 (diagnostico)** | **0.462** | **0.019** | 30 | sopra alert ma media bassissima |
| **HACCP M3 v1 (ri-misurato via autogen)** | **0.642** | 0.065 | 30 | **NON 0.339 come STEP 3 — vedi sotto** |

**SCOPERTA 1 (regime emergente) — GEN M2 è regime denso, non sparso.**
Ipotesi analista pre-estrazione: "GEN M2 = cross-Titolo intra-corpus, regime diverso da PRE M3". **Empiricamente FALSO** per la voce 1 generata: top=0.988, media=0.468, distribuzione monotona decrescente bella. La preoccupazione cross-Titolo era V2-specifica (drop-list + expansions hardcoded che inquinavano); con (a) pura + by-subtopic via autogen LLM, GEN M2 si comporta come GEN M1. **Il quinto regime ipotizzato NON esiste empiricamente. I regimi reali sui 5 moduli sono 3, non 5**:
- DENSO: GEN M1, GEN M2 (top>0.95)
- SPARSO: PRE M3, ANT M0 (top 0.6-0.8, media <0.15)
- LOW-CONFIDENCE-UNIFORMLY: HACCP M3 alla "retrieval_query letterale" (top 0.339, media 0.084) → vedi SCOPERTA 2

**SCOPERTA 2 (autogen vs retrieval_query letterale) — IMPORTANTE, da risolvere con analista.**
HACCP M3 voce 1 misurato due volte:
- STEP 3 (`verify_d168_haccp_m3.py`): chiamato `recall_hybrid(query=retrieval_query_letterale)` + `rerank_chunks(query=retrieval_query_letterale)`. Query: "normativa italiana e comunitaria che disciplina l'obbligo di autocontrollo secondo HACCP e i riferimenti del D.Lgs 81/08". → **top_score=0.339** (regime LOW-CONFIDENCE-UNIFORMLY).
- STEP 4 (`extract_groundtruth_5moduli.py`): chiamato `retrieve_for_module(module_title=retrieval_query_letterale)` che **internamente fa autogen LLM** prima del recall. Autogen riformula in: "normativa italiana comunitaria obbligo autocontrollo HACCP requisiti Regolamento CE 852 2004 disposizioni D Lgs 81 08 sicurezza sul lavoro gestione rischi alimentari". → **top_score=0.642** (sopra alert, NON LOW-CONFIDENCE-UNIFORMLY).

**Verificato in codice** (`app/services/skeleton_service.py:206-211`): `materialize_module_from_skeleton` chiama `retrieve_for_module(module_title=item.retrieval_query, ...)` → entra in `retrieve_for_module` → `autogen_module_query` riformula la query prima del recall.

**Quindi il path di produzione è**: `skeleton.retrieval_query` (instructor LLM) → **autogen** (LLM riformula in più keyword-heavy) → cosine+BM25 → rerank Cohere. **L'autogen rifrasa la retrieval_query salvata, NON la usa letteralmente.**

**Implicazione**: il regime LOW-CONFIDENCE-UNIFORMLY HACCP M3 che avevo descritto all'analista era misurato sulla query "sbagliata" rispetto al path prod. In produzione HACCP M3 voce 1 ha top=0.642 (sopra alert), non 0.339 (sotto alert). **Il "nuovo regime" del Bivio A potrebbe NON esistere in produzione.**

**Però c'è un dato a contraddizione**: il log E2E HACCP 29-maggio del passaggio reale prod loggava `top_score=0.367 under_alert_threshold=true` su HACCP M3 (lo stesso modulo, lo stesso course_id, lo stesso path materialize_by_subtopic). Quel 0.367 sembra coerente con la "retrieval_query letterale" (0.339 oggi) e non con l'autogen (0.642 oggi). Possibili spiegazioni:
- (a) autogen LLM non-deterministico: stessa query in input, prompt instructor stochastic → output query diverso fra le 2 esecuzioni → top_score diverso. Plausibile: stochastic LLM con temperature default → varianza output.
- (b) la run E2E del 29 ha avuto un autogen "sfortunato" (riformula peggiore della letterale), oggi ha avuto un autogen "fortunato" (riformula migliore). Plausibile se temperature > 0.
- (c) c'è un branch che bypassa autogen quando già c'è retrieval_query (NON ho trovato evidenza nel codice — `retrieve_for_module` chiama sempre autogen).

**Annotato come D-170** [autogen LLM stochastic introduce varianza di retrieval su stessa voce skeleton]: la pipeline può produrre regimi diversi (LOW-CONFIDENCE vs sparso) per la stessa voce skeleton in run successive a causa della variabilità autogen. Questo è un'aggravante per la calibrazione B2: la soglia relativa ha senso solo se la distribuzione è ripetibile, ma se autogen cambia la distribuzione, la soglia oscilla.

**Annotato come #R15** [need analyst decision]: dove parte la calibrazione B2 — sulla retrieval_query letterale dello skeleton (deterministica, stato logico stabile) o sull'output autogen (production-real ma stochastic)? Sono due dataset di calibrazione **strutturalmente diversi**.

**ESEGUITO ESTRAZIONE STEP 4.a (GEN M2) + STEP 4.b (HACCP M2 diag) + STEP 4.b-bis (HACCP M3 ri-misurato via path prod)**. Report: `storage/ab_test_results/GROUNDTRUTH_5MODULI_RAW.md`. First-pass classify NON ancora compilata: prima briefing analista su SCOPERTA 1 (no quinto regime) + SCOPERTA 2 (autogen stochastic).

### D-170 — RISOLTO 2026-05-30 (sign-off analista C + verifica two-run)

**D-170 — "Stocasticità inattesa in path 'deterministico per design'."** Autogen LLM era invocato nel path `materialize_module_from_skeleton` (D3) anche quando la `retrieval_query` in input era già semantica (scritta da instructor structured nello skeleton-generator). Effetto: stessa query in input produceva distribuzioni recall diverse run-by-run (top_score osservato da 0.339 a 0.642 su HACCP M3 voce 1). Risolto separando il path D3 (`retrieve_for_subtopic`, deterministico, niente autogen) dal path legacy by-title (`retrieve_for_module`, autogen necessario perché `module_title` è generico). **Pattern generale**: in ogni componente di pipeline, prima di chiamare un LLM, chiediti se l'input è già nella forma che ti serve. Riformulare via LLM un testo già LLM-generato è raddoppio di entropia senza valore informativo. È la sorella di D-160 ("metrica regex secondaria, sample-read manuale primaria") applicata alla composizione di LLM call: la composizione cieca di LLM produce stocasticità composta, e il rimedio è sempre architetturale (non chiamare il secondo LLM) prima che operativo (mediare le run).

**Implementazione (commit prossimo):**
- `app/services/retrieval_v2.py`: split in `retrieve_for_module` (path V2 legacy, fa autogen) + `retrieve_for_subtopic` (path D3, NO autogen) + helper privato `_retrieve_pipeline` (core recall→rerank→KG condiviso). Nomi affermativi al modello concettuale (analista, no flag `skip_autogen` al negativo).
- `app/services/skeleton_service.py:materialize_module_from_skeleton`: caller aggiornato a `retrieve_for_subtopic(retrieval_query=item.retrieval_query, …)`. Rimossi parametri morti `course_target`, `normative_slug` (non più usati dopo lo skip autogen).
- `app/services/generation_service.py`: caller di `materialize_module_from_skeleton` aggiornato + rimossa variabile morta `normative_slug`.
- `tests/unit/test_retrieval_v2_subtopic.py`: 2 test verdi.
  - `test_retrieve_for_subtopic_does_not_call_autogen`: assert `autogen_module_query.assert_not_awaited()` + verifica che recall+rerank ricevono la query LETTERALE in input.
  - `test_retrieve_for_module_still_calls_autogen`: regression per non rompere il path V2 by-title.

**Verifica determinacy (`scripts/verify_d170_determinacy.py`, 2026-05-30 11:10, TCP proxy zephyr:11820):**
- Two-run sulla stessa retrieval_query HACCP M3 voce 1.
- Δ top_score = **0.0000** (≤ ε jitter Cohere 0.05).
- top-10 chunk_id list **identica fra le run**.
- `bm25_size=105`, `cosine_size=147`, `fused_size=147` identici.
- **[PASS]** retrieve_for_subtopic deterministico al 100% (ZERO stocasticità residua, anche sotto il jitter Cohere atteso).

**Difesa empirica contro drift architetturale (analista directive):**
Conserviamo i numeri pre-fix come ground-truth della varianza eliminata.

| Misurazione | top_score | Path | Note |
|-------------|-----------|------|------|
| HACCP M3 v1 STEP 3 (via recall_hybrid+rerank diretti) | 0.339 | letterale | regime LCU |
| HACCP M3 v1 STEP 4 (via retrieve_for_module → autogen) | 0.642 | autogen riformula | sopra alert |
| HACCP M3 v1 E2E del 29-maggio (log prod) | 0.367 | autogen riformula | sotto alert |
| **HACCP M3 v1 RUN 1 post-refactor C** | **0.3388** | letterale (no autogen) | deterministico |
| **HACCP M3 v1 RUN 2 post-refactor C** | **0.3388** | letterale (no autogen) | identico a RUN 1 |

La forbice 0.339 ↔ 0.642 mostrava una varianza di 0.30 punti su stesso input. Post-refactor C: varianza 0.0000. Se in futuro qualcuno proporrà "rimettiamo autogen anche su D3, dai", questa tabella è la prova empirica del motivo per cui non si fa.

### SCOPERTA 1 — GEN M2 denso, NOT cross-titolo sparso (registrata fuori da D-numbers — è confirmation, non bug)

GEN M2 voce 1 (Organizzazione della prevenzione): top=0.988, media=0.468, distribuzione monotona-decrescente. Il regime ipotizzato pre-estrazione ("cross-titolo intra-corpus difficile come PRE M3") **non esiste empiricamente** dopo (a) pura + retrieval by-subtopic deterministico.

**Pattern confermato (analista):** la patologia cross-titolo intra-corpus di V2 era artefatto del retrieval V2 (drop-list `_DROP_PATTERN_*` + 38 query expansions `MODULE_QUERY_EXPANSIONS` hardcoded), NON proprietà strutturale del corpus 81/08. Il refactor sta togliendo cerotti che mascheravano nulla — non sta nascondendo un problema reale dietro una nuova architettura, sta rivelando che il problema apparente era il cerotto.

**Conseguenza per calibrazione B2**: i 5 moduli del ground-truth coprono **3 regimi reali**, non 5:
- DENSO: GEN M1, GEN M2 (top >0.95, media >0.45) — controllo negativo, B2 non deve mai escludere il cuore qui
- SPARSO: PRE M3, ANT M0 (top 0.6-0.8, media <0.15) — caso di calibrazione primario
- LOW-CONFIDENCE-UNIFORMLY: HACCP M3 (top 0.34, media 0.08) — caso stress di calibrazione, B2↔B4 dipendenza

Peso decisionale asimmetrico ma ground-truth oracolo umano resta sui 5 moduli per completezza.

### CHIARIMENTO ETICHETTA "GEN M1" (2026-05-30, post analista domanda 8)

Catalog `formazione_lavoratori_generale` ha 4 moduli:
- M1 catalog index 0 → "Concetti di rischio"
- M2 catalog index 1 → "Prevenzione e protezione"
- M3 catalog index 2 → "Organizzazione della prevenzione"
- M4 catalog index 3 → "Diritti e doveri"

**"GEN M1" della settimana scorsa** (audit 2026-05-29 in `audit_d3_skeleton_gen_m1.py`) usava `module_title="Prevenzione e protezione"` (M2 del catalog reale), voce 1 "Definizione e finalità della prevenzione e protezione" → top 0.994 media 0.747 (DENSO).

**"GEN M1" di oggi** (extract_groundtruth_5moduli.py 2026-05-30) usa `module_title="Concetti di rischio, danno, prevenzione, protezione"` (M1 del catalog), voce 1 "Definizione di rischio e sue caratteristiche principali" → top 0.7945 media 0.1285 (SPARSO con mis-ranking).

**NON è regressione**: sono 2 moduli GEN diversi su 2 sub_topic diversi. Etichetta "M1" ambigua nel mio piano. Quadro regimi aggiornato:
- GEN "Prevenzione e protezione" v1 = DENSO 0.99 (settimana scorsa)
- GEN "Organizzazione della prevenzione" v1 = DENSO 0.998 (oggi)
- GEN "Concetti di rischio" v1 = SPARSO 0.79 (oggi)
- PRE M3 v1 = SPARSO 0.73 (oggi)
- ANT M0 v1 = SPARSO 0.68 (oggi)
- HACCP M3 v1 = LCU 0.34
- HACCP M2 v1 = LCU 0.21

Implicazione meta: dentro lo stesso corso GEN, sotto-temi diversi producono regimi diversi. Per il ground-truth questo non cambia che 5 moduli sono ok (sono campioni di 5 voci 1 distinte attraverso 4 corsi). Ma sample-read disconfermativa GEN M2 (Organizzazione della prevenzione voce 1) diventa più importante: serve a capire se DENSO 0.998 è "denso vero (top-15 = cuore organizzativo D.Lgs)" o "denso apparente (Cohere uniformemente generoso, mis-rank uguale ai 'sparsi')".

### D-171 — Cohere rerank mis-ranking strutturale su top-1/top-2 (2026-05-30, analista formalizza review 17)

**D-171 — "Il rerank Cohere multilingual-v3 ha mis-ranking strutturale su top-1/top-2 quando la retrieval_query contiene riferimenti normativi specifici (Art. X, D.Lgs Y)."** Il fenomeno è universale ai regimi (osservato su GEN "Concetti di rischio" sparso, PRE M3 sparso, ANT M0 sparso post-ingest), non specifico ai moduli ombrello. La causa: la query auto-generata via LLM cita articoli/decreti per ancorare il dominio, ma Cohere reputa "topicalmente affini" chunk che menzionano quegli stessi articoli in **altri contesti** (es. Allegato I "classi di laurea esonero formazione" menziona Art. 2 in significato di "definizioni del decreto"; chunk reale on-topic Art. 222 "Definizioni agenti chimici" a rank 21 con score 0.0274).

**Implicazione su B2**: la funzione di B2 non è "filtro di rumore di superficie su regimi sparsi" ma "**ricostruzione di ranking title-aligned sopra un ranker topicalmente-largo strutturalmente inaffidabile sui primi-rank quando la query è normativamente specifica**". Cambia il modello mentale del filtro: B2 non lavora SOLO sui regimi sparsi/LCU, lavora anche sui regimi che credevamo densi (perché mis-ranking è universale).

**Possibili soluzioni in ordine di invasività (decidere DOPO ground-truth):**
- (a) B2 come **ri-ranking secondario** via Voyage embedding diretto sul subtopic (non solo filtro a soglia). Cosine(chunk.body_emb, sub_topic.text_emb) calcolato direttamente su tutti i top-30 reranked → ri-ordina o ri-pesa il ranking Cohere senza fiducia incondizionata.
- (b) Fine-tuning cross-encoder italiano-normativo (oneroso, mesi).
- (c) Riformulare retrieval_query in skeleton senza riferimenti normativi specifici (sposta il problema, perde l'ancora che già esiste in skeleton, possibile peggioramento del recall).

**Tendenza**: (a). Richiede di calcolare cosine_to_subtopic via Voyage (input già in DB chunk.embedding 1024-dim, sub_topic da embedare), poi formula B2 relativa = ri-pesa rerank Cohere con cosine Voyage. È vicino al "B2 cosine Voyage diretto + soglia relativa" che l'analista aveva descritto nelle direttive originarie, ma in versione "ri-ranking" non "filtro a soglia". Il ground-truth oracolo umano resta lo stesso (classificazione manuale on-topic/adjacent/off-topic), perché serve a stabilire la verità su cui valutare ENTRAMBE le formule B2 (filtro-a-soglia vs ri-ranking).

**Sample-read disconfermativa GEN M2 v1 (next)** discrimina fra esito 1 (DENSO vero → B2 filtro basta) ed esito 2 (DENSO apparente → B2 ri-ranking necessario). Costo 20 min, decisione architetturale.

### D-171 ESITO 2 confermato + D-171-bis (Cohere collo di bottiglia top-30, 2026-05-30)

**ESITO 2 confermato empiricamente**: sample-read disconfermativa GEN M3 "Organizzazione della prevenzione" v1 (post predizione 8 chunk attesi PRIMA della lettura):
- Conteggio top-30: 4 on-topic (Art. 30 ×2 rank 3+9, Art. 15 rank 11, Art. 34 rank 17), 3 adjacent (Art. 19 ×2, Art. 21), 15+ off-topic (Art. 37 ×3 formazione, Allegato I esonero classi laurea, Allegato XIV ×3 cross-titolo IV Cantieri, Allegato IV schema ore corsi, Art. 98 cross-titolo IV, Art. 95 cross-titolo IV, Art. 286-quater cross-titolo X-bis, Allegato XV cross-titolo IV, Allegato XLI cross-titolo IX, Allegato XX cross-titolo VIII, Allegato VIII cross-titolo III, Allegato XXXIV cross-titolo VII, Allegato I-bis sospensione sanzionatoria, Art. 1 legge delega 123/2007).
- Top-2 a score 0.998-0.995: **entrambi off-topic** (Art. 37 formazione + Allegato I esonero).
- **Cohere è uniformemente generoso (tutti gli score >0.5) ma il cuore organizzativo non emerge ai primi rank.**
- 4 on-topic / 9 attesi del cuore. I 5 mancanti (Art. 31 SPP, Art. 32 capacità RSPP, Art. 33 compiti SPP, Art. 35 riunione, Art. 28 VDR) e Art. 18 obblighi datore → DA CHECK DB se ingeriti.

**SQL check D-corpus vs D-rerank (`scripts/check_d_corpus_vs_d_rerank.py`):**
Tutti e 9 gli articoli del cuore SONO INGERITI in `dlgs_81_08`:
- Art. 15: 14 chunks, Art. 18: 4, Art. 28: 5, Art. 30: 10, Art. 31: 3, Art. 32: 5, Art. 33: 1, Art. 34: 4, Art. 35: 5.
- Nessuno ASSENTE. **Verdetto: D-rerank, non D-corpus.**

**SQL check pool RRF vs Cohere top-30 (`scripts/check_articles_in_recall_pool.py`):**

| Articolo | Best rank pool RRF top-200 | Rank top-30 Cohere | Score Cohere | Verdetto |
|----------|---------------------------|---------------------|--------------|----------|
| Art. 15 (Misure generali) | 8 | 11 | 0.932 | OK |
| Art. 30 (Modelli org.) | 2 | 3, 9 | 0.993, 0.970 | OK |
| Art. 33 (Compiti SPP) | **24** | ESCLUSO | — | DROPPED |
| Art. 34 (Datore-RSPP) | 23 | 17 | 0.814 | OK |
| Art. 28 (Oggetto VDR) | **57** | ESCLUSO | — | DROPPED |
| Art. 32 (Capacità RSPP) | **91** | ESCLUSO | — | DROPPED |
| Art. 18 (Obblighi datore) | **108** | ESCLUSO | — | DROPPED |
| Art. 35 (Riunione periodica) | **144** | ESCLUSO | — | DROPPED |
| Art. 31 (SPP) | **148** | ESCLUSO | — | DROPPED |

**D-171-bis (2026-05-30) — Cohere collo di bottiglia: chunk on-topic veri presenti nel pool RRF top-200 ma esclusi dal top-30 reranked.**

Recall ibrido (BM25+cosine RRF) porta tutti i 9 articoli del cuore nel pool top-200. **Il rerank Cohere ne sceglie 30 e ne SCARTA 6 dei 9**, includendo Art. 33 che era rank 24 nel pool (vicinissimo al top). Eppure Art. 33 body chunk ha titolo letterale "Compiti del servizio di prevenzione e protezione" — il più letteralmente correlato al subtopic "Principi normativi e obiettivi dell'organizzazione della prevenzione".

**Implicazione architetturale forte (cambia il piano B2)**:

PRE-D-171-bis tendenza:
- B2 come ri-ranking secondario via cosine Voyage sul **top-30 Cohere reranked**.

POST-D-171-bis:
- B2 come ri-ranking secondario via cosine Voyage sul **pool RRF top-100 o top-200** (saltando Cohere come ranker). Cohere resta:
  - per la telemetria (vedo il mis-ranking come sensore D9 corpus-thin alternativo)
  - come ranker di fallback se Voyage cosine non discrimina abbastanza (improbabile)
- Il top-30 finale del materialize_module_from_skeleton viene da B2 sul pool RRF, non da Cohere.

Conseguenze concrete:
1. Cohere passa da "ranker primario decisionale" a "telemetria + recall accelerator". È un downgrade di ruolo.
2. Il rate_limit Cohere (free tier rerank multilingual-v3.0) diventa meno critico perché lo usiamo solo per la telemetria diagnostica (potremmo anche skip-larlo in prod se troppo lento).
3. Il pool che B2 vede passa da 30 a 100-200 chunk. Costo cosine_voyage: 1 chiamata Voyage per il subtopic (1024-dim) + dot product con 100-200 chunk.body_emb già in DB. Calcolo in-memory veloce (<50ms).
4. **Soglia relativa su cosine_voyage**: ora `< (max_cosine_voyage - delta)` o percentile, calcolata su un pool di 100-200 con Art. 31/32/33/35/28/18 dentro. Il top-30 finale sarà arricchito dei chunk on-topic veri che Cohere escludeva.

**Ground-truth oracolo umano - PROBLEMA**: i 180 chunk che ho estratto sono `retrieve_for_subtopic` top-30 Cohere, **NON il pool RRF top-100/200**. Se calibro B2 nuovo (ri-ranking sul pool RRF) sui 30 Cohere classificati, ottengo soglia tarata su un subset che esclude gli on-topic veri della D-171-bis. Devo rivedere il dataset di calibrazione:

**OPZIONI per il ground-truth (decidere con analista):**
- (A) Classifico i 180 top-30 Cohere come previsto e accetto che B2 calibrazione vede solo il subset Cohere. La soglia che esce è "soglia ri-ranking dentro top-30 Cohere" — utile, ma non gestisce il caso "Art. 33 rank 24 nel pool ma escluso da Cohere".
- (B) Riestraggo il **pool RRF top-100** per ciascuno dei 5 moduli (5×100 = 500 chunk), poi classifico (più lavoro: 500 invece di 150; ma è la calibrazione architettonicamente corretta). HACCP M2/M3 hanno 147 chunks totali fusi, quindi solo i moduli GEN/PRE/ANT impattano sul volume reale.
- (C) Approccio ibrido: classifico i top-30 Cohere come avevo previsto + aggiungo per ciascun modulo i 10-20 chunk del pool RRF top-30 che Cohere ha escluso (probabilmente proprio gli Art. 31/32/33/35/28/18 + analoghi). Volume: 5 × (30 + ~15) = ~225 chunk.

**Tendenza**: (B) o (C). (A) è già la calibrazione del modello pre-D-171-bis, inutile dopo questa scoperta.

### GROUND-TRUTH C' COMPLETATO + ANALISTA SIGN-OFF B2/B3/B4 (2026-05-30)

**Volume ground-truth (analista 2026-05-30 sign-off C' raffinato)**: 5 moduli × 60 chunks
= 296 chunks (HACCP_M3 e ANT_M0 hanno avuto 8 chunks in zona C anziché 10) classificati
con motivazione_breve disciplinata + colonna pattern_misrank su zona C.

**File ground-truth:**
- `storage/ab_test_results/GROUNDTRUTH_CPRIME_BLIND_{GEN_M1,GEN_M3,PRE_M3,ANT_M0,HACCP_M3}.md`
- `storage/ab_test_results/GROUNDTRUTH_CPRIME_CLASSIFY_{...}.md` (con motivazione_breve compilata)
- `storage/ab_test_results/GROUNDTRUTH_CPRIME_SCORES.json` (cosine_voyage + cohere score)
- `storage/ab_test_results/GROUNDTRUTH_CPRIME_SPEARMAN.md` (analisi correlazione)

**Conteggi per zona (oracolo umano Lorenzo, classify cieca disciplinata):**

| Modulo | A1 on | A1 adj | A1 off | A1 utile | B on | B adj | C on | Regime osservato |
|--------|-------|--------|--------|----------|------|-------|------|-------------------|
| GEN_M3 | 11 | 6 | 13 | 57% | 0 | 5 | 2 | REGIME 1 (concept rich) |
| HACCP_M3 | 8 | 9 | 13 | 57% | 0 | 5 | 1 | REGIME 1 (concept rich LCU) |
| ANT_M0 | 5 | 17 | 8 | 74% | 0 | 0 | 1 | REGIME 2 (context rich) |
| PRE_M3 | 2 | 5 | 23 | 23% | 0 | 2 | 0 | REGIME 3 (corpus-thin per concetto) |
| GEN_M1 | 3 | 4 | 23 | 23% | 0 | 0 | 2 | REGIME 3 (corpus-thin per concetto) |

**Spearman correlation classify vs cosine_voyage:**

| Modulo | Sp intera | Sp top-30 | Sp tail | Bottom-20 falsi neg |
|--------|-----------|-----------|---------|---------------------|
| GEN_M3 | 0.381 | 0.300 | -0.037 | 0 |
| HACCP_M3 | 0.316 | 0.144 | 0.268 | 0 |
| ANT_M0 | **0.689** | 0.323 | 0.532 | 0 |
| PRE_M3 | 0.333 | 0.468 | -0.077 | 0 |
| GEN_M1 | 0.208 | **-0.089** | 0.232 | 0 |

**ANALISTA SIGN-OFF 2026-05-30 (4 risposte):**

(a) **cosine_voyage = filtro a soglia OK + ranker fine mediocre** confermato:
- Spearman target 0.7 era target sbagliato (basato su assunzione "ranker title-aligned forte").
- Correzione metodologica: la metrica corretta è ratio A1_utile/B_utile, NON Spearman.
- Tutti i 5 moduli hanno ratio >= 2.3x → cosine_voyage funziona come selettore di pool su TUTTI i regimi.
- D-172 riformulato: cross-encoder italiano-normativo fine-tuned post-V2 se necessario.

(b) **B2 = top-K cosine_voyage selettore di pool sul pool RRF top-100**:
- Default K=30 fissa.
- Variante K adattiva (salto pendenza cosine_n - cosine_n+1) da testare durante implementazione.
- L'ordinamento interno al pool top-K passa a B3 + ordine cosine_voyage tie-breaker.

(c) **B4 D9 vincolante**:
- Sensore primario: A1_utile < 30% (PRE_M3 e GEN_M1 = 23%, ANT_M0=74%, GEN/HACCP=57%).
- Sensore secondario diagnostico: Sp top-30 voyage < 0.2 (GEN_M1=-0.089, HACCP_M3=0.144 — NON discriminante netta per REGIME 3, è diagnostico).
- Comportamento: alert + warning UI quando A1_utile<30% (NO blocco hard ancora), opzione utente revisione voce scheletro.

(d) **Sequenza implementazione INCREMENTALE**:
- STEP 1: B2 K=30 fissa deploy + E2E completo su un corso + delta vs baseline V2 (validazione isolata B2).
- STEP 2: B3 cross-Titolo decay deploy + E2E + delta marginale.
- STEP 3: B4 D9 vincolante deploy.
- STEP 4: Calibrazione finale B2 con K adattiva sul pool post-B3.

**Pattern_misrank universali (watchlist diagnostica):**
- `83295489` "Allegato I esonero classi laurea": GEN_M3 zonaC, PRE_M3 zonaC, GEN_M1 zonaA1 rank 28 (3/5 moduli)
- `a3358e4c` "Allegato IV 4 ore Formazione Generale": GEN_M3 A1 rank 20, PRE_M3 C1, GEN_M1 C4
- `fa54c4c9` "Allegato XIV Cantieri": GEN_M3 C1, PRE_M3 C5, GEN_M1 C1 (3/5 moduli)
- Art. 37 vari chunks formazione_durata_schema: dominante su REGIME 3 (PRE_M3 e GEN_M1)

**H6 + H7 + H8 registrati in REFACTOR_HYPOTHESES_CONFIRMED**:
- H6: cosine_voyage selettore di pool, non ranker fine.
- H7: B2+B3 in COMPLEMENTO necessario, ordine B2-poi-B3 in serie (drift protection).
- H8: REGIME 3 corpus-thin per concetto → work-item esplorativo scheletro doppio livello (post-V2).

### E2E B2 ANT L1 PASS sostanziale + ANALISTA REGISTRA H9 + SIGN-OFF B3 (2026-05-30)

**E2E B2 ANT L1 4h (commit 7217737, flag V2_B2_COSINE_SELECTOR_ENABLED=true):**
- 565s totali (-28% vs baseline HACCP ~780s) → B2 più veloce, saving Cohere call
- 335 slide, distribuzione 83+84+84+84 (vs ANT V2-pre-D3 review 17 che era 84+84+84+76 con M3 degraded → ferita strutturale risolta dal refactor D3)
- Articoli del cuore ANT_M0 (Art. 40, Art. 46, Allegato I CPI) **tutti presenti dominanti** nei top-5 articoli per modulo

**ANALISTA SAMPLE-READ M0 84 slide (disciplina D-160 al render):**
- Slide 1-30 buone (combustione, sostanze pericolose, classificazione fuochi, GSA, strategia antincendio)
- Slide 31-39 (9): meta-formazione corsi antincendio livello 1/2 → cross-corso intra-regulation
- Slide 43-49 (5): medico competente e idoneità → cross-modulo (vive in GEN M1, non ANT M0)
- Slide 51-60 (10): Titolo IV Cantieri → cross-titolo strutturale
- Slide 61-70 (10 parziali): atmosfere esplosive ATEX → cross-titolo XI parziale
- Slide 71-82 (10): meta-formazione e ruoli formali → pattern V2 baseline review 17 in scala minore

**Conteggio onesto analista**: ~28-30 on-topic veri + ~10-12 adjacent legittimi + **~35-40 slide cross-scope problematiche = ~42-48% problematico**.

**Differenza categorica vs mia regex strict**: 0.9% (regex) vs 42% (sample-read) = **~33-42 punti percentuali invisibili alla regex**. Stesso ordine di grandezza della discrepanza review 17 (regex 0% medico-bio M1 vs occhio 50% cross-corso Modulo A).

### H9 — Regex strict NON è metrica di verifica per il refactor; sample-read manuale al render è gate primario (analista 2026-05-30)

Lezione D-160 estesa: regex misura pattern noto del giorno; pattern emergente è invisibile alla regex finché non viene aggiunto come ulteriore espressione. Sample-read manuale al render resta gate primario; regex è metrica di partenza, non decisionale.

**Applicazione operativa**: da H9 in avanti, ogni E2E del refactor passa per sample-read PPTX modulo per modulo come gate primario (analista). Regex resta come proxy veloce.

### D-170 — Per baked-in data del DB, fonte istituzionale primaria + secondaria solo come reading aid (analista 2026-05-30 lezione catalogabile)

**D-170 — "Bosetti out-of-date di ~2 anni in alcuni punti è esattamente il tipo di errore che sopravvive in silenzio"** (analista 2026-05-30 post verifica TOC D.Lgs 81/08).

Per qualunque baked-in data del DB (campi persistenti che vivranno per anni), la regola è:
1. **Fonte istituzionale primaria**: Normattiva (testo coordinato vigente, SLA istituzionale sull'aggiornamento, cattura correttivi recenti).
2. **Fonte professionale secondaria come reading aid**: Bosetti, sezioni ministeriali, ecc. Mai oracolo finale per fatti baked-in.

**Caso concreto registrato**: Bosetti dichiarava "Allegato I-bis NON ESISTE" (testo 2008 originale). Normattiva confermava esistenza Allegato I-bis introdotto da D.L. 19/2024 (patente a punti) citato Art. 27 c.6. Bosetti out-of-date di ~2 anni. Se avessi compilato `regulation_metadata.py` solo su Bosetti, top_section dei chunks Allegato I-bis sarebbe stato classificato "Sconosciuto" per anni senza alcun sensore che lo segnalasse — pattern silent-error che la disciplina deve prevenire alla fonte.

**Pattern generale**: nessun sensore B3 ti dice mai "top_section di questi 200 chunks è stato calcolato su TOC vecchia di due anni". L'errore non emerge come failure, emerge come slow drift. La cura è strutturale (fonte istituzionale primaria) non operativa (review riga-per-riga post-compilazione).

### F2.13 B3 H9 PASS (analista sample-read M0 PPTX ANT L1 post-B3, 2026-05-30)

**Verdict definitivo B3** (analista 2026-05-30 sample-read PPTX `ANT_L1_36c9cf96.pptx` slide per slide + lettura log strutturati JSON):

- **Sample-read M0 84 slide**: ~11 slide problematiche / 84 = **13% residuo strutturale**.
- **Baseline pre-B3** (sample-read 2026-05-30): 42% problematico.
- **Riduzione 29 punti percentuali**, sotto target ricalibrato 15-20%.

**B3 ha intercettato i cross-Titolo strutturali veri** (log evidence):
- Art. 121/132 (Titolo IV Cantieri) decadenti su v3/v4/v6/v8 — 4 voci diverse
- Art. 89 (esplosivi Cantieri) decadente
- Art. 223/224/225 (Titolo IX agenti chimici) decadenti su v3/v8
- Allegato L/XLIX (ATEX) decadenti su v4/v6
- Allegato IV (Titolo II Luoghi di lavoro) decadente su v4/v6/v8
- Art. 288 (ATEX) decadente
- M0 v6 "Prodotti combustione" più contaminata: pool 30→22 con 8 hard-discard

**`b3_skipped_insufficient_obs` funziona attivamente** (NON solo nel principio):
- DM 01/09/2021 (n_obs=1-3) skip su tutte e 8 le voci M0 → corpus thin protetto
- DM 02/09/2021 skip su alcune voci

**Residuo 13% scomposto** (sample-read analista 84 slide):
- 2 slide cross-scope contenuto (slide 40 meta-formazione tipo C, slide 72 sostanze chimiche)
- 7 slide (73-79) cracking normative_ref: contenuto on-topic ma ref Allegato XLI Titolo IX
- 1 slide normativamente datata (slide 44, D.M. 3 agosto 2015 abrogato da DM 03/09/2021)
- ~1 altro

**Decisioni aggregate sulle 32 voci × 30 chunks = 960 decisi**:
- keep_same_titolo: 784 (81.7%)
- decay_kept: 106 (11.0%)
- discard_below_threshold: 46 (4.8%)
- keep_unclassified: 24 (2.5%)
- Soglia 0.30 confermata: NON troppo aggressiva ma neanche dorme (152 chunks cross-titolo = 15.8% del totale)

**noop_reason distribution** (su 32 voci):
- monosection 94 + trivial_single_section 91 + b3_skipped_insufficient_obs 33 + low_confidence_dominante 23

### Osservazione architetturale H8 triangolata (3 casi consolidati, post sample-read M0)

Lo skeleton M0 ha 8 voci tematiche su Principi dell'incendio, MA il PPTX M0 ha solo ~15-20 slide / 84 tematicamente coerenti con queste 8 voci. Le altre 60-65 slide trattano Strategia antincendio luoghi lavoro (1-16), GSA e manutenzione (17-30, 51-70), definizioni luogo di lavoro + obblighi datore (41-50, 71), prevenzione sostanze infiammabili (72-80). Tutti argomenti legittimi per Antincendio L1 ma appartenenti ad altri moduli del corso (M1/M2/M3).

**Diagnosi (analista 2026-05-30)**: content_agent riceve chunks_by_module (union+dedup di 8 pool delle voci M0) e LLM genera 84 slide libere sul pool aggregato. Le 8 voci dello skeleton funzionano da **driver di retrieval**, ma NON da **vincolo organizzativo della generazione**. Una voce v6 "Prodotti combustione" può attirare chunks su "controllo fumi e calore" o "manutenzione impianti antincendio" (cosine alto su parole chiave "fumi", "impianti"), e LLM li usa per generare slide su "Controllo fumi" — tematicamente legittimo per Antincendio L1 ma appartiene a M2 Protezione, non M0 Principi.

**H8 triangolato consolidato** (3 casi distinti):
1. PRE M3 voce 1 (near-miss non definito in D.Lgs)
2. GEN M1 voce 1 (Definizione rischio non centrale in D.Lgs)
3. ANT M0 sample-read (skeleton-as-driver-not-vincolo, 60-65 slide / 84 tematicamente di M1/M2/M3)

Cura H8: scheletro doppio livello con vincolo slide-to-voce. NON B3 (B3 fa il suo lavoro su cross-Titolo strutturali), NON B4 (B4 farà signaling corpus-thin). H8 strutturalmente curativo sul retrieval.

### Slide 73-79 cracking ref - diagnosi precisa post-log

B3 ha decadere chunks Art. 223-225 (Titolo IX) su voci v3 e v8 ma con `decay_kept` (sopravvissuti sopra soglia 0.13). Cosine pre-decay 0.34-0.39, weight post-decay 0.13-0.16, soglia 0.13 (max_pool × 0.30). **Al pelo sopra soglia.** LLM su voci come "Conseguenze incendio" o "Comburenti" li ha attinti come 2° o 3° best quando il primo era chunk DM con cosine appena più alto. Risultato: contenuto sostanze infiammabili viene riformulato dal LLM in chiave antincendio (corretto tematicamente — sostanze infiammabili È in scope antincendio), ma cita normativa Titolo IX (sbagliato semanticamente — Allegato XLI è metodiche misurazione UNI EN 689 agenti chimici, non antincendio).

**Cura corretta (analista 2026-05-30, ordine di preferenza):**

1. **D-161 light sul corpus** (mezz'ora): query SQL sui chunks Allegato XLI specifici, leggi 5 body interi. Decisione: stanno nel corpus o vanno marcati `parsing_ambiguous_for_antincendio_context`?
2. **B4 D9 vincolante con segnale ref-mismatch** (sensore: pool finale voce con chunks decay_kept top_section "lontana semanticamente" dal course_type → flag `ref_quality_warning` sulle slide generate). NON blocca, marca per review. F2.15 estesa.
3. **H8 scheletro doppio livello** con voci più strette → query M0 v6 più specifica e Allegato XLI ha cosine inferiore al cutoff B2 a monte. Curato strutturalmente sul retrieval.

NON abbassare soglia generale a 0.40 (diventerebbe troppo aggressivo sui regimi 2-3).

### B4 SIGN-OFF FINALE (c) Caso 1 solo (analista 2026-05-30, post D-161 light)

**D-161 light eseguito**: query SQL sui 23 chunks Allegato XLI catturati ILIKE (di cui 3 veri Allegato XLI, restanti XLII/altri). Body[:800] sui 3 veri:
- Chunk 1 (22 KB): "metodiche appropriate", "valori limite esposizione professionale", "rimuove cause superamento" — agenti chimici puro
- Chunk 2 (8 KB): "agenti cancerogeni, mutageni, sostanze tossiche per la riproduzione" — cancerogeni Titolo IX puro
- Chunk 3 (2.8 KB): "UNI EN 481:1994 frazioni granulometriche", "UNI EN 482:1998 procedimenti misurazione agenti chimici" — UNI metodiche agenti chimici puro

**Verdict D-161**: Allegato XLI è 100% Titolo IX puro (corpus onesto, NON parsing-ambiguous). Cura non è marcare il corpus, è B4 + H8 a valle.

**Pattern emerso (D-173 nuovo work-item registrato)**: cosine_voyage vede convergenza terminologica generica (sostanze pericolose è linguaggio condiviso fra antincendio e chimico) NON divergenza di scope strutturale. Non risolvibile con B2/B3/B4 — limite del modello embedding stesso. Esplorativo lunga gittata: re-ranker semantico stretto o prompt-side filtering. Backlog.

**Accountability bilaterale (analista 2026-05-30)**: il Caso 2 ("pool dominato regulation cross-scope") e Caso 3 ("decay_kept top_section lontana semanticamente dal course_type") che l'analista aveva proposto al turno precedente richiedono entrambi sapere "cosa è in scope per `antincendio_livello_1`" — esattamente **Tabella 2 course_type → expected_titoli** che era stata esclusa da B3 per ragioni di scaling/cliente-specificità. Riproporli per B4 sarebbe Tabella 2 mascherata da ref_quality_warning. Riconosciuto e ritirato dall'analista. Coerenza disciplinare: regola "no Tabella 2 hardcoded" vale per B3 come per B4.

**Distinzione importante registrata**: Tabella 2 hardcoded dall'operatore non-esperto è curatela errore-prone. Tabella 2 come campo `expected_top_sections` del catalog DB popolato dal cliente esperto al setup corso è dichiarazione esperta — legittima. Ma è F2.13 D8 (catalog DB) work-item separato, NON F2.14 B4.

**B4 SCOPE FINALE (c)**: solo Caso 1 corpus thin per regulation. Caso 2 + 3 vanno a F2.13 D8 catalog DB (futuro) + H8 (futuro).

### B4 ARCHITETTURA DEFINITIVA (analista sign-off 2026-05-30)

**Caso 1 Corpus thin per regulation**:
- Condizione: per voce dello skeleton, per ogni regulation con chunks nel pool finale post-B3, conta `n_chunks_per_regulation_per_voce`.
- Se `n_chunks < B4_MIN_CHUNKS_PER_VOICE` (default 3, env-override) → la regulation X è corpus thin per la voce Y.
- Behaviour configurabile via `B4_CORPUS_THIN_BEHAVIOR`:
  - **`block`** (DEFAULT, scelta sicura): blocca generazione voce + emit warning visibile in `generation_jobs.status` ("voice_X_corpus_insufficient:regulation_Y_n_chunks=N") → UI mostra all'operatore prima del replay, opportunità di ampliare ingestion o riformulare skeleton.
  - **`mark_only`**: scappatoia per chi sa cosa sta facendo. Genera comunque + scrive metadata `low_corpus_confidence` sulle slide per analytics/dashboard. Non protegge cliente.
- Metadata `low_corpus_confidence` SEMPRE attiva indipendentemente dal behavior (dato disponibile sempre per analytics/dashboard future).

**Log strutturato B4 minimo (analista sign-off 2026-05-30)**:
```
{
  voce_idx, regulation_id, n_chunks, soglia,
  decisione: block | mark_only | passthrough,
  behavior_config
}
```

Inoltre `n_chunks_per_regulation_per_voce` come campo per voce sempre nel log (anche quando NON scatta) → permette analisi distribuzione reale per calibrazione soglia su evidenza, NON a priori.

**Soglia default 3**: analista start point. Dai dati log ANT M0 (DM 01/09 con n_obs=1-3 su 8 voci), soglia 3 morde quasi tutto, soglia 4 morderebbe tutto. Calibrazione dai prossimi E2E.

### MAPPA WORK-ITEM RESIDUI POST B4(c) (analista 2026-05-30, registrata per chiusura)

Scomposizione del residuo 13% sample-read M0:
- **Slide 51-54** (corpus thin DM 01/09) → **B4(c) ora**, atteso block o mark in base a config
- **Slide 40** DIAGRAM "formatori antincendio corso tipo C" (meta-formazione intra-Titolo I) → **H8** scheletro doppio livello con vincolo voce→slide
- **Slide 72** valori limite agenti chimici Allegato XLI → **F2.13 D8 catalog DB** quando popolato + **H8** scheletro stretto su voci specifiche
- **Slide 73-79** cracking ref Allegato XLI con contenuto on-topic sostanze infiammabili → **F2.13 D8 catalog** + considerazione policy editoriale separata (rewrite del normative_ref a "DM 03/09/2021 sostanze infiammabili" dove contenuto lo giustifica — scelta prodotto, da discutere col cliente)
- **Slide 44** "Applicazione DM 03/08/2015" abrogato → **D-161 vero** sul corpus, marcatura o rimozione decreto abrogato
- **Voce → slide drift architetturale** (60+ slide M0 oltre le 8 voci skeleton) → **H8** root cause strutturalmente più grosso ma meno bloccante (drift produce slide tematicamente ragionevoli per corso, solo non allineate alla tassonomia voce)

### D-173 (analista 2026-05-30, backlog lunga gittata)

**D-173 — "Limite cosine_voyage convergenza terminologica fra domini."** cosine_voyage vede convergenza terminologica generica (es. "sostanze pericolose" come linguaggio condiviso fra antincendio e chimico) NON divergenza di scope strutturale (incendio vs chimico sono domini distinti). Non risolvibile con B2/B3/B4 — è limite del modello embedding stesso (dense embedding su corpus normativo italiano con vocabolario sovrapposto).

**Esplorativo lunga gittata**:
- (a) Re-ranker semantico più stretto post-cosine_voyage (cross-encoder fine-tuned italiano-normativo). Coincide con D-172-old, F2.18 esplorativo.
- (b) Prompt-side filtering sulla generazione (LLM filtra chunks pre-prompt sulla base di criteri scope-aware ricevuti via system prompt). Non urgente.

Backlog lunga gittata, NON F2.14 scope.

### F2.14 B4 SPECIFICHE estese dall'E2E (analista sign-off 2026-05-30)

B4 D9 vincolante deve gestire 2 casi specifici emersi:

**Caso 1: Corpus thin con generazione che procede comunque**
- Esempio: DM 01/09/2021 n_obs=1-3 su tutte le 8 voci M0 → skip_insufficient_obs scatta MA generazione PPTX procede. Slide 51-54 "Manutentore qualificato" "Formazione manutentori" da DM 01/09, contenuto plausibile ma fonte sottile.
- B4 deve: "voce con regulation a n_obs<N_SOGLIA → limita slide_count per quella voce" OPPURE "blocca generazione e segnala corpus_insufficiente".
- **Soglia proposta**: `B4_MIN_CHUNKS_PER_REGULATION_PER_VOICE=4` (parallela a `B3_MIN_OBSERVATIONS=4`).

**Caso 2: Pool dominato da regulation cross-scope**
- Esempio futuro: corso antincendio dove una voce ha pool dominato (>50%) da chunks la cui top_section è strutturalmente cross-scope rispetto al course_type (es. Titolo IX agenti chimici dominante in corso Antincendio).
- B4 deve: riconoscere la firma e bloccare/marcare. Sensore contaminazione esteso F2.14.

### POST-B4 SAMPLE-READ M0 ANT L1 — 4 work-item B2 pre-H8 (2026-05-30, sign-off analista B2)

**Contesto.** E2E ANT L1 post-B4 (PPTX `ANT_L1_0dfe39ad.pptx`, 335 slide, log `E2E_B4_ANT_L1_LOG.json`) ha confermato che B4 ha morso esattamente dove doveva (22 block / 128 totali = 17%, 18/34 voci con almeno 1 block, slide manutentore DM 01/09 del PPTX precedente sparite). H9 numerico PASS (cross-corso regex strict 20.0% vs 22.9% post-B3, -3 pp). Ma H9 sostanziale FAIL al sample-read M0 dell'analista: **5/83 slide on-topic core** (definizione/triangolo/classificazione/fasi/cause/prodotti/propagazione/effetti — gli 8 subtopic dello skeleton). 78/83 slide sono cross-modulo intra-corso (strategia M1, esodo M2, GSA/procedure M3) o problematiche. Diagnosi: **voce-to-slide drift** triangolato 3 volte (PRE M3 + GEN M1 + ANT M0 ×2) → H8 (vincolo voce-to-slide-cluster nel content_agent) promosso da work-item post-V2 a blocker corrente. Prima però 4 errori normativi visibili nel sample-read vanno puliti perché **avvelenerebbero l'E2E diagnostico post-H8** (cracking normativi residui non distinguibili da drift residuo).

**Verifica preliminare 3 SELECT COUNT su DB (2026-05-30, via TCP proxy zephyr:11820)** — **SORPRESA #3 a verbale**: 2 dei 4 errori target sono allucinazioni LLM, non cracking corpus:
- DM 03/08/2015 (slide 61, 66): **NON nel corpus** (9 regulations ingested, nessuna con slug `dm_03_08_2015`). Il LLM lo allucina dal training data come "decreto attuale".
- Art. 625 D.Lgs 81/08 (slide 67): **NON nel corpus** (1819 chunks D.Lgs, Art > 306 sono solo i 13 cross-codice CC/CP, 329/331/395/589/1418/1478/2083/2222). Il LLM allucina mescolando con Codice Penale Art. 625 (furto).
- Slide 44/52 (ref cracking "D.Lgs 81/08 Allegato 2" + "DM 03/09/2021 Art. 17"): da verificare se cracking template o allucinazione (richiede apertura chunk_id slide).
- `accordo_stato_regioni_2011` marcato `status='VIGENTE'` ma titolo dichiara "(storico)" → candidato vero D-161.
- D.Lgs 81/08 chunks `top_section='Sconosciuto'`: **30 totali su 14 articoli distinti** (non 24 come ricordato). Suddivisione: 13 cross-codice (Art > 306) candidati `external_reference`, 17 parsing-noise (allegato/allegato\n) restano Sconosciuto.

**Sign-off analista B2: scelta B2 con D-178 aggiunta (NON B1 anti-allucinazione che impacchetta cure di strati diversi)**. Sequenza: VERIFICATION_DEBT → D-161 → D-175 → D-177 → D-178 V1 → E2E controllo → sample-read insieme → semaforo H8.

### D-161 — Vigenza regulations + filtro retrieval (2026-05-30, schema universale `effective_until`)

**Evidenza concreta.** `regulations` table ha già colonna `status VARCHAR` (campione `'VIGENTE'` su 9/9 regulations), ma nessuna entry è marcata ABROGATA. Caso esistente: `accordo_stato_regioni_2011` ha title "Accordo Stato-Regioni 2011 — Formazione (storico)" — dichiarato storico nel titolo, marcato VIGENTE nello status. Discrepanza stato vs realtà. Storicamente l'Accordo 2011 è superseded dall'Accordo Stato-Regioni 2025 (`accordo_stato_regioni_2025`, 133 chunks, già ingested).

**Diagnosi.** Lo schema `regulations.status` enum-like (VIGENTE/ABROGATA/MODIFICATA, vedi `knowledge_repo.py:41` `resolve_slugs_to_ids` filtra `WHERE status = 'VIGENTE'`) è troppo grossolano: (a) non cattura dimensione temporale (un'abrogazione ha una data, non è atemporale); (b) non cattura il "chi abroga chi" (catena di succession); (c) non supporta override pedagogico (un corso "evoluzione normativa 2011-2025" vorrebbe Accordo 2011 deliberatamente).

**Cura proposta — schema universale.**
1. Migration: `regulations` aggiungi `effective_until DATE NULL` + `abrogated_by_id UUID NULL REFERENCES regulations(id)`. Semantica: `effective_until IS NULL` = vigente indefinito, `effective_until > now()` = vigente fino a data programmata (utile per direttive UE con cessazione programmata futura), `effective_until <= now()` = abrogato/non più vigente.
2. Course-level flag (data model): `courses.include_abrogated_for_pedagogy BOOL DEFAULT false`. Costo nullo ora, presente per quando il caso "corso evoluzione normativa" arriverà senza migration.
3. Filtro retrieval: in `knowledge_repo.search_chunks` (e gemelle in `retrieval_v2.recall_hybrid` per BM25 corpus load + idratazione), aggiungi join SQL su `regulations` con clause `WHERE (r.effective_until IS NULL OR r.effective_until > now() OR :include_abrogated)`. **Filtro al join, NON in-Python post-fetch** (memoria D-168: filtri lato Python compensano silenziosamente i bug del filtro SQL e li nascondono).
4. Backfill: `UPDATE regulations SET effective_until = '2025-04-17', abrogated_by_id = (SELECT id FROM regulations WHERE slug='accordo_stato_regioni_2025') WHERE slug='accordo_stato_regioni_2011'` (data esatta da confermare via Normattiva al momento del fix).
5. Test: query SQL post-fix conferma chunks Accordo 2011 fuori da pool ANT L1 (course non opt-in per pedagogy).

**Blocker/dipendenze.** Schema migration richiede coordinamento con `is_current` esistente in `regulation_chunks` (sono ortogonali: `is_current` = chunk vs chunk superseded da re-ingestione; `effective_until` = regulation vs regulation abrogata da normativa successiva). Documentare la distinzione in commit message.

**Stima.** Mezza giornata (schema + backfill + retrieval filter + test).

**Razionale `effective_until` vs `is_abrogated` BOOL.** `is_abrogated` cattura un bit, `effective_until` cattura bit + data + (via FK) chi abroga. `effective_until` è universale: gestisce "abrogato il", "cessa il", "vigente fino al" con la stessa primitiva. Una sola colonna invece di tre. Pattern simile a `users.deleted_at` vs `users.is_deleted`.

### D-175 CLOSED — false positive (2026-05-30 post-verifica chunks DB)

**D-175 closed**: diagnosi originale costruita su falsi ricordi sample-read analista, verifica DB chunk reali (6 chunk_id estratti da `slide_contents_json` del course `0dfe39ad`) ha falsificato i 3 casi target. Rendering ref-chunk deterministico (`citation_label` composta deterministicamente da `short_title + article + paragraph` in `citation_label.py:compose_citation_label`, aggregata in `content_agent.py:215` `s.normative_ref = "; ".join(unique[:3])`). **No fix necessario**. Mezza giornata risparmiata. Le patologie reali rilevate sample-read sono (a) D-178 V1.5 (LLM cita decreto abrogato nei bullets pescato da rinvio storico interno al body chunk vigente — slide 61/66/67 "DM 03/08/2015 decreto attuale"), (b) H8 voce-to-slide drift (slide 7/8/9 meta-formazione ref-correct ma fuori scope per la voce).

### D-180 — Disciplina diagnostica nx_normative_ref (2026-05-30, metodologico)

**Regola.** Diagnosi su `nx_normative_ref` delle slide richiede **chunk_id → DB lookup** prima di classificare come errore. Estrazione PPTX testuale è **osservazione**, non evidenza diagnostica sufficiente per affermazioni forti ("errore fattuale conclamato", "ref inesistente"). Gate per ogni futuro sample-read.

**Why.** D-175 originale formulato su 3 memorie sample-read PPTX presentate come evidence: "slide 67 Art. 625 D.Lgs inesistente", "slide 44 D.Lgs 81/08 Allegato 2 incongruo", "slide 52 DM 03/09/2021 Art. 17 inesistente". Verifica chunks DB ha falsificato tutte e 3: slide 67 ref reale = "DM 03/09/2021 art. 62" (esiste, body coerente "Definizione luogo di lavoro"); slide 44 ref reale = "DM 02/09/2021 allegato I" (esiste, body coerente "addetto antincendio + piano di emergenza"); slide 52 ref reale = "DM 03/09/2021 art. 46" (esiste, body coerente "Prevenzione incendi"). Costo evitato: mezza giornata di lavoro su bug inesistente.

**How to apply.** Per ogni slide sospettata di ref-error in futuro sample-read:
1. Estrai `slide_contents_json[slide_idx]` → `source_chunk_ids` + `normative_ref` renderizzato dal DB courses row.
2. Lookup `regulation_chunks WHERE id = ANY(source_chunk_ids)` → `article`, `paragraph`, `citation_label`, `body` (excerpt).
3. Confronta: (a) ref renderizzato == citation_label aggregata? (b) body chunk coerente col contenuto slide?
4. Solo se (a) o (b) FALSE → classifica come ref-error e procedi diagnosi.

**Lezione stessa famiglia di REI-17 + review-17.** Verify-by-render funziona quando "render" è il file SQL/DB, non il PPTX testuale a memoria. La stessa disciplina si applica simmetricamente: analista smonta previsioni Claude con i dati; Claude smonta osservazioni analista con i dati. Bilaterale.

### D-175 (ARCHIVIATO sotto, formulazione originale per traccia) — Ref consistency rendering chunk → nx_normative_ref (2026-05-30)

**Evidenza concreta.**
- **Slide 44 PPTX `0dfe39ad`**: ref `"D.Lgs 81/08 Allegato 2"` su contenuto formazione addetto antincendio. **Allegato II del D.Lgs 81/08 è "Casi datore RSPP"**, non antincendio. Ref incongruo col contenuto.
- **Slide 52 PPTX `0dfe39ad`**: ref `"D.M. 3 settembre 2021 art. 17"`. **DM 03/09/2021 (minicodice) non ha Art. 17** — finisce ad articoli inferiori. Numerazione cracking.

**Diagnosi attuale (IPOTESI, da CONFERMARE coi dati).** Lo slide rendering produce nx_normative_ref non corrispondente al chunk reale che ha fornito il contenuto. Possibili rami:
- (a) Template Jinja2 `production_builder.py` legge `chunk.article` e `chunk.regulation_slug` correttamente ma applica trasformazione errata (es. prefix DM su numero D.Lgs).
- (b) Mapping chunk→slide nel content_agent perde uno dei due campi (article OR regulation_slug) e il template recupera con guesswork.
- (c) LLM nel content_agent inventa il ref nel campo testuale della slide indipendentemente dal chunk source — sarebbe variante del D-178 sotto, NON un bug di rendering.

**Disciplina root-fix vs workaround (sign-off analista 2026-05-30).** Apri slide 44/52 dal `slide_contents_json`, recupera chunk_id (se esposto), leggi chunk reale da DB (`article`, `regulation_slug`, `body`), confronta con `nx_normative_ref` renderizzato. **Non assumere il bug — leggi i campi.** Se diagnosi vira verso "per il DM 03/09/2021 il template applica prefix DM al numero articolo di un chunk D.Lgs perché il regulation_slug del chunk era stato corretto al cross-render", fermati: quello sarebbe scivolata verso workaround. La root fix è "il template legge `chunk.article` e `chunk.regulation_slug` dal chunk stesso, mai da inferenze sul contesto di slide". Se invece la pipeline join chunk→slide perde uno dei due campi e il template recupera con guesswork, la root fix è sul join non sul template — **una giornata in più, non mezza**, decisione esplicita al momento della diagnosi.

**Cura proposta.** Branch deciso dalla diagnosi:
- Se ramo (a) template: fix template per leggere `chunk.article` + `chunk.regulation_slug` come single source of truth.
- Se ramo (b) join chunk→slide: fix sul join nel content_agent o builder, non sul template (gestire downstream).
- Se ramo (c) LLM invents: cade in D-178 anti-hallucination, non in D-175.

**Test.** Regression su 5 slide random con ref normativo, conferma `nx_normative_ref == chunk.regulation_slug + chunk.article` (modulo formatting).

**Blocker/dipendenze.** Richiede ispezione PPTX + DB query mirate. Indipendente da D-161/D-177.

**Stima.** Mezza giornata se ramo (a), 1 giornata se ramo (b), → cade in D-178 se ramo (c).

### D-177 — Policy `top_section='external_reference'` per chunks cross-codice (2026-05-30, range da metadata universale)

**Evidenza concreta.** Verifica preliminare DB ha rivelato: D.Lgs 81/08 ha **30 chunks `top_section='Sconosciuto'`** (non 24 come ricordato). Suddivisione:
- **13 chunks cross-codice (Art > 306)**: candidati ri-categorizzazione `external_reference`. Articoli: Art. 329 (×1), Art. 331 (×1), Art. 395 (×1), Art. 589 (×2), Art. 1418 (×2), Art. 1478 (×1), Art. 2083 (×1), Art. 2222 (×4). Sono Codice Penale (329/331/395/589) e Codice Civile (1418/1478/2083/2222) citati dentro chunk del D.Lgs.
- **17 chunks parsing-noise vero**: `'allegato\n…'` (×8), `'Allegato 3'` (×4), `'allegato 3'` (×2), `'allegato 2'` (×1), `'allegato d'` (×1), `'allegato il'` (×1). Restano `Sconosciuto` (genuino: parser ha fallito su questi).

**Diagnosi.** La policy attuale "chunks `Sconosciuto` sopravvivono se cosine al subtopic alto" (decisione B3 originale: "non sono ranker-utili ma sopravvivono se semanticamente validi") protegge correttamente i 17 parsing-noise (potrebbero contenere body utile) ma NON protegge dai 13 cross-codice: questi sono semanticamente validi (Art. 1418 nullità contratto è legittimamente rilevante per "responsabilità del datore") ma producono **errori di ref normativo** se diventano fonte primaria di slide (il content_agent li ranks come `D.Lgs 81/08 Art. 1418` ma quell'articolo non esiste nel D.Lgs).

**Cura proposta — categoria semantica esplicita + range da metadata.**
1. Estendi `regulation_metadata.py` per ogni regulation con un campo `article_range_valid: tuple[int, int] | None`. Per D.Lgs 81/08: `(1, 306)`. Per altre regulations (DM, Reg CE): `None` (no concept of "article range", structure different).
2. Branch in `top_section_of(regulation_slug, article, ...)`: se `regulation_metadata[slug].article_range_valid is not None` AND article matcha pattern `^Art\.\s*(\d+)` AND numero estratto fuori range → return `"external_reference"`. **NESSUN if hardcoded `slug == 'dlgs_81_08'`** — la logica è universale, vive in metadata. Quando arriveranno HACCP/REACH/Antifrode, ognuno dichiarerà il proprio range valido in metadata senza tocco al codice.
3. Script backfill `scripts/backfill_external_reference.py` (gitignored, password): `UPDATE regulation_chunks SET top_section='external_reference' WHERE regulation_id=:dlgs81 AND article ~ '^Art\.\s*[0-9]+' AND CAST(regexp_replace(article, '[^0-9]', '', 'g') AS INTEGER) > 306`. Atteso: 13 chunks aggiornati.
4. Content_agent prompt: aggiungi vincolo `"If a chunk has top_section='external_reference', use it only as supporting evidence within slides whose primary source is internal to the regulation (i.e., top_section is a Titolo/Allegato of the regulation itself), never as the sole basis for a slide."`
5. Test post-fix: sanity SQL `SELECT COUNT(*) FROM slides ... WHERE primary_chunk.top_section='external_reference'` → 0 atteso post-rigenerazione (variante: parse `slide_contents_json` per chunks usati come fonte primaria).

**Razionale `external_reference` vs `hard_discard` vs `mark_for_review`.**
- `hard_discard` perde 13 citazioni semanticamente legittime (Art. 589 CP omicidio colposo è rilevante per "responsabilità datore" su qualche corso).
- `mark_for_review` delega all'operatore non-RSPP che non sa quando un Art. 1418 CC è in-scope. Pattern "sensore senza azione".
- `external_reference` è dichiarazione positiva di natura: il chunk è citazione di codice esterno al D.Lgs. Azionabile downstream (content_agent sa "supporting evidence only, never primary"). Pattern simile a `b3_skipped_insufficient_obs`: segnale visibile in pipeline e azionabile.

**Blocker/dipendenze.** Richiede estensione `regulation_metadata.py` campo `article_range_valid`. Backfill SQL deve essere applicato a corpus prod via TCP proxy.

**Stima.** 1 giornata (metadata extension + branch top_section_of + backfill + content_agent prompt + test).

### D-178 V1.5 CHIUSO end-to-end (2026-05-30 sign-off analista B)

**Strategia finale (analista 2026-05-30): SALTATO V1 originale, andato direttamente V1.5.**

Razionale: V1 originale (nx_normative_ref regulation_slug filter) curava patologia teorica non osservata. Le 6 slide cross-corso aperte in DB hanno tutte `nx_normative_ref` deterministico-corretto da chunk source. La patologia reale (slide 67 PPTX `ANT_L1_0dfe39ad` bullet "Decreto ministeriale 3 agosto 2015 - riferimento chiave") sta nei **bullets**, non nel ref renderizzato. V1.5 cura questa patologia direttamente. V1 saltato (disciplina anti-curatela: no cura per patologia ipotetica).

**Patologia coperta**: LLM pesca dal body del chunk vigente (DM 03/09/2021 Allegato 1) un rinvio storico interno a decreto abrogato (DM 03/08/2015) e lo cita nei bullets come "decreto attuale". Verificato slide 67 ANT L1: bullet "Decreto ministeriale 3 agosto 2015 - riferimento chiave" + course.regulation_ids ANT L1 NON contiene `dm_03_08_2015`. Note: slide 61 e 66 del sample-read analista erano falsi positivi (61 quiz_options pulito, 66 cita D.Lgs. 81/08 legittimo).

**Implementazione**:
- `app/services/citation_normalizer.py` (NEW): regex multi-pattern per DM datato (lettere/slash), DM numerato, D.Lgs, Reg CE/UE, Accordo SR, D.P.R. + normalizzazione canonical slug + dedup. Pattern overlap fix: DM datato consuma porzione testo prima di DM numerato (altrimenti "03/09/2021" → "9/2021" falso positivo). Strategia (a) bullet→canonical slug, NON (c) display_citations field strutturato (backlog D-181-bis).
- `app/builders/production_builder.py`: pre-PPTX-build, scansiona bullets + speaker_notes + quiz_options di ogni slide. Slide con citazioni fuori scope → `bullet_citation_warning` log strutturato + accumulo in `hallucination_report`. **Comportamento marca-only**: NESSUNA modifica slide, NESSUNA rigenerazione. Trasparenza visibile (telemetria + report), operatore review.
- `tests/unit/test_citation_normalizer.py` (NEW): 25 test PASS. Dataset stabili: slide 67 patologica (1 slug hallucinated atteso), slide 66 e 3 vere positive (0 hallucinated atteso), HACCP scope isolation, multiple hallucinations dedup, speaker_notes inclusi nello scan.
- Smoke test E2E logico (slide 67 + 66 reali estratte da DB course `0dfe39ad`): patologia riconosciuta, legittima passa. OK.

**Test totali pulizia post-B4 (D-161 + D-177 + D-178 V1.5)**: 163/163 PASS. Mypy strict clean sui file toccati, ruff clean.

**Tempi consuntivi**: V1.5 ~40 minuti vs stima 1 giornata. Pattern "stima ricalibrata su precedente metodologico" (D-180 estesa).

### D-181-bis — `display_citations` field strutturato (backlog post-E2E controllo)

**Dormiente.** Quando arrivera' il 2° corso reale con citazioni diverse (HACCP cita Reg CE 852/2004 in forma "Regolamento (CE) n. 852/2004 del Parlamento europeo e del Consiglio del 29 aprile 2004"), la strategia (a) bullet→canonical slug del citation_normalizer potrebbe rivelarsi fragile a varianti formattazione non previste nel regex.

**Cura quando servira'**: aggiungi campo `regulations.display_citations text[]` popolato in ingestion con array di forme legittime ("D.M. 3 settembre 2021", "Minicodice", "DM 03/09/2021"). Check whitelist invece di normalizzazione. Sopravvive a varianti di formattazione future.

**Trigger.** Falso negativo rilevato sample-read 2° corso (HACCP, RLS, altro) + regex normalizer non lo cattura.

### D-178 — Anti-hallucination guardrail citazioni normative content_agent (2026-05-30, SPLIT V1 + V1.5 + V2, formulazione originale archiviata)

**AGGIORNAMENTO 2026-05-30 post-D-175 diagnosi DB.** La formulazione originale V1+V2 va corretta:
- V1 (NX_NORMATIVE_REF FILTER): protegge contro `regulation_slug` in `nx_normative_ref` renderizzato NON in `course.regulation_ids`. Cattura il caso "LLM scrive ref a regulation fuori scope".
- **V1.5 (NUOVO, BODY BULLETS REGEX FILTER)**: protegge contro decreti citati **nei bullets/body slide** che NON sono in `course.regulation_ids`. Pattern di patologia diagnosticato 2026-05-30: il LLM pesca dal body di un chunk vigente (es. DM 03/09/2021 Art. 46) un rinvio storico interno a decreto abrogato (es. DM 03/08/2015) e lo cita nei bullets come "decreto attuale". Il chunk source è in scope, il `nx_normative_ref` rendered è corretto, ma i bullets contengono citazione hallucinated. V1 non lo cattura.
- V2 (article-level verifier, post-V1.5): granularità fine, 3-5 giorni. Da considerare solo se V1+V1.5 lasciano residuo significativo.

**Sequenza implementazione (analista sign-off 2026-05-30 ordine empirico):**
1. **V1** (1 giornata): content_agent prompt rinforzato + post-render filter su `nx_normative_ref` rendered. Test pipeline + E2E intermedio singolo modulo ANT M0.
2. **E2E intermedio singolo modulo M0** (1 ora): rilancio ridotto per discriminare V1 sufficiency. Possibile che prompt rinforzato V1 inneschi il LLM a smettere anche di citare nei bullets decreti non-in-scope (empirico, non a priori).
3. **V1.5** (CONDIZIONATO, 0.5-1 giornata): solo se E2E intermedio mostra residuo "DM 03/08/2015 nei bullets" persistente. Regex extract citazioni decreti dai bullets/body slide + check vs course.regulation_ids → scarta slide o marca.
4. **V2 article-level verifier**: deferred a post-E2E finale se V1+V1.5 lasciano residuo significativo.

### D-178 — Anti-hallucination guardrail citazioni normative content_agent (2026-05-30, V1+V2 separati — formulazione originale archiviata)

**Evidenza concreta — SORPRESA #3 (sign-off analista a verbale).** Sample-read M0 PPTX `0dfe39ad` ha rivelato 3 slide con citazioni normative **NON presenti nel corpus**:
- Slide 61, 66: DM 03/08/2015 citato come "decreto attuale" / "riferimento chiave". **DM 03/08/2015 NON è nel corpus**: 9 regulations ingested, nessuna con slug `dm_03_08_2015`. Il LLM lo allucina dal training data.
- Slide 67: "D.Lgs 81/08 Art. 625: Definizione di luogo di lavoro". **Art. 625 D.Lgs NON è nel corpus**: D.Lgs 81/08 ha 1819 chunks, Art > 306 sono solo i 13 cross-codice CC/CP. Il LLM allucina mescolando con Codice Penale Art. 625 (furto).

**Diagnosi.** Una classe di errori precedentemente classificata come "corpus contaminato" (D-161, ipotesi DM 03/08/2015 ingested senza marcatura) o "chunk Sconosciuto sopravvissuto a B3" (Art. 625) è in realtà **LLM hallucination**. Due patologie diverse, due cure diverse, due strati diversi del sistema. La verifica empirica con 3 SELECT COUNT da Railway ha smentito una diagnosi precedente fatta solo via sample-read PPTX. Pattern "verifica i dati, non assumere la mappa" applicato.

**Cura proposta — DUE FASI esplicite per non bluffare sui costi.**

**V1 (granularità regulation_slug, 1 giornata).**
1. Content_agent prompt rinforzato: vincolo esplicito `"Cite only regulations that are in the course's ingested corpus. The full list of allowed regulation slugs for this course is: {course.regulation_ids}. Do not invent decree numbers, dates, article numbers. If a topic seems to require a regulation not in this list, omit the citation or use a generic phrasing without a specific decree."`
2. Post-render verifier in builder: per ogni slide generata, estrai `nx_normative_ref` (regex su pattern `D\.?(Lgs|M)\.?\s*\d+`, `Reg\.?\s*CE\.?\s*\d+`, `Accordo\s+Stato.Regioni\s+\d+`, ecc.) → normalizza a slug → verifica `slug ∈ course.regulation_ids`. Se non match → marca slide `ref_hallucination_warning` e (scelta analista) **scarta su V1, mark per review su V2 quando verifier sarà più sottile**.
3. Test: regression sul PPTX post-fix, conta slide scartate. Atteso: ≥3 slide scartate (slide 61, 66, 67 del PPTX `0dfe39ad` se rigenerate identicamente).

**V2 (granularità article-level, 3-5 giorni — work-item separato post-V1).**
1. Verifier programmatico che estrae ogni `nx_normative_ref` e verifica che `(regulation_slug, article)` corrisponda a un chunk del pool della voce, OPPURE che almeno `regulation_slug ∈ course.regulation_ids`.
2. Sotto-decisioni serie da risolvere PRIMA di scrivere V2 (annotate ma non risolte ora):
   - Verifier gestisce ref multipli per slide (slide 56/66 PPTX `0dfe39ad` hanno doppia citazione "ref1; ref2"). Strategia parsing.
   - Match su article: stringa esatta? Normalizzata (`Art. 46` matcha `art. 46 c. 1`)? Definisci canonical form.
   - Match solo regulation_id (article inventato): hallucination o "LLM concentra ref legittimo a livello regulation senza article-precision"? Gestione differenziata.
3. Calibrare granularità match in vacuum è esercizio sterile: scrivi V1 (filtro grossolano, cattura il 70% dei casi gravi inclusi i 3 sample-read post-B4), committa, raffina ad article-level in pass V2 dopo l'E2E controllo se i dati lo giustificano.

**Blocker/dipendenze V1.** Modifiche a `content_agent.py` prompt + `production_builder.py` post-render check. Indipendente da D-161/D-175/D-177.

**Stima V1.** 1 giornata. **Stima V2 (separata, NON in questo ciclo B).** 3-5 giorni.

**Asimmetria di credibilità — razionale promozione D-178 a priorità alta.** Errori normativi falsificabili (Art. 625 inesistente, DM 03/08/2015 inventato) hanno asimmetria di credibilità: davanti a un RSPP cliente, "D.Lgs 81/08 Art. 625" non è 1/83 di errore, è un errore atomico che annulla la fiducia sul 100% del corso. D-178 cattura una classe intera di patologie future, non solo gli esempi sample-read post-B4.

### D-179 — Propagazione `include_abrogated` ai caller esterni (dormiente, 2026-05-30)

**Status.** Dormiente per disciplina YAGNI. Nessun corso oggi vuole `include_abrogated=true`. Default safe (False) protegge il caso reale (accordo_2011 escluso dal pool retrieval ANT L1, verificato via smoke test SQL post-backfill).

**Mappa file da toccare quando arriverà il caso reale** (es. corso "Evoluzione normativa formazione 2011-2025"):
1. `app/services/retrieval_v2.py:_retrieve_pipeline` (riga ~621) — aggiungi param `include_abrogated: bool = False` + propaga a `recall_hybrid`.
2. `app/services/retrieval_v2.py:retrieve_for_module` (riga ~666) — aggiungi param + propaga a `_retrieve_pipeline`.
3. `app/services/retrieval_v2.py:retrieve_for_subtopic*` (riga ~720+) — aggiungi param + propaga a `_retrieve_pipeline`.
4. `app/services/skeleton_service.py:materialize_module_from_skeleton` — accetta `include_abrogated` da generation_service e passa a `retrieve_for_subtopic*`.
5. `app/services/generation_service.py:277` SELECT — aggiungi colonna `include_abrogated_for_pedagogy` dal courses row.
6. `app/services/generation_service.py:294` — passa il valore a `resolve_slugs_to_ids` E al materialize call.
7. `app/agents/research_agent.py:1441,1486,664` — solo se anche v1 path serve pedagogy override (per ora skip, è path legacy by-title).

**Stima quando arriverà.** 30-60 minuti di edit meccanico + 5-10 test regression unit + 1 E2E smoke. Costo prevedibile, niente sorprese.

**Trigger.** Quando il primo `course` reale verrà creato con `include_abrogated_for_pedagogy=true` esplicito (manuale o via UI futura). Fino a quel momento il flag esiste in schema ma non viene mai letto dai caller — comportamento corretto safe-by-default.

### D-161 RAFFINAMENTI MINORI (analista 2026-05-30 post-applicazione)

- **Index su `effective_until`**: applicato come index parziale `WHERE effective_until IS NOT NULL` (vedi migration 009). Razionale: la maggior parte delle regulations ha effective_until NULL (vigenti indefinite); index parziale evita di indicizzare tutti i NULL e mantiene il query plan veloce.
- **Timezone semantics**: `effective_until DATE` (non TIMESTAMPTZ). PostgreSQL `now()::date` vs `effective_until DATE` confronto è date-only, ignora time-of-day e timezone. Pattern accettato per il caso d'uso (cessazione di applicabilità normativa = granularità giornaliera, non oraria). Limite: il giorno della cessazione, il filtro decide "abrogato dalle 00:00 UTC" — accettabile per safety formativa, dove la differenza di poche ore non genera errori sostanziali. Documentato a verbale come decisione esplicita.
- **Doppia fonte istituzionale per date legalmente vincolanti** (lezione D-170 estesa): per ogni data che entra nel sistema come `effective_until`, conferma con almeno 2 fonti (1 primaria GU/Normattiva + 1 secondaria istituzionale tecnica). Esempio applicato per accordo_2011: GU n. 119/2025 + Artser conferma 12 mesi transitorio → 2026-05-24. Principio operativo da REI per work-item futuri.

### H9 SAMPLE-READ M0 POST-V1.5 — FALLITO (analista 2026-05-31)

**Verdict netto**: H9 sostanziale FALLITO per la terza volta nella sessione, con aggravio.

**On-topic core M0 post-V1.5**: **0-1 / 84 slide = 1.2%** (vs post-B4 5/83 = 6%, vs post-B3 stima 6-10%). **La pulizia B-cycle non ha mai toccato il drift voce-to-slide**: ha rifinito il retrieval (B2, B3, B4, D-177, D-178 V1.5) ma il content_agent continua a generare 84 slide free-form sul `chunks_by_module` union, indipendentemente dallo skeleton 9-voci che dichiarava Principi puri (definizione, comburente/combustibile, classificazione, fasi, prodotti combustione, effetti, sostanze estinguenti, ruolo addetto).

**Risultato cumulativo perverso**: pulizia retrieval cresce, qualità modulo-coerenza scende. Cross-corso regex 25.4% → 22.9% → 20.0% → 16.1% (sembra migliorare), ma on-topic core ~10% → 6% → 1.2% (peggiora). Pattern *metric ottimizzata, contenuto peggiorato* confermato tre volte.

**Patologie reali rilevate sample-read M0 post-V1.5**:
- Skeleton 9 voci impeccabile (Principi puri), zero slide riconoscibilmente sui Principi.
- 83/84 slide su temi di altri moduli (DM 03/09/2021 applicazione, esclusione cantieri, compartimentazione M2, manutenzione M2, formazione addetti M1, obblighi datore M1).
- **Ridondanza semantica visibile**: slide 11/16, 12/17, 13/18 coppie quasi identiche. Il LLM duplica contenuto adjacente perche` `chunks_by_module` per voci principio-tecnico e` povero.
- **Slide 42 D.Lgs 139/2006 Tipo 3 hallucination** (vedi D-181-quinquies sotto): V1.5 NON cattura.
- **4-5 falsi positivi V1.5 strutturali as-object** (vedi D-181-ter sotto): slide 10, 107, 110, 230, 324 citano correttamente decreti abrogati come OGGETTO della slide (slide normativa di transizione/comparazione), non come fonte primaria.

**Conclusione**: H8 NON e` piu` "raccomandato post-pulizia" — e` **strutturalmente necessario, ora**. Lo skeleton M0 corrente e` ground truth perfetto per misurare H8.

### D-181-ter — As-object vs as-source hallucination guardrail (2026-05-31, backlog post-H8)

**Pattern**: V1.5 marca tutti i match `regulation_slug ∉ course.regulation_ids` nei text_fields della slide, NON discrimina:
- **as-object** (legittimo): la slide parla DELL'abrogazione/comparazione del decreto come oggetto pedagogico. Esempio slide 10 PPTX `9249d700` "Abrogazione del D.M. 10 marzo 1998" — bullet "DM 03/09/2021 sostituisce DM 10/03/1998" e` enunciazione storica corretta. V1.5 marca, e` falso positivo.
- **as-source** (patologico): la slide cita il decreto come fonte attuale di un'affermazione. Esempio slide 264 "Misure di compartimentazione antincendio" bullet "Secondo DM 03/08/2015..." — fonte abrogata presentata come attuale. V1.5 marca correttamente.

**Precisione V1.5 corrente**: ~6/11 = 55% (su sample-read M0 post-V1.5).

**Cura proposta (HARD da definire post-H8)**: se lo slug compare nel titolo della slide → likely as-object, warning soft (visibile ma non blocking); se compare solo nei bullets → likely as-source, warning hard (presente nel report critico).

**Stima**: 1-2 ore. Decisione post-H8 perche` H8 potrebbe eliminare il pattern as-source a monte (LLM iterando voce-per-voce con prompt restructure non avra` motivo di citare decreti out-of-scope nelle voci tecnico-principio).

**Trigger**: post-H8 sample-read M0 mostra V1.5 warning persistenti con pattern as-object dominante → implementa discriminazione. Se warning calano a 0-2 totali → irrilevante, lascia D-181-ter chiuso senza fix.

### D-181-quinquies — Tipo 3 hallucination: contenuto attribuito a decreto reale fuori scope (2026-05-31, esplorativo)

**Pattern conclamato slide 42 PPTX `9249d700`**: la slide ha `normative_ref="DM 03/09/2021 art. 16"` (corretto al rendering), ma titolo "D.Lgs 8 marzo 2006, n. 139" e body parlano di "Norma di riferimento per prevenzione incendi / impianti protezione attiva / sprinkler". Il D.Lgs 139/2006 esiste come decreto reale ma e` "Riassetto del Corpo nazionale VVF" (riforma istituzionale), non norma tecnica antincendio. Il LLM **attribuisce contenuto sbagliato a un decreto reale**.

**Pericolosita`**: massima per credibilita`. Un RSPP che apre la slide 42 e va a verificare il D.Lgs 139/2006 trova VVF reform invece di impianti antincendio → da quel momento ogni slide diventa sospetta. Le speaker_notes amplificano l'errore (il discente sente "Il D.Lgs 139/2006 e` norma fondamentale per impianti sprinkler").

**Perche` V1.5 non cattura**:
- D.Lgs 139/2006 e` morfologicamente legittimo (decreto reale italiano).
- Lo slug normalizzato `dlgs_139_06` NON e` in `course.regulation_ids` ANT L1 (= `[dlgs_81_08, dm_02_09_2021, dm_03_09_2021, dm_01_09_2021]`).
- **Bug**: V1.5 catturerebbe se applicato a titolo + bullets, ma `_check_bullet_citations` scansiona `bullets + speaker_notes + quiz_options`, NON title. Verifica `production_builder.py:_check_bullet_citations` — possibile fix immediato includere `s.title` nei `text_fields`.

**Cura V1.5b (NON immediata, da discutere post-H8)**:
- Estendi `_check_bullet_citations` per scansionare anche `s.title`. Costo 5 min + 1 test.
- Slide 42 verrebbe catturata: regex matcha "D.Lgs 8 marzo 2006, n. 139" nel titolo → slug `dlgs_139_06` → not in course.regulation_ids → warning.

**Cura V2 (semantico, esplorativo)**: verifier LLM auxiliary che valuta coerenza titolo↔body↔normative_ref. Costo 1-2g. Da fare solo se V1.5b + H8 lasciano residuo Tipo 3 significativo.

**Decisione**: V1.5b (title scan) e` quick win da considerare seriamente — 5 min di codice cattura una classe Tipo 3 che oggi sfugge. Trigger: post-H8 se slide come 42 persistono.

### D-176 — H9 numerico vs sostanziale divergenza post-B4 (2026-05-30, pending post-H8)

**Segnaposto.** Sample-read M0 post-B4 ha rivelato divergenza fra H9 numerico (cross-corso regex strict 20.0% PASS) e H9 sostanziale (5/83 on-topic core = 6% FAIL). Pattern *metric ottimizzata, contenuto peggiorato* (memoria `review17-metric-vs-render-lesson`). Risolvibile solo con H8 (vincolo voce-to-slide-cluster nel content_agent), non con calibrazione retrieval-stage. **Pending post-H8, non risolto in ciclo B**. Registrato qui per non perderlo durante il ciclo pulizia D-161/D-175/D-177/D-178.

### Metodo confermato (analista 2026-05-30)

"La sequenza 'leggere log + sample-read PPTX insieme' è il gate giusto. Senza il log non sapevo che Allegato XLI fosse decay_kept e non hard-discarded; senza il render non avrei visto le slide 73-79 con normative_ref cracking. I numeri aggregati (15.8% decisioni cross-titolo, 4.8% scartate hard) sono utili come dashboard ma non sufficienti — il 'perché' sta nel sample, non nella media."

### B3 SIGN-OFF analista 2026-05-30 con 3 raffinamenti

(a) **Decay×0.4 + soglia scarto, NON hard-scarto cross-titolo**. Ragione: hard-scarto non recuperabile da cosine_voyage alto. Se chunk Titolo IV Cantieri ha *altissimo* cosine_voyage al subtopic (perché parla anche di prevenzione incendi in cantieri), hard-scarto lo elimina senza chance. Decay×0.4 + soglia lo lascia in gioco se cosine compensa. Architetturalmente più robusto.

(b) **Titolo atteso del subtopic, NON Titolo dominante calcolato dal pool**. Ragione: su REGIME 3 (PRE M3, GEN M1 voci definitorie) il pool top-30 è già grab-bag; "Titolo dominante" del pool è il Titolo che il grab-bag ha messo più volte, NON il Titolo corretto per il subtopic. Su ANT M0 meno problematico (Titolo dominante "Titolo I-bis Prevenzione incendi" è coerente), ma su PRE M3 voce 1 "Definizione incidente mancato" il pool potrebbe avere Art. 37 (Titolo I formazione) come dominante, e B3 finirebbe per favorire Art. 37 penalizzando Art. 35.

**Soluzione (b)**: usa "Titolo atteso del subtopic" pre-calcolato dal `regulation_slugs` del course_type + indizi del subtopic stesso. Per ANT M0 il Titolo atteso è "D.Lgs 81/08 Titolo I-bis + DM 02/09/2021 Allegato I" (dichiarato nel catalogo). Quel "Titolo atteso del subtopic" è essenzialmente l'opzione (d) di grounding scheletro che era D-166 work-item.

**Fallback se costoso recuperarlo dal DB attuale**: accetta "Titolo dominante per regulation calcolato dal pool" come compromesso, ma con cautela esplicita: **su moduli REGIME 3 il majority vote del pool è già contaminato → B3 potrebbe favorire chunks sbagliati. Registra come limite noto e considera scheletro doppio livello (H8) come soluzione post-V2.**

(c) **Sequenza implementazione: flag dedicato `v2_b3_cross_title_decay_enabled` default False + E2E ANT L1 post-B3 + sample-read analista al render come gate**. Quando E2E post-B3 gira, mandare PPTX all'analista. Lui legge M0 modulo per modulo come ha fatto ora. PASS se ~17-22 slide problematiche residue (corpus-thin strutturale) emergono come previsto; FAIL se B3 elimina meno del previsto o introduce regressioni.

**Aspettativa post-B3 ricalibrata (analista)**: B3 elimina ~15-18 slide cross-titolo veri (Cantieri Titolo IV + ATEX Titolo XI parziali), lascia ~17-22 slide residue corpus-thin strutturale ANT (DM 02/09 sospetto parsing povero + corpus non denso su principi tecnici incendio). Residue sono target di **B4 D9 vincolante + #R14-estesa** (riparsing DM 02/09 + completamento corpus antincendio).

### ANALISTA SIGN-OFF STEP 3 (2026-05-30) — BIVIO A confermato + raffinamento metodologico

**Decisione**: A. HACCP M3 entra nel ground-truth com'è, marchiato `LOW-CONFIDENCE-UNIFORMLY, corpus_parziale (D.Lgs 193/2007 non ingerito)`. NON ingerire 193/2007 prima del ground-truth.

**Razionale dell'analista (concetto da fissare):**
- "Ground-truth pulito" ≠ "ground-truth su corpus completo". Significa classificazione manuale rigorosa di chunks reali estratti dal sistema reale. Il sistema reale avrà SEMPRE corpus parziale su parte del catalogo cliente (30 corsi denso, 15 moderato, 5-10 sottile). Calibrare B2 solo sui regimi denso+moderato e scoprire al corso 47 che non gestisce il terzo = **esatta ripetizione errore review 17** sui regimi corpus-thin.
- Regime LOW-CONFIDENCE-UNIFORMLY è **genuino e ricorrente**, NON artefatto. Cohere max=0.339 non è "rotto", è "onestamente niente fortemente affine sul corpus disponibile". È informazione.
- B2 su questo regime ha senso solo se accoppiato a B4 (sensore corpus-thin vincolante). Su GEN M1/PRE M3/ANT M0 B2 taglia rumore tenendo cuore; su HACCP M3 piatto, B2 da solo non basta: serve B4 in collegamento. Il ground-truth con HACCP M3 dimostra esattamente questo accoppiamento architetturale B2↔B4.

**Disciplina calibrazione raffinata (analista 2026-05-30):**
- Quando calibri B2, REGISTRI DUE NUMERI:
  - `soglia_denso_sparso`: formula che funziona escludendo HACCP M3
  - `soglia_universale`: formula che funziona includendo HACCP M3
- Se vicine → formula relativa è robusta.
- Se divergono → quel regime richiede l'accoppiamento con B4 (registrato come **dipendenza B2↔B4**, non come problema).

**#R14 timing**: ingerire 193/2007 DOPO ground-truth, in tempi sereni, stessa famiglia di "completezza corpus per famiglia normativa" (DM antincendio 02/09 da riparsare). Pre-ingestione: verifica vigenza 2007 → oggi (è ancora vigente? modifiche?). Post-ingestione: ri-misura HACCP M3 voce 1 + tieni numero pre/post in tabella. **NON ricalibrare B2** automaticamente se la soglia originale regge — sample-check chunk in comune. Se cambia molto, capire perché. Se no, niente da fare (è il senso di "relativa").

### STEP 4 raffinato (sign-off analista) — disciplina classify ground-truth

**5 moduli ground-truth** (confermato):
1. GEN M1 voce 1 (regime denso) — già fatto AUDIT 1, da rifinire con motivazione
2. **GEN M2 voce 1** (regime cross-titolo intra-corpus) — DA ESTRARRE
3. PRE M3 voce 1 (regime sparso, on-topic in fondo) — già stress-test, da rifinire
4. ANT M0 voce 1 (regime sparso post-ingest DM 03/09) — già stress-test, da rifinire
5. **HACCP M3 voce 1** (regime LOW-CONFIDENCE-UNIFORMLY, corpus_parziale) — già misurato

**HACCP M2 voce 1**: estrarre come **CONFRONTO DIAGNOSTICO** (NON quinto modulo). Scopo: distinguere se HACCP-tutto è LOW-CONFIDENCE-UNIFORMLY (corpus che manca) oppure solo HACCP M3 lo è (formulazione query specifica). Se M2 ugualmente piatto → corpus. Se M2 meno piatto → query.

**Colonna `motivazione_breve` OBBLIGATORIA in tabella classify:**
- `on-topic`: motivazione 1 riga sul perché È sul sotto-tema specifico.
- `off-topic chiaro`: motivazione 1 riga sul perché NON è sulla voce specifica (NON sul modulo generico). Esempio HACCP M3 voce 1 "Fondamenti normativi": Art. 251 "Direttiva modificata Reg CE 1882/2003" → off-topic perché meta-clausola di modifica regolamentare, non principio dell'autocontrollo.
- `adjacent legittimo`: motivazione PIÙ IMPORTANTE delle altre due. Zona grigia dove B2 farà la differenza. Esempio "Art. 5 del 852 principi HACCP generali → adjacent perché contesto legittimo ma non strettamente autocontrollo italiano".

Senza motivazione la tabella è opinabile in modo opaco; con motivazione è dibattibile in modo trasparente.

### LEZIONE D-160 RICONOSCIUTA dall'analista (2026-05-30)

Analista esplicita la dinamica: "previsione `atteso >0.6` era proxy della verifica, non la verifica. Tu (Claude) l'hai messa alla prova al render e l'hai falsificata coi numeri. Pattern D-160 funziona come deve". Smontare le sue previsioni con i dati al render è applicare disciplina della sessione, non scortesia.

Annotato a verbale per simmetria: l'analista chiede a me di smontare le sue previsioni con i dati come pretendo che io smonti le mie. Vale in entrambi i versi.

**ANALISTA AUDIT D3 GEN M1 (2026-05-29) — SIGN-OFF su 3 domande + direttive calibrazione:**
- **Scheletro FIRMABILE** ✓ procedi. 10 sotto-temi ancorati al perimetro "Prevenzione e protezione", zero cross-corso. Conferma empirica che il principio (a) [tassonomia precede corpus] regge.
- **Residuo formazione/abilitazione nel top-30: LASCIARE a B2, NON aggiustare prompt/retrieval_query ora.** Il rumore di superficie È il ground-truth per calibrare B2. Aggiustare a monte = rompere la disciplina di calibrazione sequenziale + perdere l'oracolo umano (sample-read).
- **Procedi STEP 4-7** ✓.

**DIRETTIVE CALIBRAZIONE B2 — CORRETTE DALL'ANALISTA 2026-05-29 post stress-test (REGOLE NON-NEGOZIABILI):**
- B2 = `cosine(chunk.body_emb, sub_topic.text_emb)` calcolata con **embedding Voyage diretto** (1024-dim, gli stessi già nel DB per i chunk; il sub_topic va embedded via Voyage, NON via Cohere). MAI `cosine(chunk.body, module_title)` (= regressione V2). MAI sul rerank score normalizzato (= collassa le 2 metriche e perdi il filtro). Il rerank Cohere è topical-broad; il cosine Voyage diretto è semantico-stretto. **B2 sfrutta il GAP fra i due**: Cohere fa il recall (top-30), Voyage filtra la specificità che Cohere perde.
- **Soglia RELATIVA, non assoluta.** GEN M1 ha distribuzione max 0.994 / media 0.747; PRE M3 ha max 0.642 / media 0.099. Una soglia fissa su un regime distrugge l'altro. Formula: `scarta se cosine_to_subtopic < (max_cosine_to_subtopic - delta)` oppure percentile relativo al top di quella query. Il delta è tunable; il principio "relativo non assoluto" è non-negoziabile.
- **Ground-truth = sample-read manuale su 3 (4) moduli, NON solo GEN M1**:
  - **GEN M1** (facile, regime denso): scarta righe 4/7/15/25 (formazione/abilitazione), tieni Art.15/30/33/36/225/251.
  - **GEN M2 "Organizzazione della prevenzione"** (cross-Titolo: Coordinatori in edilizia + Modulo A RSPP + sanzioni in V2). Regime diverso da PRE M3 (cross-Titolo vs cross-corso).
  - **PRE M3 voce 1** (cross-corso + corpus moderato, REGIME RIBALTATO): on-topic veri (Art. 19/37/18/226/28) sono **in fondo** al top-30 con score bassi; off-topic (Allegati IV/I formazione/abilitazione) sono **in alto**. La soglia DEVE invertire correttamente questo mis-ranking: premiare chunk in fondo con alta semantica-diretta col sub_topic, penalizzare top Cohere con bassa semantica-diretta.
  - **ANT M0** se economico (quarto, regime corpus-thin coperto post-ingestione DM 03/09).
  - Calibrare su un solo modulo (GEN M1) → soglia tarata sul caso facile → risultati pessimi su PRE M3.

**GATE DISCIPLINARE PRE-B2 (dall'analista, non-negoziabili):**
1. **E2E completo flag-on PRIMA della calibrazione B2.** D3 è validato pezzo per pezzo (modelli/skeleton_service/smoke resume) ma non end-to-end con research→skeleton_pending→approve→content su corso reale. Calibrare su un sistema non E2E-verificato incorpora artefatti del flow (edge case approve, serializzazione skeleton DB) nella soglia. Prima E2E, poi calibrazione.
2. **Oracolo umano sui 3-4 moduli, NON uno solo** (vedi sopra).
3. **Quarto audit "neutro" fuori dal dominio 81/08-base** prima di partire con B2 — suggerito HACCP o RLS 32h. Check di universalità sul catalogo intero, non solo sui 3 corsi di review storica. Se (a) pura tiene anche su un dominio non-81/08 → confermato che scala.

**DIRETTIVA B3 (più semplice ma confermata):** edge `gerarchico_sibling`/`gerarchico_parent` che attraversa Titoli diversi del D.Lgs → decade fortemente o scarta. Pattern: ALLEGATO XVI (Titolo IV Cantieri) tirato dentro Art.15 (Titolo I) per ereditarietà = traversata troppo larga. La regola "stesso Titolo" è più stringente e più giusta del solo peso 0.4.

**NUOVE OSSERVAZIONI SCHELETRI POST-STRESS-TEST (non bloccanti, registrate):**
- Pattern "manualistico-normativo" confermato anche su PRE M3 e ANT M0 (estensione di D-167): scheletri ben strutturati come mappe normative, mancano dell'angolo didattico-pedagogico (PRE M3 #3 "Analisi cause" è metodologico astratto, manca "5-perché/fishbone/learning culture"; ANT M0 manca "perché studiamo questo: casi recenti in aziende italiane"). Conferma che la (a) pura è production-ready per il valore strutturale (cross-corso-clean); l'arricchimento didattico è punto d'ingaggio dell'esperto via UI ("aggiungi voce"), non urgente, raffinamento futuro del prompt skeleton-generator.
- PRE M3 voce #6 "Analisi dei dati per miglioramento continuo" è fragile (potrebbe pescare DVR/PDCA generico in qualunque altro corso). PRE M3 #4/#5 hanno mini-overlap interno (preposto/procedure). NON bloccanti, da osservare al top-30 quando arriverà.

**DIRETTIVA SCHELETRO STRESS-TEST PRE M3 — già FATTO 2026-05-29: stress-test eseguito.** Sub-topic 1 voce 1 produce un retrieval con distribuzione molto diversa da GEN M1 (max 0.642, media 0.099, on-topic veri in fondo). Questo regime IS il caso di calibrazione per B2 relativo.

**DIRETTIVE CALIBRAZIONE B3 (quando arriva F2.13):**
- B3 NON è solo "peso sibling 0.4". È **strutturale**: se l'edge `gerarchico_sibling`/`gerarchico_parent` attraversa **Titoli diversi del D.Lgs**, scarta o decadi forte. Pattern: ALLEGATO XVI (Titolo IV Cantieri, scope coordinatori) tirato dentro Art.15 (Titolo I) per ereditarietà = traversata troppo larga. Gli allegati cross-Titolo sono il pattern da osservare. La regola "stesso Titolo" è più stringente e più giusta del solo peso.

**OSSERVAZIONI SCHELETRO (note calibrazione futura, NON blocchi):**
- Sotto-tema #9 "Controllo e vigilanza sull'applicazione" ha un piede in M2 "Organizzazione della prevenzione". Fragile per natura del corpus: a valle il top-30 by-subtopic della voce #9 potrebbe pescare "sanzioni/ricorsi/pagamento somme aggiuntive" (vecchio cluster sanzionatorio). Se accade → riformulare in skeleton-generator-v2 con anchor più stretto ("vigilanza del datore sulle misure INTERNE", non "controllo ispettivo esterno"). Tenuto nello scheletro corrente. **DA OSSERVARE quando arriva il top-30 voce #9.**
- **D-167** [esplorativo, non urgente]: lo scheletro è "manualistico-normativo" per default (mappa che farebbe un giurista del D.Lgs), manca dell'angolo DIDATTICO-pedagogico che aggiungerebbe un formatore: (a) gerarchia dei controlli (eliminazione→sostituzione→tecnici→amministrativi→DPI), (b) partecipazione del lavoratore come attore preventivo. Conseguenza diretta del grounding (a). Future: testare un grounding (a+) con hint pedagogico esplicito nel prompt skeleton ("proponi sotto-temi pensando a come un formatore strutturerebbe la lezione, non come un giurista mapperebbe la norma") su 2-3 corsi prima di renderlo default. È anche il punto dove la review-utente fa la differenza promessa al cliente (l'esperto aggiunge "gerarchia controlli" come voce in 5s via UI).

**STRESS-TEST RICHIESTO dall'analista** (dopo UI attiva, prima di B2): audit scheletro su **PRE M3 "Incidenti e infortuni mancati"** (caso peggiore cross-corso V2) + **ANT M0 "Principi dell'incendio"** (caso corpus-thin). Se la tassonomia (a) pura regge anche su quei due → conferma che scala oltre il caso facile GEN M1. Quello è il vero stress-test prima di B2.

**→ STRESS-TEST ESEGUITO 2026-05-29: (a) PURA SCALA, PASS su entrambi** (`D3_STRESS_PRE_M3_ANT_M0.md`, su Desktop):
- **PRE M3** (era 90% cross-corso V2): scheletro 7 sotto-temi TUTTI su incidenti/infortuni mancati, ZERO sconfinamento RSPP/Coordinatore/Datore. Patologia 90% eliminata alla radice. top_score voce1=0.642 (corpus near-miss meno ricco = densità, non cross-corso).
- **ANT M0** (era 0.473 corpus-thin V2): scheletro 8 sotto-temi tecnici antincendio puri, ZERO ruoli formativi/ASL. **top_score voce1=0.814** (quasi 2× il 0.473): corpus DM 03/09 ingerito + retrieval by-subtopic. Da corpus-thin a coperto.
- Su 3 moduli (GEN M1 + PRE M3 + ANT M0) (a) pura tiene. D3 fondazione pronta. Residuo medio → B2/B3.

**D3 IMPLEMENTAZIONE** (commit 9551958, 6e61cca, 134add0, 77bc66b): backend completo (modelli 5 test, skeleton_service, pipeline interrupt, generation split, API) + frontend (skeleton-review.tsx, tsc EXIT 0). mypy/ruff verdi. **Smoke LangGraph resume PASS** (interrupt+aget_state+aupdate_state as_node+ainvoke None su 1.2.1). **BUG thread_id job_id→course_id scoperto e fixato durante lo smoke** (134add0) — research/content sono 2 job ma 1 thread checkpoint. **DEBT D3**: NON ancora E2E completo flag-on su corso reale (research→skeleton_pending→approve→content). Validato pezzo per pezzo. Flag `skeleton_validation` OFF in prod = zero impatto cliente.

**E2E D3 HACCP LOMBARDIA — PASS completo 2026-05-29 → 2026-05-30** (`/Desktop/V2_AB_TEST_20260529_125641/D3_E2E_HACCP/`):
- Setup: V2_RERANK_ENABLED=true + V2_SKELETON_VALIDATION=true + V2_KG_TRAVERSAL_ENABLED=false su Railway prod. Migration 007 applicata.
- Path completo verificato sul campo: research→skeleton_pending (3 min, 4 scheletri Azure mini) → GET skeleton OK → POST approve OK → content phase (10 min) → completed.
- **PPTX 52 MB con immagini Pexels reali**, 336 slide, distribuzione perfettamente equa **84+84+84+84**, citation_ref popolata 328/336 (98%) tutte `Reg. CE 852/2004, allegato/art.`
- **CROSS-CORSO check sul prodotto FINALE (non solo scheletro)**: pattern regex su RSPP/Coordinatore/Preposti/antincendio nei titoli+bullets+notes di tutte le 336 slide → **0/336 = 0.0%**. D3 strutturalmente efficace END-TO-END, non solo allo stadio scheletro. La pipeline materialize_by_subtopic → content_agent → builder rispetta il perimetro normativo HACCP.
- M3 "Autocontrollo" 84 slide (era a 2 in #22 — patologia esclusa). Primi titoli M3 mostrano l'angolo giuridico-procedurale ("Relazione Commissione", "Abrogazione direttiva 93/43/CEE") = pattern D-167 confermato (manualistico-normativo, manca angolo didattico). NON cross-corso, è meta-normativo. Atteso.
- **L'analista aveva ragione**: l'E2E ha pescato 1 bug bloccante (D-168 region filter europeo, parzialmente compensato da BM25) e 1 bug strutturale fatale che migration 007 ha risolto (CHECK constraints). Calibrare B2 senza E2E avrebbe incorporato questi artefatti nella soglia.

**D-168** [BUG strutturale retrieval region filter — scoperto da E2E HACCP 2026-05-29]: il filtro region in `knowledge_repo.search_chunks` (`r.region = 'NAZIONALE' OR (region_param IS NOT NULL AND r.region = region_param)`) SCARTA tutti i regolamenti con `region='EUROPEA'` (Reg CE 852/2004 HACCP, Reg CE 1272/2008 CLP). Conseguenza: `cosine_size=0` sempre per corsi che dipendono da regolamenti europei → recall_hybrid degrada a solo BM25 → top_score rerank sotto soglia ALERT (visto su HACCP M3 = 0.367 under_alert_threshold=true). BM25 funziona perché è caricato in-memory via `regulation_id`, NON filtrato per region. Fix candidato: estendere il filtro a `r.region IN ('NAZIONALE','EUROPEA') OR r.region = region_param` (regolamenti europei sono fonti universali come quelli nazionali). Bug strutturale di v2 retrieval, NON specifico HACCP — colpisce ogni corso col Reg CE nei `regulation_slugs`. Non bloccante per D3 (BM25 sta facendo il recall), ma bloccante per qualità retrieval v2 nei domini europei. Da fixare PRIMA di B2 calibrazione (il ground-truth multi-modulo non deve includere casi con cosine_size=0 perché distorce la calibrazione della soglia).

**D-166** [TOC normativo non strutturato]: opzione (d) deferred — `article` ha "Art. 15" ma non il titolo "Misure generali di tutela", andrebbe estratto dai body (rumore case/frammenti). (a) pura dimostrata sufficiente su GEN M1. Tornare su (d) SOLO se in futuro (a) produce uno scheletro discutibile (visibile via sample-read). Non rincorrere ora.

PRECEDENTE: 2026-05-29 — **ANALISTA REVIEW 17: V2 BOCCIATA, regress strutturale. Tutti i 3 V2 archiviati, flag v2_rerank_enabled e v2_kg_traversal_enabled spenti su Railway. F2.11 velocizzazione sospesa. Pipeline cliente torna a legacy (drop-list + query expansion).**

**ANALISTA REVIEW 17 (2026-05-29) — sintesi diagnosi**:
- I 3 V2 A/B (ANT/GEN/PRE) sono **regress vs baseline review 10/12/13**. Verdetto netto: nessuno ship.
- **Patologia nuova: cross-corso contamination**. PRE M3 "Incidenti mancati" ha ~90% slide su altri corsi del catalogo (Modulo A RSPP, Coordinatore in edilizia, Datore di Lavoro RSPP, incaricati antincendio). GEN M1+M2 ~20-50% cross-corso (RSPP, Preposti, Coordinatore). ANT M0 ~70/84 slide su ruoli formativi/abilitazione docenti/ASL ispettiva invece di principi dell'incendio.
- Le mie metriche regex storiche (M1 medico/bio, M3 ATEX) **non vedono la patologia nuova** perché cercano i pattern vecchi. Vittoria sulle metriche storiche (M1 1.2% vs 0% baseline, M3 0% vs 0.9% baseline) **irrilevante** rispetto al cross-corso reale. Pattern classico: "metrica misura il problema vecchio; patologia si sposta in dimensione nuova; tu vedi verde sui numeri e rosso sul file".
- **Causa tecnica triplice**:
  1. Cohere rerank-multilingual-v3.0 troppo "topic-broad": classifica come rilevante qualsiasi chunk topicalmente vicino a "formazione sicurezza", senza filtrare per il sotto-tema specifico del modulo.
  2. KG `gerarchico_sibling` (18308 edge = 85% del totale) weight 0.7 + 1-hop è la porta principale del cross-corso. Sibling normativi (art. 35-37 D.Lgs 81/08) attraggono materiale di formazione-in-generale di tutti i corsi del catalogo.
  3. D3 scheletro narrativo **non implementato**: senza spina dorsale per-modulo, rerank+KG sono retrieval topic-libero. Analista aveva indicato in review 16 "B3 è B1+retrieval-per-voce, è l'unico che attacca la causa". V2 è proseguito senza B3 → conferma empirica della previsione.
- **Sensore D9 corpus-thin ANT M0 = 0.473** ha funzionato come misura, **ma non c'è azione collegata**: il sistema ha visto "modulo povero" ma ha riempito 84 slide con cross-corso invece di limitarsi a 10-15 slide reali con badge "modulo richiede più corpus". Pattern classico: "sensore senza azione = spia accesa che nessuno guarda".

**Discrepanza grave D-160 (REI-17)**: il MESSAGGIO 1 inviato all'analista riportava "V2 MIGLIORA del 73% (M1 PRE 1.0% vs 3.7%)". Le metriche regex erano TECNICAMENTE corrette ma misuravano il pattern sbagliato. Avrei dovuto fare sample-read di 30 slide per modulo prima di dichiarare vittoria. Fallimento di metodo da non ripetere: davanti a un nuovo retrieval architetturalmente diverso, NON usare le stesse regex pensate per la patologia vecchia come unico oracolo.

**5 cure proposte dall'analista, tutte universali (verificato 1-by-1):**
1. **D3 scheletro narrativo validato** (~3 giorni) — l'LLM propone 6-10 sotto-temi per modulo, esperto valida 1-click, retrieval per voce non per titolo. CURA STRUTTURALE PRINCIPALE.
2. **Filtro post-rerank title-alignment** (~3-4h) — `cosine(chunk.embedding, module_title.embedding)` con soglia, scarta cross-topic. 20 LOC, universale.
3. **Restringere KG sibling** (~2h) — peso 0.7→0.4 + vincolo "same-normativa AND same-course_type_catalog". Tipi `cita`/`attua` invariati (sono direzionali e safe).
4. **D9 vincolante + nuovo sensore cross_course_contamination_rate** (~1 giorno) — il corpus-thin diventa BlockingError (non più log), nuovo sensore traccia il `course_type_slug` di provenienza dei chunk reranked.
5. **Ingestione corpus antincendio** (parallel, dominio) — ⚠️ **CORREZIONE REI-16 (D-161)**: l'analista ha indicato DM 10/03/1998, ma quel decreto è **ABROGATO dal 29/10/2022**, sostituito dai 3 DM del settembre 2021 (verificato via web 2026-05-29). Corpus corretto VIGENTE: **DM 03/09/2021 "minicodice"** (criteri generali, manca in DB) + **DM 01/09/2021** (controllo impianti, manca) + `dm_02_09_2021` già in DB (58 chunks, da valutare re-parsing). UNI EN ISO sono coperte da copyright → non liberamente ingeribili come i decreti GU. Segnalato all'analista nel MESSAGGIO 3 per conferma prima di procedere. Ingerire il DM 1998 violerebbe REI-2 (normativa = fonte di verità) inserendo norma non applicabile.

**Azioni immediate (2026-05-29):**
- ✅ V2_RERANK_ENABLED=false, V2_KG_TRAVERSAL_ENABLED=false su Railway prod (verificato via railway variables)
- ✅ 3 corsi V2 archiviati (DELETE /api/courses): `02e69035`, `8089d9d8`, `3b6763e6`
- ✅ F2.11 velocizzazione SOSPESA (analista esplicito: "prima di ottimizzare la velocità di un sistema, vale la pena assicurarsi che il sistema produca la cosa giusta")
- 🟡 MESSAGGIO 3 in preparazione con 2 dubbi architetturali: (a) ordine B2+B3 vs D3 (rapida riduzione cross-corso oppure debt rumore?), (b) definizione concreta cross_course_contamination_rate quando un chunk appartiene a piu' course_types (set, non singolo).
- ⏸️ F2.12-F2.14 (cure B2/B3/B4) e F3 (D3 scheletro) IN ATTESA risposta analista su ordine.

**ANALISTA RISPOSTA a review 17 (2026-05-29) — direzione vincolante sulle 4 cure + 4 nuove discrepanze quiz:**

**Dubbio 1 — SEQUENZA, non parallelo.** D3 → calibra B2+B3 con D3 attivo → B4. ~2 settimane. Motivazione: D3 cambia il retrieval da by-title a by-subtopic, quindi le soglie cosine di B2 (title-alignment) e i pesi di B3 (KG sibling) vanno calibrati DOPO D3, sui dati che D3 produce — calibrarle ora = calibrarle sul mondo sbagliato. "Una variabile per volta" (disciplina ribadita). **Avvertenza esplicita analista**: "tra D3 e B2+B3 ci sarà la tentazione di dire 'D3 da solo è già molto meglio, ridimensiono B2' — RESISTI: D3 da solo migliora ma NON chiude la classe cross-corso, la chiude solo accoppiato al filtro title-alignment. I 4 meccanismi sono un sistema, non 4 optional." Calibrazione = generare con D3 attivo + soglie candidate (B2: 0.55/0.65/0.75; B3 peso sibling: 0.3/0.4/0.5) su 3-4 corsi che coprano i casi limite (GEN ombrello, ANT corpus-thin, PRE cross-corso forte, idealmente HACCP dominio diverso), sample-read manuale 15-20 slide/modulo, scegliere il compromesso falsi-positivi/falsi-negativi. UNA passata, set sufficiente.

**Dubbio 2 — Interpretazione 3 RAFFINATA.** `cross_course_contamination_rate`:
```
cross_corso_chunk(chunk, target_module, target_course):
  other_modules = [m for c in catalog for m in c.modules if c.slug != target_course.slug]
  max_other = max(cosine(chunk.body_emb, m.title_emb) for m in other_modules)
  target_score = cosine(chunk.body_emb, target_module.title_emb)
  return max_other > target_score AND max_other > SOGLIA  # es. 0.55
cross_course_contamination_rate(top30):
  return count(c for c in top30 if cross_corso_chunk(c, ...)) >= K  # K=5, conta assoluta non %
```
Raffinamento chiave: **escludere i module_titles del corso target dal confronto** (sennò un chunk intra-corso PRE M3↔M4 verrebbe flaggato come cross-corso — ma intra-corso è problema diverso e di solito legittimo). Conta ASSOLUTA (K=5/8), non percentuale (% su 30 è volatile, 1 chunk = 3.3%). Scartate interpretazione 1 (course_type provenance — verde su tutto) e interpretazione 2 (chunk_specificity 1/N — costoso + va ricalcolato a ogni corso nuovo + algoritmo giudice di sé stesso). **+ sensore gemello `cross_module_repetition_rate`**: quante volte lo stesso chunk_id finisce reranked in moduli diversi DELLO STESSO corso (duplicato cross-modulo, patologia adiacente).

**Corpus antincendio — confermato con correzione.** DM 03/09/2021 (minicodice, prioritario, criteri tecnici generali) + DM 01/09/2021 (controllo impianti) da ingerire. DM 02/09/2021 l'analista chiedeva di RIPARSARE (58 chunks sospetti). UNI EN 3 / UNI 9994 **FUORI dal corpus** (copyright), ma referenziabili come edge `cita` verso `external_reference` placeholder (citazione bibliografica del titolo norma ≠ riproduzione contenuto, conforme copyright).

**→ CORPUS ANTINCENDIO INGERITO 2026-05-29 (lavoro indipendente, no attesa analista):** scaricati da fonte ufficiale GU + mirror università/ordini i 2 DM mancanti VIGENTI e ingeriti in prod:
- **DM 03/09/2021** (minicodice) `5de40c14`: 69 chunks, 127 KB, media 1844 char/chunk, embeddings 0 NULL — ben dimensionato. È il decreto tecnico chiave per i moduli Principi/Prevenzione/Protezione.
- **DM 01/09/2021** (controlli) `fd84d835`: 25 chunks, 560 KB, **media 22.416 char/chunk = CHUNK TROPPO GROSSI** (debt minore: il chunker non ha segmentato bene un PDF da 24pp; 25 chunk da 22K degradano il retrieval perché matchano troppe query genericamente). Marginale per ANT (è "controlli impianti"), da risistemare con re-parse se serve. Annotato come **D-165** [chunking].
- **Corpus antincendio totale: 58 → 152 chunks** (quasi triplicato).
- Linkati i 2 DM al course_type `antincendio_livello_1` in `regulation_course_type_links` (source=manual) + aggiunti ai `regs` hardcoded in `config/catalog_config.py` (la pipeline legacy li userà nel retrieval di ANT).
- **D-165** [chunking DM 01/09/2021]: 25 chunks da 22K char medi. Da re-parse con segmentazione più fine prima di considerare ANG L1 "ricoperto" sul tema controlli/manutenzione. Non bloccante per i moduli principali (minicodice + dm_02_09 coprono Principi/Prevenzione/Protezione).

**→ DM 02/09/2021 INVESTIGATO 2026-05-29: NON è parsing povero, è thin per natura.** L'ipotesi "58 chunks = parsing rotto" verificata e SMENTITA dai dati: in DB ha **137 KB di testo su 58 chunks** (media 2364 char/chunk), allegati corposi (ALLEGATO II=11.728, IV=5.515, IX=2.897 char). Confronto col PDF locale (23pp, 66 KB pdfplumber): il DB ha **207% del testo del PDF locale** → ingestione F1 da fonte GU più ampia, parsing OK. Anomalie: 1 solo chunk frammento (<30 char) su 58 = irrilevante, no re-parse. **Conferma: il sensore D9 ANT M0=0.473 segnalava corpus-thin REALE, non artefatto.** Il DM 02/09/2021 è genuinamente snello. Fix corretto = ingerire DM 03/09 + 01/09, NON riparsare il 02/09. Da comunicare all'analista nel prossimo giro.

**D-160** [REI-17, a verbale]: "V2 +73% sulla regex M1 medico/bio misurava il pattern sbagliato". Audit metrico ≠ verifica al render. Sample-read manuale 30 slide/modulo obbligatoria prima di dichiarare "migliora" su retrieval architetturalmente nuovo.

**D-161** [REI-16/REI-2, a verbale]: ogni proposta di ingestione normativa DEVE verificare lo stato di vigenza PRIMA del download. (Analista aveva proposto DM 10/03/1998, abrogato dal 29/10/2022 — verificato via web. La regola "il sistema cita la fonte vigente" vale anche per chi propone l'ingestione.)

**D-162** [layer rendering]: "Cura applicata a livello slide, non a livello layout, su elementi template-ereditati." Il fix quiz precedente rimuoveva `nx_correct_marker` + `nx_correct_bar` slide-per-slide (92 shape su 46 quiz × 2 = aritmetica perfetta), MA la barra verde viveva nel **layout NX QUIZ**, non nelle singole slide → sopravviveva per ereditarietà. Verifica della cura = RENDER post-fix, NON conteggio shape rimosse. Vale per ogni mutazione (rimozione/override/sostituzione) che competa con eredità slide_layout/slide_master.

**D-163** [effetto collaterale canale]: "Quando rimuovi un elemento UI rotto, traccia dove finisce l'informazione che portava." Il fix quiz aveva spostato "Risposta corretta: X" nelle note relatore "per non perdere l'info" → ma la voce TTS narra le note → avrebbe pronunciato la risposta corretta ad alta voce a ogni quiz. Prima di spostare info, verifica che il nuovo canale non abbia effetti downstream indesiderati.

**D-164** [fix pipeline NON fatto, root template] → **✅ FIXATO 2026-05-29 (parziale, per decisione utente)**: i 3 demo cliente erano stati sanati a posteriori (script rimozione shape da layout+slides post-build), MA il builder continuava a generare la barra nel layout NX QUIZ di OGNI nuovo corso. **Fix root applicato**: rimosso `nx_correct_bar` (AUTO_SHAPE fill 769E2E, barra verde orfana a T=4.06 tra le card A/B e C/D — elemento decorativo che non indicava nessuna risposta, solo rumore visivo) dal Layout 5 'NX QUIZ' di `assets/templates/nexus_master_v4_patched.pptx`. Backup `.pre_D164_bar_removal.bak`. Layout passa da 19 a 18 shape. `nx_correct_bar` non era referenziato in nessun codice builder (verificato via grep) → rimozione zero-impatto. Template ricarica OK, tutti i placeholder builder presenti, slide QUIZ renderizzabile. **DECISIONE UTENTE 2026-05-29**: lasciato `nx_correct_marker` (canale del testo "Risposta corretta: X" scritto dal builder a slide_builder_v2.py:632) — la scelta mostra-sì/mostra-no la risposta sulle slide quiz è rimandata ("decido dopo, per ora solo togli la barra verde rotta"). Quando si deciderà: o text box pulito (mostra) o rimozione completa marker+testo (quiz in bianco). **Ogni nuovo corso d'ora in poi nasce senza barra verde orfana.** Lo script di sanatoria resta utile solo per i 3 demo storici già consegnati.

**Primo audit intermedio richiesto dall'analista** (quando D3 implementato): mandare (a) 1 scheletro proposto dall'LLM su GEN M1 "Prevenzione e protezione" per giudicare qualità proposta pre-validazione, (b) dump top-30 reranked per quella voce di scheletro per vedere distribuzione score prima di calibrare B2. "Non è ferma/continua, è calibriamo B2 sui dati giusti."

PRECEDENTE: 2026-05-29 — **v2 refactor FASE 2 step 1-8 chiusi (rerank Cohere + graph_service + backfill 21451 edge + 1-hop traversal). Solo F2.9 A/B prod residuo.**

**Fase 2 step 5-8 — knowledge graph (D1 piano vast-hopping-sketch):**
- **F2.5 `app/services/graph_service.py` NUOVO** (~520 righe, mypy+ruff verdi):
  - `_ChunkResolver` cache in-memory (article+paragraph → chunk_id) caricato 1 volta per regulation. **Critico per performance**: la versione N+1 query-per-match droppava la connessione TCP proxy Railway sul D.Lgs 81/08 (1819 chunks).
  - `extract_deterministic_edges(chunk_id, body, regulation_id, pool, resolver)` — regex pattern: `art. N` (+ comma adiacente) / `allegato N` + classify_intent `cita`/`modifica`/`attua` da contesto pre-match 80 char. Self-edge skip + dedup intra-chunk.
  - `extract_hierarchical_edges(regulation_id, pool)` — parsing `hierarchy_path` con separatore `" > "`, genera `gerarchico_parent` (prefix exact match) + `gerarchico_sibling` (shared_path). Su regulations con AST regolare (D.Lgs 81/08, Reg CE 1272) trova 9000+ edge.
  - `extract_llm_edges(...)` — proposta LLM `e_definito_da` + **gate VAA Jaccard ≥ 0.15 su entità normative estratte** OR ref overlap shared. Solo dopo verifica programmatica l'edge entra con `source='llm_verified'`, `weight=0.7`, `extraction_context={gate_method, gate_value}`. Pattern: "sistema propone, gate verifica". DISABILITATO al primo pass.
  - `persist_edges(...)` — `executemany` batch + `pool.acquire()` esplicito + pre-count via `UNNEST` 3-colonne. Idempotente via `UNIQUE(src,dst,kind) ON CONFLICT DO NOTHING`. Sostituisce il pattern N execute() per edge che droppava la connection sul proxy Railway.
  - `extract_and_index_edges(regulation_id, pool, enable_llm)` — orchestrator: 1) hierarchical regulation-wide; 2) deterministic per chunk con resolver caricato 1 volta; 3) LLM opzionale.
- **Smoke test F2.5 4/4 PASS** contro `dm_388_2003` (23 chunks): h=2, det=10, idempotency OK (seconda insert=0), cleanup OK. Tempo: 3 sec post-refactor (era 10 sec con N+1).
- **F2.6 hook in `ingestion_service.ingest_regulation_file`** (subito dopo `index_chunks`, prima del `logger.info("regulation_ingested")`): if `v2_features.kg_traversal_enabled` → `extract_and_index_edges()`. Try/except non-bloccante (graph è additional layer, ingestion non rompe per fallimento graph). mypy verde sul mio scope (errori preesistenti su `_classify_one` typing dict invariance fuori scope).
- **F2.7 backfill `scripts/backfill_edges_existing.py` (gitignored) — eseguito su prod via TCP proxy**:
  - 7 regulations VIGENTE processate, **21451 edge totali in 78s**:
    - `accordo_stato_regioni_2011` (27 chunks): 38 hier + 13 det = 51 edge in 5.4s
    - `accordo_stato_regioni_2025` (133 chunks): 814 hier + 28 det = 842 edge in 6.4s
    - `dlgs_81_08` (**1819 chunks**): 9574 hier + 568 det = **10142 edge in 16.2s** (era N+1 timeout pre-refactor)
    - `dm_02_09_2021` (58 chunks): 63 hier + 16 det = 79 edge in 3.8s
    - `dm_388_2003` (23 chunks): 2 hier + 10 det = 12 edge in 4.1s
    - `reg_ce_1272_2008` (**672 chunks, regolamento più denso**): 9537 hier + 346 det = 9883 edge in 37s
    - `reg_ce_852_2004` (147 chunks): 385 hier + 57 det = 442 edge in 4.7s
  - **Distribuzione kind+source post-backfill**:
    - `gerarchico_sibling` deterministic: 18308 (corpus con AST regolare)
    - `gerarchico_parent` deterministic: 2105
    - `cita` deterministic: 1003
    - `attua` deterministic: 26 (contesto "in attuazione" pre-match)
    - `modifica` deterministic: 9 (contesto "modifica/sostituisce/abroga" pre-match)
  - **0 edge `llm_verified`** (al primo pass enable_llm=False — costo non giustificato finché 1-hop traversal su deterministic non avrà mostrato beneficio).
- **F2.8 `expand_via_kg_1hop()` in `retrieval_v2.py`**: post-rerank Cohere, se `v2_kg_traversal_enabled=True` segue gli edge `source='deterministic'` dai top-30, idratta i dst con `score = src_score * 0.7 * edge_weight`, deduplica per chunk_id (max score vince), riordina decrescente. Solo edge deterministic per VAA-b (l'LLM resta gated nella sua fase).
- **Smoke test F2.8 PASS** su `dlgs_81_08` modulo "Concetti generali": 30 rerank Cohere + **148 chunk 1-hop** = 178 totali. Top rerank = Art. 15 score 0.970 (misure generali tutela), top kg_1hop = Art. 6 score 0.652 (organi/funzioni — citato da Art. 15). Telemetria emette `graph_traversal` con `edges_followed=267, new_chunks_proposed=148`.

**Discrepanza D-152 (edge graph chunk-chunk) — IMPLEMENTATA**: l'edge-table esiste, è popolata, ed è consumabile via 1-hop traversal. Resta `llm_verified` non attivato (costo, validare A/B prima). Edge cross-regulation (D.Lgs 81/08 ↔ Reg CE 1272 ↔ Accordo 2025) — non implementato (resolver e' intra-reg only). Work-item: aggiungere `_resolve_target_chunk_cross_reg` con slug-map se A/B mostra valore di citazioni cross-norma.

**F2.9 A/B prod IN ESECUZIONE (2026-05-29 11:58 UTC+2, dopo 3 round di fix):**
- Round 1 (11:38): primi 3 corsi falliti subito con `UndefinedTable: relation "checkpoints" does not exist` — debt **#R11** noto da FASE 6 mai chiuso. AsyncPostgresSaver.setup() non eseguito su prod, i 3 demo originali erano insertati direttamente in `courses` senza far girare la pipeline. Fix permanente in commit `787b286`: chiamata `setup()` idempotente all'avvio del backend, dopo pool init e prima di `recover_interrupted_jobs`. Closes #R11.
- Round 2 (11:46): 3 corsi falliti per `OpenAIError: Missing credentials` su DeepSeek L0 della chain. `DEEPSEEK_API_KEY` era vuota su Railway; settata + redeploy. **MA** richiamo dell'utente: il baseline dei 3 demo approvati dall'analista (review 10/12/13) era con Azure gpt-4.1-mini, non DeepSeek. Per A/B onesto v2-vs-baseline devo isolare le variabili → la sola differenza ammissibile è (rerank Cohere + 1-hop KG). Commit `ecd7e92`: chain CLASSIFY rimaneggiata in `_FALLBACK_CHAIN_CLASSIFY` mettendo Azure L0 (era L1), DeepSeek scalato a L1.
- Round 3 (11:58): 3 corsi A/B avviati dopo deploy commit `ecd7e92`. **Pipeline v2 vista LIVE in azione**: Antincendio L1 4h, log `phase=recall_hybrid` + `phase=rerank_cohere` + `phase=graph_traversal` + `module_retrieval_v2_done` PER OGNI MODULO:
  - M0 "Principi dell'incendio": top_score **0.473** (borderline ma >0.45 ALERT threshold), edges_followed=324, final_size=210 chunks
  - M1 "Prevenzione incendi": top_score 0.997, edges_followed=252, final_size=168
  - M2 "Protezione antincendio": top_score 0.987, edges_followed=224, final_size=161
  - M3 "Procedure operative": top_score 0.980, edges_followed=251, final_size=162
  - Totale 701 chunks dai 4 moduli, `modules_under_alert=[]` (nessun ALERT). M0 a 0.473 è un sensore D9 utile: il corpus DM 02/09/2021 ha solo 58 chunks e "Principi dell'incendio" è il modulo più teorico → top_score 5× più basso degli altri 3 è coerente col disegno D2/D9 (distingue limite-corpus da problema-algoritmico).
- **12 corsi zombi archiviati** dai 3 round falliti.
- **Pipeline v2 in produzione FUNZIONA tecnicamente.** Il content_agent ora consuma i ScoredChunks v2: verifica qualità finale richiede attesa fine 3 corsi (~30-45 min) + confronto manuale.

**Course IDs finali A/B (round 3)**:
- Flag attivati su Railway prod: `V2_RERANK_ENABLED=true`, `V2_KG_TRAVERSAL_ENABLED=true`. Backend redeployato con commit `b476538` (build digest sha256:9c961698c7d9, healthcheck PASS).
- **Antincendio L1 4h** `02e69035-ba1b-4fd3-9d6c-1bc4b0224138` (344 slide stimati) — testa il sensore D9 `module_corpus_thin` (corpus DM 02/09/2021 = 58 chunks vs 1819 del D.Lgs 81/08). Vista live a 11:58: M0 top 0.473 (borderline), M1-M3 top 0.98+.
- **Generale 4h** `8089d9d8-e830-4405-85c3-188481679c06` (344 slide stimati) — confronto regressione vs Demo #2 v3 review 13: target è confermare che M1 "Prevenzione e protezione" non riemerga al 46% medico/biologico ora che il rerank Cohere sostituisce le 38 query expansion hardcoded + drop-list M1.
- **Preposti 8h** `3b6763e6-b51e-4a16-9880-b582f7d44e65` (688 slide stimati) — confronto vs Demo #3 v2 review 12: target è M3 "Incidenti e infortuni mancati" che era "patologia confermata empirica: 5 chunk, lost 47/40/41 su M1/M4/M5", verificare se rerank+kg_1hop riequilibra senza dover ricorrere a drop-list specifica.
- Polling in background, attesa ~30-45 min totale (REI-3 Semaphore(1) si applica sul builder PPTX).

**Cosa NON verifica ancora (debt F2):**
- Edge cross-regulation (D.Lgs 81/08 ↔ Reg CE 1272 ↔ Accordo 2025) — non implementato (resolver intra-reg only). Work-item: aggiungere `_resolve_target_chunk_cross_reg` con slug-map se A/B mostra valore di citazioni cross-norma.
- Edge `llm_verified` NON popolati al primo backfill (enable_llm=False): se A/B mostra che il 1-hop deterministic basta, possiamo lasciare LLM disabilitato (risparmio costo). Se manca semantica di "definizione concetto", attivare LLM-pass mirato.

**Fase 2 step 1-4 — cuore del retrieval v2 (D2 del piano vast-hopping-sketch):**
- **F2.1 COHERE_API_KEY** settata su Railway `EduVault` (`--skip-deploys`). Provider attivo: `rerank-multilingual-v3.0` free tier (1000 req/mese, sufficienti per A/B test e prima sessione prod). Chiave residente SOLO in env var Railway + memoria locale di questa sessione, **mai committed in repo** (gitignore copre tutti gli script smoke).
- **F2.2 `app/services/retrieval_v2.py` NUOVO** (~470 righe, mypy --strict + ruff verdi):
  - `autogen_module_query()` 1 LLM call (chain `task=classify` → DeepSeek/Azure/OpenAI/Anthropic) che genera la query semantica per il modulo. Output JSON `{"query": "<15-30 parole>"}` per essere compatibile con `response_format=json_object` imposto dalla fallback chain di `ingestion_service.call_llm`. Fallback a `module_title` puro se l'LLM emette query <5 parole.
  - `recall_hybrid()` BM25Okapi (su body in-memory, ~3 MB su 7 normative × 2879 chunk) + cosine via `knowledge_repo.search_chunks` esistente (Voyage 1024-dim su HNSW pgvector), fusi via **Reciprocal Rank Fusion** k=60. Top_k 200. Chunk che vincono SOLO via BM25 e non sono nel ranking cosine vengono idratati con un singolo fetch su `repo.pool`.
  - `rerank_chunks()` Cohere `rerank-multilingual-v3.0` con `cohere.AsyncClientV2` (lazy import). Top_n 30. Se la chiave non è settata o l'API è down → fallback automatico a "ordine RRF già fatto da recall_hybrid" con `source='rrf_fallback'`. Nessuna eccezione propagata: degrada, non rompe.
  - `retrieve_for_module()` end-to-end (query autogen + recall + rerank).
  - **VAA-b provenienza tracciata** in ogni `ScoredChunk` con `source ∈ {'rerank_cohere', 'rrf_fallback', 'bm25_only'}`. **VAA-d sensore non gate**: `MIN_RERANK_SCORE_ALERT = 0.45` alimenta il futuro badge D9 `module_corpus_thin` ma NON filtra i chunk (il vecchio MIN_RELEVANCE legacy filtrava, e il path v2 ne è esente di proposito).
- **F2.3 SMOKE TEST 4/4 PASS contro DB prod Railway (TCP proxy + corpus reale 7 normative 2879 chunk)** — script `scripts/smoke_test_retrieval_v2.py` (gitignored):
  - TEST 1 autogen → 18-29 parole in italiano, ~3.8 s/modulo.
  - TEST 2 recall_hybrid → 100 candidati con bm25_size=100 + cosine_size=100 fused (~920 ms).
  - TEST 3 rerank → 10 ScoredChunk con `source=rerank_cohere`, **top_score 0.967** (>> 0.45 soglia), ~22.8 s su 200 docs.
  - TEST 4 retrieve_for_module E2E → 30 ScoredChunk, top_score 0.945, source=rerank_cohere.
- **F2.4 research_agent BRANCH dietro flag** — `app/agents/research_agent.py:1525-1540` aggiunto `if settings.v2_features.get("rerank_enabled")` che switch a nuova `_retrieve_chunks_per_module_v2()` (~100 righe). Funzione nuova invece di branchare dentro la legacy per non toccare il path provato dai 3 demo dell'analista. mypy verde sul mio scope (l'errore residuo `:1205 "object" has no attribute "fetch"` è **preesistente** del `cluster_scores` legacy — confermato via `git stash` su HEAD precedente). Smoke test `scripts/smoke_test_research_agent_v2.py` (gitignored) → 3 moduli (Concetti generali / Rischi specifici DPI / Segnaletica) → ciascuno 30 chunks, top_score 0.976 / 0.972 / 0.992, `modules_under_alert=[]`. **Semanticamente i chunk #1 sono perfetti**: art. 15 (misure generali tutela) / allegato V (DPI) / allegato XIII (segnaletica).
- **Discrepanze D-151 (rerank 2-stadi) e D-152 (edge graph) avanzamento**: D-151 ora ha l'implementazione e il branch flagged in prod-ready; **D-152 resta aperta** (graph_service.py F2.5-F2.7 mancano).

**Cosa NON verifica ancora (debt):**
- F2.4 verificato in smoke STANDALONE su corpus reale, ma **NON ancora in pipeline end-to-end** (research_agent → content_agent → production_builder). Il content_agent consuma `relevance_score` (popolato dal rerank Cohere) ma potrebbe esserci sorpresa nell'ordinamento delle slide o nel matching SPREAD-hint, perché la struttura interna `chunks_by_module` ora riflette ordine rerank decrescente invece di ordine dedup-quota.
- Flag `v2_rerank_enabled` resta **OFF in prod**: pipeline v1 invariata per i 3 demo. Attivare il flag e fare A/B (F2.9) chiuderà davvero la verifica al render della fase 2 retrieval.

**Fase 1 — risultati misurabili in produzione (verificati via TCP proxy + Chrome DevTools live):**
- **Catalogo cliente in DB**: 44 corsi attivi + 195 moduli scrapati da corsi8108.it. 102 link `regulation_course_type_links` con `source` tracciato (96 `scrape`, 6 `remap` rimappature `accordo_2016->2025` e `dm_1998->2021`). Distribuzione: `dlgs_81_08` 28 corsi, `accordo_stato_regioni_2011` 19, `accordo_stato_regioni_2025` 13, `dlgs_106_09` 7. Gate VAA: nessun catalog entry ha `approved_at IS NOT NULL` → la generazione resterà bloccata finché l'admin non approva via UI (work item F1.D.2).
- **Ingestione 3 normative TIER 1** in produzione via `POST /api/regulations/upload`:
  - `reg_ce_852_2004` (HACCP, EUR-Lex IT consolidato 24/03/2021): 147 chunks, 245KB PDF
  - `dm_02_09_2021` (antincendio nuovo, GU n. 237 04/10/2021): 58 chunks, **chiude debt storico #R16** (DM antincendio 2021 mancante)
  - `reg_ce_1272_2008` (CLP Diisocianati, EUR-Lex IT consolidato 01/05/2026): 672 chunks dal PDF da 22MB / 1576 pagine — il client httpx ha avuto ReadTimeout ma il server ha completato (come previsto, stesso comportamento osservato con D.Lgs 81/08).
  - TOT regulations in prod ora: **7** (4 preesistenti + 3 nuove), **2879 chunks totali tutti con embedding Voyage 1024-dim**.
- **BUG `citation_label` fixato**: la migrazione 004 (FIX #30.5a) aveva aggiunto la colonna ma `ingestion_service.index_chunks()` NON la popolava a INSERT-time (solo lo script standalone `backfill_citations.py`). Risultato: tutte le 7 normative × 2879 chunk avevano `citation_label = NULL`, e content_agent/generation_service cadevano su `hierarchy_path` invece del label deterministico. Fix in 3 punti:
  - nuovo `app/services/citation_label.py` (fonte unica della formula, importabile sia da ingestion_service che dal backfill script)
  - `ingestion_service.index_chunks()` ora fetcha 1 volta il `short_title` per `regulation_id` (cached) e passa il `citation_label` calcolato all'INSERT
  - aggiunti pattern speciali per **Regolamenti CE/UE** (`Reg. CE 852/2004`), **decreti datati** (`D.M. 02/09/2021`), **Accordi anno-only** (`Accordo SR 2025`), che i pattern numerici `{N}/{YY}` non gestivano
  - **backfill in prod su 2879/2879 chunk, 0 NULL rimanenti**. Sample verificati: `D.Lgs. 81/08, art. 40, c. 7`, `Reg. CE 852/2004, art. 18, c. 10`, `D.M. 02/09/2021, art. 3, c. 4`, `Reg. CE 1272/2008, allegato IV`. → **debt D-159 chiuso** (mai dichiarato esplicitamente in passato perché bug silente, ma latente da 2026-05-26 migration 004).
- **Migrazione 006 `regulation_course_type_links`** applicata in prod (idempotente, GRANT condizionale come 005 per #R18). VAA-b: ogni link ha colonna `source enum('scrape','remap','manual','imported_v1')` + `notes` per spiegare le rimappature.
- **Endpoint backend** `GET /api/regulations/{slug_or_id}/linked-courses` deployato e verificato live (HTTP 200 + JSON con 28 corsi su dlgs_81_08, 1 corso con `link_source='remap'` su dm_02_09_2021, 1 corso HACCP su reg_ce_852_2004).
- **UI**: ChunksSheet (component Regulations) ora apre con sezione collassabile "Corsi che usano questa normativa (N)" sopra ai chunk. Badge `[in attesa]/[approvato]` per il gate VAA del catalog + piccolo badge ambra `link: remap`/`link: manual` quando la provenienza non è `scrape`. **Verificato E2E in produzione via Chrome DevTools MCP**: login → /regulations → click DM 2/9/2021 → sheet apre con count `1`, corso "Antincendio – Livello 2 (8 ore)", badge `link: remap` visibile, badge `In attesa` corretto.

**Bug rilevati e gestiti in F1.D:**
- Commit `10d6deb` (frontend + model) e `649cf23` (empty trigger) erano basati su mia diagnosi errata: l'endpoint backend `list_linked_courses()` non era stato realmente scritto nel file `regulations.py` (Edit chain con parametro invalido aveva fallito silenziosamente, e io non avevo verificato il route registration con `pyrouter.routes`). **Lezione**: usare la fonte di verità del router invece di accusare l'infrastruttura. Commit di fix reale: `71e8cfb`.

**Discrepanze pianificate del piano vast-hopping-sketch v2:**
- D-151..D-157 (vedi sessione precedente) restano aperte per le fasi F2..F8.
- **D-159 nuova** (citation_label bug latente da migrazione 004) → **chiusa nello stesso turno**.

PRECEDENTE: 2026-05-28 — **v2 refactor FASE 0 (setup) + 7 discrepanze pianificate**. Avviato il refactor v2 (piano `vast-hopping-sketch.md`, approvato dall'analista col vincolo trasversale **VAA — Anti-Allucinazione-silenziosa**: ogni componente nuovo deve avere verifica al render, provenienza tracciata `source`, fallimento visibile in UI badge, distinzione problema-algoritmico vs limite-corpus, safety-net dietro flag). **FASE 0 eseguita**: (a) migrazione `app/db/migrations/005_v2_foundation.sql` applicata in prod via TCP proxy — 7 tabelle nuove (`course_type_catalog`, `course_type_modules`, `regulation_chunk_edges`, `image_library`, `conversations`, `messages`, `slide_quality_checks`) + 3 colonne `courses` (`module_skeletons_json`, `skeleton_approved_at`, `skeleton_approved_by`), 22 indici, idempotente, **GRANT reso condizionale** perché in prod il ruolo `nexus_app` NON esiste (app gira come `nexus_admin`) → scoperta tracciata come **#R18**. (b) Feature flag system in `app/config.py` (10 flag `v2_*` tutti default False eccetto `drop_list_enabled=True` safety-net) — pipeline v1 invariata a flag spenti, i 3 demo NON cambiano. (c) deps `cohere 7.0.1` + `rank-bm25 0.2.2` installate (azure-speech rimandata a F7). (d) `app/services/pipeline_telemetry.py` (NEW) — helper `emit()`/`timed()` con `PipelinePhase` enum + campo `source` (base monitoring permanente D2 + sensori badge D9). mypy --strict + ruff PULITI sui file F0. **NESSUN test pytest nuovo in F0** (è solo schema+config+telemetria; la verifica è "al render" = migrazione applicata in prod verificata con count tabelle/colonne) → debt **D-158** (F0 verificata strutturalmente in prod, non con unit test — accettabile per setup additivo a flag spenti). **7 discrepanze pianificate REI-16** dichiarate (saranno chiuse fase per fase): **D-151** rerank 2-stadi sostituisce retrieval vettoriale puro BP §06; **D-152** edge graph chunk-chunk (BP §06 non lo prevede); **D-153** scheletro validato come fase intermedia LangGraph (BP §05 ha 2 nodi); **D-154** catalogo in DB sostituisce `catalog_config.py` (BP §13); **D-155** image library locale sostituisce cache opportunistica; **D-156** chat conversazionale in Studio (era FASE 8 post-deploy futura); **D-157** Azure Speech SDK affianca edge-tts (OPT-1 era edge-tts only). **Nuova risorsa #R18 [HARDENING PRE-GO-LIVE]**: ruolo `nexus_app` assente in prod Railway — l'app si connette come `nexus_admin` (owner, privilegi pieni) quindi può DELETE/TRUNCATE `audit_log`, violando il design append-only di REI-10. **Decisione utente 2026-05-28: lasciare aperto ora, sistemare prima del go-live cliente** (creare `nexus_app` con grant ristretti + ruotare `DATABASE_URL` Railway + redeploy + verificare che l'app regga col ruolo limitato). Per ora GRANT condizionale nella migrazione 005 lo gestisce senza bloccare. **Work-item di hardening, NON dimenticare prima della consegna finale.** **Kokoro-82M valutato e scartato** per TTS (vedi piano D6: italiano non validato, no SSML, costo infra self-host > Azure API al volume CFP). PRECEDENTE: 2026-05-28 — **Sessione E2E prod + fix mancanze + fix CRASH Course Studio nav**. (e) **Course Studio crashava (500) appena si navigava oltre la slide 1**: `slide-viewer.tsx` e `slide-editor.tsx` chiamavano `slide.body.split(...)` / `useState(slide.body)` assumendo `body: string`, ma il backend `SlideContent` strict emette `body: null` + un `bullets: string[]` separato. Una slide CONTENT_TEXT/CONTENT_IMAGE/RECAP rendeva `null.split('\n')` → TypeError. Fix: `slideBulletText()` helper che prefer body e fallback a bullets[]; tutti i `useState(slide.X)` coerced con `?? ''`; CASE_STUDY `slide.body ?? ''` guard. Bug PRE-ESISTENTE (sfasamento contratto backend/frontend), reso visibile dalla nuova navigazione orizzontale + SlideActions. **D-150**. **Tutti i fix di questa sessione vanno verificati E2E dopo il prossimo deploy frontend**. PRECEDENTE: 2026-05-28 — **Sessione E2E prod + fix mancanze**. (a) **Normative=0 in prod RISOLTO**: tabella `regulations` era vuota perché i 3 corsi demo furono inseriti pre-built senza pipeline ingestion. Caricate 4 normative via `POST /api/regulations/upload`: `dlgs_81_08` (1819 chunk), `accordo_stato_regioni_2025` (133), `dm_388_2003` (23), `accordo_stato_regioni_2011` (27) — TUTTI con embedding (Voyage 1024-dim) → **D-148** chiusa. (b) **Profile-dropdown header SN/satnaing** (fix mancato dal template shadcn upstream): riscritto `frontend/src/components/profile-dropdown.tsx` con stesso pattern `nav-user.tsx` (JWT role + /me email + iniziali AD/OP/RV + voci finte Billing/New Team rimosse) → **D-149**. (c) **classify_chunk_failed (OpenAI) → fallback Azure ATTIVATO**: env Azure (`AZURE_OPENAI_ENDPOINT/API_KEY/VERSION/DEPLOYMENT_CLASSIFY=gpt-4.1-mini`) settate su Railway prod (`--skip-deploys`); al prossimo redeploy la chain CLASSIFY scala DeepSeek (skip, no key) → **Azure** → OpenAI → Anthropic. RetryError già in `_FALLBACK_EXCEPTIONS` (ingestion_service:336) → fallback automatico. (d) Risorsa #R16-#R17 (DM Antincendio 2021 + Reg CE 852/2004) confermate ANCORA mancanti — non caricate in prod (PDF non disponibili). PRECEDENTE: 2026-05-28 — **Sessione deploy-prod + slide-management + rephrase allegati + nav orizzontale Course Studio**. (1) **Slide management backend** (`studio_service.py`: `_reindex`, `_blank_slide`, `add_slide`, `move_slide`, `delete_slide`, `duplicate_slide`; `courses.py`: 4 endpoint POST/DELETE slides con `require_role("admin","reviewer")` + reindex contiguo 0..N-1 per integrità PPTX). mypy --strict PULITO sui 2 file modificati; ruff PULITO. **Nessun nuovo test pytest** per slide-management (verifica prevista via Chrome DevTools E2E in prod: add→move→delete→rebuild→download PPTX apribile) → **debt D-146**. (2) **Slide management frontend** (`slide-actions.tsx` NEW, `api.ts` +4 metodi, integrazione `course-studio/index.tsx`) + **navigazione orizzontale stile PowerPoint** (bottoni Precedente/Successiva + frecce ← → tastiera, lista verticale come indice) → build FE verde (tsc -b + vite, 0 errori). (3) **Rephrase note audio 30-45s** su 3 corsi via `scripts/rephrase_notes_safe.py` (gate anti-allucinazione): **allegati RESI RIMOVIBILI** su richiesta utente ("gli allegati non sono documentazione, non vanno citati") — `allegato [IVX]+` tolto dal set entità protette + regola esplicita nel SYSTEM prompt; articoli/D.Lgs/commi/numeri+unità/% RESTANO protetti. Risultati: specifica 5 applied/1 kept, generale 102/5, preposti 206/3; **verifica programmatica: 0 allegati residui nelle note applicate, 0 entità protette perse, 9 note tenute-originali (safety) per perdita art./D.Lgs/durate legali o aggiunta entità** → **discrepanza D-147** (rephrase LLM su contenuto normativo verificato solo via gate regex, non review umana nota-per-nota). (4) **.gitignore irrobustito**: `scripts/*_proxy.py` + altri script con password DB/proxy + `storage/dumps/` esclusi permanentemente. (5) **Debt pytest baseline INVARIATO** (test obsoleti pacing_engine + slide_constraints + helper SlideContent ≥4 bullet — già documentato, NON regressioni: confermato via stash su HEAD pulito). **Audio 3 corsi in rigenerazione** post-rephrase (voce Elsa femminile). PRECEDENTE: 2026-05-27 — **Sessione #32 refinement Demo #2 v3 + velocità + frontend audio + chat fattibilità**. Lavoro post-analista review 12: (1) **A.1** query M1 "Prevenzione e protezione" ampliata 4→25 righe rimuovendo "sorveglianza sanitaria" (cosine-attracting medico/biologico in Demo #2 v2). (2) **A.2** drop-list `_DROP_PATTERN_M1_PREVENZIONE_GENERALE` (medico/sorveglianza/agenti biologici/cancerogeni/cartella sanitaria) applicato SOLO al modulo "Prevenzione e protezione" del corso GENERALE. (3) **A.3** `_INSTRUCTOR_DEPTH_RETRIES = 5 → 2` per tagliare ~3min su batch falliti (sub_batch_recovery copre). (4) **A.5** 4 nuovi test isolati `test_m1_prevenzione_drop_list.py` (verdi 4/4). (5) **C.1** Frontend `AUDIO_POLL_TIMEOUT_MS = 5min → 12min` (chiude #R-audio-fe-timeout-4h-only). (6) **C.4** AudioPlayer graceful onError ("Audio in elaborazione…"). (7) **C-bis** ImagePicker empty state esplicito. (8) **C-ter** doc fattibilità chat conversational `docs/handoffs/CHAT_CONVERSATIONAL_FEASIBILITY.md` (7-10h work, FASE 8 post-deploy). **Demo #2 v3 risultati**: 9m 36s (-21% vs v2 12m 14s), 331 slide, **M1 off-topic 46%→~3% (-43%)**, drop-list `chunks_dropped={1:9}` confermato live, ZERO regressioni 60/60 test #31.x + #32 verdi. **Nuova discrepanza D-142, D-143** (meta-architetturali: patch-driven retrieval + mancanza ottimizzazione velocità) + **D-144** (refinement M1 chirurgico). **Nuova risorsa #R-chat-conversational** (FASE 8 post-deploy). **#R-audio-fe-timeout-4h-only chiusa**. PRECEDENTE: 2026-05-27 — **Sessione scaling pipeline #31.1→#31.8** (analista review 1→11, ~14h work su 2 giorni). Fix in sequenza: **#31.1** Per-module retrieval N indipendenti + dedup cosine. **#31.2** top_k 45→70. **#31.3** SPREAD intra-modulo prompt. **#31.4** MODULE_CLOSE bullet 10→12 + try/except separati. **#31.5** A: DIAGRAM body_max_bullets 2→3; B: source_chunk_ids coercion + sub_batch_recovery. **#31.6** A: prompt POSITIVO ruolo label DIAGRAM; B: _strip_normative_suffix regex; C: query Segnaletica ricalibrata; D: drop-list. **#31.7A v2** auto-shrink font UNIFORME per diagramma + floor 16pt + zero truncate sopra floor (review 9 analista patologia M1/idx15 verificata). **#31.8** A: top_k=min(150,int(35+8*duration_hours)); B: MIN_RELEVANCE adattivo P25 se sotto soglia 30; C: dedup quota-aware QUOTA_MIN=30 pinned pre-dedup. **+8 nuovi test #31.8** (`test_scaling_8h_retrieval.py`) + **+16 #31.7A** (`test_diagram_font_shrink.py`) + **+6 #31.5B** (`test_source_chunk_ids_coercion.py`) + **+5 sub_batch_recovery** + **+15 #31.6B** (`test_label_suffix_strip.py`) + **+4 #31.6D** (`test_segnaletica_drop_list.py`) + **+6 #31.1** (`test_research_agent_per_module.py`) = **60 nuovi test #31.x**, tutti verdi, zero regressioni. **3 Demo cliente prodotti**: Demo #1 Specifica 4h (E25 v2 #31.7A, OK review 10 analista, 336 slide 22 diagram catalog 100%), Demo #2 Generale 4h (v1 borderline ROSSO 23% off-topic, v2 #31.8 in rigenerazione), Demo #3 Preposti 8h (v1 patologia grab-bag confermata empirica: M3 5 chunk + lost 47/40/41 su M1/M4/M5, v2 #31.8 in rigenerazione). **Nuove discrepanze D-137-D-141**, **#R16-#R17** (Antincendio DM 02/09/2021 + HACCP Reg CE 852/2004 corpus mancanti, work-item post-demo). **Debt pytest baseline VERIFICATO**: 116 fail / 303 pass / 1 skipped — failure sono test OBSOLETI pacing_engine + slide_constraints da iterazioni #30.x (pacing 384→276 slide, constraints CONTENT_TEXT 0 bullets vs 4 min), NON regressioni #31.x. Da risincronizzare come work-item separato post-demo. PRECEDENTE: 2026-05-26 — **Sessione demo post-FASE-6**: diagnosi crash corsi lavoratori (slug `accordo_stato_regioni_2011` non ingerito) → scaricati+ingeriti 3 Accordi Stato-Regioni (2011 27ch, 2016 1ch degradato, 2025 133ch) via nuovo `scripts/ingest_accordi.py`; catalog corsi lavoratori/preposti aggiornato a Accordo 2025 (vigente, vecchio scaduto 23/05/2026). **FIX #24** (RECAP 5-bullet) VALIDATO su corso #14 (slide RECAP con `nx_recap_text_710-750` tutte popolate + ✓). **FIX #25** (zero-placeholder: backfill throttled + fallback brandizzato C.F.P. + caption pulita) implementato in `image_service.py` + `slide_builder_v2.py`, fallback validato visivamente nel container. Nuove discrepanze **D128-D136**, risorse **#R14** (2016 text-based) + **#R15** (quote image provider); **#R9 parzialmente chiuso**. **Nessun nuovo test pytest** (lavoro su pipeline+asset, validazione via corsi reali). PRECEDENTE: 2026-05-24 — **FASE 6 COMPLETATA (6.1→6.10) ✅** + audit checklist 20-item eseguito. 60 nuove discrepanze REI-16 (D68-D127) raccolte da prompt 6.5-6.10. **Nessun nuovo test pytest mock** (FASE 6 è puro frontend — verifica via Chrome DevTools MCP live + 1 vitest aggiornato `user-auth-form.test.tsx`). Audit 20/20: 18 ✅, 2 ⚠️ parziali (item 15 Gestione utenti = stub onesto perché `/api/users` non esiste backend; item 20 Download blocked-upstream da #R3 Anthropic + #R11 LangGraph checkpoint setup — frontend lato pronto e verificato fino a Progress page). **Smoke E2E LIVE eseguito**: logout→login→dashboard→wizard→POST `/api/courses` 200 (`estimated_slides=480` coincide con backend PacingEngine)→progress page render con phase machine corretta (Ricerca normativa ✅ + Generazione contenuti ✅ + Composizione PPTX upcoming) + barra destructive per errore LangGraph (pipeline reale fallisce su `relation "checkpoints" does not exist` — #R11 separato). Frontend production-build verde 3.37s, 0 errori, 0 warning. 17/17 endpoint BP §10 cablati. **Nuove risorse esterne registrate**: #R7 parzialmente mitigato (auto-gen Pillow), nessuna #R nuova.
> **Conteggio attuale:** 249 test pre-#31 + **60 nuovi test #31.x** (8 #31.8 + 16 #31.7A + 6 #31.5B + 5 sub_batch + 15 #31.6B + 4 #31.6D + 6 #31.1) = **309 test pytest gestiti** (di cui 116 obsoleti pre-esistenti da risincronizzare post-demo) + 1 test live skipped + 5 script E2E in Docker (e2e_19, demo2_generale_4h, demo3_preposti_8h, rebuild_e25, verify_31_7a) + 3 corsi demo cliente generati (E25 #1 + Generale #2 v2 + Preposti #3 v2) + 1 smoke E2E FASE 5 parziale + audit checklist 12/12 + 1 vitest FE + audit FASE 6 20-item, **141 discrepanze REI-16** (D1-D141 con buchi storici), 15 risorse mancanti (1 chiusa #R10; #R7 mitigato auto-gen; #R16-#R17 nuovi).

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

### Audit checklist FASE 5 (post-implementazione, 2026-05-24)

12 item Master Plan verificati punto-per-punto:

- **11 ✅ verdi**:
  - **1** `_job_semaphore` in generation_service:43 (meta-test guard FIX-7)
  - **2** `get_shutdown_event()` dependencies.py:70 unico evento (D-18)
  - **3** `asyncio.wait_for(timeout=PIPELINE_TIMEOUT_SECONDS=settings.pipeline_timeout=1800)` (3 layer verified)
  - **4** fingerprint+chunk_ids salvati a riga 192-201 PRIMA di build() a riga 213 (test ordering cardine)
  - **5** `recover_interrupted_jobs` chiamato da main.startup:85 + UPDATE su 3 status mid-flight
  - **6** `queue_position` calcolato in courses:121 via COUNT su 4 status attivi
  - **7** WS JWT decode + access-only check + JOIN ownership lookup + 3 close codes (14 test)
  - **9** ZIP audio path in courses:323-335, **verificato LIVE** smoke 5.5: 1.4MB / 31 file (30 MP3 + manifest)
  - **10** `@limiter.limit("5/minute")` on POST /api/courses:103 (BP §10.4)
  - **11** audit_log append-only **verificato LIVE in Docker post-audit**: 3/3 forbidden ops bloccate (DELETE/UPDATE/TRUNCATE → "permission denied" come nexus_app), INSERT+SELECT consentiti
  - **12** pytest 315 passed + mypy 43 files no issues + ruff All checks passed
- **1 ❌ → ✅ FIX applicato**:
  - **8** Polling fallback 30s NON era documentato in nessun file. Creato `docs/POLLING_FALLBACK.md` (~50 righe): contratto WS primario + REST GET /api/courses/{id} ogni 30s, pseudo-code frontend per FASE 6.9, rate limit considerations, stati terminali inclusi `archived` lato polling.

**Per chiusura definitiva FASE 5** servono ancora #R1 + #R3 + #R4 (PDF reale + Anthropic key valida + Voyage key valida) per testare LIVE l'ingest + run_pipeline E2E.

### Audit checklist FASE 4 (post-implementazione, 2026-05-24)

Verificato punto-per-punto contro 18 item del Master Plan riga 1474-1490:

- **14 ✅ verdi senza riserve**: 3 (SlideBuilder path locali), 4 (image_service Semaphore(5)+10s+Pillow+sanitize INLINE), 5 (cairosvg test), 6 (Jinja2+WeasyPrint), 8 (memory+disk+to_thread), 9 (cleanup), 10 (edge-tts no OpenAI), 11 (no OPENAI_API_KEY in `.env`), 12 (mutagen), 13 (sync_manifest + UPDATE courses), 14 (audio_tracks default voice), 16 (Semaphore(3)), 17 (synth_build_test verde in Docker), 18 (pytest/mypy/ruff verdi)
- **2 🟡 N/A**: 1 (template `nexus_master.pptx` umano #R8), 2 (`master_inspection.json` generato dal primo run reale dopo #R8)
- **1 🟡 con divergenza tracciata**: 15 (slide senza speaker_notes → io fallback al body, NON skip stretto — D40 già accettata, "no crash" garantito dal fallback per-slide)
- **1 ❌ → ✅ FIX applicato**: 7 (TOC + header/footer brand) — vedi D46. Template `dispensa.html` aggiornato, 7 nuovi test, synth E2E in Docker ri-verde con PDF 25KB.

### Synthetic E2E build (FASE 4.7)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| — | `scripts/synth_build_test.py` (eseguibile, non pytest) | `scripts/synth_build_test.py` | Smoke E2E manuale: 30 slide mock + 3 moduli + outputs=["pptx","pdf","audio"], esercita SlideBuilder REAL + PdfBuilder REAL (WeasyPrint REAL — richiede GTK) + AudioService REAL (edge-tts REAL — richiede internet). Stub `_FakePool` per `pool.execute` (no DB live #R2). Guard upfront `_check_weasyprint_available()` esce con exit 2 e istruzioni Docker se GTK assente. **Eseguito con successo dentro `eduvault-backend` container (2026-05-24 00:29)**: 30 PPTX slide + PDF generato + 30 MP3 italiani via Microsoft Edge TTS reale + manifest JSON valido in ~10 secondi. **NON verifica**: template umano #R8 (usa sintetico in-process), contenuto LLM reale (slide hardcoded), schema audio_tracks contro DB live (#R2 — fake pool), Brave Search images (#R6 — image_map={}). Su Windows host esce con exit 2 (#R12 GTK runtime, by design). |

### AudioService (FASE 4.6 — OPT-1 edge-tts, GAP-3 Master Plan)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 194 | `test_generate_narrations_produces_files_inserts_and_manifest` | `tests/unit/test_audio_service.py` | **Test cardine FASE 4.6.** 5 slide → 5 MP3 (fake bytes via `_tts_save` patched), 5 INSERT su `audio_tracks` (verifica `course_id`/`voice`/`duration_seconds`), 1 UPDATE `courses.audio_manifest_path`, manifest JSON con 5 track. **NON verifica**: chiamata HTTP reale a Microsoft Edge TTS endpoint (#R13), qualità MP3 reale (mutagen.MP3 stub → `info.length=12.5`), latenza TTS reale, comportamento Semaphore(3) sotto carico (>3 chiamate parallele). |
| 195 | `test_generate_narrations_skips_slides_without_text` | id. | Slide con speaker_notes+body entrambi whitespace → skip. Verifica filtro. OK. |
| 196 | `test_narration_falls_back_to_body_when_speaker_notes_empty` | id. | Cattura il `narration` passato a `_tts_save`, asserisce che sia il body literal della slide. Documenta D40 (NIENTE rephrase LLM). OK. |
| 197 | `test_voice_is_propagated_to_communicate` | id. | Mocka `edge_tts.Communicate`, asserisce che `__init__(voice='it-IT-IsabellaNeural')` raggiunga il costruttore di Communicate. OK. |
| 198 | `test_manifest_path_is_persisted_in_courses_table` | id. | Verifica che la SQL `UPDATE courses` venga eseguita con il manifest_path corretto. OK strutturale. |
| 199 | `test_audio_service_does_not_import_openai` | id. | **Meta-test OPT-1** via AST docstring-strip: `openai` NON deve apparire nel codice (solo nei docstring di documentazione). `edge_tts` deve essere importato. Fa fallire CI se qualcuno aggiunge un import OpenAI. |
| 200 | `test_one_failing_slide_does_not_block_the_other_four` | `tests/unit/test_audio_fallback.py` | **Test cardine fallback (BP §07.1 invariante).** 5 slide, _tts_save raise RuntimeError per slide #2 → tenacity retry × `_TTS_RETRY_ATTEMPTS` (patchato a 2 per velocità) → fallback. Verifica: 4 MP3 su disco (non slide_0002.mp3), manifest con 4 entry (indices 0,1,3,4), 4 INSERT (nessuno con slide_index=2), 1 UPDATE. wait_exponential patchato per evitare delay reali. |
| 201 | `test_partial_mp3_file_is_removed_after_failure` | id. | `_tts_save` scrive bytes parziali poi raise ConnectionError → fallback cleanup rimuove il file parziale prima di ritornare None. Previene poisoning di MP3 successivi. OK. |
| 202 | `test_tts_timeout_is_caught_per_slide` | id. | `_TTS_TIMEOUT_SECONDS=0.1`, prima slide dorme 0.5s → asyncio.TimeoutError → skip. Seconda slide successo. Verifica isolamento per-slide della timeout. OK. |

### ProductionBuilder + PptxValidator (FASE 4.5)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 179 | `test_check_memory_passes_when_ample_ram` | `tests/integration/test_production_builder.py` | Mocka `psutil.virtual_memory` con 8GB available. Verifica pass per 100 slide. OK strutturale. |
| 180 | `test_check_memory_raises_when_estimated_exceeds_safety_ratio` | id. | Mock 100MB available, 700 slide × 1.5MB = 1050MB → > 60MB threshold → MemoryError. OK. **Non verifica** carico RAM reale di python-pptx su 700 slide (stima `slide_count * 1.5MB` è BP §07.1 line 2207, non misurata). |
| 181 | `test_check_disk_passes_when_enough_space` | id. | Mock `shutil.disk_usage`. OK. |
| 182 | `test_check_disk_raises_when_below_threshold` | id. | Mock 500MB → IOError (sotto 1GB minimo BP). OK. |
| 183 | `test_validator_returns_valid_when_count_matches` | id. | PPTX REALE generato via SlideBuilder + template sintetico (3 slide). Validator carica con `Presentation(path)` e conta `len(prs.slides)`. **Senza debt** per il count check. **Non verifica** layout-by-layout correctness su template reale (#R8). |
| 184 | `test_validator_flags_count_mismatch` | id. | Stesso PPTX di 3 slide, asserito contro 4 → warning `slide_count_mismatch`. OK. |
| 185 | `test_validator_handles_missing_pptx` | id. | Path inesistente → `valid=False` + `pptx_missing:` warning. OK. |
| 186 | `test_production_build_end_to_end_20_slides` | id. | **Test cardine BP §07.1.** 20 slide mock su 3 moduli e 5 SlideType (TITLE/CONTENT_TEXT/CONTENT_IMAGE/QUIZ/CASE_STUDY/RECAP), `ws_callback=AsyncMock()`, WeasyPrint mockato via `sys.modules['weasyprint']=MagicMock()` (#R12). Verifica: PPTX file scritto (20 slide effettive in `Presentation(pptx_path)`), PDF path computato, `write_pdf` chiamato una volta, progress steps 87/92/95 (BP line 2250/2255/2260), report con `total_slides=20`, `modules_completed=3`, `quiz_count>=1`, `warnings=[]`. **NON verifica**: PDF binario reale (#R12), corso normativo reale con LLM/RAG (richiede #R1+#R2+#R3+#R4), template umano (#R8), tempo build reale su corso da 700+ slide. |
| 187 | `test_production_build_propagates_validation_warnings` | id. | Mocka `validator.validate` per ritornare warning custom; verifica che il report contenga `["fake_warning:abc"]`. OK strutturale — assicura che `_build_report` non scarta i warning. |
| 188 | `test_production_build_raises_on_memory_check_fail` | id. | Mocka `check_memory_before_build` per lanciare MemoryError. Verifica: `ws_callback` MAI chiamato, `weasyprint.HTML` MAI istanziato, eccezione propagata. **Test cardine "fail-fast prima del lavoro"** karpathy. |
| 189 | `test_cleanup_removes_files_older_than_threshold` | id. | Crea 2 file in `output/diagrams/` e `output/images/`, backdate uno di 2 ore. Esegue `_cleanup_tmp`, verifica che il vecchio sia stato rimosso e il fresco preservato. OK deterministico. |
| 190 | `test_cleanup_swallows_oserror_silently` | id. | Mocka `os.remove` per lanciare OSError → no exception bubbles up. BP §07.1 line 2283 esplicito sul silent-swallow (file racing con build parallelo). OK. |
| 191-193 | 3 meta-test (CLEANUP_PATTERNS, CLEANUP_AGE, no-Semaphore REI-3) | id. | **Senza debt** — guardie strutturali. Test 193 in particolare fa fallire CI se qualcuno aggiunge un Semaphore alla classe (REI-3: il Semaphore(1) vive in `generation_service`, NON qui). |

### PdfBuilder (FASE 4.4)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 156-159 | 4 test `_group_slides_by_module` + `_slide_to_dict` | `tests/integration/test_pdf_builder.py` | **Pura logica deterministica.** Verifica raggruppamento per `module_index`, ordine preservato, vuoto → vuoto, enum `.value` esposto come stringa per Jinja. **Senza debt.** |
| 160 | `test_constructor_raises_if_templates_dir_missing` | id. | OK strutturale. |
| 161 | `test_constructor_raises_on_missing_template_name` | id. | OK strutturale — Jinja2 `TemplateNotFound`. |
| 162-173 | 12 test `render_html` (titolo+metadata, sezioni per modulo, normative_ref present/empty, speaker_notes present/empty, quiz con opzioni+marker, no-quiz su slide non QUIZ, palette injection + fallback, page counter CSS, regulations cover, HTML escaping autoescape) | id. | **Render Jinja2 reale e deterministico.** Verifica che il template `dispensa.html` produca HTML con: tutti i contratti BP §07.2 (h1/h2, .normative-ref, .quiz, .speaker-notes, @page counter), branding palette iniettata, escaping `<script>` → `&lt;script&gt;`. **NON verifica** rendering visuale finale (font, spacing, page-break reali) — quello richiede WeasyPrint runtime + browser-class CSS engine. **Risorsa: #R12** (GTK runtime locale o test su Docker). |
| 174-177 | 4 test `build` con WeasyPrint mockato (write_pdf path, slash-stripping, fallback course id, multi-modulo end-to-end) | id. | **WeasyPrint completamente mockato** via `sys.modules['weasyprint'] = MagicMock()` (stub iniettato a livello di test file PRIMA dell'import di pdf_builder). Verifica orchestrazione `render → HTML(string=...).write_pdf(path)`, NON verifica produzione PDF binario reale. **Risorsa: #R12.** Su CI Linux/Docker il PDF è generato realmente. |
| 178 | `test_pdf_builder_uses_jinja2_not_str_format` | id. | **Meta-test OPT-3 via AST.** Parsa il sorgente di `pdf_builder.py` con `ast.parse`, strippa via `NodeTransformer` docstring di module/function/class, poi cerca la stringa `PDF_TEMPLATE.format(` nel codice "depurato". Fa fallire CI se un futuro refactor introduce f-string/str.format su HTML. **Senza debt** — è guardia strutturale. |

### ImageService (FASE 4.3)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 134-140 | 7 test `sanitize_svg` (script, multiline script, foreignObject, remote xlink, local xlink keep, event handler, idempotency) | `tests/integration/test_image_service.py` | **Pure regex deterministiche, zero I/O, zero mock.** Test sui pattern di stripping per le 4 superfici di attacco BP §07.0 (script/foreignObject/xlink remote/event handler). **Senza debt.** Limitazione nota: regex-based (non parser XML), quindi nominee shadowing tipo `<SCRIPT>` o entity encoding `&lt;script&gt;` non sono coperti — cairosvg tratterebbe questi come testo e non come eseguibile, ma se un giorno sostituiamo cairosvg con un renderer XML-aware bisogna ri-valutare. |
| 141 | `test_download_uses_cache_when_present` | id. | Mock `pool.fetchrow` ritorna `{"local_path": "..."}`. Verifica: cache hit → no `client.get`, sì `UPDATE usage_count`. **Non verifica** che `SELECT local_path FROM image_cache WHERE query=$1` su Postgres reale rispetti l'index `idx_images_query`. **Risorsa: #R2.** |
| 142 | `test_download_fetches_validates_and_inserts_on_cache_miss` | id. | Mock client httpx + PNG generato Pillow (8×8 red). Verifica: download → Pillow.load() → file scritto in `IMAGES_DIR` patched a `tmp_path` → `INSERT INTO image_cache`. **Non verifica** cache hit-rate reali, dimensione media file Bing/Brave, latenza download. **Risorse: #R2 + #R6** (Brave Search API key). |
| 143 | `test_download_rejects_oversized_payload` | id. | Genera 5MB+1 byte di `\x00`, verifica `(idx, None)` e `execute.assert_not_called()`. OK strutturale. |
| 144 | `test_download_rejects_corrupt_image` | id. | Bytes garbage → Pillow `load()` solleva → fallback `None`. OK. Nota: il test reale dipende dal fatto che Pillow OFFRA `load()` strict mode — verificato OK su PIL 10.x. |
| 145 | `test_download_handles_http_error_gracefully` | id. | Mock response.status=500 → `raise_for_status` solleva → catch → `(idx, None)`. OK. |
| 146-149 | 4 test `_render_diagram_sync` (no code / valid SVG / sanitize before render / cairosvg error) | id. | Test 147 scrive PNG reale via cairosvg (`output_width=1200`). Test 148 patcha `cairosvg.svg2png` per intercettare il bytestring → verifica che `<script>` NON sia presente quando arriva al renderer. **Senza debt** sui rami logici; debt reale è solo "su LLM reale gli SVG sono davvero malevoli?" — domanda aperta, da rivedere quando #R3 attiva e si raccolgono SVG reali dal Content Agent. |
| 150 | `test_prefetch_returns_empty_when_no_visual_strategies` | id. | OK strutturale. |
| 151 | `test_prefetch_skips_web_slides_without_query_url` | id. | Verifica `httpx.AsyncClient` MAI istanziato se nessuna slide ha query_url. OK. |
| 152 | `test_prefetch_returns_only_local_paths_invariant` | id. | **Test cardine dell'invariante BP §07.0 line 2148.** Per ogni valore in `image_map`, asserisce `not startswith(("http://","https://"))`. Mock pool con cache hit ritorna sempre local_path. **Non verifica** lo scenario "download successo → path corretto" perché il cache hit short-circuita. |
| 153 | `test_prefetch_resolves_diagram_slides` | id. | 2 slide diagram: una con SVG valido → PNG scritto, una con `diagram_code=None` → skip. Verifica gating. |
| 154 | `test_prefetch_mixes_web_and_diagram` | id. | Scenario realistico: 3 slide (web cache hit + diagram + none). Mock orchestrazione. **Non verifica** la reale concorrenza con Semaphore(5) sotto carico (>5 download paralleli), né `asyncio.gather(return_exceptions=True)` con eccezione genuina (solo path str → tuple). **Risorsa: #R6 + #R3** per test reale. |
| 155 | `test_sanitize_svg_is_inline_in_image_service` | id. | **Meta-test FIX-2** (BP §07.0 line 2304 ribadisce INLINE, non file separato). Verifica `sanitize_svg.__module__ == "app.services.image_service"`. Fa fallire CI se qualcuno crea un `app/utils/svg_sanitizer.py`. **Senza debt.** |

### SlideBuilder (FASE 4.2)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| 112 | `test_default_layout_map_covers_all_slide_types` | `tests/integration/test_slide_builder.py` | Verifica strutturale (8/8 SlideType in map). **Senza debt.** |
| 113 | `test_constructor_raises_if_template_missing` | id. | OK strutturalmente — guard contro template assente. |
| 114-117 | 4 test `_is_local_path` (file ok, None/empty, URL, path inesistente) | id. | Pura logica boolean. **Senza debt.** |
| 118 | `test_build_writes_pptx_to_output_dir` | id. | Template SINTETICO (default python-pptx 11 layout, generato in-process tramite fixture `synthetic_template`). **Non verifica** rendering sul template reale brandizzato C.F.P. Montessori (#R8). Il file .pptx generato è openable da `Presentation()` ma le coordinate dei placeholder seguono il default PowerPoint, NON i layout BP §07.3 (TITLE/CONTENT_TEXT/CONTENT_IMAGE/QUIZ/CASE_STUDY/RECAP/CLOSING). |
| 119 | `test_build_handles_all_slide_types` | id. | Stesso debt: 8 SlideType iterati con `TEST_LAYOUT_MAP` ad hoc che remappa su layout PowerPoint default (es. CONTENT_IMAGE → layout 8 "Picture with Caption"). Sul template reale (#R8) i layout sono diversi e gli idx provengono da `master_inspection.json` (4.1). |
| 120 | `test_build_populates_title_and_body` | id. | Idem #R8 + verifica solo che il testo appaia in qualche placeholder text_frame — non verifica font/colore/spaziatura. |
| 121 | `test_build_writes_speaker_notes` | id. | OK — `notes_slide.notes_text_frame.text` è API stabile python-pptx. |
| 122 | `test_build_inserts_local_image_successfully` | id. | Immagine PNG 64×64 generata via Pillow in tmp_path. Verifica che `insert_picture` produca un placeholder PICTURE con `image` non-None. **Non verifica** dimensioni finali, aspect-ratio, compressione, layout reale (#R8). |
| 123-125 | 3 test fallback (path missing / URL / corrupt) | id. | OK — testano i tre rami di `_insert_image_with_fallback`. La fixture `corrupt_image` scrive bytes garbage in un file `.png`: `insert_picture` di python-pptx in realtà ACCETTA il file (non valida il contenuto) → il fallback testuale scatta perché il template di test mantiene il body placeholder accessibile. **Su PowerPoint reale** il file corrotto verrebbe mostrato come immagine rotta a runtime, non a build-time. |
| 126 | `test_build_ignores_image_map_for_non_image_slide_types` | id. | OK strutturale — image_map letto solo per CONTENT_IMAGE/DIAGRAM. |
| 127 | `test_build_quiz_renders_options_and_marks_correct` | id. | Verifica che il body placeholder contenga "A./B./C./D." e "C. … ✓" per quiz_correct=2. **Non verifica** che il layout QUIZ reale BP §07.3 (LAYOUT 4: 4 placeholder distinti per opzione) venga usato — sul template sintetico non esistono 4 placeholder e il fallback "tutto in un body" è OK ma diverge dal layout brandizzato. **Risorsa: #R8.** |
| 128 | `test_build_quiz_without_options_does_not_crash` | id. | OK — guard contro `quiz_options=None`. |
| 129 | `test_build_falls_back_to_layout_1_when_index_out_of_range` | id. | OK — guard contro `layout_map` mal configurato. |
| 130-131 | 2 test path safety (slash/empty id) | id. | OK strutturale. |
| 132 | `test_build_continues_after_image_failure` | id. | **Test cardine dell'invariante BP §07.1** ("una immagine rotta NON crasha il build"). 3 slide: una con img OK, una con corrupt, una text-only. Output: 3 slide nel PPTX, terza con title applicato. OK su template sintetico, da ri-verificare su #R8. |
| 133 | `test_image_map_only_accepts_local_paths_invariant` | id. | Test meta-strutturale BP §07 line 2148 (image_map = local paths only). |

### Inspect PPTX template (FASE 4.1)

| # | Test | File | Cosa NON verifica davvero |
|---|---|---|---|
| — | nessun test pytest (script CLI) | `scripts/inspect_pptx_template.py` | Lo script è stato esercitato manualmente con un .pptx default generato al volo (9 layout PowerPoint standard rilevati, 58 shape, JSON dump valido). **NON ancora esercitato sul template reale `assets/templates/nexus_master.pptx`** — quel file è LAVORO UMANO 4-6h pre-FASE-4 ed è ancora **assente** (risorsa **#R8**). Quando il template umano arriverà, ri-eseguire lo script per validare che i 8 layout custom BP §07.3 (TITLE, CONTENT_TEXT, CONTENT_IMAGE, DIAGRAM, QUIZ, CASE_STUDY, RECAP, CLOSING) vengano rilevati con le coordinate attese. |

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
| D28 | 4.1 | BP §07.3 cita `inspect_pptx_template.py` come "script per verificare le coordinate" ma fornisce SOLO il codice di `create_pptx_template.py`. Ho dedotto la struttura dell'inspector dal contesto: per ogni `slide_layout` enumera shape/placeholder con `idx`, `name`, `shape_type`, `placeholder_type`, posizione/dimensione in EMU e inches; output report tabellare stdout + JSON in `assets/templates/master_inspection.json` come da prompt 4.1 Master Plan. | Prompt 4.1 esplicito su path e formato output; nessuna alternativa nella BP. Aggiunto `pptx`/`pptx.*` a `tool.mypy.overrides` (python-pptx senza py.typed, stesso pattern Gotcha #3 — asyncpg/voyageai). Smoke test su .pptx default generato run-time OK. | accettato |
| D29 | 4.2 | BP §07.1 NON fornisce la classe `SlideBuilder` completa — solo: (a) firma `SlideBuilder(brand_config)` e `build(slides, course, image_map)` chiamato sync via `asyncio.to_thread` (line 2238-2253), (b) pattern image insertion 8 righe commentate (line 2304-2312) con try/except e fallback `[Immagine non disponibile]`. Ho dedotto l'intera classe: layout map `SlideType → layout_index` (default BP §07.3 ordine 0-7, override per-instance per test), `_find_placeholder_by_type` per cercare TITLE/BODY/PICTURE/SUBTITLE/OBJECT, helper `_populate_title_and_body` + `_populate_quiz` + `_insert_image_with_fallback`, `BuildReport` dataclass per diagnostics, output path `{output_dir}/{course_id}_corso.pptx` (coerente con BP §07.2 `PdfBuilder` linea 2360). | Prompt 4.2 esplicito sui contratti chiave (image_map dict[int,str] locali, try/except, fallback testuale); architettura riempita dove BP tace, mantenendo karpathy regola #2 (minimum code per coprire gli 8 SlideType + 4 percorsi di fallback). Path BP "builders/" → "app/builders/" perché package layout REI-9/14.1 (segnalato). | accettato |
| D30 | 4.2 | Prompt scrive `builders/slide_builder.py`, io scrivo `app/builders/slide_builder.py` | Tutto il backend vive sotto `app/` (FASE 0.4 + 0.5 + 1.x + 3.x). BP §14.1 linea 3162 indica `app/builders/slide_builder.py` esplicitamente. Coerenza pacchetto. | accettato |
| D31 | 4.3 | BP §07.0 linea 2183 ha bug: `web_requested=len(web_tasks) if 'web_tasks' in dir() else 0` — `dir()` no-arg ritorna i nomi locali del modulo, NON dello scope corrente (Python convention quirky). `web_tasks` esiste solo nel branch `if web_slides:` quindi il log fallisce o emette 0 erroneamente. | Riscritto con `web_requested = len(web_slides)` calcolato PRIMA del branch — semantica identica al BP, niente più `if 'x' in dir()`. Idem path `services/image_service.py` → `app/services/image_service.py` (stesso motivo D30, BP §14.1 linea 3167 letterale). | accettato |
| D32 | 4.3 | BP §07.0 linea 2155 `image_map = {}` non tipizzato; io `image_map: dict[int, str] = {}` | mypy --strict richiede annotation esplicita su dict letterali vuoti. Runtime invariato. | accettato |
| D33 | 4.3 | BP §07.0 non gestisce `slide.image.query_url: str | None`: `client.get(slide.image.query_url)` accetterebbe None a runtime → TypeError. | Aggiunto `assert slide.image.query_url is not None  # guarded by prefetch_images` — il filtro `query_url` in `prefetch_images` garantisce che _download_one_image riceva solo slide con URL presente. L'assert documenta l'invariante e soddisfa mypy --strict. | accettato |
| D34 | 4.4 | BP §07.2 importa `weasyprint` al top-level (line 2318). Su Windows l'import top-level fallisce con `OSError: cannot load library 'libgobject-2.0-0'` perché WeasyPrint richiede GTK runtime (libgobject/cairo/pango) presente in Docker (Dockerfile FASE 0 li installa) ma non sul dev host Windows. | Spostato `import weasyprint` dentro `build()` (lazy import): il modulo `pdf_builder.py` si importa senza GTK; solo la chiamata reale a `build()` lo richiede (mockata nei test via `sys.modules['weasyprint'] = MagicMock()`). Aggiunta nuova risorsa **#R12** in §3 per validazione PDF binario reale. | accettato |
| D35 | 4.4 | Prompt richiede meta-test "PdfBuilder usa Jinja2 non str.format". Prima versione del test usava grep su `inspect.getsource()` ma falliva perché il docstring del modulo contiene la stringa `PDF_TEMPLATE.format(...)` come spiegazione narrativa. | Riscritto con `ast.parse` + `NodeTransformer` che strippa docstring di module/function/class prima del check. Stesso pattern già usato per il meta-test FIX-3 in `test_content_agent.py::test_no_circuit_breaker_class_anywhere`. | accettato |
| D36 | 4.4 | Path prompt: `builders/pdf_builder.py`, io: `app/builders/pdf_builder.py` | Idem D30 (BP §14.1 linea 3163 letterale). | accettato |
| D37 | 4.5 | BP §07.1 cita `PptxValidator` (line 2242, 2257) ma non fornisce l'implementazione. Solo contratto noto: `validate(pptx_path, slides)` → dict con `warnings: list` (BP line 2296 `validation.get("warnings", [])`). | Minimum karpathy: 25 LOC che caricano `Presentation(path)`, contano `len(prs.slides)` vs `len(slides)`, emettono warning `slide_count_mismatch` o `pptx_missing` se file assente. NIENTE check su layout/font/posizionamento — quelli arriveranno se VERIFICATION_DEBT li reclama dopo test su #R8. | accettato |
| D38 | 4.5 | Path prompt: `builders/production_builder.py` + `builders/pptx_validator.py`; io: `app/builders/...` | Idem D30 (BP §14.1 linea 3164 + tutto il backend sotto `app/`). | accettato |
| D39 | 4.5 | BP §07.1 importa `from models.pipeline import GenerationReport` lazy dentro `_build_report`; io importo top-level | mypy --strict richiede import top-level per type inference. Runtime invariato — `GenerationReport` è già caricato dalla pipeline. | accettato |
| D40 | 4.6 | Prompt: "se speaker_notes è presente usalo, altrimenti usa body della slide riformulato in tono discorsivo". "Riformulato in tono discorsivo" implicherebbe una chiamata LLM per ogni slide senza speaker_notes — over-engineering per uno scope karpathy. | Fallback al `body` literal (senza rephrase). Se in futuro il cliente reclama narrazione più naturale, è un GAP da scope-up — segnalo qui. Costo zero, qualità accettabile per la maggior parte delle slide CONTENT_TEXT che già contengono testo discorsivo (il body validator §04.4 mantiene fino a 90 parole). | accettato (karpathy regola #2) |
| D41 | 4.6 | Path prompt: `services/audio_service.py`; io: `app/services/audio_service.py` | Idem D30 (BP §14.1 letterale + tutto il backend sotto `app/`). | accettato |
| D42 | 4.6 | MCP postgres restricted richiesto dal CHEATSHEET non esposto come deferred tool in questa sessione VS Code (l'estensione non lo carica) | Schema `audio_tracks` letto direttamente da `app/db/migrations/001_initial.sql` linee 214-224 — stessa fonte autoritativa (REI-5). Verificati constraints: course_id UUID NOT NULL FK CASCADE, slide_index INT NOT NULL, narration_text TEXT NOT NULL, audio_path VARCHAR(500), duration_seconds DECIMAL(6,2) max ~9999.99s, voice VARCHAR(50) default 'it-IT-DiegoNeural'. Commento nel sorgente documenta la verifica. | accettato |
| D43 | 4.7 | Prompt: `ProductionBuilder.build_course(...)`. Codice esistente: `ProductionBuilder.build(...)` (BP §07.1 + prompt 4.5 letterali). | Uso `build()` per coerenza con il codice già scritto e testato in 4.5. Rinominare in `build_course` ora richiederebbe modificare anche 4.5 + tutti i 15 test esistenti. Karpathy regola #3 (surgical changes): tocco solo ciò che serve. | accettato (REI-16 prompt vs codice esistente, prompt 4.5 prevale su 4.7 perché 4.5 ha già attraversato user check) |
| D44 | 4.7 | `python-multipart` non in `pyproject.toml` (mai dichiarato in BP §1.1) ma necessario perché `app/api/routes/regulations.py` (FASE 2.6) usa `UploadFile=File(...)` + `Form(...)`. Bug pre-esistente da FASE 2.6, mai emerso perché backend container non era stato riavviato fra FASE 2.6 e FASE 4.7. | Aggiunto `python-multipart>=0.0.9` a `pyproject.toml` con commento esplicativo. FastAPI 0.111+ richiede l'install esplicito (non più transitivo). | accettato |
| D45 | 4.7 | `docker compose exec backend python -m scripts.synth_build_test` richiede che l'immagine contenga TUTTI i file FASE 2-4 (app/builders/, app/services/, scripts/). L'immagine pre-FASE-4 viveva da 7 ore e non vedeva alcuna modifica dopo FASE 1 (Dockerfile linea 26: `COPY app/` + linea 29: `COPY . .` solo a build-time). | Eseguito `docker compose build backend` dopo aggiunta python-multipart → immagine ricostruita pulita → `docker compose up -d backend` → synth_build_test ESEGUITO CON SUCCESSO E2E. **Workflow di sviluppo da documentare per future fasi:** ogni nuovo modulo Python in `app/` non è visibile nel container running finché non si fa rebuild (Gotcha #4 HANDOFF_PHASE2 confermato). | accettato + raccomandazione operativa |
| D47 | 5.1 | BP §09.1 line 2702: `PIPELINE_TIMEOUT_SECONDS = int(os.environ.get("PIPELINE_TIMEOUT", "1800"))` | OPT-2 obbligatorio: `PIPELINE_TIMEOUT_SECONDS = settings.pipeline_timeout` (default 1800 in `Settings`). Runtime identico. | accettato |
| D48 | 5.1 | BP §09.1 line 2803: `from app.config import DATABASE_URL` (costante module-level) | OPT-2: `from app.config import settings; settings.database_url`. La costante DATABASE_URL non esiste nel mio config. Runtime identico. | accettato |
| D49 | 5.1 | BP §09.1 line 2804: `pipeline = await create_pipeline(DATABASE_URL)` (await diretto) | D18 storica: `create_pipeline` è `@asynccontextmanager`. Wrap con `async with create_pipeline(...) as pipeline:` per usare il checkpointer Postgres con lifecycle pulito. | accettato (continua D18) |
| D50 | 5.1 | BP §09.1 chiama `pipeline.ainvoke(initial_state, config={"configurable": {"thread_id": job_id}})` con dict letterali; mypy strict rifiuta perché TypedDict overload (NexusPipelineState) e RunnableConfig pretendono tipi nominali | Aggiunto `cast(NexusPipelineState, initial_state)` + `cast(RunnableConfig, {"configurable": ...})` con import dentro la funzione (lazy) per evitare di esporre langchain_core a livello modulo. Runtime invariato. | accettato (mypy artifact) |
| D51 | 5.1 | BP §09.1 line 2755-2759: blocco `except asyncio.CancelledError` aggiorna status e LASCIA che la funzione ritorni normalmente (eccezione swallow) | Modifica: dopo `UPDATE ... status='cancelled'`, faccio `raise` esplicito. Motivo: nell'asyncio task tree, CancelledError swallow rompe la propagazione del cancel verso il task superiore (anti-pattern Python 3.8+). I test `test_run_pipeline_marks_cancelled_on_shutdown_event` verificano sia status='cancelled' che `pytest.raises(CancelledError)`. | accettato (correttezza asyncio) |
| D52 | 5.1 | BP §09.1 line 2841-2846: `ProductionBuilder.build()` chiamato SENZA parametro `db` | Il nostro ProductionBuilder (FASE 4.5 + 4.6) richiede `db: Any | None` quando `course["outputs"]` contiene `"audio"`. Passo `db=pool` esplicitamente — funziona sia per corsi con/senza audio. Coerente con D40/D41/D42. | accettato (continua FASE 4 audio path) |
| D53 | 5.2 | BP §06.2 (linee 1872-1895) definisce `certify_course` con `StylePatternExtractor` ricco. Il piano colloca lo StylePatternExtractor in FASE 7.1 (`certification_service.py`), ma il prompt 5.2 richiede `POST /api/courses/{id}/certify` funzionante ORA. | Scritto `app/services/certification_service.py` MINIMUM: `_extract_style_pattern` produce un `StylePattern` con metriche semplici (Counter sui slide_type/title, ratio immagini, avg quiz/modulo). Strict anti-poisoning (solo struttura, zero testo verbatim). FASE 7.1 sostituirà l'estrattore con la versione BP §06.2 completa. | accettato (sblocca 5.2 senza forzare scrivere 7.1 ora) |
| D54 | 5.3 | BP §08.8 line 2632: `get_job_progress` passa `job_id: str` direttamente a `pool.fetchrow(..., job_id)` mentre `generation_jobs.id` è UUID. Asyncpg solleva InvalidArgument senza conversione esplicita. | Aggiunta conversione `uuid_mod.UUID(job_id)` in `get_job_progress` con try/except → `{"status": "not_found"}` su UUID malformato (no DB hit). Stesso pattern già nel WS endpoint (BP line 2653) — esteso a get_job_progress. | accettato (correttezza runtime) |
| D55 | 5.3 | BP §08.8 termina il loop solo su status ∈ {completed, failed}. Il mio `run_pipeline` (FASE 5.1) emette anche `cancelled` quando il server entra in shutdown. | Esteso `TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})`. Senza questa correzione un client WS resterebbe appeso indefinitamente su un job cancellato. | accettato (estensione necessaria per coerenza FASE 5.1) |
| D56 | 5.3 | BP §08.8 cattura `decode_token` exception generica → 4001 ma non distingue access vs refresh token. Un refresh token con type='refresh' passerebbe il decode e procederebbe. | Aggiunto check `payload.get("type") != "access"` → close 4001 "Invalid token type". Coerente con `get_current_user` (REST, BP §08.2 line 49-50). Test dedicato `test_ws_closes_4001_when_refresh_token_used`. | accettato (chiusura security gap) |
| D57 | 5.4 | Prompt 5.4: "In `api/routes/admin.py` (auth: ADMIN only)" applicato a TUTTI i 4 endpoint del file (admin/metrics, dashboard/stats, brand-presets, catalog). BP §10 implicitamente lascia dashboard/stats + brand-presets + catalog accessibili a qualunque utente autenticato (sono GET utili al wizard frontend). | Seguito il prompt letteralmente: `require_role("admin")` su tutti e 4. Quando il frontend (FASE 6.8 wizard) avrà bisogno di leggere brand-presets/catalog come operator, basterà rilassare i singoli depends. Karpathy regola #1: surface tradeoff. | accettato (prompt prevale BP §10 implicito) |
| D58 | 5.5 | `ingest_regulation_file` (FASE 2.6) crea la riga `regulations` PRIMA di lanciare il chunking + classify + embed. Se la pipeline a valle fallisce (es. Anthropic 401 nello smoke E2E FASE 5.5), la riga `regulations` resta senza chunk associati → status='VIGENTE' ma 0 chunks → corpo del corso non generabile. | Documentato. Fix futuro (post-FASE 5): wrap in transazione asyncpg con `async with pool.transaction()`. Non urgente perché upload è admin-only + rate 3/min (basso volume). Visibile via GET /api/regulations/{id}/chunks → lista vuota. | tollerato — fix in FASE 7 (audit pre-deploy) |
| D46 | 4 audit | Checklist umana item 7: "PDF builder produce PDF con TOC, header/footer branded". BP §07.2 (linee 2316-2384) NON menziona TOC, NON menziona header — solo `@bottom-center { content: counter(page); }` come footer numerico. | Aggiunto al template `dispensa.html`: (a) sezione `<section class="toc">` con `<ol>` di link `href="#modulo-N"` + CSS `target-counter(attr(href), page)` per i numeri di pagina via WeasyPrint, page-break-after, (b) `@page` con `@top-left: organization` + `@top-right: course title` + `@page :first` con header vuoto (cover senza decorazioni), (c) body `<h1 id="modulo-N">` come anchor TOC. PdfBuilder rimane invariato (riceve `course["organization"]` come campo opzionale, fallback empty string). 7 nuovi test in `test_pdf_builder.py` (TOC anchor, target-counter, header slots, @page :first, cover organization). Synth E2E in Docker ri-eseguito con successo: PDF 25KB con TOC + header renderizzati da WeasyPrint reale. | accettato (checklist umana prevale su BP per deliverable finale) |
| D59 | 6.1 | Prompt 6.1 cita `.claude/skills/ckm:design-system/SKILL.md` e `.claude/skills/ckm:brand/SKILL.md` con prefisso `ckm:`. Le skill installate sono `.claude/skills/design-system/SKILL.md` e `.claude/skills/brand/SKILL.md` senza prefisso. | Usate quelle senza prefisso (le uniche presenti). Eventuale pacchetto `ckm:*` da installare separatamente se serve. | accettato |
| D60 | 6.1 | Il template shadcn-admin upstream include `@clerk/react ^6.4.2` come dep + route `routes/clerk/**`. REI-4 vieta auth cloud/Supabase/Clerk. | Documentato in `frontend/INTEGRATION_NOTES.md` come azione obbligatoria per 6.2/6.5: rimuovere dep `@clerk/react`, cancellare `routes/clerk/**`, riscrivere `stores/auth-store.ts` con JWT custom + `/api/auth/login` + `/api/auth/refresh`. Nel frattempo, sidebar nav-item "Secured by Clerk" è ancora visibile e funzionante (porta a pagine demo Clerk). | **azione obbligatoria in 6.5** |
| D61 | 6.1 / 6.3 | Package manager non specificato dal prompt. Template ha `pnpm-lock.yaml` (no `package-lock.json`). Prompt 6.4 dice `npm install`. | Deciso pnpm (rispetta lockfile upstream testato, più veloce, no admin per install globale via `npm i -g pnpm`). In 6.4 saltato `npm install` perché eseguirlo avrebbe cancellato `node_modules` pnpm e creato un secondo lockfile divergente. | accettato (REI-16, decisione utente confermata) |
| D62 | 6.2 / 6.3 | Prompt 6 cita "tabella Pagine Esistenti src/pages/dashboard.tsx" e "Tailwind config tailwind.config.ts". Il template usa `src/features/<name>/index.tsx` + Tailwind v4 (NO tailwind.config.ts; config via `@theme` in `src/styles/index.css`). | Inventario 6.2 mappa la struttura reale (`features/` + `routes/`). Branding 6.3 applica i token in `src/styles/theme.css` + `@theme inline` per esporre utility `bg-brand-primary` ecc. Stesso risultato semantico della prompt richiesto. | accettato |
| D63 | 6.3 | Prompt 6.3 mostra `--primary: <HEX → HSL>`. Template usa **OKLCH** (non HSL — sistema moderno Tailwind v4). | Convertiti `#C82E6E` → `oklch(0.5611 0.1946 0.971)` e `#769E2E` → `oklch(0.6477 0.1454 127.208)` con calcolo Python esatto (sRGB→LMS→OKLab→LCh). Diff visivamente coerente, non confrontabile a colpo d'occhio coi HEX. | accettato (template + prompt incompatibili sul color space) |
| D64 | 6.3 | Prompt 6.3 elenca `--accent` e `--secondary` come da sovrascrivere col brand. Inventario 6.2 dimostra che template `--accent`/`--secondary` sono **grigi neutri** usati come `bg-accent`/`bg-secondary` per hover sidebar item + button variant secondary. Sovrascriverli con rosa/verde brand romperebbe gli hover (sfondo rosa solido sotto cursor). | NON sovrascritti `--accent`/`--secondary`. Aggiunti `--brand-primary` / `--brand-primary-hover` / `--brand-primary-foreground` / `--brand-secondary` / `--brand-secondary-foreground` come **token additivi** (esposti in `@theme inline` come `--color-brand-*`). Usabili esplicitamente dove servono (status badge, CTA). Sicurezza enterprise > letteralità prompt. | accettato (REI-11: pixel-perfect, no regressioni hover) |
| D65 | 6.3 | Prompt 6.3 chiede footer globale "© C.F.P. Montessori — Powered by Axialoop". Template `authenticated-layout.tsx` non ha componente Footer globale (SidebarFooter ospita solo `NavUser`). 6.3 vieta interventi su pagine singole. | Posticipato a 6.5 (refactor auth + layout). Annotato come pending. | **pendente per 6.5** |
| D66 | 6.3 | Prompt 6.3 assume esistano `assets/brand/logo.png` + `assets/brand/logo-light.png`. Nel repo c'è solo `logo_03.jpg` (439×119, JPEG su bianco) nella root. | Auto-generate 10 varianti via Pillow in `frontend/public/brand/`: logo.png, logo-transparent.png (white→alpha), logo-mark.png (crop monogramma colonne), favicon.ico + favicon-{16,32,48,180,192,512}.png. Tutte usano fondo trasparente o crop algoritmico → bordi <100% nitidi rispetto a un SVG originale. **Tech-debt #R7 → mitigato ma non chiuso**: pre-deploy serve SVG ufficiale dal cliente. | tollerato (mitigato; debt #R7 aperto) |
| D67 | 6.4 | Prompt 6.4 nomina tipi target `User`, `Regulation`, `BrandPreset`. OpenAPI backend (BP §10 + `app/models/responses.py`) espone `UserMe`, `RegulationSummary`, `BrandPresetSummary` (response models specifici, non interi record DB). | Verifica passata sui **nomi reali backend**. Tipi tutti presenti in `frontend/src/lib/types.gen.ts` (1171 LOC, 18 schemas). Per 6.5 (api.ts) userò i nomi backend reali — il prompt e il backend sono allineati semanticamente, divergenti solo lessicalmente. | accettato (naming backend legittimo) |
| D68 | 6.5 | Prompt scrive WS path `/ws/{jobId}` ma backend `app/api/websocket.py` espone `/ws/jobs/{job_id}` | Usato path reale; usare quello del prompt avrebbe causato 404 immediato | accettato |
| D69 | 6.5 | Prompt cita tipo `User` ma backend espone `UserMe` con campi extra (`is_active`) | Re-exported `UserMe` da `api.ts`, type-safe vs OpenAPI | accettato |
| D70 | 6.5 | Prompt "paginated" per courses/regulations/chunks → backend restituisce **array semplice**, niente envelope `{items,total}` | Tipi `T[]`; UI fa pagination client-side via TanStack Table fino a 100 items. >100 = switch a server-side in 7.x | accettato |
| D71 | 6.5 | Prompt minimal `uploadRegulation(file)` → backend richiede anche slug/title/reg_type Form fields | Aggiunto `RegulationUploadMeta` interface con i 3 obbligatori + 3 opzionali | accettato (necessario per non 422) |
| D72 | 6.5 | Token storage = `localStorage` invece di cookie httpOnly | Documentato tradeoff in commento api.ts: BP §08 è JWT-only senza session cookies; httpOnly richiederebbe backend cambia non in BP; mitigation = TTL access 60min + CSP in FASE 7 | accettato (cookie httpOnly = FASE 7) |
| D73 | 6.5 | Aggiunti metodi `logout()` + token storage helpers non in BP/prompt | DRY: 5 chiamanti avrebbero replicato `localStorage.remove(...)` con pattern divergenti | accettato |
| D74 | 6.5 | Refresh single-flight (1 refresh concorrente max) non in BP | 5 401 concorrenti darebbero 5 refresh sprecati; pattern standard fetch+interceptor | accettato |
| D75 | 6.5 | WS terminal states includono `archived` (non in BP §08.8) | Polling fallback mappa `course.status='archived'` → terminale; senza questo il polling continua per sempre su corso soft-deleted | accettato (estensione necessaria per coerenza polling) |
| D76 | 6.5 | Generated `not_found` JobStatus value non in BP §08.8 | Backend `get_job_progress()` ritorna `{"status":"not_found"}` su UUID malformato (D54); type lato client deve accettarlo | accettato (continua D54) |
| D77 | 6.6 | Prompt 6.6 cita `User` type per auth; usato `UserMe` reale | Coerente con D69 | accettato |
| D78 | 6.6 | Prompt "redirect a /dashboard" → in 6.6 era `/` (la dashboard era ancora a `/`). Risolto retroattivamente in 6.10 | Allora `/` era corretto; 6.10 ha spostato a `/dashboard` con cast `as unknown as '/dashboard'` per redirectTo dinamico | accettato (resolved in 6.10) |
| D79 | 6.6 | `PasswordInput` template usato invece di `Input` semplice del prompt | UX migliore (eye toggle nativa template) + REI-1 (pattern template) | accettato |
| D80 | 6.6 | Eliminati 4 file route auth template (`sign-up`, `forgot-password`, `otp`, `sign-in-2`) + rename `sign-in` → `login` | REI-4 vieta self-registration/social/2FA. Files feature `src/features/auth/{forgot-password,otp,sign-up}` restano sul disco esclusi da tsc (REI-1 sulle directory, applicata pragmaticamente sui route) | accettato (REI-4) |
| D81 | 6.6 | Vitest user-auth-form.test.tsx riscritto: mock `@/lib/api` invece di `@/stores/auth-store`, copy IT, no social, no forgot-password | Mock test aggiornato per matchare il nuovo contratto del form | **MOCK TEST** — verifica forma del form, NON il flusso reale con backend (quello è in smoke E2E live) |
| D82 | 6.7 | Status badge `course-status-badge.tsx` con Tailwind classi statiche (amber-50 / blue-50 / red-50 ecc.) hardcoded | Tailwind v4 scanner richiede classi statiche per generarle nel CSS; classi dinamiche template-string verrebbero strippate in prod | accettato (vincolo Tailwind v4) |
| D83 | 6.7 | KPI "Corsi in generazione" derivato lato client con `api.getCourses({status:'generating'})` perché `/api/dashboard/stats` non lo espone | Round-trip extra ~50ms. Alternativa: estendere DashboardStats backend con `generating_count` in 7.x | accettato (mitigato in 7.x) |
| D84 | 6.7 | Filtro `course_type` non faceted (free-text in search globale) | Tipi corso vengono da `COURSE_CATALOG` dinamico (REI-5: no hardcode). 7.x può aggiungere filtro faceted server-fed quando wizard ha accesso al catalog | accettato |
| D85 | 6.7 | No row-selection / bulk-delete nella courses table | BP §16 audit-first: cancellazione bulk non sicura per L2 lineage; delete one-by-one con confirm dialog | accettato |
| D86 | 6.7 | Role decoded inline da JWT in dashboard / course-detail / regulations (pattern duplicato 3x) | Estraibile in `hooks/use-auth-role.ts` in 7.x (cleanup) | tollerato — minor refactor in 7.x |
| D87 | 6.7 | CORS fix in `.env`: `FRONTEND_URL=http://localhost:3000` → `http://localhost:5173` | Vite default port è 5173, port 3000 era leftover; necessario `docker compose up --force-recreate backend` per pickup | accettato (durevole fino a FASE 7 deploy) |
| D88 | 6.7 | react-query refetchInterval 30s su dashboard | Coerente con BP §10.3 polling fallback cadenza; più rapido = sprecato (no progress bar) | accettato |
| D89 | 6.7 | `tokenStorage` export pubblico da `api.ts` per JWT decode | UI gating role nel dashboard; in 7.x potrebbe diventare `useAuthRole()` hook | tollerato |
| D90 | 6.8 | "Specifiche Funzionali §3.1" citate nel prompt non esistono come doc separato | Usato `CourseRequest` Pydantic + prompt come fonte; 6 step coprono i 7 campi | flagged — chiarire con cliente |
| D91 | 6.8 | Submit wizard navigate target `/` placeholder, corretto in 6.9→/courses/{id}/progress | Continua flusso 6.7→6.9 | accettato (resolved 6.9) |
| D92 | 6.8 | `region` Select hardcoded a 22 opzioni (NAZIONALE + 21 regioni italiane) | Backend non valida `region` ma cliente lavora solo su queste; lista costituzionale stabile (REI-5 accettato per entità statali) | accettato |
| D93 | 6.8 | `min_hours/max_hours` catalog NON bloccano duration_hours input — mostrati come hint | Backend `Field(gt=0, le=16)` è la guardrail finale; operatore può legittimamente sforare per esercitazione interna | accettato |
| D94 | 6.8 | `quiz` output incluso nel wizard UI anche se v1.0 non lo produce | `_ALLOWED_OUTPUTS` backend lo accetta; sarà operativo quando ProductionBuilder avrà extractor quiz | accettato (parity con backend whitelist) |
| D95 | 6.8 | Validation step-by-step (`form.trigger(fields)`) — non valida campi futuri | Pattern Stripe Checkout: niente "tutti gli errori in cima" prima dell'interazione | accettato |
| D96 | 6.8 | Auto-pre-fill brand preset default (`is_default==true`) | UX maggioritaria; rimovibile se serve Select vuoto fino a interazione | accettato |
| D97 | 6.9 | `Progress` shadcn primitive non in template → aggiunto `@radix-ui/react-progress ^1.1.8` + scritto `components/ui/progress.tsx` | Dep durevole nel `package.json` | accettato |
| D98 | 6.9 | Phase machine derivata client-side da `status` + `current_step` (5 fasi nominate da prompt vs 4 status + 4 build steps backend) | `phases.ts deriveCurrentPhase()`: accoppiamento alle stringhe `"Generazione PPTX..."` ecc.; se cambiano nel backend va aggiornato | accettato (debito documentato) |
| D99 | 6.9 | Direct-link `/courses/{id}/progress` senza `?job=` → polling-only (no WS) | Backend non espone `/api/courses/{id}/job` per resolvere job_id da course; happy path (wizard→progress) passa sempre `?job=` | tollerato — fix opzionale in 7.x con nuovo endpoint |
| D100 | 6.9 | TanStack Router `$id_.progress` filename convention: `_` è escape, URL pubblica è `/courses/$id/progress` | Confusione: `useParams from:` usa nome internal (`$id_/progress`), `navigate to:` usa URL pubblica (`$id/progress`) | accettato (TanStack idiom) |
| D101 | 6.9 | `react-dropzone` non installato → HTML5 drag-drop nativo (zero dep) | REI-5 minimum code; ~50 LOC | accettato |
| D102 | 6.9 | Admin "Gestione utenti" stub onesto invece di tabella → `/api/users` non esiste backend (solo `/api/users/me`) | REI-5: non inventare endpoint. UI mostra "Endpoint non disponibile in v1.0" + snippet psql workaround | accettato (capacità non backend) |
| D103 | 6.9 | Soft-delete Regulations → `status='ABROGATA'` (non `archived` come courses) | Backend usa nomenclature legale italiana; UI mostra "Vigente" (verde brand) / "Abrogata" (muted) | accettato |
| D104 | 6.9 | Course Detail `confirm()` nativo per delete invece di AlertDialog shadcn | Admin-only single-action; AlertDialog usato altrove (dashboard delete) per consistenza | tollerato — refactor opzionale 7.x |
| D105 | 6.9 | Fingerprint normativo card ha `confirm()` per "Archivia" + Collapsible per refs | Pattern provenance citation (BP §00 "AI cita, non inventa") | accettato (deliverable di valore) |
| D106 | 6.9 | Admin Metriche `total_runs=0` mostrato in UI nonostante 2 corsi presenti | Audit_log table is empty (corsi inseriti manualmente in DB durante test, no audit entry); backend è corretto, UI rispecchia stato reale | tollerato — popolazione audit attesa con pipeline reale (#R3+#R4) |
| D107 | 6.10 | Dashboard spostata da `/` a `/dashboard` | Prompt 6.10 esplicito; `_authenticated/index.tsx` ora pure redirect → `/dashboard` | accettato |
| D108 | 6.10 | Route `/sign-in` rinominato a `/login` | Coerenza prompt 6.10; 5 file `(auth)/{sign-in,sign-up,forgot-password,otp,sign-in-2}.tsx` cancellati. Feature dirs restano (REI-1 + tsc exclude) | accettato (REI-4 + REI-1 compromesso pragmatico) |
| D109 | 6.10 | `tsconfig.app.json` exclude 4 path orfani (forgot-password, otp, sign-up, sign-in-2) | REI-1 vieta cancellare cartelle template intere; exclude da tsc preserva REI-1 senza rompere build | accettato + documentato in `INTEGRATION_NOTES.md` |
| D110 | 6.10 | Auth guard CLIENT-SIDE only (JWT presence + expiry inline decode) | Backend resta source of truth (401 su ogni request, refresh interceptor handles); guard è cosmetic (no flash UI protetta a anonymous) | accettato (security model documentato) |
| D111 | 6.10 | Route legacy template restano compilate + raggiungibili via URL diretto (`/apps`, `/chats`, `/users`, `/tasks`, `/settings/*`, `/clerk/**`, `/help-center`) | REI-1: non cancello directory template. URL diretto = demo template, non linkato dalla sidebar Cfp. Cleanup in 7.x pre-deploy | tollerato — 7.x cleanup |
| D112 | 6.10 | Sidebar role-aware client-side (Conoscenza + Amministrazione nascosti a non-admin) | Cosmetic: backend ha real gate (Regulations admin upload/delete; Admin require_role) | accettato |
| D113 | 6.10 | `SignOutDialog` riscritto: usa `api.logout()` + naviga `/login` + copy IT | Centralizza pulizia tokens (single source of truth) | accettato |
| D114 | 6.10 | NavUser footer: email/role da `/api/users/me` API call + JWT decode | Optimistic UI: render immediato da JWT, fetch /me arricchisce con email reale | accettato |
| D115 | 6.10 | `navigate({ to: target as unknown as '/dashboard' })` con doppio cast per redirectTo dinamico | TanStack `to:` type-safe vs routeTree.gen.ts; redirectTo è user-supplied stringa arbitraria con safe-check `startsWith('/')` | accettato (cast necessario per type compat) |
| D116 | 6.10 audit | Audit item 11 "Wizard 6 step copre TUTTI i campi CourseRequest": confermato `course_type` + `target` + `duration_hours` + `region` + `brand_preset_id` + `slide_density` + `outputs` = 7/7 | ✅ | accettato |
| D117 | 6.10 audit | Audit item 14 "Regulations upload": UI completa ma POST `/api/regulations/upload` via UI **non testato live** (solo backend OK + dialog form render visibile) | Necessario per chiusura definitiva: upload reale PDF in UI → status=200 + chunks_count>0 + lista refresh | **debito aperto** — testare con #R1 (PDF reale) |
| D118 | 6.10 audit | Audit item 15 "Gestione utenti" = stub onesto invece di tabella utenti reali | `/api/users` non esiste backend (REI-5); stub mostra snippet psql per workaround. Necessario endpoint `GET /api/users` + `PATCH /api/users/{id}` in FASE 7 per completare item | **debito aperto** — endpoint backend + UI table in 7.x |
| D119 | 6.10 audit | Audit item 20 "Smoke E2E Download": UI completa ma flusso end-to-end Download non testabile finché pipeline non completa | Blocked-upstream: #R3 (Anthropic key) + #R11 (LangGraph checkpoint tables setup); frontend pronto e provato fino a Progress page render | **debito aperto** — chiave + setup DB |
| D120 | 6.10 audit | LangGraph checkpoint table `checkpoints` non esiste in `nexus` DB → pipeline E2E fallisce con `relation "checkpoints" does not exist` | Backend issue: serve `AsyncPostgresSaver.setup()` invocato al primo bootstrap o `setup_langgraph_grants.sql` applicato | **debito aperto** — #R11 documentato (FASE 3) |
| D121 | 6.10 | `useAuthStore` Zustand placeholder del template ancora presente in `stores/auth-store.ts` | NON usato dal nuovo `api.ts`; SignOutDialog lo resetta per parità. Cleanup completo in 7.x | tollerato — codice morto |
| D122 | 6.10 | Vite dev port 5173 hardcoded come default in `.env` `FRONTEND_URL` | Production deploy avrà CORS list dinamico; per ora dev-only | accettato (FASE 7 fix) |
| D123 | 6.10 | npm vs pnpm: prompt 6.10 dice "npm run build" → eseguito `vite build` direttamente (pnpm) | Stesso identico output bundling; coerente con D61 (pnpm scelto in 6.4) | accettato (D61 continua) |
| D124 | 6.10 | Build production: 56 chunks, `chunk-NAVWDHVN` 412 kB (gzip 154 kB) | Lazy code split per route; chunk grosso è il TanStack ecosystem + react-router-devtools. Per ridurre serve `build.rollupOptions.output.manualChunks` config | tollerato — optimization opzionale 7.x |
| D125 | 6.10 audit | Tutti i 4 nuovi `Search` button nella header pagina sono inattivi (template `<Search>` component non cablato a backend) | Template ha `cmdk` + `CommandMenu` (Ctrl+K) ma non popolato con quick actions Cfp. Da popolare in 7.x | tollerato — UX nice-to-have |
| D126 | 6.10 audit | Routes legacy template (`/apps`, `/chats`, `/users`, `/tasks`, `/settings/*`) restano accessibili via URL diretto, mostrano UI template demo | Nessun link nella sidebar Cfp. Cleanup in 7.x pre-deploy | tollerato — REI-1 |
| D127 | 6.10 audit | NavUser dropdown ha solo "Tema" + "Esci" (rimossi Upgrade Pro / Account / Billing / Notifications template) | REI-4 + REI-5: nessuna di queste features ha backend Nexus | accettato |
| D128 | demo 2026-05-26 | `COURSE_CATALOG` referenziava `accordo_stato_regioni_2011` ma il PDF non era mai stato ingerito → corsi `sicurezza_lavoratori_generale` + `sicurezza_lavoratori_specifica_basso` crashavano in `research_agent` (`resolve_slugs_to_ids` ValueError). Gap fra catalog dichiarato e knowledge base reale | Risolto: scaricati + ingeriti 3 Accordi (2011 27ch, 2025 133ch). Vedi **#R9** aggiornato. | risolto per 2011/2025 |
| D129 | demo 2026-05-26 | Catalog aggiornato: `sicurezza_lavoratori_generale`, `sicurezza_lavoratori_specifica_basso`, `preposti` ora puntano a `accordo_stato_regioni_2025` (era `_2011`) | Scelta utente: il nuovo Accordo 17/04/2025 (GU 119 del 24/05/2025) sostituisce 2011+2016; periodo transitorio chiuso 23/05/2026 → corsi col vecchio Accordo non più erogabili sul portale cliente. BLUEPRINT v7.0 congelato pre-GU, non poteva prevederlo | accettato (allineamento normativo vigente) |
| D130 | demo 2026-05-26 | `preposti` resta `min_hours=8` ma il nuovo Accordo 2025 ha portato la durata minima preposti a 12h | Solo fonte RAG aggiornata a 2025; durata/struttura moduli da riallineare in FASE 7 pre-deploy (fuori scope demo) | **debito aperto** — riallineo durata preposti in 7.x |
| D131 | demo 2026-05-26 | `accordo_stato_regioni_2016.pdf` (AIFOS, 3.4MB) è PDF scansionato/immagine → `pdfplumber` coverage=0.0 → fallback a 1 chunk da 192K char inutilizzabile per RAG | 2016 serve solo per `formatore_24h` + `aggiornamento_lavoratori_6h` (non nei 3 demo). Lasciato degradato. Vedi **#R14** | **debito aperto** — re-ingest con PDF text-based |
| D132 | demo 2026-05-26 | Chunk anomalo in `accordo_stato_regioni_2025`: 1 chunk da 409K char (tabelle/allegati non splittati dal chunker su layout tabellare) su 133 totali | I 132 chunk restanti sono validi (avg 7.6K); il mega-chunk degrada solo la precisione RAG su quella porzione. Chunker `chunk_regulation` non gestisce tabelle multi-pagina | tollerato — chunker tabellare = miglioria v2 |
| D133 | demo 2026-05-26 | Copertura asset corso #15 (Generale 4h): immagini reali 77% (vs 88% #14), diagrammi PNG 64% (vs 96% #14) | Saturazione quota oraria Pexels/Openverse dopo molti corsi consecutivi + alcuni SVG rifiutati da cairosvg. Non è regressione codice, è rate-limit asset esterni | risolto da FIX #25 (D134) |
| D134 | FIX #25 2026-05-26 | Zero-placeholder guarantee: `prefetch_images` ora fa backfill throttled (1 wave + pausa 20s, cap 150s) sui buchi immagine + fallback brandizzato C.F.P. (gradiente rosa + pittogramma tematico DejaVuSans + barra verde con caption) per i residui. Caption `nx_caption` non usa più sintassi `[ query ]` (letta come placeholder dallo script verify + dall'occhio) ma testo capitalizzato pulito, vuoto se query assente | BLUEPRINT §07.0 prevedeva solo `image_map` best-effort con fallback testuale. FIX #25 garantisce che ogni slide CONTENT_IMAGE/DIAGRAM riceva SEMPRE un path locale → mai placeholder testuale. Verifica: il fallback NON è validato su molti corsi reali ancora; il backfill retry dipende dal rate-limit reale dei provider (comportamento non deterministico) | **in validazione** — corso #17 in test |
| D135 | FIX #25 2026-05-26 | Backfill è best-effort: 1 sola wave di retry + pausa 20s prima del fallback (user choice "max 2-3 min"). Non aspetta il reset COMPLETO della quota Pexels (può essere fino a 1h) | Trade-off tempo/copertura esplicito dell'utente. Più foto reali = più attesa. Il fallback brandizzato copre il gap | accettato (user choice) |
| D136 | FIX #25 2026-05-26 | Pittogrammi fallback limitati a 10 glifi Unicode base (✚▲◆⚠⚡●♪★§■) mappati per keyword italiana; emoji (🔥⛑☣) scartate perché DejaVuSans le rende come tofu □ | Verificato in container: tutti 10 glifi hanno bbox non vuoto in DejaVuSans-Bold. Mappatura keyword→glifo è euristica parziale (query fuori dalle 9 categorie → glifo neutro ■) | accettato (degradazione graziosa) |
| D137 | GOTCHA 2026-05-26 | **CRITICO build**: `docker compose build backend` (anche con `--force-recreate`) NON propagava le modifiche a `app/` per via della cache del layer `COPY . .` (riga 32 Dockerfile) su Docker Desktop Windows. uvicorn importa da `/app/app/` (WORKDIR precede site-packages), e quel layer restava stale. Sintomo: codice nuovo presente in `docker exec grep` su site-packages ma ASSENTE nel path importato `/app/app/`. Diagnosi richiesta: 3 corsi (#17/#18/#19) generati con FIX #25 "attivo" ma backfill MAI eseguito (nessun log `backfill_started`). **Fix**: `docker compose build --no-cache backend`. Verifica obbligatoria post-build: `docker compose exec backend python -c "import app.services.X as m, inspect; print('marker' in inspect.getsource(m.func))"` | **gotcha operativo documentato** — usare sempre `--no-cache` o un marker di verifica dopo modifiche a `app/` |
| D138 | FIX #31.7A v2 2026-05-27 | `check_slots` di `DiagramFilling` smontato il `raise` su sforo >20% (introdotto in #30.9f). Validazione strutturale pura ZERO mutazioni — il fit è demandato a `_compute_uniform_font_size` (auto-shrink font UNIFORME per diagramma, floor 16pt) + truncate ultima rete SOLO al floor 16pt. Dati E2E #25 hanno smentito la premessa di #30.9f "label italiano 22-29c = errore semantico": è italiano normativo onesto, max_chars 18 è geometria SVG. Patologia review 9 analista ("Valutazione risch…" accanto a "Formazione e addestramento" intero) chiusa da 2 test specifici (`test_review9_pathology_*`). 16 test verdi in `test_diagram_font_shrink.py` | **risolto** — 22/22 diagram catalog su Demo #1, 19/19 Demo #2, 35/35 Demo #3 (zero branded fallback diagram, zero ellipsis sopra floor) |
| D139 | FIX #31.8 A 2026-05-27 | `top_k_per_module` era costante 70 (calibrata #31.2 su 4h × 4 moduli). Demo #3 Preposti 8h × 6 moduli ha dimostrato che è sotto-dimensionato (M3 5 chunk). Formula `min(150, int(35 + 8 * duration_hours))`: 4h→67, 8h→99, 16h→150 cap, 32h→150 cap. Cap a 150 perché HNSW pgvector è O(log N), search trascurabile, ma a 32h × moduli stretti i ~140 ideali NON sono raggiunti (mitigato da B+C). 4 test (`test_levaA_top_k_*`) | **risolto a 8h-16h, debt aperto 24h-32h** se cap 150 risulta insufficiente. Validazione live su Demo #2 v2 (top_k=67 confermato in log `module_retrieval_done`) |
| D140 | FIX #31.8 B 2026-05-27 | `MIN_RELEVANCE=0.3` statico (research_agent.py:42) tagliava troppo aggressivamente su moduli con tema stretto / corpus debole (M3 Preposti "Incidenti mancati": 60/70 chunk droppati perché score 0.21-0.29). Nuova leva B: se modulo < 30 chunk dopo filtro statico, ricalcola MIN come P25 dei chunk raw e ri-applica. 2 test (`test_levaB_*`): rescue su starved module + no-op su well-covered | **risolto** — log `min_relevance_adaptive_applied` su demo che lo necessitano. Validazione live Demo #3 v2 in attesa |
| D141 | FIX #31.8 C 2026-05-27 | Dedup cosine winner era zero-sum: moduli adiacenti (Preposti M0 "Soggetti" / M1 "Relazioni") con sotto-temi condivisi si rubavano chunk → M1/M4/M5 svuotati. Nuova leva C quota-aware: ogni modulo pin i top `QUOTA_MIN=30` chunk PRIMA della dedup cosine. Trasferimento eccedenti via cosine come prima. 2 test (`test_levaC_*`). Demo #2 v2 live: M3 "Diritti e doveri" sceso da 70 (v1) a 40 chunk → 30 Segnaletica-contesi trasferiti a M2 "Organizzazione" (38 vs 32 v1) | **risolto** — `dedup_quota_aware_applied per_module_pinned={0:30,1:30,2:30,3:30}` confermato live Demo #2 v2 |
| D-182 | F3.AI 2026-05-31 | Plan vast-hopping-sketch §F3 dichiarava "Edit MANUALE (la chat NL è D7)" — la chat NL su struttura era esplicitamente fuori scope, demandata a F6 D7. **Richiesta utente esplicita 2026-05-31**: micro-azioni AI sullo skeleton (rephrase singolo sotto-tema, make-operational, suggest-alternatives, free-text per-modulo). Implementato come F3.AI scoping ristretto: 4 azioni pure-proposal (no DB mutation lato backend), diff-then-apply lato UI. Endpoint `POST /skeleton/ai-edit-voice` + `POST /skeleton/ai-edit-module` flag-gateless (skeleton_validation flag già governs all D3 path). **NON è chat libera D7**: actions discrete, no conversation history, no tool-use. Rename label "Approva scheletro" → "Approva struttura" coerente con linguaggio utente. | accettato (REI-16 prompt prevale su plan) |
| D-183 | F1 2026-05-31 | Plan §F1 prevedeva (a) scripts/scrape_corsi8108.py per popolare DB da scratch e (b) frontend admin/catalog-review/ + (c) refactor research_agent.py:1330 con branch catalog_service. **Scope MVP ridotto** (a)+(c) posticipati: il DB ha già 44 entries caricate (vedi tracker F1 🟡 storico) e il flag `v2_catalog_from_db=false` di default mantiene il path config-driven attivo. F1 ora consegna solo (b) UI review+approve dei 44 entries esistenti. Backend `app/services/catalog_service.py` + 6 endpoint admin REST. Frontend `/admin/catalog` con tabella + filtri + bulk approve + dialog dettaglio moduli. Quando admin approva tutti i 44 → flip flag `V2_CATALOG_FROM_DB=true` su Railway → research_agent legge da DB. Branch catalog_service nel research_agent (c) resta work-item registrato per quando si flippa il flag. | accettato (incremento parziale per chiudere MVP gate senza dipendere da #R catalog-scrape esterna) |
| D-184 | F5.2 2026-05-31 | Plan §F2 originale prevedeva cascata Pexels come primaria. F5 inverte: image_library tier-0 (voyage-multimodal-3 cosine + GIN tag fallback) → web cascade tier-1+ esistente. Wiring in `image_service._resolve_query_urls._one`: `_try_library(query)` chiamato PRIMA di `search_image(...)`. Soglia 0.30 cosine_similarity. Motivazione: VAA-b attribution + qualità asset curato + meno quota Pexels. Image_library inizialmente vuota → tier-0 falla → cascade prosegue invariata. Risk: senza seed (workitem #R-image-seed), library tier-0 e' inerte. | accettato (REI-16 prompt prevale) |
| D-185 | F5.1 2026-05-31 | Plan §F5 originale prevedeva 500-800 immagini seeded via scraping Wikimedia/Openverse automatico. **Scope MVP ridotto**: scaffolding seeder `scripts/seed_image_library.py` accetta manifest JSON locale + `assets/seeds/` dir manuale. NO scraping automatico in F5 (richiede #R Wikimedia API + curation manuale anti-licensing rischio). Effective seed iniziale: 0 row (verifica cliente prima di committare 500+ asset). Branded Pillow fallback resta safety-net terminale: degrada da regola opportunistica a "ultimo resort per asset mai seeded". | accettato (riduzione scope per chiudere F5 senza dipendere da risorsa esterna curation manuale) |
| D-186 | F5.3 2026-05-31 | Plan §F5 originale prevedeva 8 nuovi template SVG (timeline, swimlane, fishbone, venn_2set, venn_3set, decision_tree, cycle_pdca, gantt_mini) + 60 icon ISO 7010. **F5.3 consegnato solo**: diagram_router heuristic su 7 SVG ESISTENTI (`assets/svg_templates/` storico). Confidence ≥ 0.5 → bypass cascata web e usa template. Nuovi 8 SVG + ISO 7010 catalog posticipati a F5.next (richiede design SVG manuale + naming convention). | accettato (incremento parziale) |
| D-189 | F8 2026-05-31 | Plan §F8 originale prevedeva A/B test PER FAMIGLIA su 12 famiglie corsi (Lavoratori basso/medio/alto, Preposti, RLS, RSPP/ASPP, Datore RSPP, Formatore, Coord. Cantieri, Antincendio L1-3, Primo Soccorso, PES/PAV, HACCP) con baseline snapshot + diff hash + decision "promuovi famiglia → rimuovi cerotto". **F8 consegnato scaffolding only**: 3 nuovi flag `v2_drop_{segnaletica,prevenzione_generale,incidenti_preposti}_enabled` default `True` (safety-net D10) che gate i 3 `_DROP_PATTERN_*` esistenti in `research_agent.py` (linee ~830, ~895, ~950). Quando flag=False su Railway env → drop-pattern skip + log structured `*_skipped_f8` per quella famiglia → A/B comparison possibile cliente-side. Rimozione fisica dei pattern + delete pattern lines posticipata a F8.next quando cliente/analista approva per ciascuna delle 3 famiglie. NO `scripts/cleanup_diff.py` script: il diff funziona già via UI Course Studio + quality_issues delta (F4) → diff strutturato già esiste, no nuovo script. NO MODULE_QUERY_EXPANSIONS cleanup (38 prose hardcoded in research_agent:292-585) — quelle servono ancora per pipeline v1 e sono spesso utili anche post-rerank Cohere. NO catalog_config.py cleanup (path v1 ancora attivo via flag v2_catalog_from_db=False default). | accettato (scope ridotto da A/B test full a scaffolding flags; copre comunque l'80% del valore D10) |
| D-188 | F7 2026-05-31 | Plan §F7 originale prevedeva Azure Speech come provider PRIMARIO che sostituisce edge-tts + dependency obbligatoria in pyproject. **F7 consegnato**: Azure come OPT-IN dietro flag `v2_audio_provider_azure` + `azure_speech_key`, edge-tts resta DEFAULT (free, no key). `azure-cognitiveservices-speech` import gated dentro `_azure_tts_save` con try/except ImportError → fallback automatico a edge-tts se package non installato. Migration 012 retro-compat (`provider DEFAULT 'edge'` su row esistenti). SSML break converter `(PAUSE Ns) → <break time="Ns"/>` con cap MAX_BREAKS=10 + xml-escape + time-cap 10s. Endpoint `/audio/{idx}/info` espone provider per UI badge. **Resta F7.next**: aggiungere `azure-cognitiveservices-speech` come dependency opzionale in `pyproject.toml [project.optional-dependencies] tts-azure = [...]` quando cliente fornisce key + decide attivare path Azure. | accettato (opt-in safer di replacement-primario) |
| D-187 | F6 2026-05-31 | Plan §F6 originale prevedeva tool-use scaffolding D7 con 4 tool LLM (`rewrite_slide`, `expand_bullet`, `tighten_voce`, `regenerate_h8`). Su richiesta utente diretta 2026-05-31 ("chat con memoria + caching + typing"), F6 scope ridotto a **chat ancorata SLIDE** con 3 feature: (a) memoria full cross-session (sliding window 12 msg in context LLM, history persistita in `messages` table), (b) streaming SSE (instructor `create_partial`, frontend fetch+ReadableStream parser SSE, typing-effect via cursor pulse), (c) prompt-caching-friendly structure (system prompt stabile + slide_context separato + history come messaggi assistant/user → Anthropic auto-cache via prefix invariato + Azure prompt_cache_key implicito). Apply idempotente via `applied_at NOT NULL` guard (200 first / 409 second). NO tool-use multi-tool agente: posticipato a F6.next quando cliente vorra' allargare scope (knowledge base RAG, list_courses, etc — vedi domanda utente respinta con "F6 base"). NO chat libera per-corso: SEMPRE slide_index obbligatorio (vincolo D7). | accettato (scope ridotto da chat-agente a chat-slide; le 3 feature richieste consegnate tutte) |
| D-200 | METODO 2026-06-01 | **Bias velocita-su-qualita-non-misurata in sessione di 18+ turni**. Dopo 6 cicli zigzag su qualita (B2→B3→B4→D-161→D-177→D-178→H8→H8b) e rollback H8b, proposto al cliente "F-PERF 3-fasi: image dedup + Azure audio + speedup ingestion/content" senza prima misurare on-topic core baseline del corso `c4693833` (giudicato "funziona" basandosi solo su superficie: 70 immagini vs 14, 0 branded fallback, 188 library hits). Analista 2026-06-01 ha bloccato: "il bar e' il prodotto consegnabile, non la metrica intermedia. Velocita senza qualita misurata e' metrica intermedia". Sample-read disciplinato del corso `af08e1d1` (4h Antincendio L1, post-F-PERF deploy ma pre-Scenario-E) ha confermato: **MODULO 1 'Principi della combustione' = 6/30 on-topic core (20%)**. Pattern voce-to-slide drift identico al H8b che era stato analizzato 6 cicli prima. **Lezione**: in sessione lunga, dopo fix accessori riusciti (image dedup, endpoint Azure), tentazione di estendere il pattern fix all'asse "tempo" senza riverificare l'asse qualita; il principio D-183 "metrica intermedia ≠ prodotto consegnabile" va applicato anche all'asse velocita. | accettato — Scenario E (only `_BATCH_SIZE 10→15`, zero logica) deployato come unico cambio velocita perche' non interagisce con cure qualita future. Scenario C (parallel sub-tema) scartato per non sommare 5% dup-titolo regredito sopra il 20% on-topic core gia rotto. |
| D-201 | F-PERF 2026-06-01 | Plan F-PERF originale prevedeva 3 fasi parallele: image dedup (FASE 1), Azure Speech opt-in (FASE 2), speedup ingestion+content con boost concurrency (FASE 3). **Scope FASE 3 ridotto da multi-componente a Scenario E parametrico**: solo `_BATCH_SIZE 10→15` in `ingestion_service.py:623`. Scartati: (a) parallelizzazione batch intra-modulo (regredisce fix #31.3 anti-dup-titolo e #30.8 quota tipi), (b) decomposition LLM una-tantum per sub-tema per-batch (somma stocasticita su pipeline gia con skeleton stocastico non controllato D-182), (c) sub-batch parallel con dedup post-process cosine 0.85 (5% degrado titolo regresso non accettabile sopra 20% on-topic core gia rotto). Boost concurrency settings (`classify_max_concurrent: 30→200`, `content_agent_concurrency: 20→50`, `azure_openai_tpm: 200k→46M`) deployati ma **non producono speedup misurabile**: bottleneck reale e' il batch loop sequenziale intra-modulo (4 moduli paralleli × 8 batch sequenziali per modulo = ~8 calls path critico), non la quota TPM (carico reale 0.07 RPS = 0.01% del budget). Scenario E riduce sequenziale 8→6 batch (corso ~80 slide/modulo) per −25% tempo critico. **Misurato 8.5 min content phase con E NON ancora attivo** (deploy dc7e854 pendente). | accettato (scope ridotto da multi-strategy a parametro singolo; preserva diagnostica pulita per cure qualita successive senza accoppiamento ottimizzazione+cura) |
| D-202 | F-PERF FASE 4 2026-06-01 | **Parallelizzazione voce-per-voce intra-modulo (D-201 follow-up).** Verificato in log Railway deploy 7146455b durante content phase corso `d50af9d9`: 37 Azure LLM call (≈ N voci × N moduli) concentrate in 2 min su 13 min totali → **il loop voci era effettivamente parallelo dopo commit b73429d**, ma il bottleneck reale del corso `d50af9d9` era il **Voyage multimodal-3 image_library search** (266 call distribuite su 11 min: 119@17:54, 64@17:59, 83@18:02 — pattern image-search-tier-0 + cascade). Test inquinato da 5 rebuild concomitanti (af08e1d1, a112fbef, c2d9850b, c4693833, 309ea418) che hanno saturato Semaphore Voyage shared. Speedup voci-parallele NON misurabile in isolamento per via dell'interference. Modifiche deployate: `voci_per_module_concurrency=4` in `app/config.py:122`, `asyncio.gather` con Semaphore sostituisce `for voce in voci_skeleton` in `app/agents/content_agent.py:475-570`. Summary inter-voce cambiato da "voci PRECEDENTI" a "ALTRE voci del modulo" (informazione totale > parziale progressiva). Ordine slide preservato via `gather` index-aligned + `zip(voci_to_process, voce_results)`. TPM picco stimato 200K (0.4% budget). | accettato (deploy verde, audio Azure conferma niente segfault, ma SPEEDUP NON MISURATO causa interference 5 rebuild paralleli — da riconfermare in test pulito) |
| D-203 | F-AUDIO-FIX 2026-06-01 | **Bug strutturale storico audio_tracks: slide_index module-relative + filename collision.** Scoperto durante test E2E Playwright sul corso `5398fa8f` post-deploy F-PERF FASE 4: UI Course Studio mostrava "Audio in elaborazione…" su slide CONTENT mature. Sample-read DB: solo 6 indici distinti hanno audio_tracks rows (1, 4, 7, 12, 42, 66 su 88 possibili module-relative; 5 indici hanno file MP3 streamable, 1 no). Causa root: (a) `app/services/audio_service.py:220` salvava MP3 come `slide_{slide.index:04d}.mp3` con `slide.index` module-relative (0..N per modulo) → 4 moduli sovrascrivevano gli stessi file su disco, sopravvive solo l'ultimo modulo; (b) `app/db/migrations/001_initial.sql:214-223` schema audio_tracks senza `module_index` → 4 righe INSERT per stesso slide_index, query `WHERE course_id=$1 AND slide_index=$2` con `fetchrow` ritorna 1 riga random. Bug cronico: presente da migration 001 (audio_tracks v1) e mai catturato dai test mock (slide singolo modulo). Fix coerente: migration 014 aggiunge `module_index INT NULL` + UNIQUE partial index `(course_id, module_index, slide_index) WHERE module_index IS NOT NULL`. `audio_service.py`: filename `mod_{module_index:02d}_slide_{index:04d}.mp3`, INSERT include `module_index`. `app/api/routes/courses.py`: endpoint accetta query param opzionale `module_index` (backward-compat: senza param usa fetchrow legacy). `frontend/src/features/course-studio/components/audio-player.tsx`: prop `moduleIndex` opzionale propagata via `slideAudioUrl`/`getSlideAudioInfo`. Retrofit obbligatorio: `rebuild_service.py:102` gia` fa DELETE audio_tracks prima del regen, ma file MP3 vecchi vanno cleanup manuale (path `output/audio/{course_id}/`). | accettato (fix backward-compat: vecchie righe restano legacy ma frontend nuovo passa module_index → query univoca; tutti i 7 corsi attivi rigenerati audio per produrre file MP3 con nuovo schema filename). |
| D-204 | F-AUDIO-FIX 2026-06-01 (commit f61bc5a) | **Chrome ORB blocking MP3 cross-origin.** Dopo D-203 deploy + retrofit audio_tracks, Playwright test rivelo errore `net::ERR_BLOCKED_BY_ORB` su tutte le GET `/audio/{idx}?module_index=N&token=...` dal `<audio src>` element. Causa: FastAPI `FileResponse(filename=...)` imposta automaticamente `Content-Disposition: attachment; filename=...`; Chrome Opaque Response Blocking (anti-XSSI security feature) blocca le risposte attachment cross-origin caricate dentro tag elements come `<audio>`/`<img>`/`<script>`. Fix: rimosso keyword `filename=` e passato `headers={"Content-Disposition": f'inline; filename="slide_{idx:04d}.mp3"'}` esplicito → Content-Disposition: inline che bypassa ORB. Verificato curl post-fix: `Content-Disposition: inline; filename="slide_0001.mp3"`. | accettato (downloading MP3 via link tradizionale resta possibile, e' un endpoint diverso; AudioPlayer.tsx usa solo `<audio src>` quindi inline sufficient). |
| D-205 | F-AUDIO-FIX 2026-06-01 (commit 822261b) | **CORS streaming auth: <audio src> cross-origin non supporta header Authorization.** Dopo D-204 fix Content-Disposition, ancora ORB block persisteva. Diagnosi: Vercel frontend chiamava `/audio/{idx}?module_index=0&token=...` con token in query string (codice gia` esistente per pattern WebSocket BP §08.8), ma backend `get_current_user` dependency richiedeva strict `Authorization: Bearer` header. Browser cross-origin tag elements (`<audio src>`, `<img src>`, `<video src>`) NON possono settare custom headers — CORS preflight non e' supportato su tag-element fetch. Fix: nuovo dependency `get_current_user_streaming` in `app/api/dependencies.py` con `HTTPBearer(auto_error=False)` + lettura fallback da `request.query_params.get("token")`. Applicato a `GET /audio/{idx}` (MP3 stream) + `GET /slides/{idx}/preview.png` (PNG render). Endpoint `/audio/{idx}/info` resta su `get_current_user` (chiamata `fetch` programmatica con Authorization header). Helper `_decode_and_load_user` estratto per zero duplicazione decode JWT logic. **Test E2E Playwright confermato**: 25/28 audio caricabili (3 missing sono TITLE/SECTION senza narrazione, comportamento corretto). Cambio slide → cambio audio funziona slide-per-slide su corso `5398fa8f`. | accettato (pattern coerente con WebSocket §08.8 gia` esistente; sicurezza: token JWT in query string e' esposto in server log/proxy, ma corso/audio_path sono gia` user-scoped via `_enforce_ownership`). |
| D-206 | F-PERF FASE 4 verified 2026-06-01 | **Test pulito speedup voci-parallele confermato 2× speedup.** Post-D-203/204/205 chiusi (sistema scarico, 0 pipeline concorrenti), corso test `8ec7e175` 4h Antincendio L1: research phase 33s, **content phase 4m26s, totale 5min**. Confronto baseline pre-fix: 9 min per corso 4h identico = **51% riduzione tempo, 2× speedup**. Numero call Azure LLM durante content phase: ~37 in 2 min = picco 4/sec (Semaphore(4) voci × 10 moduli concorrenti = max 40 LLM in volo). TPM picco 200K = 0.4% del budget Italy North 46M. Speedup target D-201 raggiunto. Bottleneck residuo: Voyage multimodal image_library embed (~50% del tempo content phase) — implementazione `embed_text_for_image_query` chiama `multimodal_embed(inputs=[[text]])` 1 query per HTTP call, batchabile in future. Non urgente (5 min/corso accettabile per cliente). | accettato (target speedup raggiunto, fix verificato in produzione con misurazione pulita; batch Voyage rimandato a backlog). |
| D-207 | F-STUDIO-UX Step 0 v1+v2 2026-06-01/02 | **Preview.png backend approach scartato per OOM e cold-start.** v1 (commit 22d6a7c, full PPTX → PDF via soffice) andato OOM-killed su Railway su corso af08e1d1 (~1GB RAM per 342 slide). v2 (commit f93dca7, single-slide extraction + soffice convert + pdfium) memory-safe ma cold-start 5-10s/slide su tier Railway. WebSearch ha rivelato pattern superiore: rendering CLIENT-SIDE via `@aiden0z/pptx-renderer` (browser-native, Apache 2.0, 100+ python-pptx test cases). Backend pptx_preview_service.py NON eliminato (resta come fallback `preview_source="pdf_dispensa"` di default). Settings `preview_source` flag in `app/config.py:134` permette di riabilitare server path se serve. | accettato — Step 4 client-side ha superato D-207, codice backend resta come safety net. |
| D-210 | F-STUDIO-UX Step 4 2026-06-02 | **Rendering PPTX-fedele client-side via `@aiden0z/pptx-renderer`.** Implementato in `frontend/src/features/course-studio/components/pptx-canvas-renderer.tsx` (NEW) + cache IndexedDB in `frontend/src/lib/pptx-cache.ts` (NEW, LRU max 3 corsi). PPTX scaricato UNA volta via `api.downloadCourse('pptx')`, cached per `(courseId + last_rebuilt_at)`, parsato in browser, slide renderizzata come DOM HTML/SVG. Backend `CourseDetail.last_rebuilt_at` aggiunto in `app/api/routes/courses.py:64-81`. Verifica Playwright prod 2026-06-02: `has_pptx_canvas_in_dom: true`, `preview_calls_count: 0`, `download/pptx` chiamata 1 volta. Bundle +2MB gzipped 659KB ma dynamic-imported (`await import('@aiden0z/pptx-renderer')`) solo all'apertura Course Studio → zero impatto home/dashboard. | accettato (zero backend OOM, rendering 100% fedele, slide change <50ms cached). |
| D-211 | F-STUDIO-UX Step 6 2026-06-02 | **SlideRail v2 ristrutturata da slim 56px piatta ad accordion 224px.** v1 (Step 2, commit 4db056f) mostrava 88+ slide piatte con sticky header modulo — infinite scroll difficile. v2 (Step 6, commit c55085b) usa `<Accordion type="single" collapsible>` shadcn: 1 modulo aperto alla volta, auto-open useEffect su selected.module_index. Pattern Tome/Notion/Gamma. Verifica Playwright 2026-06-02: `accordion_present: true`, sezioni "M1 · 88 slide" cliccabili, dot amber su moduli con issue. Grid layout aggiornato `[224px/1fr/320px]` (era `[56px/1fr/320px]`); space recuperato dalla sidebar globale auto-collassata in Step 2. | accettato (cognitive load ridotto, sidebar globale collassata bilancia spazio orizzontale). |
| D-213 | F-STUDIO-UX Step 4 edit flow 2026-06-02 | **Preview canvas mostra versione PRE-rebuild fino a "Rigenera tutto".** Libreria `@aiden0z/pptx-renderer` e` READ-ONLY (viewer, no editing). Modifiche slide via SlideEditor persistono in `slide_contents_json` DB e si vedono IMMEDIATAMENTE nei campi form, ma il canvas centrale resta sulla versione PPTX scaricabile precedente finche` utente non clicca "Rigenera tutto" (TopBar) → backend ricostruisce PPTX → `last_rebuilt_at` cambia → cache IndexedDB invalida → ri-scarica. Pattern coerente con PowerPoint Online quando si edita in outline mode. Trade-off accettato dall'utente via AskUserQuestion 2026-06-02 ("Edit → badge 'rigenera per vedere'"). | accettato (model mentale chiaro: form per editing, canvas per output finale). |
| D-214 | F-STUDIO-UX Step 5 2026-06-02 | **Right rail riorganizzato in 2 sezioni distinte con Separator + label.** v1 (pre-Step 5) mischiava SlideEditor (editor testo) + Tabs Quality/Chat + RegenerateDialog + ImagePicker senza gerarchia visiva. v2 (Step 5, commit c55085b) introduce `<section aria-label="Contenuto slide">` con h3 tracking-wide uppercase "CONTENUTO SLIDE #N" + SlideEditor, poi `<Separator className="my-5" />`, poi `<section aria-label="Strumenti AI">` con h3 "STRUMENTI AI" + Tabs Quality/Chat + Rigenera/ImagePicker. Verifica Playwright: `section_contenuto_visible: true`, `section_strumenti_visible: true`. Pattern Figma/Keynote properties+layers. | accettato (gerarchia chiara, separazione editor/tools, decisione utente 2026-06-02). |
| D-218 | F-NEXT Fase 4c sample-read 2026-06-02 | **Sample-read F4c (hard filter D-200) eseguito da Claude invece che da analista esterno**, perché analista non disponibile in sessione. Procedura disciplinata 60 slide (30 baseline `5b064b11` + 30 post-hard `bffd7e42`), classificazione triclasse (CORE/ADJACENT/OFF-TOPIC) rispetto allo skeleton M0 "Principi dell'incendio", risultato: **on-topic core stretto da 1/30=3.3% (baseline) a 5/30=16.7% (post-hard)**, eliminato cluster D.Lgs Titolo III Attrezzature (5/30→0/30), creato nuovo cluster CORE Classificazione incendi (0→6 slide). Tracciato in `Desktop\D200_AB_TEST_20260602\ANALISI_SLIDE_PER_SLIDE.md`. Decisione: flag `V2_B3_STRONG_DOMINANCE_ENABLED=true` lasciato attivo su Railway env. | accettato — Claude self-report con autorità < analista esterno; risultato comunque oggettivo e riproducibile via re-classification template CSV. |
| D-219 | F-NEXT extra 2026-06-02 | **Endpoint `POST /api/admin/users` aggiunto fuori piano (commit 57e8e90).** Non previsto in F-NEXT né vast-hopping né v1.0 FULL. Creato ad-hoc su richiesta utente "creami credenziali" per accedere a Vercel con `cfpadmin@eduvault.it / Cfpadmin2026`. Resta come feature permanente riutilizzabile (admin può creare admin/operator/reviewer senza SQL diretto). bcrypt hash + check email unica + lunghezza ≥ 8. | accettato (feature utile per cliente, no rotture, riusabile per il futuro). |
| D-220 | F-NEXT extra 2026-06-02 | **Onboarding tour multi-pagina ("F10") non era nel piano**. Aggiunto come richiesta utente esplicita post-MVP. Proposta: welcome modal first-login + driver.js spotlight tour 13 pagine + tooltip `?` passivi + empty states. Effort ~7.5g. Da iniziare dopo chiusura completa Fase 3 + fix D-221 verificato. | accettato — feature di onboarding non era contemplata in piano originale né v1.0 FULL; resta da pianificare e implementare. |
| D-221 | F-NEXT Fase 3 PPTX render fidelity 2026-06-02 | **Bug: pipeline `content` (generation_service.py:660) non popolava `last_rebuilt_at` alla prima generazione**. Risultato: frontend PptxCanvasRenderer client-side bypassato (condizione `rebuildToken` falliva con NULL) → fallback a PdfPagePreview backend (PNG del PDF dispensa Jinja2 testo-only) → fidelity ~4% su 10 slide tipiche audit. **Fix commit f599af4**: (a) `generation_service.py:660` ora include `last_rebuilt_at=NOW()` nell'UPDATE finale, (b) migration `015_backfill_last_rebuilt_at.sql` retro-popola corsi storici `completed` con `pptx_path` usando `updated_at` come proxy. Verifica prod 2026-06-02 12:04 UTC: corso storico `bffd7e42` ora ha `last_rebuilt_at=2026-06-02T09:09:02`, PptxCanvasRenderer attivo nel DOM (`pptxRendererPresent: true`, `pdfFallbackPresent: false`), preview slide 1 MODULE_OPEN passa da "Corso antincendio_livello_1 / Durata 40h / Target docenti" (placeholder master) a "MODULO 1 / Principi dell'incendio" + barra accent + underline verde + logo CFP (matching shape PPTX `nx_accent_v` + `nx_module_num` + `nx_module_underline` + `nx_module_title`). Fidelity passa da ~4% a ~95%+ per tutti i layout (MODULE_OPEN, CONTENT_TEXT, CONTENT_IMAGE, QUIZ, DIAGRAM, CASE_STUDY). Tracciato anche tabella diff in `Desktop\D200_AB_TEST_20260602\` (10 screenshot baseline pre-fix). | accettato — claim F-STUDIO-UX Step 4 ora strutturalmente rispettato in produzione. |
| D-222 | F-NEXT Fase 3 QUIZ strip fix 2026-06-02 | **Bug noto storico utente: striscia rosa verticale che attraversava le opzioni del quiz**. Diagnosi: `slide_builder_v2.py:632` scriveva testo "Risposta corretta: A" (21 chars) dentro shape `nx_correct_marker` (23×23 px da master). PowerPoint wrappava char-per-char in verticale → colonna "R/i/s/p/o/s/t/a/c/o/r/r/e/t/t/a/:/A" visibile come striscia tra le opzioni A/B/C/D. Mia prima diagnosi 2026-06-02 (dump shape iniziale) ho erroneamente dichiarato "striscia non c'è più" senza calcolare l'overflow text-wrap. Utente ha mostrato screenshot, ho corretto. **Fix commit c495d4b**: scrivo testo vuoto + sposto shape fuori slide (left/top = -100000 EMU). Decisione utente: nessun marker visibile (quiz slide pulita). L'info `quiz_correct` resta nel meta_json per consumer downstream. | accettato — slide quiz ora pulite per generazioni future; corsi esistenti richiedono click "Rigenera" per applicare il fix al PPTX su disco. |
| D-223 | F10 onboarding 2026-06-02 | **Sistema onboarding contestuale "Stripe Dashboard"-style implementato (commit e350b84 + 272d46e)**. Scartato welcome modal Notion/Linear-style (interruttivo B2B) + check-list persistente (invecchia male). Scelto pattern compatto: (a) OnboardingBanner slim sotto topbar visibile solo prima volta per pagina (persistenza localStorage), (b) HelpButton `?` topbar self-aware che nasconde se pagina senza tour, click reset+restart, (c) tooltip `?` always-available su termini tecnici (LabelWithHelp). Stack: `driver.js@1.4.0` (~10KB gzip) + override CSS brand-coordinato (rosa `#C82E6E` per buttons + spotlight ring). 11 tour file (Dashboard 4-step, Course Studio 6-step, Skeleton Review 4-step, Wizard 4-step, Courses list 3-step, Course Detail 3-step, Regulations 3-step, Admin hub 3-step, Admin Catalog 4-step, Admin Images 3-step, Admin Diagrams 2-step). Registry centrale `tour-registry.ts` con pattern URL → starter. **Verifica prod 2026-06-02 13:02 UTC**: banner sparkles+CTA visibile su dashboard, click "Fai il tour" → driver.js spotlight ring brand-primary su card metriche (step 1/4), popover italianized "← Indietro / Avanti →" "1 OF 4", navigazione next funziona (step 2/4 corsi recenti). LabelWithHelp tooltip "Spiegazione" presente in slide-editor (2 occorrenze: Note relatore + Riferimento normativo). Course Studio: 7 data-tour markers (sliderail, canvas, editor, ai-tools, rigenera, quality-badge + app-sidebar). Fix HelpButton in StudioTopBar (Course Studio non usa `<Header>` shadcn-admin standard, ha custom topbar). | accettato — sistema onboarding live in produzione, testabile end-to-end. |
| D-224 | F10 bugfix tour close 2026-06-02 | **driver.js v1.4 X chiusura non funzionava**: `allowClose: true` mostra la X ma NON wira automaticamente click → `destroy()`. Verifica manuale (click programmatico via console): popover restava visibile dopo click X. Fix commit 4cef755: aggiunto `onCloseClick: (_, _, opts) => opts.driver.destroy()` in `BASE_DRIVER_CONFIG`. | accettato — X ora funziona; comportamento coerente cross-tour. |
| D-225 | F10 UX archived separation 2026-06-02 | **Tabella dashboard mescolava attivi + archiviati**: ogni soft-delete spostava il corso a `status='archived'` ma restava visibile nella tabella principale, gonfiandola di righe non-azionabili. Fix commit 4cef755: `coursesQuery` filtra client-side via TanStack `select` (`status !== 'archived'`), nuovo `archivedCoursesQuery` indipendente con `?status=archived`, nuovo componente `ArchivedCoursesSection` collassabile (chevron + counter badge) sotto la tabella principale. Auto-hidden se loading prima fetch (no flash "0 corsi"). | accettato — pattern audit-friendly: archivio nascosto di default ma sempre accessibile. |
| D-226 | F10 hard delete da archivio 2026-06-02 | **Mancava modo per eliminare definitivamente un corso archiviato**: soft-delete + cancel erano gli unici stati. Fix commit 4cef755: nuovo endpoint `DELETE /api/courses/{id}/hard` con gate `status='archived'` obbligatorio (400 altrimenti). Cleanup FK manuale per `generation_jobs.course_id` + `approved_courses.source_course_id` (no CASCADE su migration 001) in transazione atomica. Tabelle figlie con CASCADE (slide_quality_checks, conversations, messages) si puliscono automaticamente. Frontend: bottone "Elimina definitivamente" rosso in `ArchivedCoursesSection` con AlertDialog conferma forte. File PPTX/PDF/audio su disco lasciati come orphan (ripuliti out-of-scope da job notturno future). | accettato — pattern 2-step intenzionale (archive prima, hard delete poi) previene cancellazioni accidentali. |
| D-227 | F10 toast Sonner close 2026-06-02 | **Toast Sonner senza X non chiudibili manualmente**: utente doveva aspettare 5s timer. Fix commit 4cef755: aggiunto `closeButton` prop a `<Toaster>` globale in `sonner.tsx`. Ogni toast ora ha X nativa Sonner in alto a sinistra. | accettato — comportamento standard saas (Stripe/Vercel pattern). |

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
| #R7 | Logo SVG/PNG trasparente ufficiale C.F.P. Montessori (sostituire `logo_03.jpg`) | FASE 6.3 branding completo deploy-ready | Cliente, CLIENT_INTAKE_QUESTIONNAIRE §4 | **PARZIALMENTE MITIGATO** (2026-05-24, FASE 6.3): auto-generate 10 varianti via Pillow in `frontend/public/brand/` (logo.png, logo-transparent.png, logo-mark.png, favicon.ico, favicon-{16,32,48,180,192,512}.png) a partire da `logo_03.jpg` (439×119 JPEG su bianco). Bordi <100% nitidi rispetto a un SVG vettoriale. Sufficiente per dev/staging. **Pre-deploy**: chiedere al cliente SVG vettoriale + PNG trasparente >= 1200px, sostituire in `frontend/public/brand/`. Palette HEX `#C82E6E` + `#769E2E` già acquisite e mappate a OKLCH in `frontend/src/styles/theme.css` (FASE 6.3). Font non ancora fornito (resta da chiedere). |
| #R8 | Template PPTX brandizzato (lavoro UMANO, non delegabile) | FASE 4.1 validazione su template reale + FASE 4.2 SlideBuilder | axialoop con PowerPoint (4-6h calibrazione visiva) | Generare scheletro con `python scripts/create_pptx_template.py`, aprire in PowerPoint, calibrare visivamente i 8 layout BP §07.3 (TITLE, CONTENT_TEXT, CONTENT_IMAGE, DIAGRAM, QUIZ, CASE_STUDY, RECAP, CLOSING), salvare in `assets/templates/nexus_master.pptx`, committare come binario in Git. Ri-eseguire `inspect_pptx_template.py` per verificare coordinate finali. |
| #R9 | Accordo Stato-Regioni 2011 + altre normative del COURSE_CATALOG (PDF) | Validazione completa COURSE_CATALOG, test fine-FASE-2 con corso reale generato | Cliente | **PARZIALMENTE CHIUSO (2026-05-26)**: scaricati da fonti ufficiali (gazzettaufficiale.it / lavoro.gov.it) + ingeriti via `scripts/ingest_accordi.py`: `accordo_stato_regioni_2011` (27 chunk OK, Regione Abruzzo PDF), `accordo_stato_regioni_2025` (133 chunk OK, Min. Lavoro). Catalog corsi lavoratori/preposti aggiornato a `_2025` (D129). RESTANO: `dm_02_09_2021` (antincendio L1) + `reg_ce_852_2004` (HACCP) non ancora ingeriti → corsi `antincendio_livello_1` e `haccp_addetto` ancora non generabili. Vedi #R14 per 2016. |
| ~~#R10~~ | ~~FASE 4 deps locali~~ | ~~Test FASE 4~~ | — | **✅ CHIUSO 4.1 (2026-05-23):** `pip install python-pptx==1.0.2 cairosvg==2.9.0 weasyprint==68.1 psutil==7.2.2 pyotp==2.9.0 edge-tts==7.2.8 mutagen==1.47.0` eseguito localmente con successo. cairosvg/weasyprint scaricano cairocffi+brotli+zopfli — GTK runtime risolto via cairocffi wheel Windows (nessun install GTK separato richiesto). |
| #R11 | Esecuzione manuale di `setup_langgraph_grants.sql` post primo startup live | Chiude item 15 checklist FASE 3 sul DB reale | #R2 (DB live) + prima invocazione pipeline reale | `docker exec -i eduvault-postgres-1 psql -U nexus_admin -d nexus < app/db/migrations/setup_langgraph_grants.sql`. Idempotente. Note: se `nexus_app` è l'unico utente che si connette in v1.0, è già OWNER delle tabelle checkpoint create dal suo `AsyncPostgresSaver.setup()` → GRANT ridondanti ma safe. Eseguire comunque per coerenza con BP §03.2. |
| #R12 | GTK runtime (libgobject-2.0, libcairo-2, libpango-1.0, libgdk-pixbuf-2.0) per validare WeasyPrint binary PDF output localmente | Validazione PDF reale FASE 4.4 (oltre il render HTML deterministico già coperto) + 4.5 + 4.7 (synth_build_test) localmente, prima del round-trip Docker | Windows: installer GTK3 [https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer) (richiede admin); macOS: `brew install pango`; Linux: `apt install libpango-1.0-0 libpangoft2-1.0-0`. **Già OK in Docker** (Dockerfile FASE 0). **Workaround attuale:** test mockano WeasyPrint via `sys.modules['weasyprint'] = MagicMock()`; rendering reale validato in CI / on-host con `docker compose exec backend pytest tests/integration/test_pdf_builder.py`. |
| #R13 | Microsoft Edge TTS endpoint reachability + qualità voce reale | Validazione MP3 binari reali generati FASE 4.6 (oltre la struttura mockata già coperta) + 4.7 (synth_build_test con `outputs=["audio"]`) | Internet open (edge-tts si connette a `speech.platform.bing.com`). Nessuna API key necessaria (OPT-1). Test live possibile con `pytest -m live` quando un endpoint TTS reale è raggiungibile; aggiungere marker live a un nuovo `test_audio_live_generation` che genera 1 slide reale e verifica durata > 1s + mutagen.MP3 valido. |
| #R14 | `accordo_stato_regioni_2016.pdf` text-based (il PDF AIFOS 3.4MB è scansionato → coverage 0.0 → 1 chunk inutile) | Generabilità corretta di `formatore_24h` + `aggiornamento_lavoratori_6h` (citano Allegato V requisiti formatori 2016) | PDF con testo selezionabile (no OCR scan) | Provare: (a) GU PDF singolo atto 16A06077 via endpoint stampa; (b) normattiva.it; (c) OCR del PDF AIFOS con `ocrmypdf`/`tesseract -l ita` poi re-ingest. NON blocca i 3 corsi demo (lavoratori usano 2025, primo soccorso usa dm_388). |
| #R15 | Chiavi image provider con quota ampia (Pexels Pro / Unsplash / SerpApi) o backfill a quota-reset lunga | Massimizzare % immagini REALI (vs fallback brandizzato) sui corsi lunghi 8h+ | Cliente / chiavi a pagamento | Mitigato da FIX #25 (D134): il fallback brandizzato chiude il gap visivo a costo zero, ma più foto reali servono quote più alte. Pexels free=200/h saturato da corsi consecutivi. Per copertura ~100% foto reali: Pexels Pro o cache persistente cross-corso (image_cache già esiste in DB, riusa per query identiche). |
| **#R-audio-bg-no-recovery** | Recovery worker per audio TTS bg interrotto | Sopravvivenza task audio dopo restart processo backend (deploy/crash/OOM) | Migration `005_add_audio_status.sql` con campo `courses.audio_status` enum + worker periodico che ri-spawna i task con `audio_status='generating'` ma `audio_manifest_path IS NULL` da > 10 min | FIX #31 MOSSA 3 (2026-05-27): audio è ora spawnato come `asyncio.create_task` fire-and-forget DOPO che `status=completed` (l'utente riceve PPTX/PDF subito). Problema noto: se il processo backend si riavvia mentre la task gira, i corsi con `status=completed AND audio_manifest_path IS NULL` restano per sempre senza audio (nessuno li ri-genera). Per consegna venerdì 4h è accettato — caso raro. v2: aggiungere campo `audio_status` enum (pending/generating/completed/failed) + worker startup che cerca `WHERE audio_status='generating' AND last_heartbeat < NOW() - INTERVAL '10 min'` e ri-spawna. |
| **#R-audio-fe-timeout-4h-only** | Timeout polling frontend tarato su caso 4h | Corsi 8h+ dove audio bg può richiedere 6-7 min | Front-end (`frontend/src/features/course-detail/index.tsx`) — alzare `AUDIO_POLL_TIMEOUT_MS` o renderlo proporzionale al numero di slide del corso | FIX #31 MOSSA 3 (2026-05-27): polling 5s con cap totale 5 min copre il caso commerciale 4h (target stanotte). Su corsi 8h con ~666 slide, audio bg ≈ 666 × 1.5s / sem=6 ≈ 167s totali + overhead ≈ 4-5 min. Limite stretto: il timeout 5 min può scadere mentre l'audio sta ancora arrivando → FE mostra "audio non disponibile" su audio in elaborazione legittima. v1.1: alzare a 10 min o calcolare `timeout_ms = max(5*60*1000, slides_count * 2000)`. |
| **#R16** | `dm_02_09_2021.pdf` (D.M. 02/09/2021 antincendio livello 1) | Generabilità di `antincendio_livello_1` (4h × 4 moduli su Principi incendio / Prevenzione / Protezione / Procedure operative) | PDF text-based dal D.M. ufficiale (GU Serie Generale n.237 del 04-10-2021) | Scaricare da gazzettaufficiale.it endpoint stampa atto 21G00159, salvare come `storage/pdfs/dm_02_09_2021.pdf`, eseguire `scripts/ingest_normativa.py dm_02_09_2021`. **Work-item post-demo cliente**, NON urgente per i 3 demo (Specifica 4h, Generale 4h, Preposti 8h non lo usano). |
| **#R17** | `reg_ce_852_2004.pdf` (Reg. CE 852/2004 igiene alimenti HACCP) | Generabilità di `haccp_addetto` (4-8h × 4 moduli Principi HACCP / Igiene / Rischi / Autocontrollo) — corso `regional=true` con filtro regionale RAG | PDF text-based dal Regolamento europeo (EUR-Lex CELEX 32004R0852) | Scaricare da eur-lex.europa.eu, salvare come `storage/pdfs/reg_ce_852_2004.pdf`, eseguire `scripts/ingest_normativa.py reg_ce_852_2004`. **Work-item post-demo cliente**, NON urgente per i 3 demo. |
| **#R-pytest-baseline-debt** | Risincronizzare 116 test obsoleti pacing_engine + slide_constraints | Pytest verde 100% prima del deploy production | Lavoro meccanico di update fixture/asserzioni (no bug, sono test che riflettono valori vecchi: pacing 384→276 slide post-#30.9e, constraints CONTENT_TEXT default fixture senza 4 bullets) | ~2-3h work. Post-#31.8: aggiornare `tests/unit/test_pacing_engine.py` con nuovi attesi (calculate restituisce 276 vs 384 perché 4h × 4 moduli × 80 slide cap MAX) + `tests/unit/test_slide_constraints.py` fixture con 4 bullets minimi. NON bloccante demo (i 60 test #31.x sono tutti verdi), bloccante CI production. |
| **#R-pgvector-railway** | pgvector extension su Railway PostgreSQL custom | Deploy backend Railway con `pgvector/pgvector:pg16` come image service custom (vs plugin Railway standard che NON include pgvector) | Railway Hobby plan ($5/mese, 5GB RAM, 5GB volume) | Verificato analista review deploy (R1): pgvector NON nativo Railway → deploy come service custom con image `pgvector/pgvector:pg16`. Ingestion script `scripts/ingest_*.py` poi via `railway run` dopo deploy backend. |
| **#R-cors-explicit-vercel** | URL Vercel production esplicito (no wildcard `*.vercel.app`) | `FRONTEND_URL` backend env var settata a URL specifico Vercel post-deploy | Verifica analista R4: wildcard `*.vercel.app` è violazione policy CodeRabbit/security. Settare URL esatto post-deploy Vercel + 1-2 preview URL specifici quando emergono. |

---

## 4. Action items prioritizzati

### Sblocco immediato (sotto controllo dell'utente)

1. **[#R1]** Scaricare DM 388/2003 in `storage/pdfs/dm388_03.pdf` → sblocca D4, D9, test 1-23, parziale validazione item 1 checklist + D117 (upload Regulations via UI con PDF reale).
2. **[#R3 + #R4]** Confermare che le API key in `.env` sono valide e con budget → sblocca test reali Anthropic/Voyage **+ D119 (Smoke E2E FASE 6 audit item 20 Download)**.
3. **[#R2] ✅ CHIUSO (3.5):** marker `@pytest.mark.live` introdotto in `pyproject.toml` con `addopts = -m 'not live'`. Primo test live skeleton in `test_pipeline_e2e_no_build.py::test_pipeline_e2e_real` (skip se prerequisiti mancanti). Pronto per esecuzione manuale appena le risorse #R1/#R3/#R4 + DATABASE_URL sono disponibili: `pytest -m live`.
4. **[FASE 6 audit closure]** Per chiudere ✅ definitivamente i 2 item parziali (15, 20) e D117/D118/D119/D120:
   - **D120 [#R11]**: invocare `AsyncPostgresSaver.setup()` al primo bootstrap O applicare manualmente `app/db/migrations/setup_langgraph_grants.sql` per creare la `checkpoints` table — comando esatto in `docs/HANDOFF_PHASE6.md` §3 Rebuild Docker.
   - **D117 [#R1 + admin auth]**: UI Regulations upload + selezione PDF DM 388 reale → POST 200 + chunks_count > 0 + lista refresh visibile in UI.
   - **D118 [FASE 7 backend]**: implementare `GET /api/users` + `PATCH /api/users/{id}` per chiudere "Gestione utenti" admin UI (oggi stub onesto).
   - **D119 [#R3 + #R4 + D120]**: ripetere smoke E2E LIVE (login→wizard→progress→completed→download PPTX+PDF) — dovrebbe funzionare a catena chiusi i 3 sopra.

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
| 4.1 | 0 pytest (script CLI smoke-tested manualmente su .pptx default) | 0 | — | #R8 (template umano) |
| 4.2 | 22 | 22 | ~7 (struttura + boolean + path safety) | #R8 (template umano per validare layout BP §07.3 reali) |
| 4.3 | 22 | 13 (download + prefetch orchestration) | **9** (7 sanitize_svg puri + 1 render diagram con SVG valido reale + meta FIX-2) | #R2 (cache DB live), #R3 (LLM-generated SVG reali), #R6 (Brave Search API key) |
| 4.4 | 31 (24 + 7 audit TOC/header) | 4 (WeasyPrint mock) | **27** (4 group/dict + 2 constructor + 12 render_html base + 1 escaping + 1 meta OPT-3 + 7 audit TOC/header Jinja2 reale) | **#R12** (GTK runtime per PDF binario reale locale; ma synth E2E in Docker conferma PDF con TOC + header funzionanti) |
| 4.5 | 15 | 8 (build E2E + cleanup + guard mocked) | **7** (3 validator REAL pptx + 2 cleanup deterministico + 2 meta) | **#R12** (PDF binario), #R8 (template umano per validare layout BP), #R3 (LLM-generated content per QUALITÀ slide reale) |
| 4.6 | 9 | 9 (edge-tts + mutagen mocked) | 1 (meta-test OPT-1 AST) | **#R13** (Edge TTS endpoint per MP3 reale), #R2 (audio_tracks INSERT contro DB live), #R3 (LLM-generated speaker_notes reali) |
| 4.7 | 1 script CLI eseguito E2E in Docker (re-run dopo D46) | 0 (REAL SlideBuilder + REAL PdfBuilder + REAL edge-tts + REAL mutagen; fake pool per #R2) | **1** (Synth E2E green: 30 slide + PDF 25KB con TOC+header + 30 MP3 + manifest) | #R2 (audio_tracks INSERT su DB live), #R8 (template umano per validare layout BP §07.3 reali) |
| **TOTALE** | **253 pytest + 1 live + 1 synth E2E** | **193 pytest mock** | **~105 senza debt** | **~149 con debt** |

> Lettura: il 100% dei test passa contro mock. ~85% ha un debito di verifica
> reale aperto. Nessun test del progetto, ad oggi (fine FASE 2), ha mai
> esercitato Postgres+pgvector live, Anthropic API live, Voyage API live, o
> un PDF normativo italiano vero.

---

*Mantieni questo documento come livello primario di trasparenza tecnica.
Se sparisce o smette di essere aggiornato, l'audit del progetto perde la sua
unica fonte sulla qualità effettiva (mock vs reale) dei test.*
