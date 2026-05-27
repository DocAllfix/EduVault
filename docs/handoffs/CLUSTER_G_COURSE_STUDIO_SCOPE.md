# Cluster G — Course Studio in-app (post test live A→F)

> **Stato**: SCOPE READY, da implementare dopo che A→F sono tutti verdi.
> Il piano `vast-hopping-sketch.md` sezione 2.G contiene il contesto.
> Questo file è il dettaglio operativo step-by-step per partire spediti.

## Obiettivo

Trasformare l'app da "genero PPTX, scarichi, apri in PowerPoint" a "genero
PPTX, lo visualizzo slide-per-slide in-app, modifico testo/immagini, chiedo
al sistema di rigenerare singola slide o intero modulo via LLM, riascolto
l'audio, vedo i quiz come domande interattive".

## Backend — 9 nuovi endpoint (`app/api/routes/courses.py`)

| Endpoint | Method | Funzione | Costo per chiamata |
|---|---|---|---|
| `/api/courses/{id}/slides` | GET | `slide_contents_json` array + paginazione | 1 SELECT |
| `/api/courses/{id}/slides/{idx}` | GET | Singola slide + audio MP3 URL | 1 SELECT |
| `/api/courses/{id}/slides/{idx}` | PATCH | Aggiorna title/body/notes/normative_ref/image_query via `jsonb_set`. Se text cambia → re-gen audio MP3 per quella slide. Mark course `status='draft'`. | 1 UPDATE + opzionale 1 TTS |
| `/api/courses/{id}/slides/{idx}/regenerate` | POST | Body `{instruction}` → LLM regenera la slide preservando `source_chunk_ids` | 1 chiamata Sonnet 4.6 (~$0.01) |
| `/api/courses/{id}/modules/{mod_idx}/regenerate` | POST | LLM regenera tutto un modulo. Confirm UI obbligatorio. | 1 chiamata Sonnet 4.6 grande (~$0.05) |
| `/api/courses/{id}/rebuild` | POST | Trigger `ProductionBuilder.build()` con `slide_contents_json` corrente → sovrascrivi PPTX/PDF/Audio. Async (Semaphore(1)). | 5-15 min, $0.10 |
| `/api/courses/{id}/audio/{slide_idx}` | GET | Stream singolo MP3 (per `<audio>` tag in-app) | 1 file serve |
| `/api/courses/{id}/slides/{idx}/image/search` | POST | Body `{query}` → cerca Pexels → ritorna 4-6 thumbnail candidate | 1 chiamata Pexels |
| `/api/courses/{id}/slides/{idx}/image` | PATCH | Body `{image_url}` → setta `slide.image.query_url` + invalida cache | 1 UPDATE |

**Auth gating**: tutti admin/reviewer (operatore visualizza solo).

**Stima backend**: ~250 LOC + 8-10 test live (admin auth, ownership, JSONB update, LLM call, audio regen).

## Frontend — nuova pagina Course Studio (`/courses/:id/studio`)

| Componente | Path | Funzione |
|---|---|---|
| `SlideViewer` | `features/course-studio/components/slide-viewer.tsx` | Render HTML che imita layout PPTX (8 SlideType). Navigazione prev/next + jump-to-slide (Ctrl+G) |
| `SlideEditor` | `.../slide-editor.tsx` | Form react-hook-form: title, body, speaker_notes, normative_ref, image_query. "Salva" → PATCH backend |
| `AudioPlayer` | `.../audio-player.tsx` | `<audio controls src="/api/courses/:id/audio/:idx" />` sync con slide corrente |
| `RegenerateDialog` | `.../regenerate-dialog.tsx` | Modal con textarea "Istruzione" + 2 button "Solo questa slide" / "Tutto il modulo" |
| `ImagePicker` | `.../image-picker.tsx` | Modal grid 2×3 thumbnail Pexels post POST `/image/search`. Click → PATCH image_url |
| `RebuildBanner` | `.../rebuild-banner.tsx` | "Hai modifiche non rigenerate. PPTX/PDF scaduti." + button "Rigenera tutto (5-10 min)" → POST `/rebuild` |
| `QuizInteractive` | `.../quiz-interactive.tsx` | Per slide QUIZ, mostra 4 radio + button "Verifica" → mostra giusto/sbagliato. Display only (no save) |
| `studio/index.tsx` | `features/course-studio/index.tsx` | Page shell + react-query hooks per tutti i 9 endpoint |

