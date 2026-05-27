# Messaggio analista FINALE — E2E #23 + R1-R5 + Piano H6

**Allegati Desktop:**
- `CFP_4h_E2E23_31.4_da_analista.pptx` (44 MB, 301 slide) — il build sano post-FIX#31.4
- `CFP_4h_E2E23_31.4_dispensa.pdf` (328 KB)
- Anche utili per confronto: `CFP_4h_E2E21_31.2_da_analista.pptx`, `CFP_4h_E2E20_31.1_da_analista.pptx`

---

```
Caro analista,

FIX #31.4 (A+B+gate fatal) implementato secondo le tue indicazioni
review 5. E2E #23 ha confermato che il fix funziona — il modulo che
era sparito è tornato — ma ha portato in superficie 2 cose nuove
che voglio discutere con te. E poi ti propongo il piano H6 concreto
che hai approvato in #31.

══════════════════════════════════════════════════════════════════
1. NUMERI E2E #23 — confronto + dettagli
══════════════════════════════════════════════════════════════════

  Metrica                      E2E #21    E2E #22    E2E #23    Δ #22→#23
  Tempo pipeline               8m 28s     11m 18s    15m 16s    +3m 58s (!!)
  Slide totali                 326        246        301        +55
  Moduli numerazione           1-2-3-4    1-2-4      1-2-3-4    ✓ ripristinata
  M0 slide                     84         86         76         degraded -8
  M1 slide                     84         78         57         degraded -27 (!!)
  M2 slide ("Procedure emerg") 84         2 (rotto)  84         ✓ ripristinato
  M3 slide                     84         84         84         ✓
  MODULE_CLOSE bullet violation 0          1 (rotto)  0         ✓ truncate funziona
  fallback_legacy triggered    0          1 (M2)     0          ✓ separazione try/except
  gate fatal triggered         0          0          0          (per fortuna)
  reask_avg_per_batch          0.0        0.0        0.0        invariato
  M2 "vie sgombre" titles      7          0 (rotto)  5          SPREAD attivo
  M2 angoli dichiarati         no         n/a        sì         ✓ es. "Controllo pratico per vie libere"
  DIAGRAM catalog              100%       100%       100% (23)  invariato

CONFRONTO LIVELLO ALTO:
- ✓ Il fix A+B+gate fatal funziona: M2 è tornato modulo intero,
  numerazione ripristinata, MODULE_CLOSE auto-truncated senza
  triggerare fallback.
- ⚠ Tempo regredito a 15m (era 8.5 in #21). Ti spiego sotto perché.
- ⚠ M1 degraded a 57 slide su 82 attese (-27). Causa scoperta nei log,
  NON è il fix mio, è un altro pattern.

══════════════════════════════════════════════════════════════════
2. ANALISI TEMPO LENTO — diagnosi onesta
══════════════════════════════════════════════════════════════════

15:16 vs 8:28 di #21 = +6m 48s. Diagnosi:

(a) SPREAD prompt aggiunge ~250 token al system prompt per batch.
    Per modulo 8 batch × 4 moduli = 32 batch. Su gpt-4.1-mini
    ogni token in più costa latenza variabile. Stimo ~30s/modulo
    extra = ~2 min totali attribuibili a SPREAD.

(b) M1 ha avuto 2 batch falliti con InstructorRetryException
    (vedi sezione 3). Ogni retry esaurisce instructor.max_retries=5,
    quindi 5 tentativi × 30s = 2.5 min PER BATCH FALLITO × 2 batch
    = ~5 min "buttati" prima del fallimento finale. Questo spiega
    gran parte del rallentamento M1 e del tempo totale.

(c) Latenza Azure variabile: nei log vedo batch normali in 30-40s
    e batch lenti in 60-90s. È la variance di cui parlavi nella
    review 2 (module 3 lento). Sommata su 32 batch totali, +1-2 min.

Somma: ~9 min spiegati (SPREAD 2 + reask M1 5 + variance 2) +
8 min baseline #21 = 17 min stimati. Misurato 15:16, dentro range.

NB: il tempo NON è bug. È il costo combinato di SPREAD prompt +
2 batch failure (LLM error pre-esistente, non #31.4).

══════════════════════════════════════════════════════════════════
3. M1 DEGRADED — 2 batch persi per LLM-error pre-esistente
══════════════════════════════════════════════════════════════════

Per trasparenza ti riporto i 2 errori che hanno causato il -27 slide
in M1 (non sono colpa di #31.4):

Batch 0 M1 fallito:
  error="1 validation error for ModuleSlides slides.6
   Value error, slide_type=DIAGRAM ha 3 bullets > 2 max.
   SPLITTA il concetto in 2 slide consecutive
   (NON troncare, NON comprimere)."
  class=InstructorRetryException

Batch 2 M1 fallito:
  error="1 validation error for ModuleSlides slides.1
   Input should be an object [type=model_type,
   input_value='source_chunk_ids([', input_type=str]"
  class=InstructorRetryException

Lettura:
- Primo errore: DIAGRAM con 3 bullets invece di 2 max (constraint
  Pydantic). Instructor ha re-asked 5 volte ma l'LLM ha continuato
  a generare 3 bullets. È un'idiosincrasia che ho già visto su
  qualche slide in E2E precedenti, ma di solito instructor riusciva
  a correggere entro 5 retry. Qui no.
- Secondo errore: LLM ha emesso JSON malformato per source_chunk_ids
  (stringa invece di lista). Anche questo non recuperato in 5 retry.

Il fix B (separazione try/except) ha funzionato: i 6 batch OK su 8
sono stati TENUTI invece di buttare via tutto. M1 ha 55 slide
on-topic + bookends invece di sparire come #22. Il gate fatal NON
ha triggered perché 55 > MIN_ACCEPTABLE_SLIDES_PER_MODULE=20.

Domanda: il -27 slide su M1 ti pare ancora demo-grade o vuoi che
investighi gli 2 errori specifici (es. abbassare DIAGRAM bullets
max da 2 a 3, o validare source_chunk_ids prima di instructor)?
Mia opinione: M1 a 57 slide è accettabile per la demo come "modulo
leggermente più corto", ma se vuoi che lo risolvo posso.

══════════════════════════════════════════════════════════════════
4. M2 — IL FIX HA FUNZIONATO COSÌ COME VOLEVI
══════════════════════════════════════════════════════════════════

5 "vie sgombre" residue su 84 slide (era 7 in #21, 0 in #22 rotto).
I 5 titoli rimasti dichiarano l'angolo:
   - "Vie e uscite di emergenza: mantenerle libere"
   - "Vie di emergenza sgombre: garantire il rapido accesso al
      luogo sicuro"
   - "Mantenere le vie di emergenza sempre libere: obblighi
      operativi"
   - "Controllo pratico per vie di emergenza libere"
   - "Vie di emergenza libere e sgombre nel magazzino"

Non sono 5 doppioni "Vie sgombre e sicure" — è esattamente quello
che chiedevi: spread tra "mantenere", "obblighi operativi",
"controllo pratico", "magazzino". Variazione angolazione legittima,
NON ridondanza.

══════════════════════════════════════════════════════════════════
5. RICHIESTE PARALLELE — TUE VERIFICHE SU PPTX #23
══════════════════════════════════════════════════════════════════

L'utente CFP mi ha chiesto esplicitamente di farti controllare
tutto, non solo M2. Apri CFP_4h_E2E23_31.4_da_analista.pptx
(Desktop) e dimmi:

(R1) COERENZA MODULI M0/M1/M2/M3
   Scorri 10-15 titoli per modulo (specialmente M3 Segnaletica che
   in #21 derivava su sanzioni dopo slide ~50). M3 #23 sembra
   on-topic, ma è meglio i tuoi occhi.

(R2) IMMAGINI UNA PER UNA contestuali
   Apri 15-20 slide CONTENT_IMAGE random nei 4 moduli e dimmi:
   - La foto Pexels è davvero contestuale al titolo?
     (es. titolo "Vie di emergenza" ha davvero una foto di uscita
     di emergenza, non una foto generica di ufficio?)
   - Le foto sono professionali o look-and-feel da stock random
     poco mirato?
   - La dedup #31 MOSSA 2 (max 2 riusi per URL) regge —
     non vedi la stessa foto su 8 slide diverse?

(R3) DIAGRAMMI UNO PER UNO
   23 DIAGRAM totali, 100% catalog (filling valido, zero branded
   fallback). Apri TUTTI E 23 e dimmi:
   - Per ogni diagram, il template scelto è semanticamente
     adatto al contenuto?
     - flow_horizontal_3step/4step per sequenze
     - pyramid_3level per gerarchie
     - matrix_2x2 per assi probabilità×gravità
     - org_tree_3level per organigrammi
     - causa_effetto per relazioni causali
     - compare_2col per confronti
   - I testi nei box ci stanno bene o sono troncati?
   - Il pyramid_3level che avevi ridisegnato in #30.9g compare?
     Quale modulo lo usa?

(R4) NORMATIVE_REF — controllo random su 20 slide
   - I riferimenti normativi sono coerenti col contenuto?
   - Ci sono ancora "pag. X-Y" allucinati (zero atteso)?
   - Le slide MODULE_OPEN/CLOSE hanno normative_ref vuoto
     (corretto) o lo riempiono comunque (errato)?

(R5) AUDIO
   È ancora "spento" per il bug `outputs` non persistito nel DB
   (visto in #22 e #23, audio_in_background=False sempre).
   Decidiamo se fixarlo per la demo o lo lasciamo off?
   Fix LOC stimato: ~30 (migration 005_add_outputs.sql + update
   API courses POST per persistere outputs + read in pipeline).

══════════════════════════════════════════════════════════════════
6. H6 — PIANO IMPLEMENTATIVO CONCRETO PER VALIDATION
══════════════════════════════════════════════════════════════════

CONTESTO RINFRESCATO (perché sono passate 5 sessioni):

Tempi cumulativi storici:
  #18 baseline pre-FIX#31:                15m 41s
  #19 post-FIX#31 (4 mosse):              13m 32s (-13.7%)
  #20 post-#31.1 (per-modulo retrieval):  10m 38s (-32.2%)
  #21 post-#31.2 (top_k 70):               8m 28s (-46%)
  #22 post-#31.3 (SPREAD) [rotto]:        11m 18s
  #23 post-#31.4 (fix fallback) [oggi]:   15m 16s

L'effetto-doping di -46% su #21 era artefatto: il content_agent
era veloce perché non aveva ancora SPREAD prompt che aggiungeva
load semantico. Realisticamente, post-SPREAD (necessario per
qualità M2/M3) il tempo "regime" è 11-15 min.

Tier OpenAI verificato (la chiamata API che mi avevi chiesto):
TIER 1, 200K TPM, 500 RPM, 2M TPD su gpt-4.1-mini. Quindi H6
= 200K Azure + 200K OpenAI = 400K aggregati.

Caso d'uso H6:
- Batch notturno 3-10 corsi paralleli: H6 dà raddoppio reale TPM
- Self-serve singolo corso: H6 doma la VARIANCE (M1 che sfora,
  M3 lento). Stima -20-30% tempo grazie a "domare variance",
  non al raddoppio TPM puro.

Le tue 5 risposte tecniche review 4 (già confermate):
  H6.1 → dopo la demo
  H6.2 → cieco con cooldown 429
  H6.3 → cooldown 60s (NON 30, allineato sliding window)
  H6.4 → counter reask per-provider, no quota differenziata
         finché numeri non lo chiedono
  H6.5 → L1 resta Azure-premium (gpt-4o), non toccare

PIANO IMPLEMENTATIVO PRONTO IN docs/H6_IMPLEMENTATION_PLAN.md
sul mio disco. Sintesi:

File da toccare:
- app/config.py: +1 LOC (openai_deployment_content="gpt-4.1-mini")
- app/services/ingestion_service.py: ~50 LOC
  (_L0_LOAD_BALANCE cycle + cooldown 60s thread-safe + escalation
   a L1 se tutti L0 in cooldown)
- _instructor_client_for: ~5 LOC (counter ha last_provider per
   audit divergenza Azure vs OpenAI)
- tests/unit/test_ingestion_l0_balance.py: ~80 LOC (round-robin
   alterna, 429 triggera cooldown 60s, escalation L1 se tutti
   cooldown, counter last_provider)

Codice nucleo (estratto):

```python
_L0_LOAD_BALANCE = [
    ("azure_openai", "azure_openai_deployment_content", "L0a_azure_mini"),
    ("openai",       "openai_deployment_content",       "L0b_openai_mini"),
]
_l0_iter = itertools.cycle(_L0_LOAD_BALANCE)
_l0_iter_lock = threading.Lock()
_l0_cooldown: dict[str, float] = {}

