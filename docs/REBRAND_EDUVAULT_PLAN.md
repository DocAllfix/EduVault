# Piano Rebrand: rimozione totale C.F.P. Montessori → solo "EduVault"

**Data:** 2026-07-11
**Obiettivo:** eliminare ogni riferimento a C.F.P. Montessori (logo, nome, footer, credenziali, metadati) da frontend, backend, template PPTX, database e artefatti generati, lasciando solo il brand "EduVault". **Vincolo assoluto: nessun corso esistente va perso; nessuna funzionalità va rotta.**

---

## ⚠️ SCOPERTA CRITICA (prerequisito bloccante)

**La produzione è COMPLETAMENTE GIÙ da oltre un mese:**
- Railway: tutti i deployment di `EduVault` (backend) e `pgvector` (DB) risultano `REMOVED`; l'ultimo risale al **2026-06-02**.
- Backend: entrambi i domini (`eduvault-production-82c1` / `-5c73.up.railway.app`) rispondono `404 Application not found` (edge Railway = nessun deployment attivo).
- DB: il TCP proxy (`zephyr.proxy.rlwy.net:11820`) accetta TCP ma resetta la connessione al protocollo Postgres (container non in esecuzione). Credenziali e proxy config risultano invariati nelle variabili Railway → non è un problema di password.
- Frontend Vercel: risponde **500**.

Causa più probabile: crediti/piano Railway esauriti o servizi rimossi dal piano. **I volumi Railway sopravvivono ai deployment rimossi**, quindi i dati (corsi, KB, storage) dovrebbero essere recuperabili al redeploy — da verificare come primo check della FASE 0.

Le fasi 1–3 (codice locale) NON dipendono dal ripristino. Le fasi 4–6 (DB + rebuild + E2E) SÌ.

---

## Inventario completo dei riferimenti CFP (analisi + contro-analisi)

### A. Frontend (visibile all'utente)
| # | Dove | Cosa |
|---|------|------|
| A1 | `frontend/index.html:22-43` | Title + 6 meta tag "Cfp EduVault — C.F.P. Montessori" |
| A2 | `frontend/public/brand/` | `logo.png`, `logo-transparent.png`, `logo-mark.png`, `favicon-*.png`, `favicon.ico` = logo CFP Montessori (verificato visivamente) |
| A3 | `frontend/src/components/layout/app-title.tsx:30-38` | `<img alt='C.F.P. Montessori'>` + testi "Cfp EduVault" / "C.F.P. Montessori" |
| A4 | `frontend/src/features/auth/auth-layout.tsx:28-41` | Logo CFP sopra il form di login (2 `<img>`) |
| A5 | `frontend/src/components/layout/data/sidebar-data.ts:33-35` | `name: 'Cfp EduVault'`, `plan: 'C.F.P. Montessori'` |
| A6 | `frontend/src/features/auth/sign-in/index.tsx:29` | `PAGE_TITLE = 'Cfp EduVault — Accesso'` |
| A7 | `frontend/src/features/auth/sign-in/components/user-auth-form.tsx:125` | placeholder `nome@cfpmontessori.it` |
| A8 | `frontend/src/features/course-studio/components/slide-viewer.tsx:339` | Footer mock "Formazione Globale — C.F.P. Montessori" |
| A9 | `frontend/src/lib/onboarding/driver-config.ts` | Testi/commenti tour onboarding CFP-branded (verificare stringhe visibili) |
| A10 | `frontend/src/routes/_authenticated/dashboard.tsx` + ~15 file | "Cfp EduVault" in commenti/docstring (non visibili — bassa priorità) |
| A11 | `frontend/src/styles/theme.css` | Solo COMMENTI + colori brand (vedi "Decisione palette") |

### B. Backend / builder (Railway)
| # | Dove | Cosa |
|---|------|------|
| B1 | `assets/templates/nexus_master_v4_patched.pptx` | **`ppt/media/cfp_logo.jpeg`** (ereditato dai layout → su OGNI slide generata); footer "C.F.P. Montessori — Formazione Globale" in `slideLayout10` (cover); `docProps` "CFP Montessori — Nexus Master v4"; theme name "CFP" (invisibile) |
| B2 | `assets/brand/cfp_montessori_logo.jpeg` | File sorgente logo |
| B3 | `deploy/railway-backend.env:21` + variabile Railway | `ADMIN_BOOTSTRAP_EMAIL=admin@cfp-montessori.it` |
| B4 | `assets/seeds/demos_manifest.json` | `attribution: "CFP Montessori demo review-13 / ..."` → seeda `image_library.attribution`, **visibile nell'image picker** |
| B5 | `app/services/image_service.py` placeholder brandizzato | Solo colori rosa/verde + glifo — **nessun testo CFP** (ok, dipende solo dalla decisione palette) |
| B6 | `app/templates/dispensa.html` (PDF) | **Pulito** — nessun logo/nome CFP nel PDF |

