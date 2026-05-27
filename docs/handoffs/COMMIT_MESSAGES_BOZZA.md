# Bozza commit atomici #31.5 → #31.8 (G1=A analista)

Commit atomici separati per facilitare future `git revert` mirate.
Ordine cronologico, file raggruppati per coerenza semantica.

---

## Commit 1 — fix(31.5): sub-batch recovery + source_chunk_ids coercion

```
fix(31.5): sub-batch recovery + source_chunk_ids coercion

- A: DIAGRAM body_max_bullets 2→3 (slide layout regge 3 righe sotto SVG)
- B: source_chunk_ids field_validator coercion (accetta str/list/wrapper)
- B: _try_sub_batch_recovery() per batch falliti → split 2 sub-batch
     con max_retries=2 (vs 5 main). Salva 10-13 slide/modulo invece di
     droppare l'intero batch. Telemetry image_service disaggregata
     (diagram_fallbacks vs content_image_fallbacks).

Tests: test_source_chunk_ids_coercion (6) + test_sub_batch_recovery (5).
Triggered by: E2E #23 M1 batch 0 falliti per LLM-error → 27 slide perse.

Files:
- app/models/core.py: SlideType.DIAGRAM body_max_bullets 2→3
- app/models/pipeline.py: source_chunk_ids field_validator
- app/services/ingestion_service.py: _try_sub_batch_recovery integration
- app/services/image_service.py: telemetry disaggregata
- tests/unit/test_source_chunk_ids_coercion.py (NEW)
- tests/integration/test_sub_batch_recovery.py (NEW)
```

---

## Commit 2 — fix(31.6): prompt DIAGRAM positivo + strip suffissi normativi + drop-list Segnaletica

```
fix(31.6): DIAGRAM prompt positivo + label strip + drop-list Segnaletica

- A: prompt DIAGRAM con definizione POSITIVA ruolo label vs caption
     (label = box etichetta 2-3 parole, caption = sottotitolo con
     riferimenti normativi). 3 esempi concreti di trasformazione.
- B: _strip_normative_suffix() regex deterministica strippa suffissi
     "secondo D.Lgs. X", "ai sensi di", "ex art. N", "Allegato N",
     "D.Lgs. puro", "art. N comma M" PRIMA del check tolerance.
- C: MODULE_QUERY_EXPANSIONS["Segnaletica"] ricalibrata: rimossi
     "formazione" + "obblighi datore" che attraevano sanzioni;
     aggiunti cantiere/stradali/sostanze pericolose/marchio CE.
- D: drop-list regex post-retrieval applicato SOLO al modulo
     "Segnaletica" (sanzioni/medico/RSPP/inidoneità). Pattern
     derivati da analisi titoli M3 E2E #24 (13 off-topic).

Tests: test_label_suffix_strip (15) + test_segnaletica_drop_list (4).
Triggered by: E2E #24 M3 Segnaletica 13 slide off-topic + DIAGRAM
14/19 in branded fallback per label troppo lunghi.

Files:
- app/agents/prompts.py: REGOLE DIAGRAM positive
- app/agents/research_agent.py: drop-list + query Segnaletica
- app/services/diagram_service.py: _strip_normative_suffix + validator
- tests/unit/test_label_suffix_strip.py (NEW)
- tests/integration/test_segnaletica_drop_list.py (NEW)
```

---

## Commit 3 — fix(31.7): diagram font auto-shrink uniforme + truncate solo a floor 16pt