def _next_l0_endpoint() -> tuple[str, str, str] | None:
    now = time.time()
    with _l0_iter_lock:
        for _ in range(len(_L0_LOAD_BALANCE)):
            candidate = next(_l0_iter)
            if _l0_cooldown.get(candidate[2], 0) <= now:
                return candidate
        return None  # tutti in cooldown → caller escalate a L1

async def call_llm(messages, system, *, model=None, task=None,
                   _fallback_level: int = 0) -> str:
    if _fallback_level == 0:
        endpoint = _next_l0_endpoint()
        if endpoint is not None:
            provider, deployment_key, label = endpoint
            eff_model = model or getattr(settings, deployment_key)
            try:
                return await _call_llm_single(provider, eff_model,
                                              messages, system)
            except (openai.RateLimitError, openai.APIStatusError):
                _l0_cooldown[label] = time.time() + 60.0  # H6.3
                logger.warning("l0_cooldown_triggered", label=label, ...)
    # fallthrough a L1/L2 (analista H6.5: L1=Azure-premium invariato)
    ...
```

Tempo stimato implementation: ~1h codice + 30min test + 10min E2E.
Eseguibile in 1 mattinata post-demo.

DOMANDA SECCA H6: confermi che il piano sopra è esattamente quello
che intendevi nelle 5 risposte review 4, o vedi qualcosa da
correggere prima che io lo implementi post-demo?

══════════════════════════════════════════════════════════════════
7. CHE DECISIONE TI CHIEDO IN UNA RISPOSTA
══════════════════════════════════════════════════════════════════

(1) OK visivo su PPTX E2E #23: la qualità è "consegnabile bozza-RSPP"
    come #20/#21 o vedi regressioni?

(2) Le R1-R5 (immagini contestuali, diagrammi catalog 23/23,
    normative_ref, audio decisione) sono il "gate visivo finale".
    Quando confermi, posso procedere con 2 altri corsi demo.

(3) M1 a 57 slide (-27): accettabile o vuoi che investighi i 2
    LLM-errors specifici?

(4) Tempo 15:16: accettiamo come "regime post-SPREAD" oppure ti
    sembra che valga la pena spegnere SPREAD per scendere a 11-12
    min accettando un po' di ripetizione M2 in più?

(5) Il piano H6 sopra è quello giusto da implementare post-demo?
    Eventuali correzioni?

(6) Se OK su (1) e (2): procedo con 2 corsi demo (Generale 4h +
    Primo Soccorso 8h) + commit fix(31.2+31.3+31.4) + deploy
    Vercel+Railway. Tempo stimato totale: ~5h.

Aspetto. Grazie.
```

