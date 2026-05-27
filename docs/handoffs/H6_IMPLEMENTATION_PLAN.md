# H6 Load-balance Azure + OpenAI — Piano implementativo concreto

**Status**: piano scritto post review 4 analista. Le 5 risposte tecniche
H6.1-H6.5 dell'analista sono già chiare → questo NON è "richiesta piano"
ma "piano operativo per validazione".

---

## Contesto rinfrescato (per analista — leggere prima)

### Tempi cumulativi (verità aggiornata)

| Run | Tempo PPTX | Δ vs #18 baseline | Note |
|---|---|---|---|
| #18 baseline | 15m 41s | — | pre-FIX #31 |
| #19 post-FIX#31 (4 mosse) | 13m 32s | -13.7% | backfill via, dedup attiva |
| #20 post-#31.1 (per-modulo) | 10m 38s | -32.2% | M2/M3 trasformati no più grab-bag |
| #21 post-#31.2 (top_k 70) | 8m 28s | **-46%** | più chunk distinti, batch più rapidi |
| #22 post-#31.3 (SPREAD) | 11m 18s | -28% | rallentato + bug fallback (M2 perso) |
| #23 post-#31.4 (fix fallback) | (TBC) | TBC | misurando ora |

### Tier OpenAI verificato

Chiamata API diretta `https://api.openai.com/v1/chat/completions`:
- Modello `gpt-4.1-mini`
- HTTP 200 OK
- Headers letti:
  - `x-ratelimit-limit-tokens: 200000` (TPM)
  - `x-ratelimit-limit-requests: 500` (RPM)
  - `x-ratelimit-reset-tokens: 0s`
- Org: `nexus-seo` (chiave utente)
- **TIER 1**: H6 dà 200K + 200K = **400K aggregati**

### Caso d'uso CFP — H6 conta diversamente per scenario

