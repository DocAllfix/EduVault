# Analisi scaling pipeline: 4h → 8h → 32h

**Data**: 2026-05-27, post Demo #3 Preposti 8h (primo run scala 8h × 6 moduli).

**Trigger**: l'utente ha chiarito che il catalogo cliente arriva a 32 ore.
Il comportamento osservato su Preposti 8h NON è un caso isolato, è
**l'anteprima di una patologia che peggiora linearmente con la durata**.

## Telemetry osservata su Demo #3 (Preposti 8h × 6 moduli)

```
per_module_kept = {0:59, 1:23, 2:55, 3:5, 4:30, 5:29}
lost_to_other_module = {0:11, 1:47, 2:15, 3:5, 4:40, 5:41}
relevance_filter_dropped M3 = 60/70  (top_score 0.45 < MIN_RELEVANCE 0.3 NON è la
                                       causa, è invece il fatto che gli altri 65
                                       chunk hanno score < 0.3)
```

Tradotto:
- **M0 "Principali soggetti"**: 59 chunk → buono
- **M1 "Relazioni tra i vari soggetti"**: 23 chunk (47 persi a dedup verso M0 — concetti sovrapposti)
- **M2 "Definizione fattori di rischio"**: 55 chunk → buono
- **M3 "Incidenti e infortuni mancati"**: 5 chunk → **CATASTROFICO** (107 slide attese ÷ 5 = 21 slide/chunk)
- **M4 "Tecniche di comunicazione"**: 30 chunk (40 persi a dedup verso M0/M5)
- **M5 "Valutazione rischi dell'azienda"**: 29 chunk (41 persi a dedup verso M2)

## Aritmetica dello scaling

Le costanti di pipeline:
- `SECONDS_PER_SLIDE = 45`
- `DENSITY_MULTIPLIER STANDARD = 1.0`
- `top_k_per_module = 70` (default research_agent #31.2)
- `MIN_RELEVANCE = 0.3` (research_agent.py:42)
- `CHUNKS_TO_SLIDES_RATIO = 1.5` (1 chunk ≈ 1.5 slide pedagogiche)

Calcoli per slide/modulo a varie durate (con num_moduli da catalog):

| Durata | Slide totali | Moduli tipici | Slide/mod | Chunk/mod ideali | Disponibili @ top_k=70 |
|--------|--------------|---------------|-----------|------------------|------------------------|
| 4h     | 320          | 4             | 80        | ~53              | 30-50 (OK)             |
| 8h     | 640          | 6             | ~107      | ~71              | **5-59 (KO su M3)**    |
| 16h    | 1280         | 8-10          | ~128-160  | ~85-107          | **crash previsto**     |
| 32h    | 2560         | 12-16         | ~160-213  | ~107-142         | **crash critico**      |

A top_k=70 fisso, il sistema NON può fornire >70 chunk per modulo, ma a 32h
ne servirebbero ~140. Anche se i 140 ci fossero nel corpus, il limite
strutturale del retrieval li tagliá.

## Le tre cause concomitanti

### Causa 1 — `top_k_per_module` costante

È stato calibrato per 4h (#31.2: 45→70 dopo ripetizione "vie sgombre"). A 8h
o oltre la stessa costante è sotto-dimensionata. Serve scalare.

### Causa 2 — `MIN_RELEVANCE` statico (0.3)

Su moduli con tema "stretto" o corpus piccolo (Primo Soccorso DM 388 = 23
chunk totali; "Incidenti e infortuni mancati" è una nicchia del D.Lgs 81/08),
la soglia 0.3 taglia troppo aggressivamente. Su M3 Preposti, 60/70 chunk
sono finiti sotto soglia. La soglia è giusta per "Rischi specifici" che ha
50+ chunk forti, è sbagliata per nicchie.

### Causa 3 — Dedup cosine wins è zero-sum

L'algoritmo (`_compute_uniform_font_size` analogo per dedup): ogni chunk vince
nel modulo col cosine score più alto. Quando hai 6+ moduli semanticamente
adiacenti (Preposti M0/M1/M4 tutti su "soggetti/ruoli/comunicazione"), il
modulo "campione" del cosine prende tutto e gli altri restano svuotati.

A 4h × 4 moduli i temi sono più larghi (DPI vs Procedure emergenza vs
Segnaletica vs Rischi specifici) → dedup non si pesta i piedi.
A 8h × 6 moduli (e 32h × 12-16) i moduli si stringono e si sovrappongono
sui sotto-temi → dedup zero-sum diventa fame.

## Le tre leve di fix possibili (ordinate per impatto/costo)

### Leva A — `top_k_per_module` scalabile con durata

```python
# Nuovo (research_agent.py):
top_k_per_module = min(150, int(35 + 8 * duration_hours))
# 4h → 67  (~ attuale 70)
# 8h → 99
# 16h → 163 → cap 150
# 32h → 291 → cap 150
```

Pro: 1 LOC, deterministico, retroattivo (E25 e Demo #2 invariati).  
Contro: a 32h cap 150 è ancora sotto i ~140 ideali per modulo stretto. Da
sola non basta sopra 16h.  
Costo tempo: trascurabile (search_chunks è O(log N) su HNSW pgvector).

### Leva B — `MIN_RELEVANCE` adattivo per modulo

```python
# Per ogni modulo: filtro se chunk_count_after_relevance < 30 (soglia gate),
# ricalcola MIN_RELEVANCE come percentile 25 dei chunk del modulo.
# Esempio M3 Preposti: 70 chunk con score [0.45, 0.41, 0.38, ...] → MIN
# automatico = 0.10 (P25) → tutti 70 passano → da 5 a ~50 chunk.
```

Pro: rimedia il punto cieco "corpus debole sul tema = modulo svuotato".  
Contro: scelta del percentile arbitraria (P25 sembra ragionevole, ma serve
calibrare). Comportamento dinamico per modulo = più test da scrivere.  
Costo tempo: trascurabile.

### Leva C — Dedup "quota-aware" anti-starvation

```python
# Pre-dedup: stabilisci una quota minima per modulo (es. 25 chunk).
# Durante dedup, NON sottrarre chunk a un modulo se quello scende sotto quota.
# Solo gli ECCEDENTI vengono trasferiti via cosine winner.
```

Pro: nessun modulo scende sotto quota minima (5 → 25 garantiti su M3 Preposti).  
Contro: complessità algoritmica più alta (~30 LOC). Decisione: quota fissa 25
o dinamica `total_chunks / num_modules`?  
Costo tempo: trascurabile.

## Raccomandazione

Combinare **A + B** (entrambe 1-2 LOC, rete sicurezza in catena):
- A garantisce abbastanza pesce nel mare (top_k scalato a durata)
- B garantisce di non scartarlo (MIN_RELEVANCE adattivo per modulo)

Lasciare C come **work-item next sprint** se A+B non bastano per 32h reali.

## Verifica preventiva richiesta all'analista

Q1. Conferma le 3 cause come diagnosi corretta?
Q2. A+B è il combo giusto per 8h/16h/32h, o vuoi anche C?
Q3. La cap su top_k a 150 ti va bene o preferisci 200?
Q4. Per MIN_RELEVANCE adattivo, P25 va bene o preferisci P15?
Q5. Demo #3 Preposti che sto generando ora con la pipeline VECCHIA (M3=5 chunk)
    lo mandiamo lo stesso all'analista per la valutazione "patologia
    grab-bag confermata empiricamente", o aspetto a generarlo dopo A+B?
