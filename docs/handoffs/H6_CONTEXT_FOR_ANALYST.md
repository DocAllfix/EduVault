# H6 — Contesto rinfrescato + richiesta piano dettagliato

**Da unire al messaggio finale post-E2E #22.** Sezione H6 da inviare
all'analista con tutto il contesto attualizzato per il piano di
implementazione.

---

## Stato attuale POST tutte le iterazioni FIX #31 family

### Numeri cumulativi dei tempi (decisivi per H6)

| Run | Tempo | Δ vs baseline | Note |
|---|---|---|---|
| E2E #18 baseline (pre-FIX #31) | **15m 41s** | — | Audio mai partito (bug `outputs`) |
| E2E #19 post-FIX #31 (4 mosse) | 13m 32s | -13.7% | Backfill rimosso, dedup attiva |
| E2E #20 post-#31.1 (per-modulo retrieval) | 10m 38s | -32.2% | M2/M3 trasformati no più grab-bag |
| E2E #21 post-#31.2 (top_k 70) | **8m 28s** | **-46%** | Più chunk distinti, batch più rapidi |
| E2E #22 post-#31.3 (SPREAD prompt) | (TBC) | — | Atteso ~8-9 min, qualitativo M2 |

**Verità su H6 cambiata**: l'analista aveva detto a #31 che H6 era la
"leva grossa rimasta" per scendere sotto i 13 min. Ma le iterazioni
#31.1+#31.2 hanno già fatto **-46% da #18 (15:41 → 8:28)** senza H6,
solo con retrieval per-modulo + top_k bump. **L'urgenza H6 è crollata**
per il corso singolo self-serve.

Citazione analista review 4 verbatim:
> "8m28s, altri -20% — al contrario della mia previsione. A 8,5 minuti
> H6 per il corso singolo NON vale quasi più la pena — l'attesa
> self-serve è gestibile senza acrobazie. H6 è ormai quasi puramente
> una mossa da BATCH (10 corsi paralleli)."

### Verifica tier OpenAI (già fatta, da rinfrescare)

Account OpenAI cliente (`nexus-seo` org, key `sk-proj-...`):
- Modello: `gpt-4.1-mini` (identico Azure)
- **TPM: 200.000** (tier 1)
- RPM: 500
- TPD: 2.000.000
- HTTP test 2026-05-27 mattina: 200 OK

Quindi piano originale H6 vale: Azure 200K + OpenAI 200K = **400K
aggregati**, raddoppio capacità content_agent.

### Cosa H6 attacca DAVVERO (diagnosi precedente)

Analista verbatim review 2:
> "Il content_agent ha 4 moduli in parallelo. Tempo content NON è
> la somma ma il MASSIMO dei 4. Su corso singolo da 4 moduli con
> 200K TPM, i 4 moduli in parallelo NON saturano sempre il budget
> → raddoppiare a 400K non dimezza il tempo del corso singolo.
> Quello che H6 fa è soprattutto domare la VARIANCE: il modulo
> sfortunato che becca la coda Azure lenta (module 3 a 12 min vs
> module 1 a 7 min) può spostare i suoi batch sulla coda OpenAI
> libera. Quindi il corso singolo diventa più veloce e SOPRATTUTTO
> PIÙ COSTANTE. Su BATCH (10 corsi paralleli) invece il raddoppio
> è pieno."

### Caso d'uso cliente CFP — ricontestualizzato

3 scenari uso post-#31.3:
1. **Batch notturno** (3-10 corsi insieme): H6 è LA leva, raddoppio
   reale capacità (TPM sufficiente per 1, scarso per 10 paralleli).
2. **Wizard self-serve singolo corso**: 8m 28s è gestibile, H6
   marginale (variance domata ma non dimezzato).
3. **Iterazione corso (cambio durata, rigenero)**: 8m 28s × N
   iterazioni. H6 contribuisce solo se l'utente NON è bloccante
   (apre altri tab mentre aspetta).

---

## Cosa avevo proposto in piano (riassunto, da validare con analista)

### Architettura load-balance

`app/services/ingestion_service.py` — modificare `_FALLBACK_CHAIN`
e wrapper `call_llm`:

```python
# PRIMA (oggi):
_FALLBACK_CHAIN = [
    ("azure_openai", "azure_openai_deployment_content",   "L0_azure_mini"),
    ("azure_openai", "azure_openai_deployment_premium",   "L1_azure_premium"),
    ("anthropic",    "llm_content_model_fallback",        "L2_anthropic_emergency"),
]

# DOPO (H6 — proposta):
_L0_LOAD_BALANCE = [
    ("azure_openai", "azure_openai_deployment_content",   "L0a_azure_mini"),
    ("openai",       "openai_deployment_content",         "L0b_openai_mini"),  # NUOVO
]
_FALLBACK_CHAIN = [
    # L0 round-robin tra Azure-mini e OpenAI-mini (gestito separatamente)
    ("azure_openai", "azure_openai_deployment_premium",   "L1_azure_premium"),
    ("anthropic",    "llm_content_model_fallback",        "L2_anthropic_emergency"),
]

# Round-robin counter + cooldown 429
import itertools, time
_l0_iter = itertools.cycle(_L0_LOAD_BALANCE)
_l0_cooldown: dict[str, float] = {}  # provider → next_available_timestamp
```