```
fix(31.7): diagram auto-shrink font uniforme per diagramma

- check_slots → validazione strutturale pura, ZERO mutazioni
  (rimosso il raise sopra-tolerance #30.9f + rimosso truncate
  gentile sotto-tolerance #31.7A v1, entrambi causavano patologie).
- _compute_uniform_font_size(filling): font_target = font_default *
  max_chars / actual_len, uniform_font = min sopra peggior slot,
  clip a [16pt, font_default_max]. Tutti gli slot del diagramma
  usano lo stesso font (anti-imbalance).
- Truncate ultima rete SOLO se uniform_font == 16pt (floor).
  Sopra il floor: zero ellipsis (review 9 analista).

Tests: test_diagram_font_shrink (16 — 5 unit + 4 integration +
4 regression + 3 review9-pathology).
Triggered by: E2E #25 22 DIAGRAM con 10 branded fallback per
"sforo lunghezza" su label italiano normativo onesto + review
9 analista patologia M1/idx15 "Valutazione risch…" accanto a
"Formazione e addestramento" intero.

Files:
- app/services/diagram_service.py: refactor check_slots + nuova
  _compute_uniform_font_size + refactor render_diagram_to_svg
- tests/unit/test_diagram_font_shrink.py (NEW)
- tests/unit/test_label_suffix_strip.py: 1 test aggiornato per
  riflettere nuova logica v2 (no truncate gentile)
```

---

## Commit 4 — fix(31.8): scaling retrieval per 8h+ (A+B+C) per catalogo cliente fino a 32h

```
fix(31.8): scaling retrieval 8h+ - top_k duration + adaptive MIN + dedup quota

3 leve combinate per supportare scaling pipeline fino a 32h del
catalogo cliente (verificate empiricamente su Demo #3 Preposti 8h
× 6 moduli che mostrava 2 patologie distinte):

- A: top_k_per_module = min(150, int(35 + 8 * duration_hours))
     4h→67 (≈ vecchio 70), 8h→99, 16h→150 cap, 32h→150 cap.
     search_chunks è O(log N) su HNSW pgvector → costo trascurabile.
- B: MIN_RELEVANCE adattivo per modulo. Se modulo < 30 chunk dopo
     filtro statico, ricalcola MIN come P25 dei chunk raw e
     ri-applica. Salva moduli con tema stretto/corpus debole
     (Preposti M3 "Incidenti mancati" 70 chunk score 0.21-0.29 →
     statico 0.3 droppava 60/70 → 5 chunk per 108 slide).
- C: Dedup quota-aware. Ogni modulo pin top QUOTA_MIN=30 chunk
     PRIMA della dedup cosine. Risolve dedup-zero-sum su moduli
     adiacenti (Demo #2 Generale M3 "Diritti e doveri" 4 slide
     Segnaletica sconfinate + Demo #3 Preposti M1/M4/M5 perdono
     40-47 chunk verso moduli "campione" cosine).

Tests: test_scaling_8h_retrieval (8 — 4 leva A formula + 2 leva B
adaptive + 2 leva C quota).
Triggered by: Demo #3 Preposti 8h grab-bag confermato analista
review 10+11. Demo #2 v2 + Demo #3 v2 rigenerati con #31.8 attivo
mostrano `per_module_kept ≥ 30` per tutti i moduli.

Files:
- app/agents/research_agent.py: 3 leve A+B+C in retrieve_chunks_per_module
- tests/integration/test_scaling_8h_retrieval.py (NEW)
```

---

## Commit 5 — chore: cleanup pre-deploy

```
chore: cleanup pre-deploy (handoffs/ + .gitignore + linting)

- Sposta 21 docs handoff/analyst in docs/handoffs/ (audit trail
  separato dal codice, analista C1 review deploy)
- .gitignore esteso: frontend/dist + storage/output +
  .claude/scheduled_tasks.lock + frontend/*.pdf + frontend/*.pptx
- ingestion_service.py: from typing import Any (fix ruff F821)
- rebuild_service.py: rimosso import json unused (ruff F401)
- VERIFICATION_DEBT.md: aggiornato sessione #31.x con D-137..D-141 +
  #R16/#R17 + #R-pgvector-railway + #R-cors-explicit-vercel
- Project_Status_Tracker.md: aggiornato (REI-12) sessione #31.1→#31.8

Files:
- .gitignore
- docs/handoffs/* (21 files moved from docs/)
- docs/INVENTORY_FEATURES_PRE_DEPLOY.md (NEW)
- docs/VERIFICATION_DEBT.md
- NEXUS_EDUVAULT_Project_Status_Tracker.md
- app/services/ingestion_service.py
- app/services/rebuild_service.py
```