### C. Database produzione (verifica bloccata: DB giù — da confermare in FASE 4)
| # | Dove | Cosa |
|---|------|------|
| C1 | `users` | `admin@cfp-montessori.it` (admin dev); `cfpadmin@eduvault.it` (cliente — contiene "cfp") |
| C2 | `brand_presets` (id `28dc416b-…`) | `name = 'C.F.P. Montessori'` — mostrato nel wizard step 4 e step 6 |
| C3 | `image_library.attribution` | "CFP Montessori demo …" (da B4) |
| C4 | `courses.slide_contents_json` | ATTESO pulito (il CFP visibile sulle slide viene dal TEMPLATE, non dai testi; prompt degli agenti non menzionano CFP) — **da verificare con query prima del rebuild** |
| C5 | Volume storage: PPTX/PDF generati | Contengono logo+footer CFP "cotti" dentro → si risolvono col REBUILD (non serve toccare i file a mano) |

### D. Config/docs operativi
| # | Dove | Cosa |
|---|------|------|
| D1 | `CLAUDE.md` REI-1/REI-11 | Istruzioni "applica branding C.F.P. Montessori" — da aggiornare a EduVault |
| D2 | Tracker, VERIFICATION_DEBT, handoffs, script storici (`build_master_v4.py`, `rebrand_slidesgo_to_cfp.py`…) | **NON toccare**: storia del progetto, non superfici prodotto |

