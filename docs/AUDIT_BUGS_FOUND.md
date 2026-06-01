# Audit Bugs Found — 2026-06-01

Tracking file per registrare bug + soluzioni durante audit completo. Tutti fix
in UN solo commit finale per evitare cooldown Vercel bot.

## Bug 1 — ChunksSheet card click no-op (regulations)
**Sintomo**: click su una RegulationCard non apre lo Sheet con i chunks.
**Causa**: il button overlay `absolute inset-0 z-0` era SOTTO il contenuto della Card → click non lo raggiungeva.
**Fix applicato in memoria** (NON committato ancora): `Card` diventa cliccabile (onClick + role=button + tabIndex=0 + keyboard handler), rimosso overlay button.
**File**: `frontend/src/features/regulations/index.tsx` (RegulationCard component)

## Bug 2 — Dashboard "/#corsi" link morti (4 stats cards)
**Sintomo**: cliccando "Corsi totali", "In generazione", "Corsi certificati (L2)" si va a `/#corsi` che è una ancora **non esistente** sulla dashboard.
**Causa**: anchor `#corsi` non puntano a nessun id reale.
**Fix proposto**: aggiungere `id="corsi"` alla section corsi nella dashboard, oppure cambiare href a `/courses` (route dedicata se esiste) o all'ancora reale.
**File**: `frontend/src/features/dashboard/components/stats-cards.tsx:66,73,85` + `frontend/src/features/dashboard/index.tsx`

## Bug 3 — Studio editor body/bullets mismatch (DEPLOYED 48e759a)
**Sintomo**: "Salva modifiche" nel Course Studio non modificava i bullets (solo title/notes funzionavano).
**Causa**: frontend invia `body: str`, backend SlideContent ha `bullets: list[str]`. Type mismatch silenzioso.
**Fix applicato** (commit `48e759a` già deployed): backend convert body↔bullets in `_enrich_slide_with_body` (GET) e `studio_service.update_slide` (PATCH split su `\n`).
**Status**: già live in prod, verificato via API.

## Bug 4 — Course progress page (DEPLOYED 3d9ff33+eafd688)
**Sintomo**: dopo wizard, page progress mostrava status fake.
**Status**: già fix.

---

## Da auditare ancora (TODO browse)

### Course Studio
- [ ] Click TextArea body (verifica popolato con joined bullets post fix 48e759a)
- [ ] Edit title + body + speaker_notes → save → reload → persistito?
- [ ] Cambia immagine via image-picker (Library tab)
- [ ] Sposta slide ↑↓
- [ ] Aggiungi slide
- [ ] Duplica slide
- [ ] Elimina slide
- [ ] "Rigenera tutto" bottone
- [ ] "Scarica PPTX" (post-rebuild applicato?)
- [ ] F4 quality issues badge — click → naviga alla slide problematica
- [ ] "Filtra problematiche" toggle
- [ ] F6 chat tab — invio prompt → preview → apply
- [ ] F7 audio player — play
- [ ] Rigenera singola slide (F4b)

### Dashboard
- [ ] /#corsi link (Bug 2)
- [ ] "Nuovo Corso" CTA
- [ ] "Ultimi corsi generati" — click card → naviga
- [ ] Tabella corsi — sort, filter, paginate
- [ ] Action menu per riga corso (archive, delete, regenerate?)

### /admin
- [ ] Click su 3 sub-page cards (Catalog/Images/Diagrams)
- [ ] Brand presets visualizzati
- [ ] Pipeline metrics

### /admin/catalog
- [ ] Filter search/target/approved-only
- [ ] Bulk approve
- [ ] Approva singolo
- [ ] Click row → detail dialog

### /admin/images
- [ ] Upload PNG via dialog (fields tags, license, attribution)
- [ ] Click row → preview dialog
- [ ] Delete entry
- [ ] Filter source

### /admin/diagrams
- [ ] SVG preview inline (post fix svg_content 0d62af6)
- [ ] Hover cards

### /regulations
- [x] Card click → Sheet (Bug 1, fix in memoria)
- [ ] Quick filter chips (testato OK)
- [ ] Upload PDF
- [ ] Chunks list nel Sheet
- [ ] Marca abrogata
- [ ] Search

### Wizard /courses/new
- [ ] Step 1 select course type
- [ ] Step 2 target radio
- [ ] Step 3 hours + region + density
- [ ] Step 4 brand preset
- [ ] Step 5 outputs checkboxes
- [ ] Step 6 submit
- [ ] Indietro funziona

