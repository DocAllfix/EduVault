# Gap da definire PRIMA di FASE 7 (post test mock reali)

> **Stato**: documento aperto, **NON IMPLEMENTARE** finché tutti i test mock non sono
> stati ri-eseguiti come live (vedi piano `~/.claude/plans/vast-hopping-sketch.md`).
> Ogni voce è un open question che richiede una decisione esplicita dell'utente.

## 1. Anti-hallucination — come garantiamo che le slide citino chunk reali?

**Stato attuale**: il prompt system (`app/agents/prompts.py:19-61`) instructa l'LLM:
*"Ogni affermazione fattuale DEVE essere ancorata a un chunk normativo fornito. Non
inventare MAI informazioni normative"*. Lo `source_chunk_ids` viene registrato nel
`SlideContent` ma **NON c'è validazione post-LLM** che verifichi che i chunk_id citati
esistano davvero tra quelli forniti.

**Gap aperto**: serve guardia hard? Opzioni:
- (a) Lasciare instruction-only (oggi) + monitoraggio statistico su `audit_log`
- (b) Validatore post-LLM: per ogni slide, verifica `set(source_chunk_ids) ⊆ set(chunk_id forniti)`. Se viola → retry con prompt corrective. Costo: +1 chiamata LLM ~10% delle volte.
- (c) Validatore + scarto: se viola dopo retry → slide rimossa dal modulo. Rischio: corso più corto del previsto.
- (d) Validatore semantico: verifica anche che il `body` della slide contenga una sostringa significativa del chunk body citato.

**Decisione**: TBD post test reali.

## 2. Slide ogni 30 secondi — confermato o configurabile?

**Stato attuale**: `PacingEngine.SECONDS_PER_SLIDE = 30` hardcoded
(`app/services/pacing_engine.py`, GAP-1 v2.0).

**Conseguenze**:
- 1h corso = 120 slide
- 8h corso = 960 slide
- 16h corso = 1920 slide
- Costo Anthropic Sonnet 4.6 per 960 slide ≈ $2-5

**Gap aperto**:
- (a) Confermare 30s come default ma esporlo nel wizard? (campo "slide_per_minute" o "rhythm")
- (b) Variare per `slide_density`? Oggi `leggera/standard/intensiva` moltiplica solo il
  count ma non i secondi. Mockup proposto: leggera 45s/slide, standard 30s, intensiva 20s.
- (c) Mantenere 30s fisso perché è il commitment commerciale al cliente.

**Decisione**: TBD post test reali. Probabile (c) per coerenza con vincolo commerciale,
ma verificare con cliente.

## 3. Lunghezza body slide — quante parole/caratteri?

**Stato attuale**: BP §05 dice "body validator §04.4 mantiene fino a 90 parole". Il
validator Pydantic in `app/models/pipeline.py` ha un check?

**Gap aperto** da verificare in fase test reali:
- Confermare limite 90 parole vs caratteri (es. 600 char)
- Differenziare per SlideType? CONTENT_TEXT 90 parole, CASE_STUDY 120, RECAP 60, QUIZ
  question 30 + 4 opzioni × 15
- Cosa fa il sistema se LLM eccede? Trunca? Re-prompt? Accetta?

**Decisione**: TBD. Misurare empiricamente media output Sonnet 4.6 su 1 modulo reale.

## 4. Generazione tempo: chiamate sequenziali o parallele?

**Stato attuale**: `content_agent._generate_module()` itera moduli in sequenza
(`for module in pacing.modules[start_index:]`). Per un corso 4h da 12 moduli = **12
chiamate LLM sequenziali**. Latenza Anthropic ~10-30s per chiamata → totale 2-6 minuti
solo per il content. Più research, image search, build PPTX/PDF/audio.

**Gap critico — pipeline lenta su corsi lunghi**:
- Corso 4h: ~5-15 minuti totali (documentato BP §08.8)
- Corso 16h: stima ~20-45 minuti (non testato live)

**Opzioni**:
- (a) **Mantenere sequenziale** (oggi): semplice, deterministica, no race condition,
  rispetta `Semaphore(1)` REI-3. Costo: lento sui corsi lunghi.
- (b) **Parallelizzare moduli con `asyncio.gather`**: 12 chiamate Anthropic concorrenti
  → tempo totale ≈ chiamata più lenta (15-30s). **MA**: viola coerenza narrativa
  (`previous_summary` non disponibile per moduli che girano in parallelo). Soluzione: 2
  fasi — gather di metà moduli, riepilogo, gather dell'altra metà.
- (c) **Streaming per modulo**: invia progress al frontend ogni modulo completato (oggi
  già lo fa). Non riduce tempo totale, ma migliora UX percepita.
- (d) **Batch API Anthropic**: 50% sconto, ma latenza fino a 24h → inutile per UX live.

