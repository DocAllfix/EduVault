# Messaggio analista — E2E #22 + diagnosi bug fallback + richieste finali

**Allegati Desktop:**
- `CFP_4h_E2E22_31.3_M2_BROKEN.pptx` (PPTX corrotto, M2 quasi vuoto — è proprio quello che voglio farti vedere)
- `CFP_4h_E2E22_31.3_M2_BROKEN_dispensa.pdf`
- Anche utili per confronto: `CFP_4h_E2E21_31.2_da_analista.pptx` (l'ultimo "buono")
  e `CFP_4h_E2E20_31.1_da_analista.pptx` (gate passato originale)

---

```
Caro analista,

E2E #22 finito ma con un problema serio che devo farti vedere prima
di decidere come procedere. Ti spiego tutto come l'ho ricostruito,
poi ti dico cosa PENSO io e ti chiedo di confermare il ragionamento.

══════════════════════════════════════════════════════════════════
1. NUMERI E2E #22 — risultato superficiale e cosa nasconde
══════════════════════════════════════════════════════════════════

  Metrica                       E2E #21    E2E #22    Δ
  Tempo pipeline                8m 28s     11m 18s    +2m 50s
  Slide totali                  326        246        -80
  Slide M2 "Procedure emerg."   84         2          -82 (!!)
  per_module_kept retrieval     stesso     stesso     invariato
  reask                         0          0          invariato
  "vie sgombre" M2 (gate tuo)   7          0 (!!)     -7

A occhio sembra "drastico ma SPREAD ha funzionato troppo". In realtà
il "0 vie sgombre" e i "2 slide M2" sono lo stesso evento: M2 è
praticamente sparito dal corso. La regola SPREAD NON ha causato
questo. Te lo dimostro qui sotto coi log.

══════════════════════════════════════════════════════════════════
2. COSA HA FATTO LA REGOLA SPREAD — la verità coi log
══════════════════════════════════════════════════════════════════

Log di M2 (verbatim, in ordine):
  12:30:40  module_retrieval_done module_index=2 count_after=70
  12:31:05  module_batch_ok       batch_idx=0  got=5  (degraded -5)
  12:31:56  module_batch_ok       batch_idx=1  got=10
  12:32:39  module_batch_ok       batch_idx=2  got=10
  12:33:30  module_batch_ok       batch_idx=3  got=10
  12:34:24  module_batch_ok       batch_idx=4  got=10
  12:35:09  module_batch_ok       batch_idx=5  got=10
  12:35:54  module_batch_ok       batch_idx=6  got=10
  12:36:46  module_batch_ok       batch_idx=7  got=12
  12:36:46  module_structured_done degraded=True expected=82 final_count=77 module_index=2
  12:36:46  module_instructor_ok  degraded=True final=77

Lettura: SPREAD ha funzionato. M2 ha prodotto 77 slide su 82 attese
(degraded perché batch_0 ne ha generato solo 5 invece di 10 — minore,
accettabile). Il content_agent ha rispettato la regola: niente "vie
sgombre" ×7, varietà tematica reale, 77 slide on-topic.

POI succede questo (riga successiva del log, stesso secondo 12:36:46):

  12:36:46  module_instructor_failed_fallback_legacy
            module_index=2
            error="1 validation error for SlideContent
                   Value error, slide_type=MODULE_CLOSE
                   bullets[3] ha 11 parole > 10 max.
                   Riscrivi più sintetico o splitta in 2 slide."

E poi 4 minuti dopo:

  12:40:54  module_below_threshold_accepted
            module_index=2  slide_count=2  threshold=20

Cosa è successo: il MODULE_CLOSE che chiude M2 ha generato un bullet
da 11 parole. Il validator Pydantic (MODULE_CLOSE ha bullet_max_words=10
in core.py:158) ha sollevato ValueError. Il content_agent ha attivato
`fallback_legacy` che ha BUTTATO TUTTE LE 77 SLIDE BUONE e ha
rigenerato il modulo dall'inizio con un altro path. Il fallback ne
ha prodotte 2. Il quality gate `module_below_threshold_accepted` ha
loggato il problema ma ha accettato comunque.

Risultato: il modulo che era 77 slide a tema, perfetto sui titoli,
è diventato 2 slide.

══════════════════════════════════════════════════════════════════
3. IL MIO RAGIONAMENTO (chiedo conferma)
══════════════════════════════════════════════════════════════════

Penso questo, in 4 passaggi:

(a) IL BUG NON È #31.3 SPREAD. SPREAD ha lavorato fino in fondo,
    77 slide on-topic, regola rispettata. Il problema è dopo,
    in fase di validation.

(b) IL BUG NON È NEMMENO IL "MODULE_CLOSE BULLET 11 PAROLE" IN SÉ.
    11 vs 10 parole è una violazione di limite stretto, non un crollo
    qualitativo. Una slide con 1 bullet appena sopra il limite NON
    giustifica buttare 77 slide buone.

(c) IL BUG VERO È IL FALLBACK ARCHITETTONICO. Quando 1 slide viola
    validation, `module_instructor_failed_fallback_legacy` butta
    TUTTO il modulo e rigenera con path legacy. Il legacy è
    estremamente debole: ha prodotto 2 slide invece di 82. Il fix
    "cattura una violazione su 1 slide" è MOLTO più distruttivo
    della violazione stessa. È un comportamento difensivo che ha
    senso quando il modulo è in stato disastroso (es. 0 slide
    generate per OOM), ma è inappropriato quando 77/82 sono buone
    e solo 1 ha un dettaglio fuori limite.

(d) IL FALLBACK È PRE-ESISTENTE, NON L'HO INTRODOTTO IO IN #31.x.
    Era dormiente perché in #19/#20/#21 il MODULE_CLOSE non aveva
    mai sforato bullet_max_words. È riemerso ora per coincidenza
    (l'LLM ha generato un bullet leggermente più lungo, può
    succedere a chiunque). Il fatto che non sia mai esploso prima
    NON significa che andava bene — significa che eravamo
    fortunati.

CONFERMI questo ragionamento? Vedi punti dove ho sbagliato?

══════════════════════════════════════════════════════════════════
4. 4 OPZIONI OPERATIVE — qual è la tua scelta?
══════════════════════════════════════════════════════════════════

OPZIONE A — Fix chirurgico bullet_max_words MODULE_CLOSE
  Alzo bullet_max_words=10→12 per MODULE_CLOSE (uguale a CONTENT_TEXT
  che è 12). 1 riga in core.py, 5 min, rilancio E2E #23.
  Pro: probabilità altissima che il fallback non scatti più.
  Contro: tappa il sintomo, non la causa. La prossima volta che
  l'LLM genera 13 parole in un bullet succede di nuovo (su un
  modulo diverso, altro caso).

OPZIONE B — Fix fallback non-distruttivo (la causa)
  Quando 1 slide viola validation in un modulo dove 77/82 sono
  buone, droppo SOLO quella slide (o auto-fix con truncate
  intelligente sui bullet) e tengo le altre. ~30-40 LOC in
  ingestion_service.py (zona module_instructor_failed_fallback_legacy).
  Pro: risolve il bug architetturale. Vale per qualsiasi violazione
  futura, non solo MODULE_CLOSE bullets.
  Contro: 1-2h lavoro + rischio regressioni su path testato.

OPZIONE C — Rollback SPREAD #31.3
  Tolgo la regola SPREAD dal prompt, torno a E2E #21 com'era
  (8m 28s, 7 ripetizioni "vie sgombre" che tu avevi giudicato
  "bozza-RSPP sopravvivibile" nella review 4). Demo parte con
  #21 nessuna acrobazia.
  Pro: ho già il tuo OK condizionato su #21. Zero rischio.
  Contro: butto via il lavoro #31.3 anche se ha dimostrato di
  funzionare (lo SPREAD diceva di non ripetere e infatti ha
  variato). E il bug fallback resta dormiente per la prossima
  esplosione.

OPZIONE D — A + B insieme, scegli tu l'ordine
  Faccio A subito per sbloccare la demo (E2E #23 in 15 min totali),
  poi faccio B post-demo come fix architetturale strategico.
  Pro: demo non bloccata + fix vero in roadmap.
  Contro: 2 lavori invece di 1.

LA MIA PREFERENZA: D. A subito per non bloccare la deadline,
B come tech-debt prioritario post-demo. Ma se tu mi dici "fai B
adesso, ne vale la pena anche se sforo 2h", lo faccio — il bug
B è il fix strategico vero.

══════════════════════════════════════════════════════════════════
5. RICHIESTE PARALLELE — non solo M2 da verificare
══════════════════════════════════════════════════════════════════

L'utente CFP mi ha chiesto esplicitamente di farti analizzare tutto,
non solo M2. Quindi quando avremo un E2E sano (post fix decisione tua),
ti chiedo di guardare con i tuoi occhi:

(R1) COERENZA MODULI M0/M1/M2/M3 — stesso check che hai fatto su
     #19 e #21. M2 e M3 restano on-topic dopo SPREAD?

(R2) IMMAGINI UNA PER UNA — apri 15-20 slide CONTENT_IMAGE
     random in 4 moduli diversi e dimmi:
     - La foto Pexels è davvero contestuale al titolo?
       (es. titolo "Vie di emergenza" ha foto di un'uscita di
       emergenza, non una foto generica di ufficio?)
     - Le foto sono di qualità professionale o look-and-feel
       da stock random poco mirato?
     - La dedup #31 MOSSA 2 (max 2 riusi per URL) regge —
       non vedi la stessa foto su 8 slide diverse?

(R3) DIAGRAMMI UNO PER UNO — apri tutti i ~15-20 DIAGRAM:
     - Sono dal catalogo (template flow/pyramid/matrix/org_tree)
       o sono cascati in branded fallback?
     - Per ogni diagram, il template scelto è semanticamente
       adatto al contenuto? (es. una "sequenza di azioni" usa
       flow_horizontal, una "gerarchia" usa pyramid/org_tree)
     - I testi nei box ci stanno bene o sono troncati?

(R4) NORMATIVE_REF — controllo random su 20 slide:
     - I riferimenti normativi sono coerenti col contenuto?
     - Ci sono ancora "pag. X-Y" allucinati o solo "art./allegato"?
     - Le slide MODULE_OPEN/CLOSE hanno normative_ref vuoto
       (corretto) o lo riempiono comunque (errato)?

(R5) AUDIO — è ancora "spento" per il bug `outputs` non persistito,
     decidiamo se fixarlo per la demo o no?

══════════════════════════════════════════════════════════════════
6. H6 LOAD-BALANCE AZURE+OPENAI — piano dettagliato
══════════════════════════════════════════════════════════════════

CONTESTO RINFRESCATO (perché le ultime sessioni hanno cambiato
parecchio):

Tempi cumulativi:
  E2E #18 baseline:                       15m 41s
  E2E #19 post-FIX#31 (4 mosse):          13m 32s  (-13.7%)
  E2E #20 post-#31.1 (retrieval modulo):  10m 38s  (-32.2%)
  E2E #21 post-#31.2 (top_k 70):           8m 28s  (-46% da #18!)
  E2E #22 post-#31.3 (SPREAD):            11m 18s  (regressione causata da bug fallback su M2 — non da SPREAD)

La verità su H6 dopo questi numeri: tu stesso nella review 4 avevi
detto "8m 28s, altri -20% — al contrario della mia previsione. A
8.5 min H6 per il corso singolo NON vale quasi più la pena, l'attesa
self-serve è gestibile senza acrobazie. H6 è ormai quasi puramente
una mossa da BATCH."

Tier OpenAI verificato (ho fatto la chiamata API): TIER 1 — 200K TPM,
500 RPM, 2M TPD su gpt-4.1-mini. Quindi H6 darebbe 200K Azure + 200K
OpenAI = 400K aggregati, raddoppio reale capacità content_agent.

Caso d'uso CFP — H6 conta diversamente:
- Batch notturno (3-10 corsi insieme): H6 è LA leva, raddoppio reale
- Wizard self-serve singolo: 8.5 min gestibile, H6 marginale
- Iterazione utente: H6 contribuisce solo se non bloccante

ARCHITETTURA CHE AVEVO ABBOZZATO (in /docs/H6_CONTEXT_FOR_ANALYST.md
sul mio disco, te lo passo se vuoi i dettagli):

```python
# ingestion_service.py
_L0_LOAD_BALANCE = [
    ("azure_openai", "azure_openai_deployment_content",  "L0a_azure_mini"),
    ("openai",       "openai_deployment_content",        "L0b_openai_mini"),
]
_FALLBACK_CHAIN = [
    ("azure_openai", "azure_openai_deployment_premium",  "L1_azure_premium"),
    ("anthropic",    "llm_content_model_fallback",       "L2_anthropic_emergency"),
]
_l0_iter = itertools.cycle(_L0_LOAD_BALANCE)
_l0_cooldown: dict[str, float] = {}

async def _call_with_l0_balance(...):
    for _ in range(len(_L0_LOAD_BALANCE)):
        provider, deployment_key, label = next(_l0_iter)
        if _l0_cooldown.get(label, 0) > time.time():
            continue  # endpoint in cooldown post-429, skip
        try:
            return await _call_llm_single(...)
        except openai.RateLimitError:
            _l0_cooldown[label] = time.time() + 30.0
            continue
    raise LLMProviderError("all L0 endpoints cooling down")
```

+ counter reask per-provider in MOSSA 4 hook esteso:
```python
client.on("completion:error", lambda exc: counter.update(
    reasks=counter["reasks"] + 1,
    last_provider=provider,  # NUOVO
))
```

DOMANDE TECNICHE H6 — qui ti chiedo conferma o correzione:

(H6.1) URGENZA H6: con 8.5 min (post fix bug fallback torniamo lì),
       H6 va PRIMA della demo o DOPO?
       Mia ipotesi: dopo. Il -46% cumulato ha già fatto il lavoro
       per il caso self-serve singolo. H6 lo facciamo quando il
       cliente vuole batch notturno (= scenario non ancora attivato).

(H6.2) DESIGN ROUND-ROBIN: 3 alternative
       (a) cieco (alterna batch 0→Azure, 1→OpenAI, 2→Azure, ...)
       (b) least-loaded (vince provider con meno batch in volo)
       (c) sticky per modulo (M0→Azure, M1→OpenAI, ecc.)
       Mia ipotesi: (a) cieco con cooldown 429 — semplice, reattivo,
       il cooldown 429 cattura la variance senza least-loaded.
       Tu preferisci (b) per la variance domata che dicevi?

(H6.3) COOLDOWN 429: 30s sufficienti? Azure e OpenAI hanno sliding
       window 60s. Pensavo 30s, ma se uso 60s evito di re-mandare
       a un endpoint nella stessa finestra rate-limited.

(H6.4) COUNTER REASK PER-PROVIDER: se OpenAI-mini reaska il 15% in
       più di Azure-mini, cosa faccio?
       (a) niente, è rumore accettabile (modelli "identici" su infra
           diverse possono divergere di poco)
       (b) riduco quota OpenAI nel round-robin (60/40 Azure)
       (c) sticky per task: instructor structured-output sempre
           Azure, classify_chunk sempre OpenAI (compiti diversi,
           comportamenti diversi)
       Mia ipotesi: (a) prima misura, poi decide. Non over-engineer.

(H6.5) RIORDINO FALLBACK CHAIN: se L0 ora è 2 endpoint (Azure-mini
       + OpenAI-mini), L1 resta Azure-premium (gpt-4o 5× costo)? O
       lo demoto a "OpenAI-premium gpt-4o" per non avere stessa infra
       Azure su 2 livelli consecutivi?
       Mia ipotesi: lascio L1=Azure-premium per ora. Cambiarlo
       non sblocca nulla, aggiunge solo un endpoint nuovo non testato.

══════════════════════════════════════════════════════════════════
7. RIASSUNTO COSA TI CHIEDO IN UNA RISPOSTA
══════════════════════════════════════════════════════════════════

(1) Conferma il mio ragionamento sui 4 punti (bug NON è SPREAD,
    bug È il fallback distruttivo, fallback è pre-esistente, ecc.)

(2) Scegli tra A/B/C/D per sbloccare la demo.

(3) Quando ti mando E2E #23 sano, fai R1-R5 (coerenza moduli +
    immagini contestuali + diagrammi + normative + audio decisione).

(4) Su H6, conferma/correggi le 5 sotto-domande tecniche (H6.1-H6.5).

Aspetto. Se non risponde nelle prossime 30 min vado di D
(opzione A subito + B post-demo) per non bloccare la deadline,
ma fammi sapere appena puoi.

Allegati Desktop:
- CFP_4h_E2E22_31.3_M2_BROKEN.pptx (la prova del bug — apri M2,
  vedi 2 slide invece di 82)
- CFP_4h_E2E22_31.3_M2_BROKEN_dispensa.pdf
- (Se vuoi confronto, hai ancora CFP_4h_E2E21_31.2_da_analista.pptx
  e CFP_4h_E2E20_31.1_da_analista.pptx)

Grazie.
```

---

## Per te (fuori dal messaggio analista)

### Cosa farò mentre aspetto l'analista (se dici "vai")

Niente. Aspetto la sua risposta. Non parto neanche con A (fix chirurgico)
senza il suo OK perché:
- È una decisione di scope (A vs B vs D, dipende dalla deadline)
- Faccio confusione con un E2E #23 mentre lui sta ancora guardando #22

### Tempistica per la demo

Se l'analista risponde entro 1h con OPZIONE A o D:
- Fix bullet_max_words 5 min
- E2E #23 ~9 min (atteso post-fix simile a #21 con SPREAD attivo, ~9-10 min)
- Verifica titoli M2 + copia Desktop 10 min
- Messaggio analista finale per gate visivo R1-R5 + decisione H6
- Se OK gate → 2 altri corsi demo + commit + deploy

**Totale time-to-demo se tutto verde**: ~4-5h dopo risposta analista.

### File pronti sul Desktop

- `CFP_4h_E2E22_31.3_M2_BROKEN.pptx` (43 MB) — la PROVA del bug
- `CFP_4h_E2E22_31.3_M2_BROKEN_dispensa.pdf` (293 KB)
- Già lì da prima: `CFP_4h_E2E21_31.2_da_analista.pptx` (43 MB) — l'ultimo "buono"
- Già lì da prima: `CFP_4h_E2E20_31.1_da_analista.pptx` (45 MB) — gate originale passato

### Numeri grezzi per follow-up

E2E #22:
- pipeline_completed elapsed=677.5s = 11m 18s
- M2 module_index=2: 77 slide generate, poi fallback→2 slide
- Bug error: `slide_type=MODULE_CLOSE bullets[3] ha 11 parole > 10 max`
- File: `core.py:158` (MODULE_CLOSE bullet_max_words=10)