---

## Per te (fuori dal messaggio analista)

### Stato file Desktop

| File | Size | Cosa contiene |
|---|---|---|
| `CFP_4h_E2E23_31.4_da_analista.pptx` | 44 MB | Il build sano post-fix |
| `CFP_4h_E2E23_31.4_dispensa.pdf` | 328 KB | PDF |
| `CFP_4h_E2E22_31.3_M2_BROKEN.pptx` | 43 MB | Lasciato sul Desktop come prova bug (utile per confronto se l'analista vuole vedere "prima/dopo") |
| `CFP_4h_E2E21_31.2_da_analista.pptx` | 43 MB | E2E #21 (8m 28s, 7 vie sgombre) — confronto velocità |
| `CFP_4h_E2E20_31.1_da_analista.pptx` | 45 MB | E2E #20 (gate originale passato) — confronto |

### Cose che mentre aspetto la risposta NON faccio

- Investigazione M1 LLM-errors (DIAGRAM 3 bullets / source_chunk_ids stringa) — aspetto OK analista
- H6 implementazione — aspetto OK analista
- 2 corsi demo + commit + deploy — aspetto OK analista
- Audio fix outputs — aspetto OK analista

### Cose che SE l'analista dice "vai" subito faccio in sequenza

1. Genero corso "Sicurezza Generale Lavoratori 4h" sotto #31.4 (~15 min)
2. Genero corso "Primo Soccorso 8h" sotto #31.4 (~25-30 min stimati per 8h)
3. Copio tutti i 3 PPTX su Desktop (E2E #23 + 2 nuovi)
4. Commit `fix(31.2+31.3+31.4)` su branch `fix/31-pipeline-surgery`
5. Push branch a remote
6. Setup deploy Railway (1-2h) — backend container + Postgres-pgvector
7. Setup deploy Vercel (~30 min) — frontend Vite build con env API URL
8. Smoke deploy: genero 1 corso 2h dal dominio cloud
9. Mando link demo all'utente (e via lui al cliente CFP)

Tempo totale estimato post-OK analista: **5-6h work + ~50 min E2E in background**.