### Hook 429 cooldown

```python
async def _call_with_l0_balance(messages, system, task):
    # Try L0 round-robin con cooldown
    for _ in range(len(_L0_LOAD_BALANCE)):
        provider, deployment_key, label = next(_l0_iter)
        if _l0_cooldown.get(label, 0) > time.time():
            continue  # endpoint in cooldown post-429, skip
        try:
            return await _call_llm_single(provider, ...)
        except openai.RateLimitError:
            _l0_cooldown[label] = time.time() + 30.0  # 30s cooldown
            continue
        except ...
    # Tutti L0 in cooldown → escalate a L1
    raise LLMProviderError("all L0 endpoints cooling down")
```

### Counter reask per-provider (MOSSA 4 estesa)

Hook `client.on("completion:error", ...)` deve loggare il provider
per distinguere se OpenAI-mini reaska più di Azure-mini (stesso
modello ma infrastructure diverse, possono divergere):

```python
client.on("completion:error", lambda exc: counter.update(
    reasks=counter["reasks"] + 1,
    last_provider=provider,  # NUOVO
))
```

E in `module_batch_reasks` logga `provider=L0a_azure_mini` o
`provider=L0b_openai_mini`. Permette di pesare il round-robin (se
un provider reaska troppo, riduci la sua quota).

---

## Domande all'analista (piano dettagliato H6)

1. **L'urgenza H6 è cambiata davvero?** Conferma che con #31.3 a
   8m 28s, H6 è da rimandare a "fase batch" e NON va prima della
   demo? Oppure il -46% non basta e vuoi comunque H6 prima della
   consegna cliente (per la robustezza batch implicito)?

2. **Round-robin VS Weight-based VS Sticky-per-modulo?** Tre design
   alternativi:
   - (a) **Round-robin cieco**: batch 0 → Azure, batch 1 → OpenAI,
     batch 2 → Azure, ... Semplice ma se Azure ha 1 batch lento
     mentre OpenAI è libero, il successivo va comunque su Azure.
   - (b) **Round-robin con backpressure**: vince il provider con
     meno batch in volo (least-loaded). Più complesso ma reagisce
     alla variance in tempo reale.
   - (c) **Sticky per modulo**: M0 → Azure, M1 → OpenAI, M2 →
     Azure, M3 → OpenAI (fissato all'inizio). Massimizza locality
     ma se un provider è lento, blocca metà del corso.
   Tu cosa scegli?

3. **Cooldown 429 — durata?** Avevo proposto 30s, ma Azure e OpenAI
   usano sliding windows diversi (Azure 60s, OpenAI 60s). Vale 60s?
   O cooldown adaptive (incrementa se 429 ripetuto)?

4. **Counter reask per-provider e azione su divergenza**. Se
   OpenAI-mini reaska il 15% in più di Azure-mini per validation
   bullet/notes, cosa faccio:
   - (a) niente, è rumore accettabile?
   - (b) riduco quota OpenAI nel round-robin (es. 60/40 invece
     di 50/50)?
   - (c) sticky per task: structured-output instructor sempre su
     Azure, classify_chunk sempre su OpenAI?

5. **Test isolato H6 — come simulo la variance Azure?** Per testare
   che il cooldown 429 funzioni e che il least-loaded scelga
   davvero il provider giusto, devo simulare un endpoint lento +
   un endpoint veloce. Mock con `asyncio.sleep` random? O lascio
   solo verifica E2E sui 3 corsi demo?

6. **Riordino fallback chain**. Se L0 ora è 2 endpoint (Azure-mini
   + OpenAI-mini) in load-balance, L1 resta Azure-premium (gpt-4o
   5× costo) o lo demoto? Oggi L1 si attiva se TUTTI gli L0
   falliscono — con 2 L0 indipendenti, è MOLTO più raro. Vale la
   pena cambiare L1 a "OpenAI-premium gpt-4o" per non avere stessa
   infra Azure su 2 livelli consecutivi? O lascio com'è?

---

## Cosa NON ti chiedo, perché lo so già

- Tier OpenAI = TIER 1 (verificato API call diretta)
- Compliance NON in discussione (dati pubblici D.Lgs. 81/08)
- API keys disponibili (mie chiavi dev, sufficienti per demo)
- REI-3 Semaphore(1) python-pptx NON è violato (H6 è solo content_agent
  LLM call, non tocca python-pptx)

---

## Riepilogo: il messaggio operativo che ti chiedo

Quando rispondi al messaggio finale post-E2E #22, includi:
1. OK visivo sulla qualità #22 (M2/M3 coerenti, immagini contestuali,
   diagrammi OK)
2. Decisione H6 prima/dopo demo
3. Risposta alle 6 domande sopra (specialmente design round-robin e
   cooldown 429)
4. Eventuali correzioni al piano architetturale che ho abbozzato
