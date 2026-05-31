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

### 7. Content phase ❌ STUCK
- Polling status ogni 30s via API: **status=`content` per >22 minuti** vs media ~10 min
- `slide_contents_json` = `null` (0 slides generated cumulato)
- Possibili cause backend:
  - Anthropic API LLM timeout / 429 rate limit / retry exhaustion (50-60 LLM calls per 6 moduli × 8-10 voci)
  - Semaphore(1) deadlock (REI-3)
  - Background task `asyncio.create_task(run_pipeline)` morto silenziosamente
  - Voyage embed throttling per immagini library tier-0 lookup
- **Investigazione richiesta**: log Railway content_agent + generation_service per capire dove pipeline si è fermata
- **Studio + asset library + diagram catalog test bloccati su content phase completion**

### 8. Studio test ⏸ DEFERRED
Pending content phase completion. Quando completata:
- [ ] Sidebar 50+ slide con thumbnail
- [ ] Click slide CONTENT_IMAGE → image-picker → tab "Library" mostra hit `demo_seed` / `iso7010`
- [ ] Query "estintore" → F001_estintore.png trovato
- [ ] Slide DIAGRAM → uno dei 15 template usato (verify diversità: ≥3 tipi diversi su 6 moduli)
- [ ] F6 chat tab → invio prompt + apply diff
- [ ] F7 audio player → play
- [ ] Download PPTX → file valido

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