**Vincoli architetturali**:
- `Semaphore(1)` è sui JOB (1 corso intero alla volta), NON sulle chiamate LLM
  interne. Quindi parallelizzare i moduli **dentro** un job è OK.
- python-pptx non thread-safe (REI-3) → ma è POST-pipeline, non in content_agent. Safe.

**Decisione**: TBD. Probabile (b) con 2 fasi per coerenza. Misurare tempo reale post
cluster D per capire se è davvero un problema.

## 5. Decisione CONTENT_IMAGE — query LLM-generated, search Pexels, fallback

**Stato attuale**: GAP-1/2/3 documentati in sezione 3.D del piano. Da implementare in
**Cluster F** (parte del piano test reali).

**Open question da definire prima**:
- L'LLM genera `query` italiano o inglese? Pexels indicizza meglio inglese
  ("safety helmet" vs "casco protezione"). Tradurre via dictionary in `image_service`?
- Quante query candidate provare per slide? 1 (la prima Pexels) o 3 (mostriamo all'utente
  in Course Studio)?
- Cache TTL: se la stessa query produce risultato 6 mesi dopo, refresh o stay?
- Attribution: Pexels non lo richiede ma è cortesia. Includere photographer name nella
  caption della slide? Footer PDF?

## 6. Decisione DIAGRAM — riabilitare quando?

**Stato attuale**: distribution 0% (FIX-8). Solo emissione spontanea LLM.

**Gap aperto**:
- Riabilitare a 0.05 (5% delle slide) post-cluster C live test → osservare output
- Test cliente: 20 corsi reali → quanti SVG sono utili vs brutti?
- Soglia "utile": leggibile a 1920×1080, no overlap, frecce sensate, max 10 elementi

**Decisione**: TBD post FASE 7 deploy con primi corsi reali.

## 7. Voce TTS — quale default? Quante voci?

**Stato attuale**: `it-IT-DiegoNeural` default in `audio_service`. Edge-TTS supporta
~10 voci italiane.

**Gap aperto**:
- Voce singola o configurabile per corso? (es. corso "Primo Soccorso" voce femminile
  Isabella, corso "Cantieri" voce maschile Diego)
- Velocità + tono regolabili? Edge-TTS supporta SSML rate/pitch
- Pause tra paragrafi: oggi inferite. Migliorabile con SSML `<break time="500ms"/>`
- L'utente in Course Studio può cambiare voce di una slide o di tutto il corso?

**Decisione**: TBD. Probabilmente fisso `Diego` per v1.0, configurable in FASE 8.

## 8. Modularizzazione — titoli moduli fallback "Modulo N"

**Stato attuale**: `COURSE_CATALOG.default_modules` ha 4-6 titoli per corso, ma
`PacingEngine` calcola fino a 24 moduli per corso 8h → 18-20 moduli senza titolo
descrittivo ("Modulo 7", "Modulo 8", …).

**Gap aperto**:
- Espandere `default_modules` cliente con tutti i 60 corsi reali corsi8108? Lavoro
  domain-expert, non delegabile a LLM.
- O: chiedere all'LLM di proporre titoli moduli aggiuntivi basati sui chunk RAG? Pro
  flexible, contro variabilità tra corsi.

**Decisione**: TBD post-cluster D. Probabile mix: catalog con titoli base + LLM completion
per i restanti.

## 9. Slide content per modulo — l'LLM riceve TUTTO o solo il modulo corrente?

**Stato attuale**: l'LLM vede **solo il proprio modulo** + riepilogo prime 5 slide
moduli precedenti.

**Gap aperto**:
- Funziona per coerenza locale (modulo è autocontenuto) ma può causare ripetizioni
  cross-modulo (es. slide "Concetti di rischio" appare in modulo 1 e poi un concetto
  simile in modulo 3 perché LLM non vede tutte le slide precedenti)
- Soluzione: passare anche un **outline** (titoli di tutte le slide precedenti) come
  ulteriore contesto. Costo: +500-2000 token per chiamata = +$0.01-0.05 per modulo.

**Decisione**: TBD. Misurare empiricamente in cluster C/D quante ripetizioni emergono
su corso 4h reale.

## 10. Edit/Regenerate Course Studio — cluster G

**Stato attuale**: piano cluster G documentato (sezione 2.G del piano).

**Gap da definire prima di partire cluster G**:
- **Granularità undo**: storico modifiche slide? Solo last-write-wins?
- **Concurrent edit**: 2 admin che editano lo stesso corso? Optimistic lock con
  `slide_contents_json.updated_at` o just last-write-wins (single tenant CFP, basso
  rischio)?
- **Audit trail**: ogni PATCH/regenerate finisce in `audit_log` con `actor, slide_idx,
  diff`?
- **Cosa succede al fingerprint normativo dopo edit?** Resta fissato al primo build o
  si aggiorna? Importante per L2 certification.
