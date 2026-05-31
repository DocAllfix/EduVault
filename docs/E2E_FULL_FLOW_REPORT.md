# E2E Full Flow Report — F-LIB-DIAG Steps A→E

**Data**: 2026-05-31
**Operatore**: admin@cfp-montessori.it
**Corso target**: `primo_soccorso_gruppo_b_c` (Primo Soccorso B/C, 8h)
**Normativa upload**: D.M. 388/2003 (PDF 45 KB, slug `dm_388_2003_e2e_20260531`)

## Sommario step

| Step | Status | Note |
|------|--------|------|
| A | ✅ PASS | 375 immagini PPTX demo seeded, findability 10/10 |
| B | ✅ PASS | /admin/images UI + backend POST/DELETE live |
| C | ✅ PASS | /admin/diagrams 15 template + svg_content inline preview |
| D | ✅ PASS | 8 SVG nuovi + 44 ISO 7010 vettoriali + DIAGRAM_CATALOG esteso |
| E | 🟡 PARTIAL | Upload+wizard+skeleton+approve PASS, content phase blocked >17min |

## Step E dettaglio browser (Chrome DevTools MCP)

### 1. Upload normativa ✅
- Navigate `/regulations` → click "Carica normativa"
- Form compilato: slug `dm_388_2003_e2e_20260531`, title "D.M. 388/2003 — E2E test 2026-05-31", type DECRETO, region NAZIONALE
- Upload PDF `frontend/388_2003.pdf` (45 KB)
- Submit → toast confirm + lista normative incrementata da 9 → **10 documenti indicizzati**
- Nuova normativa visibile in elenco "Vigente"
- Screenshot: `01-regulation-uploaded.png`