| Scenario | H6 impatto | Priorità |
|---|---|---|
| Batch notturno (3-10 corsi paralleli) | **Raddoppio reale**: 400K TPM aggregati permettono saturazione doppia | **ALTA** (è il caso d'uso target H6) |
| Wizard self-serve (1 corso 4h) | Marginale: i 4 moduli paralleli su 200K non saturano sempre, raddoppio non dimezza il tempo singolo | bassa (8m 28s già gestibile) |
| Iterazione utente (rigenero modifiche) | H6 contribuisce a domare la variance del modulo lento (es. module 3 = 12 min vs module 1 = 7 min) | media |

---

## Decisioni tecniche analista review 4 (già confermate)

| ID | Decisione analista (verbatim) | Status |
|---|---|---|
| **H6.1** | "Dopo la demo. A 8.5 min H6 per il corso singolo non vale quasi più la pena. H6 è leva da batch." | ✅ CONFERMATO |
| **H6.2** | "(a) cieco con cooldown 429. Il least-loaded aggiunge contabilità di stato per guadagno marginale; il cooldown 429 cattura già la variance che conta." | ✅ CONFERMATO |
| **H6.3** | "60s, non 30. Se la finestra rate-limit è 60s, un cooldown di 30 ti fa ri-mandare all'endpoint ancora dentro la stessa finestra. Usa 60s, allineato alla finestra." | ✅ CONFERMATO (correggo mia ipotesi 30s) |
| **H6.4** | "(a) prima misura. Non over-engineerare. Logga last_provider nel counter reask, gira qualche corso, e POI decidi tra quota 60/40 o sticky. Probabilmente è rumore." | ✅ CONFERMATO |
| **H6.5** | "Lascia L1=Azure-premium. Cambiarlo non sblocca nulla e aggiunge endpoint non testato in livello di fallback che vuoi affidabile." | ✅ CONFERMATO |

Quindi il piano sotto NON è "vediamo cosa dice", è "implemento secondo le sue specs e validation".

---

## Implementazione operativa H6

### File da toccare

| File | Modifica | LOC |
|---|---|---|
| `app/config.py` | `openai_deployment_content: str = "gpt-4.1-mini"` (nuovo) | +1 |
| `app/services/ingestion_service.py` | `_L0_LOAD_BALANCE` cycle + cooldown 60s | ~50 |
| `app/services/ingestion_service.py` | Hook `last_provider` in `_instructor_client_for` counter | ~5 |
| `tests/unit/test_ingestion_l0_balance.py` | Nuovo test isolato (mock 2 provider + cooldown) | ~80 |

**Net**: ~+135 LOC. Stima tempo: 1h codice + 30 min test + ~10 min E2E.

### Codice — Modifica 1: `_L0_LOAD_BALANCE` round-robin con cooldown

```python
# app/services/ingestion_service.py (sopra _FALLBACK_CHAIN)
import itertools, time, threading

# H6 — load-balance L0 tra Azure-mini e OpenAI-mini (analista review 4
# decisione H6.2 + H6.3). NON least-loaded, NON sticky-per-modulo.
# Round-robin cieco + cooldown 60s al 429 = sufficient per la variance.
_L0_LOAD_BALANCE = [
    ("azure_openai", "azure_openai_deployment_content", "L0a_azure_mini"),
    ("openai",       "openai_deployment_content",       "L0b_openai_mini"),
]
_l0_iter = itertools.cycle(_L0_LOAD_BALANCE)
_l0_iter_lock = threading.Lock()  # cycle non è thread-safe
_l0_cooldown: dict[str, float] = {}  # label → timestamp di "available again"

# FIX #31 MOSSA 4 + H6: counter reask ora include provider per audit
# divergenza Azure-mini vs OpenAI-mini (decisione H6.4 — misura prima
# di decidere quota differenziata o sticky).

# Fallback chain INVARIATA (analista H6.5):
_FALLBACK_CHAIN = [
    ("azure_openai", "azure_openai_deployment_premium",  "L1_azure_premium"),
    ("anthropic",    "llm_content_model_fallback",       "L2_anthropic_emergency"),
]


def _next_l0_endpoint() -> tuple[str, str, str] | None:
    """Round-robin thread-safe + skip endpoint in cooldown.
    Ritorna None se tutti gli L0 sono in cooldown (caller escalate a L1).
    """
    now = time.time()
    with _l0_iter_lock:
        for _ in range(len(_L0_LOAD_BALANCE)):
            candidate = next(_l0_iter)
            label = candidate[2]
            if _l0_cooldown.get(label, 0) <= now:
                return candidate
        return None  # tutti in cooldown


async def call_llm(
    messages, system, *, model=None, task=None, _fallback_level: int = 0,
) -> str:
    """Wrapper unica: L0 load-balance prima, L1/L2 fallback chain dopo."""
    if _fallback_level == 0:
        # H6: tenta L0 round-robin + cooldown
        endpoint = _next_l0_endpoint()
        if endpoint is not None:
            provider, deployment_key, label = endpoint
            eff_model = model or getattr(settings, deployment_key)
            try:
                return await _call_llm_single(provider, eff_model, messages, system)
            except (openai.RateLimitError, openai.APIStatusError) as exc:
                # 429 → cooldown 60s (analista H6.3: allineato a sliding window)
                _l0_cooldown[label] = time.time() + 60.0
                logger.warning(
                    "l0_cooldown_triggered", label=label,
                    cooldown_until=_l0_cooldown[label], error_class=type(exc).__name__,
                )
                # Fallthrough a fallback chain L1+L2
            except Exception as exc:
                logger.warning(
                    "l0_unexpected_error", label=label,
                    error_class=type(exc).__name__, error=str(exc)[:200],
                )
        # else: tutti L0 in cooldown → vai diretto su L1

    # Codice fallback L1/L2 invariato
    if _fallback_level >= len(_FALLBACK_CHAIN):
        raise LLMProviderError("all fallback levels exhausted")
    provider, deployment_key, label = _FALLBACK_CHAIN[_fallback_level]
    eff_model = getattr(settings, deployment_key)
    try:
        return await _call_llm_single(provider, eff_model, messages, system)
    except (openai.RateLimitError, openai.APIStatusError,
            openai.APIConnectionError, anthropic.RateLimitError,
            anthropic.InternalServerError) as e:
        logger.warning("llm_fallback_triggered",
                       task=task, from_level=label, error_class=type(e).__name__)
        return await call_llm(
            messages, system, model=None, task=task,
            _fallback_level=_fallback_level + 1,
        )
```

### Codice — Modifica 2: `_instructor_client_for` con `last_provider` in counter

```python
def _instructor_client_for(provider: str, model: str):
    """H6: extended per loggare provider nel counter reask (decisione
    analista H6.4: misura prima, decide dopo se OpenAI-mini reaska
    più di Azure-mini)."""
    import instructor
    from instructor import Mode

    reask_counter = {"reasks": 0, "last_provider": provider}  # NUOVO last_provider

    def _on_completion_error(*_args: Any, **_kw: Any) -> None:
        reask_counter["reasks"] += 1
        reask_counter["last_provider"] = provider  # ultimo provider che ha causato reask

    # ... resto invariato ...

    return client, model, reask_counter
```

E in `generate_module_structured`:

```python
logger.info(
    "module_batch_reasks",
    module_index=module_index,
    batch_idx=batch_idx,
    reasks=batch_counter["reasks"],
    last_provider=batch_counter["last_provider"],  # NUOVO
)
```

### Codice — Modifica 3: `config.py`

```python
# app/config.py — aggiungere accanto a azure_openai_deployment_content
openai_deployment_content: str = "gpt-4.1-mini"  # H6: OpenAI L0b
```

`.env`: già presente `OPENAI_API_KEY=sk-proj-...`, niente da aggiungere.

---

## Test isolato `test_ingestion_l0_balance.py`

```python
"""H6 tests — round-robin + cooldown 429."""
import asyncio, time
import pytest
from unittest.mock import AsyncMock, patch
from app.services import ingestion_service as svc

@pytest.fixture(autouse=True)
def _reset_l0_state():
    svc._l0_cooldown.clear()
    svc._l0_iter = itertools.cycle(svc._L0_LOAD_BALANCE)


@pytest.mark.asyncio
async def test_round_robin_alternates_providers():
    """Chiamate consecutive alternano Azure → OpenAI → Azure."""
    with patch.object(svc, '_call_llm_single', new=AsyncMock(return_value="ok")):
        for expected_idx in [0, 1, 0, 1]:
            await svc.call_llm([{"role":"user","content":"x"}], "sys")
            assert svc._call_llm_single.call_args[0][0] == svc._L0_LOAD_BALANCE[expected_idx][0]


@pytest.mark.asyncio
async def test_429_triggers_60s_cooldown():
    """Azure 429 → cooldown registrato a now+60s, prossima chiamata va su OpenAI."""
    azure_call = AsyncMock(side_effect=openai.RateLimitError(...))
    openai_call = AsyncMock(return_value="ok")

    def routing_mock(provider, *a, **kw):
        return azure_call() if provider == "azure_openai" else openai_call()

    with patch.object(svc, '_call_llm_single', side_effect=routing_mock):
        await svc.call_llm(...)  # Azure → 429 → cooldown
        result = await svc.call_llm(...)  # next L0 = OpenAI (Azure in cooldown)
        assert openai_call.called
        assert svc._l0_cooldown["L0a_azure_mini"] >= time.time() + 59.5


@pytest.mark.asyncio
async def test_all_l0_cooldown_escalates_to_l1():
    """Quando entrambi L0 in cooldown → call_llm scala a L1 (Azure-premium)."""
    svc._l0_cooldown["L0a_azure_mini"] = time.time() + 100
    svc._l0_cooldown["L0b_openai_mini"] = time.time() + 100
    with patch.object(svc, '_call_llm_single', new=AsyncMock(return_value="L1_ok")):
        result = await svc.call_llm(...)
        # Verifica che sia stato chiamato con provider L1 (azure_openai_premium)
        called_with_premium = any(
            call.args[1] == settings.azure_openai_deployment_premium
            for call in svc._call_llm_single.call_args_list
        )
        assert called_with_premium


@pytest.mark.asyncio
async def test_counter_reask_logs_last_provider():
    """Counter reask deve loggare quale provider ha causato l'errore."""
    client, model, counter = svc._instructor_client_for("openai", "gpt-4.1-mini")
    assert counter == {"reasks": 0, "last_provider": "openai"}
    client.hooks.emit_completion_error(ValueError("test"))
    assert counter["reasks"] == 1
    assert counter["last_provider"] == "openai"
```

---

## Verifica E2E H6

**Smoke isolato** (~30s):
```bash
pytest tests/unit/test_ingestion_l0_balance.py -v
```

**E2E #24 corso 4h con H6 attivo** (~9-10 min stimati):
```bash
docker compose exec backend python scripts/e2e_19_run.py
```

**Cosa misurare nei log E2E #24**:
- `module_batch_reasks last_provider=L0a_azure_mini` vs `L0b_openai_mini`: distribuzione round-robin
- `l0_cooldown_triggered` events: quanti 429 effettivi Azure/OpenAI hanno ricevuto
- `module_reask_stats reask_total_module` per modulo: dovrebbe restare 0 (come #21/#23 senza H6)
- Tempo totale: confronto con #23 baseline

**Gate go/no-go H6**:
- ✅ Tempo ≤ #23 oppure ≤ #21 (8m 28s) — non deve peggiorare
- ✅ Almeno 1 batch processato da OpenAI nei log (round-robin attivo)
- ✅ Zero `cooldown_triggered` su run normale (no 429 a regime)
- ✅ Reask cumulativo ≈ #21 baseline (no degrado qualità)

---

## Rischi & Mitigazioni

| Rischio | Probabilità | Mitigazione |
|---|---|---|
| OpenAI-mini divergenza qualità vs Azure-mini | Media (modelli "identici" ma infra diverse) | Counter reask per-provider già loggato (H6.4) → dopo 3 corsi vedo divergenza, decido se quota diff |
| `itertools.cycle` non thread-safe sotto Semaphore(20) | Bassa | `threading.Lock` wrapper in `_next_l0_endpoint` |
| 429 cooldown 60s troppo lungo se Azure ha problema temporaneo brevi | Bassa | Cooldown SOLO L0, escalation a L1 immediata → no degrado servizio |
| Costi raddoppiati (uso 2 chiavi invece di 1) | NESSUNO | Stesso costo per token su Azure e OpenAI ($0.40 in / $1.60 out 1M tk), distribuisci ma non aumenti |

---

## Quando H6 va attivato

Analista H6.1: **DOPO la demo**.

Ordine concreto:
1. Adesso: chiudo demo CFP con #31.4 (E2E #23 sano + 2 corsi demo + deploy Vercel+Railway)
2. Post-demo (settimana prossima): implemento H6 secondo questo piano
3. Verifica H6 con E2E #24 + 3 corsi misti per audit divergenza per-provider
4. Se OK divergenza ≤15%, H6 resta attivo permanentemente. Niente sticky/quota.