### Contro-analisi (cosa NON contiene CFP — verificato)
- PDF dispensa (template Jinja2): pulito.
- Placeholder immagini branded: solo colori, nessun testo.
- Prompt agenti research/content: nessuna menzione (solo 1 commento).
- Note speaker / audio TTS: i prompt non iniettano il nome → l'audio NON pronuncia mai "Montessori" (conferma finale con query C4). Conseguenza: **rebuild con `skip_audio=true` è sufficiente** (15-30s/corso invece di 60-180s).
- Nessun `brand_preset_id` hardcoded nel frontend (il wizard usa `is_default` dall'API).

---

## Decisione palette — ✅ DECISA 2026-07-11
L'umano ha confermato: **tenere i colori attuali** (rosa `#C82E6E` + verde `#769E2E`). Nessun riferimento testuale nei colori; eventuale nuova palette = task separato futuro.

## Nuove credenziali — ✅ DECISE 2026-07-11
- `admin@cfp-montessori.it` → `admin@eduvault.it` (stessa password, UPDATE email = UUID/FK preservati)
- `cfpadmin@eduvault.it` → `cliente@eduvault.it` (stessa password)

---

## FASI (ognuna con verifica di uscita)

### FASE 0 — Ripristino produzione Railway (PREREQUISITO, richiede azione umana)
1. L'umano verifica sul dashboard Railway il motivo dei deployment REMOVED (crediti/piano) e riattiva.
2. Redeploy `pgvector`, poi `EduVault`.
3. **Verifica:** `/health` → 200; query `SELECT COUNT(*) FROM courses` = numero atteso; login funzionante; Vercel torna a rispondere.
4. **Gate:** se il volume dati fosse perso → STOP, si passa a piano di recovery (dump locali `assets/seeds`, script `insert_3_demos_railway.py`), niente rebrand finché i dati non sono al sicuro.

### FASE 1 — Nuova identità visiva EduVault (locale, nessun rischio)
1. Creare wordmark "EduVault" (testo Montserrat + monogramma semplice) → generare `logo.png`, `logo-transparent.png`, `logo-mark.png`, set favicon completo in `frontend/public/brand/`.
2. **Non cancellare** i vecchi file CFP: spostarli in `assets/brand/_retired_cfp/` (rollback facile).
3. **Verifica:** `pnpm build` verde; controllo visivo login + sidebar in dev.

### FASE 2 — Frontend: testi e riferimenti (locale)
1. A1, A3–A9: sostituire "Cfp EduVault"→"EduVault", rimuovere "C.F.P. Montessori" da title/meta/alt/plan/footer mock/placeholder email (`nome@eduvault.it`).
2. A10 (commenti): sweep leggero solo dove il commento è fuorviante; niente churn di massa.
3. **Verifica:** `rg -i "montessori|cfpmontessori" frontend/src frontend/index.html` → 0 match in stringhe UI; `pnpm build` verde; screenshot login/dashboard/studio.

### FASE 3 — Template PPTX EduVault (locale, chirurgico)
1. Script `scripts/rebrand_master_to_eduvault.py`: apre `nexus_master_v4_patched.pptx` come zip e:
   - sostituisce/rimuove `ppt/media/cfp_logo.jpeg` (opzione: wordmark EduVault stesse dimensioni, così i layout non si muovono);
   - sostituisce il footer testo in `slideLayout10` → "EduVault";
   - aggiorna `docProps` (title/author).
   - **NON** tocca shape name/indici layout (vincolo: `slide_builder_v2.py` mappa i layout per indice — un template ricostruito da zero romperebbe tutto).
2. Backup automatico `nexus_master_v4_patched.pptx.pre_eduvault.bak` prima della modifica.
3. **Verifica:** script di ispezione → 0 occorrenze CFP nel PPTX; build sintetico locale (`scripts/synth_build_test.py` o equivalente) → PPTX generato, render 2-3 slide via LibreOffice e confronto visivo (identiche salvo logo/footer).

### FASE 4 — Backend config + DB (richiede FASE 0)
1. Railway: `ADMIN_BOOTSTRAP_EMAIL` → nuova email; allineare `deploy/railway-backend.env`.
2. Query read-only preliminare: `slide_contents_json ILIKE '%montessori%'` su tutti i corsi (conferma C4). Se >0 hit → analizzare campo per campo prima di procedere.
3. UPDATE (tutti reversibili, valori precedenti salvati in un file di log prima di ogni UPDATE):
   - `users.email` (2 righe — FK intatte, corsi preservati);
   - `brand_presets.name/footer_template` → 'EduVault';
   - `image_library.attribution` → replace 'CFP Montessori' → 'EduVault';
   - allineare `assets/seeds/demos_manifest.json`.
4. Deploy backend con template FASE 3 (il template viaggia nell'immagine Docker).
5. **Verifica:** login con nuove email OK e vecchie rifiutate; wizard step 4 mostra preset "EduVault"; image picker mostra attribution nuova.

### FASE 5 — Rebuild corsi esistenti (richiede FASI 3+4)
1. Per ogni corso `completed`: `POST /api/courses/{id}/rebuild?skip_audio=true` — **sequenziale** (Semaphore(1), REI-3), attesa completamento tra un corso e l'altro.
2. `skip_audio=true` giustificato dalla verifica C4 (audio senza riferimenti CFP) → audio esistente resta valido.
3. **Verifica per ogni corso:** status torna `completed`; download PPTX → unzip + grep CFP = 0 occorrenze; PDF invariato nei contenuti; audio ancora presente (`audio_manifest_path` non NULL); preview Course Studio renderizza.

### FASE 6 — E2E finale + governance
1. Sweep finale: `rg --no-ignore -i "montessori"` sulle superfici prodotto (frontend src, app/, assets/templates attivo, seeds) → 0.
2. Test browser completo: login → dashboard → apri corso → studio → download artefatti → catalogo.
3. `CLAUDE.md` REI-1/REI-11 aggiornati (branding EduVault); VERIFICATION_DEBT §2 nuova riga Dnn (REI-17) PRIMA del Tracker; Tracker aggiornato (REI-12).
4. Commit atomici per fase (niente `git add -A`; script con credenziali restano gitignored).

## Rollback
- Template: ripristino `.bak`.
- Loghi frontend: ripristino da `assets/brand/_retired_cfp/`.
- DB: UPDATE inversi dal log valori-precedenti.
- Corsi: il rebuild è idempotente — un secondo rebuild col template vecchio riporta gli artefatti allo stato precedente. `slide_contents_json` non viene MAI toccato.

## Discrepanze segnalate (REI-16)
- **BP/CLAUDE.md REI-1**: prescrivono branding C.F.P. Montessori sul frontend. Il prompt umano chiede la rimozione totale → prompt prevale; CLAUDE.md verrà aggiornato in FASE 6 per non lasciare istruzioni contraddittorie.
- **Credenziali**: il cambio email invalida i login comunicati alla cliente (Michela) — se il suo account resta attivo, va avvisata delle nuove credenziali.
