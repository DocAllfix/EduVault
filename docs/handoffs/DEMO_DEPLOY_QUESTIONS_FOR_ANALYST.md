# Messaggio analista — stato post-FIX#31 + piano demo cliente + deploy + tempo

**Data:** 2026-05-27 pomeriggio
**Allegati Desktop:**
- `CFP_4h_E2E19_post-FIX31_da_analista.pptx` (45 MB, 326 slide, corso 4h)
- `CFP_4h_E2E19_post-FIX31_dispensa.pdf` (356 KB)

---

## Messaggio da copiaincollare in chat analista

```
Caro analista,

Tre cose: (1) i numeri reali post-FIX#31 (li hai chiesti, e cambiano
l'ordine d'attacco H6/H3a), (2) un piano per portare il sistema a
demo cliente questa settimana, (3) la decisione che mi serve da te
sul tempo per-corso (perché 13 min è meglio di 15 ma il cliente non
li può aspettare).

Allego il PPTX dell'E2E #19 (corso 4h post-FIX#31, 326 slide). È
quello da analizzare per dare il via libera "consegnabile bozza RSPP"
o segnalare regressioni qualità.

══════════════════════════════════════════════════════════════════
1. NUMERI VERI E2E #19 — i risultati delle 4 mosse
══════════════════════════════════════════════════════════════════

Confronto col baseline E2E #18 stamattina:

  Metrica                  E2E #18    E2E #19     Δ
  Tempo pipeline           15m 41s    13m 32s     -2m 09s (-13.7%)
  backfill_wave count      5-8        0           ✓ MOSSA 1 OK
  backfill wall-clock      ~150s      <1s         -99%
  pexels_hits count=5      n/a        80+ query   ✓ MOSSA 2 attivo
  reask_avg_per_batch      n/a        0.0         ✓ MOSSA 4 risposta
  DIAGRAM catalog          21/21      18/18       100% catalog
  normative_ref 'pag.'     0          0           zero allucinazioni

DISTRIBUTION qualità E2E #19 (326 slide, 4 moduli 84/84/74/84):
  CONTENT_TEXT  45% | CONTENT_IMAGE 28% | QUIZ 12% | DIAGRAM 5.5%
  CASE_STUDY 3% | RECAP 3% | MODULE_OPEN/CLOSE 4+4 bookends

LA SCOPERTA CHE CAMBIA TUTTO PER H6/H3a:
Avevi detto "reask_avg_per_batch > 0.5 → batch-size pesa; ~0 → H6
da solo basta". È esattamente 0.0 su tutti e 4 i moduli. I reask
diagram che vedevamo nei log (8 in E2E #18) erano TUTTI quelli con
log dedicato — non c'erano reask di profondità invisibili sotto.

Conclusione operativa: H3a (batch 10→6) NON porterebbe guadagno
apprezzabile. La leva grossa rimasta per scendere è SOLO H6
(load-balance Azure+OpenAI per attaccare la variance). Confermi che
posso saltare H3a e prepararmi a H6 quando vorrai darmi il via?

══════════════════════════════════════════════════════════════════
2. DEMO CLIENTE + DEPLOY — il piano che ti propongo
══════════════════════════════════════════════════════════════════

OBIETTIVO: il cliente CFP Montessori deve avere un URL pubblico
dove (a) vede i 3 corsi demo (Primo Soccorso 8h, Generale 4h,
Specifica Basso 4h) già generati, (b) può loggarsi e crearne uno
quarto suo per testare il wizard, (c) scarica i PPTX/PDF generati.

STATO FRONTEND (verificato direttamente, non da terzi):
- 7 pagine operative: Login, Dashboard, Wizard 6-step, Progress,
  Course Detail, Regulations, Admin
- COURSE STUDIO C'È: route $id_.studio.tsx + 6 componenti
  (slide-viewer, slide-editor, image-picker, audio-player,
  regenerate-dialog, rebuild-banner). Devo solo verificare lo
  smoke end-to-end con Chrome DevTools.
- 17/17 endpoint BP §10 cablati, build production verde.

DEPLOY — utente vuole "tutto su Vercel". Vincoli tecnici:
- Vercel funzioni serverless Edge/Node: backend Python long-running
  NON è compatibile (timeout 10min vs nostra pipeline 15min,
  /output filesystem ephemeral, Semaphore(1) richiede stato).
- Soluzione split: frontend su Vercel (subdomain free
  nexus-eduvault.vercel.app per la demo), backend+DB+storage su
  Railway "tutto-in-uno" (container Python + Postgres+pgvector
  managed + volume persistente per /output). Costo demo: ~$5/mese
  Railway hobby tier. API keys uso le mie (Anthropic+Voyage, ho
  budget per ~20 corsi 4h).

PIANO OPERATIVO che ho in mente:

Fase A — Validazione qualità (oggi-domani, dopo il tuo OK sul PPTX)
  - Genero altri 2 corsi (Primo Soccorso 8h + Generale 4h) post-FIX#31
    sotto editable install garantito
  - Smoke Chrome DevTools end-to-end: login → wizard → progress
    → detail → download PPTX → apertura PowerPoint reale
  - Smoke Course Studio: clicco "edit" su una slide del 4h, cambio
    titolo, regenero quella sola, verifico

Fase B — Deploy infrastruttura demo (1 giorno)
  - Railway: spinup backend Python da Dockerfile + Postgres-pgvector
    managed addon + volume persistente /output. Migrations applicate
    al primo boot, seed admin user dal mio bootstrap email.
  - Vercel: frontend Vite build da branch fix/31-pipeline-surgery,
    env VITE_API_URL → URL Railway, subdomain free Vercel.
  - Smoke deploy: genero 1 corso 1h dal dominio cloud per
    verificare che tutto giri end-to-end in produzione.

Fase C — Hand-off cliente (immediata post-Fase B)
  - Mando al cliente: URL demo + credenziali admin temporanee + i
    3 corsi pre-generati visibili in dashboard.
  - "Prova a crearne uno tuo dal wizard, ci metti 13-15 minuti.
    Quando finisce scarichi PPTX e PDF dalla card Dettaglio."

══════════════════════════════════════════════════════════════════
3. IL PROBLEMA TEMPO — il cliente non può aspettare 13 min
══════════════════════════════════════════════════════════════════

Adesso siamo a 13m 32s per un 4h, partendo da 15m 41s. È un -2 min
reale ma 13 min davanti a uno spinner sono troppi per uno user che
non sa cosa sta succedendo. Il cliente CFP avrà tre tipi di uso:

(i) "Mi generi 3 corsi al mese, batch notturno" → 13 min/corso ×
    3 = 40 min totali una volta al mese, non è collo
(ii) "Voglio provare la piattaforma, faccio un wizard al volo" →
     13 min davanti a uno spinner = sensazione "sistema lento", il
     cliente abbandona prima della fine
(iii) "Voglio iterare un corso (cambio durata da 4h a 8h, rigenero)"
      → 13 min × ogni iterazione, intollerabile

Per (ii) e (iii) ho una soluzione UX immediata (faccio sì che il
progress page diventi engaging, con phase concrete tipo "sto
recuperando i chunk normativi su DPI...", "sto generando il modulo
3 di 4..."). Ma quello è palliativo. Il taglio reale del tempo
dipende da H6, che hai già messo in roadmap.

LE DOMANDE SECCHE su cui mi serve la tua decisione:

(A) H6 quando? Ho il dato `reask_avg_per_batch=0.0` che lo sblocca
    (non serve più H3a prima). Mi rispondi tu sul tier OpenAI
    (avevo chiesto stamattina ma poi ci siamo concentrati su FIX#31
    — è ancora valida la chiave OpenAI del cliente?), e io stimo
    30 LOC + 1 giorno. Target post-H6: ~8 min/corso 4h (era 13).

(B) Verifica visiva PPTX E2E #19: dimmi se la qualità è
    "consegnabile bozza RSPP" o se vedi regressioni rispetto a #18.
    Le metriche dicono "uguale o meglio" (18/18 DIAGRAM catalog,
    zero pag. allucinati, dedup attivo) ma sui dettagli (coerenza
    moduli, ordine slide, template diagrammi usati) servono i tuoi
    occhi.

(C) Coerenza moduli per la demo cliente: il cliente CFP vedrà 4
    moduli (Rischi specifici / DPI / Procedure emergenza /
    Segnaletica) — su #18 mi avevi detto "M3 emergenze scivola
    formazione, M4 segnaletica titolo non mantiene". È peggiorato,
    uguale, migliorato su #19? Se è ancora "bozza RSPP da revisione",
    okay per demo; se è "sembra auto-generato grezzo", devo
    sospendere demo finché non aggiusto.

(D) Deploy schema vercel+railway: è la strada giusta o vedi
    alternativa più semplice (es. tutto Railway, Vercel solo CNAME)?
    Per la demo basta funzionare, non deve essere production-grade.

(E) Su (ii) UX engaging del progress page: mentre aspetto H6, vale
    la pena spendere 2-3h di lavoro per fare il progress page
    "vivo" (eventi WS dettagliati tipo "modulo 2/4 al 60%",
    counter slide generate)? O è palliativo che il cliente capirà
    come tale e meglio puntare tutto su H6 e portare il tempo a 8m?

Grazie. Aspetto le tue 5 risposte prima di partire con Fase A.

Per riferimento, lo stato repo:
- Branch fix/31-pipeline-surgery pushato (commit 8958e89), 23 test
  nuovi verdi, baseline non degradata (110 failures pre-esistenti
  FIX #30.x non in scope)
- Course Studio frontend implementato (route + 6 componenti), da
  testare end-to-end nella Fase A
- API keys Anthropic+Voyage: uso le mie ($30 anthropic + $5 voyage
  tier free, basta per ~20 corsi 4h, sufficiente per demo cliente)
- Niente cambi backend pending. Tutto stabile.
```