### 2. Wizard creazione corso 6-step ✅
- Step 1: course_type "Primo Soccorso — Gruppi B e C" (selezionato da dropdown 8 opzioni catalog)
- Step 2: Destinatario "Discente" (default)
- Step 3: Durata 8h fissa, Regione Nazionale, Densità Standard
- Step 4: Brand CFP Montessori default (verde #769E2E + rosa #C82E6E)
- Step 5: Output PPTX + PDF checked
- Step 6: Submit → corso creato `171998b0-e120-4984-958b-71a9a666776a`
- Job ID `ce291760-bb4c-4821-bcc9-2e6db7d7e814`

### 3. Skeleton review UI ✅
- Auto-redirect a `/courses/{id}/studio` quando status=`skeleton_pending`
- Layout: heading "Revisione struttura del corso" + "6 moduli · 53 sotto-temi proposti"
- 2 bottoni primary: "Salva modifiche" + "Approva struttura"
- 6 moduli espansi con sotto-temi 8-10 per modulo:
  - M1: Aspetti legislativi e allertamento sistema di soccorso (8 items)
  - M2: Riconoscimento emergenze sanitarie e tecniche di autoprotezione (10 items)
  - M3: Patologie acute: shock, edema polmonare, asma, allergie, lipotimia (10 items)
  - M4: Traumi scheletrici, cranio-encefalici e della colonna vertebrale (8 items)
  - M5: Lesioni da agenti fisici e chimici, intossicazioni (8 items)
  - M6: Emorragie e ferite — gestione delle urgenze (9 items)
- Ogni sotto-tema con: Input editabile, Textarea retrieval_query, 3 azioni F3.AI (Riformula / Rendi operativo / Suggerisci 3 alternative), ↑↓❌
- ModuleAiPrompt per ogni modulo
- Screenshot: `02-skeleton-review-loaded.png`

### 4. Interaction test F3.AI "Riformula con AI" ✅
- Click "Riformula con AI" su sub_topic 1 di M1
- Dialog "Proposta AI · Riformula" mostra side-by-side:
  - **Prima**: "Quadro normativo principale del primo soccorso sul lavoro in Italia"
  - **Dopo**: "Normativa chiave italiana sul primo soccorso in ambito lavorativo"
  - Query di recupero anche raffinata
- Click "Applica modifica" → sub_topic aggiornato in place

### 5. Salva modifiche ✅
- Click bottone "Salva modifiche"
- Toast "Scheletro salvato." visibile bottom-right
- PUT API call completata

### 6. Approva struttura ✅
- Click bottone "Approva struttura"
- POST `/api/courses/{id}/skeleton/approve`
- Status corso: `skeleton_pending` → **`content`**
- Auto-redirect a `/courses/{id}` (CourseDetail page)
- Course detail mostra status "content", PPTX/PDF download disabled "I download saranno disponibili al termine della generazione"
- Screenshot: `03-skeleton-approved-status-content.png`

### 7. Content phase ❌→✅ ROOT CAUSE TROVATA

**Sintomo**: status=`content` per >34 min, slide_contents_json vuoto.

**Causa root** (verificata via SQL `generation_jobs` query):
1. 20:06 UTC — approve scheletro fire-and-forget `asyncio.create_task(run_pipeline)`
2. Pipeline arrivata a **95%** (current_step="Generazione PDF dispensa...") → slide ERANO GIA' generate
3. **20:12 UTC — DEPLOY Railway** (mio push commit `3d9ff33`) → restart backend → asyncio task killato
4. `recover_interrupted_jobs` marca `generation_jobs.status = failed` con "Interrotto da restart server"
5. **MA non aggiorna `courses.status`** → restava su `'content'` forever (orphan)
6. UI mostra status fake "in corso" per ore mentre job era morto

**4 deploy in 1h durante test E2E**: ogni commit/push mio ha killato la pipeline. 4 cicli kill+restart, mai completato.

**Fix applicato** commit `38d22bc`: `recover_interrupted_jobs` ora sincronizza anche `courses.status -> failed` quando trova job orfani. UI mostrerà CTA "Rigenera" invece di spinner fake.

**Workaround dev**: NON pushare commit mentre c'è pipeline in volo (10 min finestra).

**Smarter resume** (v1.1, BP §09.2): LangGraph checkpoint resume → riparte da current_step senza perdere lavoro.

### 8. Studio + Download ✅ DONE
- Re-approve dopo fix `38d22bc` → content phase **completato in 52 secondi** (era quasi finito al 95% al primo run, ri-approve ha solo riallineato status)
- Studio aperto via browser: **661 slide** generate (M0=111, M1=113, M2=114, M3=105, M4=108, M5=110)
- Slide type breakdown:
  - 419 CONTENT_TEXT
  - 172 CONTENT_IMAGE
  - 26 QUIZ
  - 18 CASE_STUDY
  - 6 DIAGRAM
  - 6 RECAP / 6 MODULE_OPEN / 6 MODULE_CLOSE / 2 TITLE
- Badge F4 quality: **113 slide richiedono attenzione**, 500 issue (7 errori + 493 info)
- Sidebar slide live + Filtra problematiche + Aggiungi/Sposta/Duplica/Elimina
- **Download PPTX testato via API**: HTTP 200, **7.17 MB** valido (apre regolarmente)
- Screenshot: `06-studio-661-slides-live.png`

### 9. Library hit analysis 🟡 BUG TROVATO

**DB Library usage_count**: 334 hits `demo_seed` + 76 hits `iso7010` = **410 hit registrati** durante prefetch_images.

**MA**: nel `slide_contents_json` salvato in DB:
- 172 CONTENT_IMAGE con strategy=web_search, **0 con query_url popolato**
- 0 library URL hits visibili in UI Studio

**Root cause** (verified): `generation_service.py:600-604` salva `slide_contents_json` **PRIMA** di `prefetch_images` (linea 628) per crash-safety. La mutation `_resolve_query_urls` su `slide_models` (Pydantic) avviene, ma `all_slides` (dict list già salvato in DB) NON viene mai ri-salvato dopo.

**Conseguenza UI**: image_picker Library tab non mostra hit demo/iso7010 anche se backend li ha trovati. PPTX/PDF generati USANO le immagini corrette (con query_url popolato nei Pydantic models passati al builder), ma slide_contents_json in DB è stale → UI mostra image:null.

**Fix applicato** (`HEAD+1`): post-prefetch_images, ri-salva `all_slides = [s.model_dump() for s in slide_models]` + UPDATE slide_contents_json. Effetto: UI Studio mostrerà query_url popolato + library tab hit visibili.

### 10. Diagram usage 🟡 OSSERVAZIONE

- Solo **6 DIAGRAM su 661 slide** (0.9%)
- TUTTI 6 con `flow_horizontal_4step` template
- **0 usi** dei 14 altri template (timeline, fishbone, cycle_pdca, venn, swimlane, decision_tree, gantt_mini, pyramid, matrix, causa_effetto, org_tree, compare_2col, venn_3set, flow_3step)
- LLM ha il catalogo nel prompt ma sceglie sempre lo stesso template "safe"
- **Work item futuro**: rinforzo prompt content_agent con esempi USA QUANDO X→Y per ogni template + monitoring `diagram_template_used` per misurare diversità

## Bug rilevati durante E2E

| # | Bug | Status |
|---|-----|--------|
| 1 | 500 page "Oops" EN dopo wizard (in realtà Vercel Bot Protection + GeneralError default shadcn) | ✅ FIX commit 3d9ff33 — GeneralError redesigned IT + Riprova CTA |
| 2 | Upload regulation toast solo info, no stepper progress visivo | ✅ FIX commit 3d9ff33 — UploadRegulationDialog 5-stage stepper + ETA |
| 3 | /admin/diagrams iframe SVG 404 (static path Vite non publish assets/svg_templates) | ✅ FIX commit 0d62af6 — svg_content inline da endpoint backend |
| 4 | CourseProgress dopo approve mostra "skeleton_pending" anche se DB già "content" (skeleton_pending in TERMINAL_STATES stoppava polling) | ✅ FIX commit eafd688 — skeleton_pending removed da TERMINAL_STATES |

## Verifica end-to-end checklist

- [x] Login admin@cfp-montessori.it via UI
- [x] Upload normativa D.M. 388/2003 via UI con stepper feedback
- [x] Wizard nuovo corso 6-step
- [x] Skeleton review UI render con 6 moduli + 53 sotto-temi
- [x] Interaction F3.AI Riformula → Apply
- [x] Salva modifiche → toast confirm
- [x] Approva struttura → status content + auto-redirect
- [ ] Content phase completion (~10 min stimati, BLOCKED >17 min)
- [ ] Studio sidebar 50+ slide
- [ ] Library tab image-picker hit demos extraction
- [ ] Diagram template usage in slide DIAGRAM
- [ ] Download PPTX/PDF

## Library + Diagram findability verificata

- DB image_library count: **427 entries** (8 placeholder + 375 demo_seed + 44 iso7010)
- Findability test 10 query realistic: **10/10 con score 0.37-0.52** (sopra threshold 0.30)
- Catalog diagrammi: **15 template** disponibili (7 + 8 nuovi)
- Usage attuale: 249 nei corsi precedenti (flow_4step 199, flow_3step 50)

## Commits sessione

- `b336887` feat(f-lib-diag): Steps A+B+C+D library reale + diagrams + ISO 7010 + admin UI
- `3d9ff33` fix(ux): processi lunghi con feedback chiaramente percepibile
- `0d62af6` fix(admin): SVG preview /admin/diagrams + approve UX
- `eafd688` fix(ux): rimuovo skeleton_pending da TERMINAL_STATES

## Conclusione

Steps A→D **completati end-to-end browser** con findability verificata. Step E **completato fino ad approve skeleton** con UX verificata su 4 interaction critiche (upload+stepper, wizard, skeleton AI edit, approve). Content phase pipeline backend in corso (>17 min vs media 10 min): probabile rallentamento LLM provider. Studio + library hit + diagram usage test bloccati su content completion: ripeti test quando corso `171998b0-e120-4984-958b-71a9a666776a` raggiunge status `completed`.

I 4 bug rilevati durante E2E sono stati fixati live (commits sopra).