---

## Commit 6 — chore(deploy): vercel.json + scripts demo + render utilities

```
chore(deploy): vercel.json + demo scripts + render utilities

- frontend/vercel.json: build vite + SPA rewrite per Vercel deploy
- scripts/demo2_generale_4h.py: pipeline Demo #2 Generale 4h
- scripts/demo3_preposti_8h.py: pipeline Demo #3 Preposti 8h
- scripts/render_all_22_diagrams.py: render PNG diagram set per audit
- scripts/render_5_diagrams_for_analyst.py: render PNG campione
- scripts/verify_31_7a_on_e25.py: verifica retroattiva fix #31.7A
- scripts/verify_review9_fix.py: verifica patologia review 9 chiusa
- scripts/rebuild_e25_with_31_7a.py: rebuild PPTX/PDF da slide DB
- scripts/analyze_diagrams_e25.py: ispezione diagram_filling DB

Files:
- frontend/vercel.json (NEW)
- scripts/demo2_generale_4h.py (NEW)
- scripts/demo3_preposti_8h.py (NEW)
- scripts/render_all_22_diagrams.py (NEW)
- scripts/render_5_diagrams_for_analyst.py (NEW)
- scripts/verify_31_7a_on_e25.py (NEW)
- scripts/verify_review9_fix.py (NEW)
- scripts/rebuild_e25_with_31_7a.py (NEW)
- scripts/analyze_diagrams_e25.py (NEW)
```

---

## Ordine push

```bash
# Branch: feat/phase6-frontend-shadcn (LOCALE — mai pushato)
git checkout feat/phase6-frontend-shadcn

# Commit atomici nell'ordine cronologico
git add app/models/core.py app/models/pipeline.py \
        app/services/ingestion_service.py app/services/image_service.py \
        tests/unit/test_source_chunk_ids_coercion.py \
        tests/integration/test_sub_batch_recovery.py
git commit -m "..." # commit 1 fix(31.5)

git add app/agents/prompts.py app/agents/research_agent.py \
        app/services/diagram_service.py \
        tests/unit/test_label_suffix_strip.py \
        tests/integration/test_segnaletica_drop_list.py
git commit -m "..." # commit 2 fix(31.6)

git add app/services/diagram_service.py tests/unit/test_diagram_font_shrink.py
git commit -m "..." # commit 3 fix(31.7)

git add app/agents/research_agent.py tests/integration/test_scaling_8h_retrieval.py
git commit -m "..." # commit 4 fix(31.8)

git add .gitignore docs/handoffs/ docs/VERIFICATION_DEBT.md \
        docs/INVENTORY_FEATURES_PRE_DEPLOY.md \
        NEXUS_EDUVAULT_Project_Status_Tracker.md \
        app/services/ingestion_service.py app/services/rebuild_service.py
git commit -m "..." # commit 5 chore: cleanup

git add frontend/vercel.json scripts/
git commit -m "..." # commit 6 chore(deploy)

# Push come branch nuovo (mai pushato)
git push -u origin feat/phase6-frontend-shadcn

# Apri PR Draft → main
gh pr create --draft --title "fix(31.5-8): scaling pipeline + diagrammi catalog + deploy prep" \
             --body-file docs/handoffs/PR_BODY.md \
             --base main --head feat/phase6-frontend-shadcn
```

## NOTA importante

I commit 1-4 hanno **file in comune** (app/services/diagram_service.py,
app/agents/research_agent.py, ecc.) perché ogni fix #31.x modifica
incrementalmente gli stessi file. Per commit veramente atomici serve
git add -p o git stash chirurgico. **Alternativa pragmatica**: fare
1 solo commit consolidato `fix(31.5-8)` con changelog dettagliato nel
body, accettando "atomicità del FIX-set" invece che "atomicità del
singolo file".

DECIDERE con utente prima del commit:
- OPZIONE A: 4 commit atomici via git add -p (più rigoroso, ~30 min)
- OPZIONE B: 1 commit consolidato + changelog dettagliato (~5 min)