---

## Per te, fuori dal messaggio analista — note operative

### Cosa ho corretto rispetto al draft precedente

1. **Course Studio** ✅ esiste davvero (verificato `frontend/src/features/course-studio/` + 6 componenti + route `$id_.studio.tsx`). Avevo creduto a un agent senza verificare di persona. Mai più.
2. **Deploy** → tutto Railway per backend+DB+storage, Vercel solo frontend con subdomain free. Più semplice di quanto avessi scritto prima.
3. **API keys** → le mie. Tolto domanda inutile sul cliente.
4. **Tempo per-corso** → nuova sezione esplicita (tre scenari uso cliente), è ora la priorità #1 dopo qualità.

### Cosa è già pronto sul Desktop

- `CFP_4h_E2E19_post-FIX31_da_analista.pptx` — 45 MB, 326 slide, l'ultimo corso generato
- `CFP_4h_E2E19_post-FIX31_dispensa.pdf` — 356 KB

L'analista può aprirli direttamente, validare qualità visiva, rispondere alle 5 domande.

### Numeri grezzi E2E #19 pronti per il messaggio

| Aspetto | Valore |
|---|---|
| Tempo pipeline | 13m 32s (-13.7% vs #18) |
| Distribution slide | TEXT 45% / IMAGE 28% / QUIZ 12% / DIAGRAM 5.5% / CASE 3% / RECAP 3% + bookends |
| Moduli | 84/84/74/84 (uniformi) |
| DIAGRAM catalog | 18/18 = 100% |
| Reask invisibili instructor | 0 medi per batch (= H3a non serve) |
| normative_ref allucinazioni "pag." | 0 |

### Sul deploy Railway — ricognizione rapida prima di Fase B

Railway hobby tier free $5 di credito/mese permette: 1 servizio container (backend) + 1 DB Postgres con extension. pgvector è disponibile come addon. Storage volume persistente fino a 5GB free. Costo concreto demo: $0 se sotto il credito, max $5/mese se sforiamo.

Per il backend Python:
- Dockerfile esiste già, va bene per Railway
- Migrations applicate al boot via `app.db.migrations`
- Seed admin user dal bootstrap (`ADMIN_BOOTSTRAP_EMAIL` env var)
- `setup_langgraph_grants.sql` da eseguire una-tantum post-boot (manuale, 30 sec)

Per il frontend su Vercel:
- Build script già verde (Vite + TypeScript)
- Env `VITE_API_URL` punta al dominio Railway
- Auto-deploy da branch `fix/31-pipeline-surgery` (o creo `deploy/demo`)