**Routing**: aggiungere `routes/_authenticated/courses/$id_/studio.tsx`.

**Stima frontend**: ~600 LOC totali (1 pagina + 7 componenti + 5-6 hooks react-query).

## Test live Cluster G

| Test | File | Verifica |
|---|---|---|
| `test_g01_get_slides_returns_paginated_array` | `tests/live/test_cluster_g_studio.py` | Backend ritorna array + paginazione |
| `test_g02_patch_slide_updates_only_specified_jsonb_fields` | id. | `jsonb_set` non sovrascrive l'intero JSON |
| `test_g03_patch_slide_regenerates_audio_only_when_text_changed` | id. | No regen audio se solo `title` cambia |
| `test_g04_regenerate_slide_keeps_source_chunk_ids` | id. | LLM regen mantiene provenance |
| `test_g05_regenerate_module_costs_under_budget` | id. | Budget guard ($0.10 max per modulo test) |
| `test_g06_audio_streaming_single_mp3` | id. | Stream singolo MP3 funziona, MIME audio/mpeg |
| `test_g07_image_search_returns_pexels_candidates` | id. | Pexels integration, >= 4 risultati |
| `test_g08_rebuild_triggers_production_builder_with_current_jsonb` | id. | Full PPTX/PDF re-gen post-edit |

## Sequenza implementazione (4 sub-fasi)

### G.1 — Backend endpoints (1-2 prompt medi)
1. Aggiungi `app/api/routes/courses.py` 9 nuovi endpoint
2. Add `app/services/slide_editor_service.py` per `regenerate_slide()` + `regenerate_module()`
3. Test live G01-G05

### G.2 — Frontend Studio shell (1 prompt medio)
1. Crea route `/courses/:id/studio`
2. Componente `SlideViewer` base (no edit, solo display)
3. `useQuery` per `/slides` + `/slides/:idx`

### G.3 — Edit + Regenerate (1 prompt grande)
1. `SlideEditor` form + PATCH wire
2. `RegenerateDialog` + POST wire
3. `RebuildBanner` + invalidate queries
4. Test live G02-G05 funzionali via UI

### G.4 — Audio + Image picker (1 prompt medio)
1. `AudioPlayer` + endpoint `/audio/:idx`
2. `ImagePicker` + endpoint `/image/search` + `/image` PATCH
3. `QuizInteractive` display
4. Test live G06-G08

## Decisioni TBD (linked a `GAPS_TO_DEFINE_BEFORE_PHASE7.md` §10)

- Granularità undo: storico modifiche slide o just last-write-wins?
- Concurrent edit: 2 admin contemporanei → optimistic lock o LWW?
- Audit trail: ogni PATCH/regenerate in `audit_log`?
- Cosa succede a `normative_fingerprint` dopo edit? Resta fissato o si aggiorna?
- Rebuild costo UX: avviso utente con stima tempo + costo?

**Tutte queste decisioni vanno prese PRIMA di partire con G.1** — non implementare a casaccio.

## Costo totale stimato Cluster G

- Mio tempo: 6-8 ore (3-4 prompt FASE 7 medio-grandi)
- LLM budget per test live: ~$1-2 (regenerate calls)
- Pexels budget: $0 (free tier)

## Prerequisiti per partire

- [ ] Cluster A verde ✅ (DB live)
- [ ] Cluster B verde ✅ (Voyage live)
- [ ] Cluster C verde ✅ (Anthropic live)
- [ ] Cluster D verde ⏳ (pipeline E2E in corso ingestion D.Lgs 81)
- [ ] Cluster E.2 verde + fix shape_map (vedi GAP §11)
- [ ] Cluster F verde (image pipeline + PEXELS_API_KEY)
- [ ] Decisioni TBD prese (§10 GAPS_TO_DEFINE)