- **Rebuild costo**: ogni `POST /rebuild` ri-paga audio TTS (~$0 ma 10 min) e immagini
  Pexels (cache hit). Avviso utente con stima tempo?

**Decisione**: TBD. Definire UX prima di scrivere endpoint.

---

## 11. SlideBuilder vs template Claude Design — compatibility gap (NEW — scoperto Cluster E.2)

**Stato attuale**: il template `nexus_master.pptx` esportato da Claude Design (sez. 3.B
opzione 2) contiene 8 `slide_layouts` con shape posizionate **come AUTO_SHAPE**, NON
come PowerPoint **placeholder**. Tutti gli shape hanno `name` convenzionale (`Text 0`,
`Text 2`, `Image 0`, ecc.) ma `slide.placeholders` ritorna **lista vuota** su ogni
layout.

**Bug rivelato**: `SlideBuilder._find_placeholder_by_type` cerca per
`slide.placeholders` → ritorna None su ogni layout → `_populate_title_and_body` e
`_populate_quiz` **non scrivono nulla**. Risultato pratico: il PPTX finale ha il design
originale del template (header, footer, logo, brand) ma il **contenuto LLM-generated
NON viene scritto** — al suo posto resta il testo placeholder del template
("Formazione Generale dei Lavoratori", "Art. 18 D.Lgs 81/08", ecc.).

**Opzioni di fix** (TBD):

- **(a) Estensione SlideBuilder con `shape_map`** (~50 LOC chirurgico):
  Aggiungere parametro opzionale `shape_map: dict[SlideType, dict[str, str]]` che
  mappa `(slide_type, semantic_role) → shape.name`. Esempio:
  ```python
  SHAPE_MAP_NEXUS = {
      SlideType.TITLE: {"title": "Text 1", "subtitle": "Text 2"},
      SlideType.CONTENT_TEXT: {"title": "Text 0", "body": "Text 2",
                                "footer_ref": "Text 3", "page_num": "Text 4"},
      SlideType.CONTENT_IMAGE: {"title": "Text 0", "body": "Text 2",
                                "picture": "Text 4"},
      ...
  }
  ```
  `_find_placeholder_by_type` viene esteso: prima cerca placeholder PowerPoint (compat
  test esistenti); se None e `shape_map` ha entry per quel ruolo, cerca shape per nome.

- **(b) Rifare template aggiungendo placeholder PowerPoint** (lavoro manuale in
  PowerPoint, ~2h umane): aprire `nexus_master.pptx`, per ogni layout convertire le
  TextBox in placeholder veri. Rischio: design Claude Design può alterarsi durante
  la conversione manuale.

- **(c) Strategia clone-and-fill via XML** (~100 LOC): in `SlideBuilder.build`, invece
  di `prs.slides.add_slide(layout)`, fare `deepcopy` della slide-template (servono le
  8 slide originali Claude Design come riferimento, oggi cancellate dal nostro
  conversion script). Pro: design garantito identico. Contro: serve mantenere sia
  layouts che template-slides nello stesso file.

**Decisione tecnica**: **(a) shape_map** è la più chirurgica e mantiene backwards
compat con i test mock. Costo: ~1 ora mia + retest 22 test SlideBuilder esistenti.

**Quando agire**: post-cluster D verde (pipeline E2E completa). Il fix è prerequisito
per generare un PPTX brandizzato cliente realmente utilizzabile — senza, ogni corso
generato avrà testo placeholder Claude Design statico.

**Test E.2 documentano questo gap**: `test_e03` e `test_e04` falliscono
intenzionalmente; quando il fix è applicato vanno aggiornati per asserire la
sostituzione effettiva del testo.

---

## Checklist consolidamento (da rivedere insieme post test reali)

- [ ] 1. Anti-hallucination: solo prompt vs validator hard
- [ ] 2. Slide / 30s fisso vs configurable
- [ ] 3. Lunghezza body 90 parole vs altro per SlideType
- [ ] 4. Sequenziale vs parallelo (gather moduli con 2 fasi)
- [ ] 5. CONTENT_IMAGE: query lingua, candidati, cache, attribution
- [ ] 6. DIAGRAM: riabilitazione + soglia qualità
- [ ] 7. Voce TTS: default, configurable, SSML
- [ ] 8. Titoli moduli fallback: expand catalog vs LLM completion
- [ ] 9. Contesto LLM: outline cross-modulo per anti-ripetizione
- [ ] 10. Course Studio: undo, concurrent edit, audit, fingerprint, rebuild cost UX
- [ ] **11. SlideBuilder vs Claude Design template: shape_map fix (opzione a) prima di FASE 7** [NEW]

---

**Riprendere questo documento DOPO**:
1. Tutti i cluster A→F testati live e verdi
2. Aggiornamento finale di `VERIFICATION_DEBT.md`
3. Audit risultati con metriche reali (tempo pipeline, costo, qualità output)