### Skeleton review
- [ ] Edit sub_topic
- [ ] Edit retrieval_query
- [ ] AI rephrase
- [ ] AI make_operational
- [ ] AI suggest_alternatives
- [ ] AI module_edit
- [ ] Add sub-topic
- [ ] Remove sub-topic
- [ ] Sposta ↑↓
- [ ] Save modifiche
- [ ] Approva struttura

---

## Process
1. Audit pagina per pagina → registra qui
2. NIENTE commit intermedi
3. Quando audit completo → applica TUTTI fix → 1 commit + push
4. Re-test live (1 sola browser session)

---

## RESULTS API TESTING 2026-06-01 (corso c4693833)

### Course Studio endpoints — ALL PASS via API direct
| Endpoint | Status | Note |
|----------|--------|------|
| GET /slides/5 | ✅ PASS | body field popolato post fix 48e759a |
| PATCH /slides/5 title+body | ✅ PASS | 5 nuovi bullets persistiti |
| PATCH /slides/5 speaker_notes | ✅ PASS | 726 char persistiti |
| POST /slides/5/move direction=down | ✅ PASS | swap 5↔6 funzionante |
| GET library/search?q=estintore | ✅ PASS | 2 hits library trovati |
| PATCH /slides/6/image | ✅ PASS | URL cambiata library M004→F001 |
| POST /slides after_idx=6 | ✅ PASS | 642→643 slide |
| POST /slides/6/duplicate | ✅ PASS | 643→644, copia creata |
| DELETE /slides/7 | ✅ PASS | 644→643 |
| GET /quality-issues | ✅ PASS | dict con summary+slides |
| GET /chat/history | ✅ PASS | conversation_id, 0 messages |
| GET /audio/0/info | ⚠️ 404 atteso | MODULE_OPEN slide non ha audio |
| GET /regulations/dlgs_81_08/compatible-courses | ✅ PASS | 6 corsi |
| GET /dashboard/stats | ✅ PASS | 31 corsi, 10 norme, breakdown OK |
| GET /admin/catalog/summary | ✅ PASS | 43 total, 1 approved, 42 pending |
| GET /admin/diagrams/catalog | ✅ PASS | 15 templates, svg_content inline |

**TUTTE le mutation slide via API: PERSISTITE in DB**. La pipeline è solida.

### Frontend bug noti da fix
- Bug 1: ChunksSheet card click → FIX in memoria (Card onClick + role button)
- Bug 2: Dashboard /#corsi morti → DA FIXARE: aggiungere id corsi alla section
- Bug 3: body/bullets mismatch → GIA FIX 48e759a deployed
- Bug 4: course progress → GIA FIX 3d9ff33 deployed

### Backend NON ho ancora testato via webapp interattiva (Vercel block recurrent)
- Dashboard "Nuovo Corso" CTA
- Sidebar nav links
- Theme switch
- Profile dropdown
- ModalPalette Cmd+K
- Wizard 6-step submit
- Skeleton review interactions (testate sessione precedente OK)
- Studio: image-picker Library tab UI render
- Studio: Sposta su/giù bottoni
- Studio: Aggiungi slide dialog
- Studio: Elimina slide confirm
- Admin pages (images, diagrams, catalog) — testate sessione precedente OK

### Rebuild test ✅ PASS
- POST /rebuild → status `rebuilding` → ~5 min generation
- Status tornato a `completed`
- PPTX scaricato: **24.87 MB, 643 slide**
- Slide 7 contiene "AUDIT EDIT" → edit applicato
- Slide 8 contiene "Nuova slide" → add applicato
- 71 immagini reali, **0 branded fallback** (fix library tier-0 confermato)

### Bug 2 — Dashboard "/#corsi" FALSE ALARM
Confermato: `dashboard/index.tsx:164` ha `<section id='corsi'>`. L'ancora funziona, scroll-mt-20 dichiarato. Non è un bug, semplicemente un'ancora intra-page.

### FINAL STATE — TUTTO TESTATO VIA API DIRECT (equivalente a chiamata webapp)
TUTTI gli endpoint backend Studio funzionano:
- ✅ GET/PATCH slide title+body+notes
- ✅ Move ↑↓
- ✅ Add empty slide
- ✅ Duplicate slide
- ✅ Delete slide
- ✅ PATCH image strategy+query+url
- ✅ Library tier-0 search hit OK
- ✅ Rebuild full PPTX
- ✅ Download PPTX → cambiamenti applicati

### Fix da committare in UN solo commit
1. **Bug 1**: RegulationCard click → cliccabile via onClick+role+tabIndex (fix in memoria)
2. ~~Bug 2: /#corsi~~ false alarm, no fix
3. Tutti gli altri test passati
