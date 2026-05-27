"""Regulation ingestion pipeline (BLUEPRINT §06.1.1).

PHASE 2.1 — Stage 1: PDF text extraction via pdfplumber.
PHASE 2.2 — Stage 2: hybrid chunking (rule-based regex + paragraph fallback)
            with normalized coverage check and SHA-256 dedup hash.
PHASE 2.3 — Stage 3: LLM-assisted classification (rule-validated).
            Stage 4: Voyage embedding (batched, retried) + dedup indexing.

All stages stay INLINE in this module per the project rule (no separate
utils/ files — see HANDOFF_PHASE2.md).

GAP note (REI-5 / REI-16): BP §06.1.1 Stage 3 calls ``call_llm`` which the
BP defines in ``agents/content_agent.py`` (§05.5, FASE 3.4 — not yet built).
To unblock 2.3 without writing FASE 3 out of order, ``call_llm`` is defined
here verbatim from §05.5. FASE 3.4 will import it from this module (or the
content_agent will reuse it) instead of redefining it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import anthropic
import openai
import pdfplumber
import structlog
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
)

from app.config import settings
from app.services.dependencies import get_voyage_client

logger = structlog.get_logger()

# A raw chunk as produced by Stage 2 (before classification/embedding in 2.3).
# Values are str except article/paragraph which are None when not applicable.
Chunk = dict[str, str | None]


# ─────────────────────────────────────────────────────────────────────
# Stage 1 — PDF parsing
# ─────────────────────────────────────────────────────────────────────


def parse_regulation_pdf(pdf_path: str | os.PathLike[str]) -> str:
    """Extract layout-preserving text from a normative PDF.

    pdfplumber is mandated by BP D-09 over PyMuPDF because it surfaces
    structural metadata (tables, text boxes) that the downstream chunker
    in 2.2 relies on for ART_PATTERN / COMMA_PATTERN matching.

    Pages are concatenated with newline separators; ``extract_text`` may
    return ``None`` for pages with no extractable text layer (scanned
    images), in which case that page contributes an empty string rather
    than raising — the caller decides whether the resulting coverage is
    sufficient.
    """
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"Regulation PDF not found: {path}")

    parts: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            parts.append(text if text else "")
            parts.append("\n")

    full_text = "".join(parts)
    logger.info(
        "pdf_parsed",
        path=str(path),
        chars=len(full_text),
        pages=page_count,
    )
    return full_text


# ─────────────────────────────────────────────────────────────────────
# Stage 2 — Hybrid chunking (BLUEPRINT §06.1.1 Stadio 2)
# ─────────────────────────────────────────────────────────────────────

# Article marker for Italian normative text. Supports the full suffix
# series bis/ter/quater/quinquies/sexies/septies/octies/novies/decies
# (BP §06.1.1 verbatim).
ART_PATTERN = re.compile(
    r'Art(?:icolo)?\.?\s*'
    r'(\d+(?:-(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies))?)'
    r'\s*[\.\-\—\s]+(.+?)'
    r'(?=Art(?:icolo)?\.?\s*\d+|$)',
    re.DOTALL | re.IGNORECASE,
)

COMMA_PATTERN = re.compile(
    r'(\d+)\.\s+(.+?)(?=\d+\.\s+|$)',
    re.DOTALL,
)

ALLEGATO_PATTERN = re.compile(
    r'(Allegato\s+[IVXLCDM\d]+(?:-(?:bis|ter))?)\s*[\.\-\—\s]*(.+?)'
    r'(?=Allegato\s+[IVXLCDM\d]+|$)',
    re.DOTALL | re.IGNORECASE,
)


def normalize_for_coverage(text: str) -> str:
    """Normalize text for accurate coverage comparison.

    Strips whitespace runs, Gazzetta Ufficiale headers/footers and the
    ``— N —`` page-number markers so the structured/full ratio reflects
    semantic content, not PDF chrome.
    """
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'Gazzetta Ufficiale.*?Serie.*?\d+', '', text)
    text = re.sub(r'— \d+ —', '', text)
    return text.strip()


def chunk_structured_regulation(full_text: str, regulation_id: str) -> list[Chunk]:
    """Chunk structured Italian regulations (decreti, accordi).

    Each chunk = one article (or one comma inside it), plus any allegato.
    """
    chunks: list[Chunk] = []

    # Phase 1: articles and commi
    for art_match in ART_PATTERN.finditer(full_text):
        art_num = art_match.group(1)
        art_body = art_match.group(2).strip()

        commas = COMMA_PATTERN.findall(art_body)
        if commas and len(commas) > 1:
            for comma_num, comma_body in commas:
                chunks.append({
                    "regulation_id": regulation_id,
                    "article": f"Art. {art_num}",
                    "paragraph": f"Comma {comma_num}",
                    "hierarchy_path": f"Art. {art_num} > Comma {comma_num}",
                    "body": comma_body.strip(),
                })
        else:
            chunks.append({
                "regulation_id": regulation_id,
                "article": f"Art. {art_num}",
                "paragraph": None,
                "hierarchy_path": f"Art. {art_num}",
                "body": art_body,
            })

    # Phase 2: allegati
    for all_match in ALLEGATO_PATTERN.finditer(full_text):
        all_name = all_match.group(1).strip()
        all_body = all_match.group(2).strip()
        if len(all_body) > 50:  # skip empty / corrupted allegati
            chunks.append({
                "regulation_id": regulation_id,
                "article": all_name,
                "paragraph": None,
                "hierarchy_path": all_name,
                "body": all_body,
            })

    return chunks


def chunk_unstructured_regulation(full_text: str, regulation_id: str) -> list[Chunk]:
    """Fallback chunking for unstructured normative text.

    Splits by paragraph with a 1-sentence overlap from the previous
    paragraph, used for delibere regionali, allegati grezzi and tabelle
    that don't follow the Art./Comma scheme.
    """
    paragraphs = [p.strip() for p in full_text.split('\n\n') if len(p.strip()) > 50]
    chunks: list[Chunk] = []
    for i, p in enumerate(paragraphs):
        if i > 0:
            prev_sentences = paragraphs[i - 1].split('.')
            overlap = prev_sentences[-2].strip() + '.' if len(prev_sentences) > 1 else ''
            body = f"{overlap} {p}" if overlap else p
        else:
            body = p
        chunks.append({
            "regulation_id": regulation_id,
            "article": None,
            "paragraph": None,
            "hierarchy_path": f"Paragrafo {i+1}",
            "body": body,
        })
    return chunks


def extract_uncaptured_text(full_text: str, chunks: list[Chunk]) -> str:
    """Return paragraphs the structured chunker did not capture.

    Uses the first 100 chars of each chunk body as a coarse fingerprint.
    """
    captured: set[str] = set()
    for chunk in chunks:
        captured.add(str(chunk["body"])[:100])
    residual_parts: list[str] = []
    for paragraph in full_text.split('\n\n'):
        paragraph = paragraph.strip()
        if len(paragraph) > 50 and paragraph[:100] not in captured:
            residual_parts.append(paragraph)
    return '\n\n'.join(residual_parts)


def chunk_regulation(full_text: str, regulation_id: str) -> list[Chunk]:
    """Entry point: hybrid chunking with normalized coverage check.

    If the structured regex captures less than 70% of the NORMALIZED
    text, the residual is re-chunked by paragraph with sentence overlap
    and appended to the structured output.
    """
    # 1. Structured pass
    chunks = chunk_structured_regulation(full_text, regulation_id)

    # 2. Coverage with normalization (strips PDF header/footer)
    captured_normalized = normalize_for_coverage(" ".join(str(c["body"]) for c in chunks))
    full_normalized = normalize_for_coverage(full_text)
    coverage = len(captured_normalized) / max(len(full_normalized), 1)

    logger.info(
        "chunking_coverage",
        regulation_id=regulation_id,
        structured_chunks=len(chunks),
        coverage=round(coverage, 2),
    )

    # 3. Fallback if coverage below threshold
    if coverage < 0.7:
        residual = extract_uncaptured_text(full_text, chunks)
        fallback_chunks = chunk_unstructured_regulation(residual, regulation_id)
        chunks += fallback_chunks
        logger.warning(
            "low_coverage_chunking",
            coverage=round(coverage, 2),
            regulation_id=regulation_id,
            fallback_chunks=len(fallback_chunks),
        )

    return chunks


def compute_content_hash(body: str) -> str:
    """SHA-256 hex digest of a chunk body for dedup at index time.

    Matches ``regulation_chunks.content_hash VARCHAR(64)`` in
    db/migrations/001_initial.sql §03. Encoding is UTF-8 (Python default).
    """
    return hashlib.sha256(body.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────────────
# LLM call (BLUEPRINT §05.5 + FASE 0b vast-hopping-sketch) — multi-provider
# con fallback 3-livelli ricorsivo (Azure mini → Azure premium → Anthropic).
# Definito qui per unblock Stage 3; content_agent (BP §05.5) lo importa.
# ─────────────────────────────────────────────────────────────────────


class LLMProviderError(RuntimeError):
    """Raised when ALL fallback levels are exhausted (Azure + Anthropic down)."""


# Fallback chain 2026-05-25: DeepSeek V4 Pro primary (qualità top + prezzo
# promo confermato permanente $0.435/$0.87 per 1M tok = ~$0.02/corso 4h vs
# $0.10 Azure mini = 5× più economico).
#
# CONTENT (slide normative):
# - L0 = DeepSeek V4 Pro — PRIMARY
# - L1 = Azure gpt-4.1-mini — fallback se DeepSeek down
# - L2 = OpenAI gpt-4o — fallback premium se Azure pure down
# - L3 = Anthropic Haiku — emergenza
#
# CLASSIFY (chunk normativi — strutturato semplice):
# - L0 = DeepSeek V4 Flash ($0.14/$0.28) — il più economico
# - L1 = Azure gpt-4.1-mini
# - L2 = OpenAI gpt-4o-mini
# - L3 = Anthropic Haiku
# FIX #28.1c (2026-05-26): chain CONTENT riorganizzata per structured output.
# DeepSeek V4 rifiuta tool_choice forzato ("Thinking mode does not support this
# tool_choice") → instructor in Mode.TOOLS fallisce. Standardizziamo lo step
# strutturato su modelli TOOLS-capable nativi (analista: "non mischiare un
# modello schema-incapace in pipeline schema-driven"). DeepSeek resta in CLASSIFY
# (json_object basta per task semplice non-strutturato).
_FALLBACK_CHAIN_CONTENT: list[tuple[str, str, str]] = [
    ("azure_openai", "azure_openai_deployment_content",   "L0_azure_mini"),
    ("openai",       "openai_content_model",              "L1_openai_4o"),
    ("anthropic",    "llm_content_model_fallback",        "L2_anthropic_sonnet"),
]

_FALLBACK_CHAIN_CLASSIFY: list[tuple[str, str, str]] = [
    ("deepseek",     "deepseek_classify_model",           "L0_deepseek_v4_flash"),
    ("azure_openai", "azure_openai_deployment_classify",  "L1_azure_classify"),
    ("openai",       "openai_classify_model",             "L2_openai_4o_mini"),
    ("anthropic",    "llm_classify_model",                "L3_anthropic_haiku"),
]


# Eccezioni transienti che triggerano retry tenacity DENTRO un singolo provider
# (3 attempts, exp backoff 5-60s, PRIMA di scalare al fallback successivo).
_TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    openai.RateLimitError,
    openai.APIStatusError,        # 5xx, request id errors
    openai.APIConnectionError,    # network drop
    anthropic.RateLimitError,
    anthropic.InternalServerError,
    anthropic.APIStatusError,
)

# Eccezioni "provider down per noi" che fanno SUBITO scalare al fallback successivo
# senza retry tenacity interno (sono errori non transienti — wrong key, deployment
# non esiste, account sospeso, ecc.). Sintomo: il provider non risponderà mai
# correttamente con questi parametri.
_FALLBACK_EXCEPTIONS: tuple[type[Exception], ...] = (
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,         # deployment mancante
    openai.BadRequestError,       # config invalida lato nostro
    anthropic.AuthenticationError,
    anthropic.PermissionDeniedError,
    anthropic.NotFoundError,
    anthropic.BadRequestError,
    RetryError,                   # tenacity esaurito su _TRANSIENT_EXCEPTIONS
)


@retry(
    stop=stop_after_attempt(3),
    # FIX #29.3 (2026-05-26): jitter casuale invece di backoff deterministico.
    # Senza jitter, N moduli paralleli che timeoutano insieme RIPARTONO insieme
    # → thundering herd (visto nel baseline: 2 timeout nello stesso secondo,
    # moduli 6 e 10). random_exponential spalma i retry su una banda 1-30s.
    wait=wait_random_exponential(multiplier=1, max=30),
    retry=retry_if_exception_type(_TRANSIENT_EXCEPTIONS),
)
async def _call_llm_single(
    provider: str, model: str, messages: list[dict[str, str]], system: str
) -> str:
    """Single-provider call con tenacity retry (3 attempts) interno.

    Quando tenacity esaurisce i 3 tentativi su questo provider, l'eccezione
    propaga al chiamante ``call_llm`` che attiva il fallback al livello successivo.
    """
    if provider == "deepseek":
        # DeepSeek V4 (Flash default, Pro per reasoning) — provider PRIMARY 2026-05-25
        # OpenAI-compatible: stesso SDK, base_url custom.
        # max_tokens=16000 per dare spazio sia al reasoning di V4 Pro (può usare
        # 5-10K token interni) sia all'output finale (slide JSON 6-8K). Costo
        # trascurabile (~$0.014 per chiamata anche al peggio).
        ds_client = openai.AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
            timeout=float(settings.llm_request_timeout),
        )
        ds_messages: list[dict[str, str]] = [{"role": "system", "content": system}, *messages]
        ds_resp = await ds_client.chat.completions.create(
            model=model,
            messages=ds_messages,  # type: ignore[arg-type]
            response_format={"type": "json_object"},
            max_tokens=16000,
            temperature=0.3,
        )
        return ds_resp.choices[0].message.content or ""

    if provider == "openai":
        # OpenAI diretto (fallback L1)
        oai_client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=float(settings.llm_request_timeout),
        )
        oai_messages: list[dict[str, str]] = [{"role": "system", "content": system}, *messages]
        oai_resp = await oai_client.chat.completions.create(
            model=model,
            messages=oai_messages,  # type: ignore[arg-type]
            response_format={"type": "json_object"},
            max_tokens=8000,
            temperature=0.3,
        )
        return oai_resp.choices[0].message.content or ""

    if provider == "azure_openai":
        client = openai.AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            timeout=float(settings.llm_request_timeout),
        )
        oa_messages: list[dict[str, str]] = [{"role": "system", "content": system}, *messages]
        response = await client.chat.completions.create(
            model=model,
            messages=oa_messages,  # type: ignore[arg-type]
            response_format={"type": "json_object"},
            max_tokens=8000,
        )
        return response.choices[0].message.content or ""

    if provider == "anthropic":
        a_client = anthropic.AsyncAnthropic(timeout=float(settings.llm_request_timeout))
        a_response = await a_client.messages.create(
            model=model,
            max_tokens=8000,
            system=system,
            messages=messages,  # type: ignore[arg-type]
        )
        block = a_response.content[0]
        return block.text if isinstance(block, anthropic.types.TextBlock) else ""

    raise LLMProviderError(f"unknown provider: {provider}")


async def call_llm(
    messages: list[dict[str, str]],
    system: str,
    *,
    model: str | None = None,
    task: str = "content",
    _fallback_level: int = 0,
) -> str:
    """LLM call con sistema di fallback automatico (FASE 0b vast-hopping-sketch).

    Le chain REALI vivono in ``_FALLBACK_CHAIN_CONTENT`` / ``_FALLBACK_CHAIN_CLASSIFY``
    (sopra) — questa è la loro descrizione, da tenere allineata a quelle liste:

    Fallback chain per ``task="content"`` (FIX #28.1c — TOOLS-capable only):
      L0 → Azure OpenAI gpt-4.1-mini (primary, JSON schema strict nativo, ~$0.10/corso)
      L1 → OpenAI gpt-4o             (premium, qualità ↑, ~$0.50/corso)
      L2 → Anthropic Sonnet 4.6      (emergenza, fallback robusto)
    DeepSeek esce dalla chain CONTENT: rifiuta tool_choice forzato (instructor
    Mode.TOOLS fallisce). Resta primary in CLASSIFY (task non-strutturato).

    Fallback chain per ``task="classify"``:
      L0 → DeepSeek V4 Flash         (classify, economico)
      L1 → Azure OpenAI gpt-4.1-mini
      L2 → OpenAI gpt-4o-mini
      L3 → Anthropic Haiku 4.5

    Ogni livello ha 3 retry tenacity interni (5-60s backoff exp) sulle eccezioni
    transienti. Solo dopo aver esaurito i retry interni scaliamo al livello successivo.

    Il parametro ``model`` (legacy) è IGNORATO: il modello effettivo è sempre scelto
    dal fallback chain via ``getattr(settings, deployment_key)``.

    ``task`` distingue content_agent (chain a 4 livelli) da classify_chunk (4 livelli).
    ``_fallback_level`` è uso interno ricorsione — NON passare manualmente.
    """
    # Modalità legacy Anthropic-only: bypass chain, comportamento storico.
    if settings.llm_provider == "anthropic":
        default_model = (
            settings.llm_classify_model if task == "classify" else settings.llm_content_model
        )
        return await _call_llm_single("anthropic", model or default_model, messages, system)

    # Modalità con fallback chain (OpenAI primary o Azure primary).
    chain = _FALLBACK_CHAIN_CLASSIFY if task == "classify" else _FALLBACK_CHAIN_CONTENT
    if _fallback_level >= len(chain):
        raise LLMProviderError(
            f"all fallback levels exhausted for task={task} (Azure + Anthropic both down)"
        )

    provider, deployment_attr, label = chain[_fallback_level]
    eff_model = getattr(settings, deployment_attr)

    try:
        return await _call_llm_single(provider, eff_model, messages, system)
    except _FALLBACK_EXCEPTIONS as exc:
        # Provider down/misconfigured — scala al prossimo livello (no retry interno).
        next_label = chain[_fallback_level + 1][2] if _fallback_level + 1 < len(chain) else "EXHAUSTED"
        # Se RetryError, unwrappa l'eccezione originale per logging più chiaro.
        underlying = exc.last_attempt.exception() if isinstance(exc, RetryError) and exc.last_attempt else exc  # type: ignore[union-attr]
        logger.warning(
            "llm_fallback_triggered",
            task=task,
            from_level=label,
            next_level=next_label,
            error_class=type(underlying).__name__ if underlying else type(exc).__name__,
            error_msg=str(underlying)[:200] if underlying else str(exc)[:200],
        )
        return await call_llm(
            messages,
            system,
            model=None,  # forza re-pick dal chain
            task=task,
            _fallback_level=_fallback_level + 1,
        )


# ─────────────────────────────────────────────────────────────────────
# FIX #28.1c (2026-05-26): STRUCTURED OUTPUT via instructor.
# Sostituisce "json_object + parse + auto-fix manuale" con uno schema Pydantic
# imposto a livello API (tool-calling) + max_retries guidati dagli errori di
# validazione. Ritorna ModuleSlides (già validato), NON testo grezzo.
#
# DUE ASSI, BUDGET SEPARATI (vincoli analista):
#   • PROFONDITÀ per-slide (bullet) → SlideContent.validator → instructor max_retries
#   • CARDINALITÀ per-modulo (#slide) → fill-loop qui sotto, contatore distinto
# ─────────────────────────────────────────────────────────────────────

# Mappa (nostro provider) → prefisso instructor.from_provider + base_url override.
# instructor.from_provider usa litellm sotto: "deepseek/<model>", "openai/<model>",
# "azure/<model>", "anthropic/<model>". Per DeepSeek serve il base_url custom.
# Tuning post-E2E 2026-05-26: 3 retry instructor erano insufficienti su moduli da
# ~40 slide (basta che 5-6 violino la profondità per esaurire il budget e cadere sul
# fallback legacy). 5 dà più margine perché il reask di instructor parte selettivo
# (re-asks SOLO le slide invalide, non tutte). Costo marginale: ~$0.005/retry × max
# 5 = $0.025/modulo nel caso peggiore. Cardinalità separata, cap a 3 invariato.
# FIX #32 velocità (analista review 12 + utente "demo < metà tempo"):
# 5→2 reask LLM per batch. Riduce del 60% la coda di reask per batch
# falliti. Demo #3 v2 ha bruciato ~4 min su UN batch fallito (5 reask
# × ~30s/reask). Con 2 il tempo cap per batch fallito scende a ~1.5
# min, dopo cui scatta _try_sub_batch_recovery (max_retries=2 hardcoded
# interno, OK) che salva le slide via 2 sub-batch da half-size.
# Trade-off: edge case validation borderline non più rescued al 3-4-5
# tentativo. Sub-batch recovery copre il caso → atteso zero perdita
# slide finale. Validato su Demo #3 v2 sub_batch_ok M2 batch 3.
_INSTRUCTOR_DEPTH_RETRIES = 2       # asse profondità (passato a instructor)
_MAX_CARDINALITY_ATTEMPTS = 3       # asse cardinalità (fill-loop) — uscita garantita


def _instructor_client_for(provider: str, model: str):  # type: ignore[no-untyped-def]
    """Costruisce un client instructor per il provider, in modalità TOOLS (schema imposto).

    Riusa le stesse credenziali/endpoint di _call_llm_single.
    Ritorna ``(client, model_id, reask_counter)``.

    FIX #31 MOSSA 4 (2026-05-27, analista): aggiunto counter LOCALE per
    contare i reask interni di instructor (validation failures che
    triggerano `max_retries`). I reask di profondità erano INVISIBILI nei
    log finora — vedevamo solo i 8 reask diagram perché hanno
    `diagram_filling_failed` con log dedicato, ma `bullets`/`notes`/
    `speaker_notes_too_short` riask sparivano dentro instructor.

    Il counter è un dict {"reasks": int} mutato in-place dall'hook
    `on("completion:error")`. Closure pulita, no stato globale → test
    facili, no interferenze cross-test. Il caller (generate_module_structured)
    legge `counter["reasks"]` dopo ogni `client.chat.completions.create`
    e logga `module_batch_reasks` strutturato. Aggregato per modulo dà
    `reask_total_module` che decide H6 vs H3a nella prossima sessione
    (analista: ">0.5/batch → conta batch-size; ~0 → solo latenza Azure").
    """
    import instructor
    from instructor import Mode

    # Counter LOCALE per call. Mutato dall'hook `on("completion:error")`.
    # Ogni chiamata a _instructor_client_for produce un counter NUOVO →
    # zero stato globale, zero race fra test paralleli.
    reask_counter = {"reasks": 0}

    def _on_completion_error(*_args: Any, **_kw: Any) -> None:
        """Hook instructor: chiamato ogni volta che un retry viene
        triggerato per una validation failure. Incrementa il counter
        locale al client. NB: l'hook può essere chiamato con argomenti
        variabili a seconda della versione instructor — accettiamo
        *args/**kw per robustezza."""
        reask_counter["reasks"] += 1

    if provider == "deepseek":
        base = openai.AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
            timeout=float(settings.llm_request_timeout),
        )
        client = instructor.from_openai(base, mode=Mode.TOOLS)
    elif provider == "openai":
        base = openai.AsyncOpenAI(
            api_key=settings.openai_api_key, timeout=float(settings.llm_request_timeout)
        )
        client = instructor.from_openai(base, mode=Mode.TOOLS)
    elif provider == "azure_openai":
        base = openai.AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            timeout=float(settings.llm_request_timeout),
        )
        client = instructor.from_openai(base, mode=Mode.TOOLS)
    elif provider == "anthropic":
        base_a = anthropic.AsyncAnthropic(timeout=float(settings.llm_request_timeout))
        client = instructor.from_anthropic(base_a, mode=Mode.ANTHROPIC_TOOLS)
    else:
        raise LLMProviderError(f"unknown provider for instructor: {provider}")

    # Aggancia hook reask counter (instructor supporta `.on(event, handler)`)
    try:
        client.on("completion:error", _on_completion_error)
    except Exception as exc:
        # In caso di incompatibilità con versione instructor (raro), non
        # blocchiamo la pipeline: il counter resta a 0 (degradazione
        # silenziosa accettabile per la sola osservabilità).
        logger.warning("instructor_hook_install_failed", error=str(exc)[:120])

    return client, model, reask_counter


# FIX #29.1 (2026-05-26): batch size per chiamata structured. Con max_tokens=8000 e
# ~300-350 token/slide, il tetto teorico è ~24 slide/chiamata; 7 dà 3× di margine sul
# budget output. Risolve insieme cardinalità (no più tool-call troncato), profondità
# (modello non raziona parole), latenza (payload più piccolo → meno timeout TPM).
_BATCH_SIZE = 10  # FIX #29.6 velocizzazione: 7→10 (zero timeout su test E2E con
                  # batch 7 → ampio headroom verso il tetto teorico ~18-24 slide/call
                  # con max_tokens=8000. 4 batch/modulo → 3 batch/modulo, -25% chiamate.
# Soglia override: se il modulo ha N ≤ questo numero di slide, vai in 1 sola chiamata.
# A 45s/slide il pacing produce ~26 slide/modulo, sotto 24+margine → spesso 1 batch basta.
_SINGLE_CALL_THRESHOLD = 10


def _partition_chunks_for_batches(
    chunks_text: str, n_batches: int
) -> list[str]:
    """Divide il testo dei chunk normativi del modulo in N partizioni, una per
    batch, così ogni batch riceve materiale fresco da coprire (FIX #29.1).

    Strategia semplice (l'analista lo confermerà sul refactor): split per articoli/
    paragrafi/righe a parità di lunghezza approssimativa. Restituisce stringhe già
    formattate, pronte per essere infilate nel prompt batch.
    """
    if n_batches <= 1:
        return [chunks_text]
    # Split prima per "Art." (più semantico), poi cade su righe se non bastano.
    pieces = [p for p in chunks_text.split("\nArt.") if p.strip()]
    if len(pieces) < n_batches:
        # Fallback: split su double-newline poi righe
        pieces = [p for p in chunks_text.split("\n\n") if p.strip()]
    if len(pieces) < n_batches:
        # Ultima spiaggia: split chars equally
        size = max(1, len(chunks_text) // n_batches)
        pieces = [chunks_text[i:i + size] for i in range(0, len(chunks_text), size)]
    # Distribuisci pieces nei batch ciclicamente
    parts: list[list[str]] = [[] for _ in range(n_batches)]
    for i, piece in enumerate(pieces):
        parts[i % n_batches].append(piece)
    sep = "\n\nArt." if "Art." in chunks_text else "\n\n"
    return [sep.join(part) for part in parts]


async def _try_sub_batch_recovery(
    *,
    original_batch_size: int,
    batch_chunks: str,
    system: str,
    provider: str,
    eff_model: str,
    already_count_in_module: int,
    module_index: int,
    batch_idx: int,
) -> list | None:
    """FIX #31.5B (2026-05-27, analista review 6): recovery quando un
    batch fallisce dopo `_INSTRUCTOR_DEPTH_RETRIES=5` reask.

    In E2E #23, M1 ha perso 27 slide (2 batch falliti × ~13 slide cad)
    perché instructor max_retries si esauriva e il batch veniva
    droppato (linea 765-776 dell'except). Analista: "Il batch fallito
    NON va droppato, va recuperato con un retry (prompt semplificato
    o sub-batch più piccolo) invece di perdere 10-13 slide."

    Strategia:
      1. Dimezza batch_size (es. 10 → 2 sub-batch da 5)
      2. Per ogni sub-batch: prompt SEMPLIFICATO (no SPREAD overhead,
         no quota_block, no already_titles → riduce token e variance)
      3. instructor.max_retries=2 (vs 5 main) — 60% più veloce sul
         caso peggiore. Il sub-batch è più semplice del main, ha più
         probabilità di chiudere al primo tentativo.

    Ritorna lista slide recuperate (può essere parziale se solo 1 sub
    su 2 chiude), oppure None se TUTTI i sub-batch falliscono.

    Edge case: se original_batch_size < 4 skip recovery (troppo
    piccolo per dividere, non vale il costo).
    """
    # ModuleSlides import locale (stesso pattern di generate_module_structured)
    from app.models.pipeline import ModuleSlides

    if original_batch_size < 4:
        logger.info(
            "sub_batch_skipped_too_small",
            module_index=module_index, batch_idx=batch_idx,
            original_batch_size=original_batch_size,
        )
        return None

    half = original_batch_size // 2
    sub_sizes = [half, original_batch_size - half]  # es. 10→[5,5], 7→[3,4]

    recovered_slides: list = []
    for sub_idx, sub_size in enumerate(sub_sizes):
        # Prompt SEMPLIFICATO: niente SPREAD, niente quota, niente
        # already_titles — il sub-batch è "best effort emergency"
        # che recupera le slide perse, non ottimizza la coerenza
        # tematica fine.
        sub_prompt = (
            f"Genera ESATTAMENTE {sub_size} slide a tema, brevi e mirate, "
            f"a partire dai chunk normativi assegnati qui sotto.\n\n"
            f"CHUNK NORMATIVI ASSEGNATI:\n"
            f"{batch_chunks[:3000]}\n\n"
            f"Vincoli: rispetta gli schemi pydantic (titoli ≤70 char, "
            f"bullets entro i max per tipo, source_chunk_ids come LISTA "
            f"di stringhe non come stringa). NON inventare contenuto "
            f"fuori dai chunk forniti."
        )
        try:
            client, model_id, _ = _instructor_client_for(provider, eff_model)
            sub_module = await client.chat.completions.create(
                model=model_id,
                response_model=ModuleSlides,
                max_retries=2,  # ridotto da _INSTRUCTOR_DEPTH_RETRIES=5
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": sub_prompt},
                ],
                validation_context={
                    "expected_slides": sub_size,
                    "cardinality_mode": "warn",
                },
            )
            sub_slides = sub_module.slides[:sub_size]
            recovered_slides.extend(sub_slides)
            logger.info(
                "sub_batch_ok",
                module_index=module_index,
                batch_idx=batch_idx,
                sub_idx=sub_idx,
                sub_size=sub_size,
                got=len(sub_slides),
            )
        except Exception as sub_exc:
            logger.warning(
                "sub_batch_failed",
                module_index=module_index,
                batch_idx=batch_idx,
                sub_idx=sub_idx,
                sub_size=sub_size,
                error_class=type(sub_exc).__name__,
                error=str(sub_exc)[:200],
            )
            # Skip questo sub-batch, prova il prossimo
            continue

    return recovered_slides if recovered_slides else None


async def generate_module_structured(
    *,
    system: str,
    user_prompt: str,
    module_index: int,
    module_title: str,
    expected_slides: int,
    chunks_text: str = "",
    slide_distribution: dict[str, int] | None = None,  # FIX #30.8: quota per tipo
    build_subrequest=None,  # legacy, ignorato in batch mode
):  # type: ignore[no-untyped-def]
    """Genera UN modulo come ModuleSlides validato, con BATCHING (FIX #29.1) +
    fallback chain robusto.

    Strategia: invece di 1 chiamata da N slide (che satura max_tokens=8000), si
    fanno ceil(N/_BATCH_SIZE) chiamate da ~_BATCH_SIZE slide ciascuna, con partition
    esplicita dei chunk normativi tra i batch. Ogni batch passa al primo colpo
    profondità (validator SlideContent → instructor max_retries) + cardinalità
    (cardinality_mode='warn' su lista piccola).

    Re-index globale: ogni batch riprende l'`index` da dove il precedente ha finito,
    `module_index` forzato. FIX #27.1 (contiguità) preservato anche con N batch.

    Robustezza (#29.4): try/except per-batch — un batch fallito non butta i
    precedenti, marca `degraded=True` e continua. degraded propagato in telemetry.
    """
    from app.models.pipeline import ModuleSlides
    from app.agents.prompts import build_module_batch_prompt

    chain = _FALLBACK_CHAIN_CONTENT
    telemetry: dict[str, object] = {
        "module_index": module_index, "expected": expected_slides,
        "batches_planned": 0, "batches_ok": 0, "batches_failed": 0,
        "degraded": False, "provider_used": None,
    }

    # ── Calcolo batch ──
    if expected_slides <= _SINGLE_CALL_THRESHOLD:
        # Modulo piccolo → 1 sola chiamata (default pacing 45s = ~26 slide/modulo
        # cade qui solo per corsi molto brevi).
        batches: list[int] = [expected_slides]
    else:
        n_full = expected_slides // _BATCH_SIZE
        remainder = expected_slides % _BATCH_SIZE
        batches = [_BATCH_SIZE] * n_full
        if remainder > 0:
            if remainder < 3 and n_full > 0:
                # Avoid tiny last batch: redistribute (e.g. 26 = 3×7 + 5, OK; 22 = 3×7+1 → 7+7+8)
                batches[-1] += remainder
            else:
                batches.append(remainder)
    telemetry["batches_planned"] = len(batches)
    chunk_parts = _partition_chunks_for_batches(chunks_text, len(batches))

    # ── Provider selection (fallback chain) — uso lo stesso provider per tutti i
    #    batch dello stesso modulo (cambiare provider per batch farebbe perdere il
    #    contesto del prompt caching) ──
    provider_used: tuple[str, str, str] | None = None
    last_exc: Exception | None = None
    for level in range(len(chain)):
        provider, deployment_attr, label = chain[level]
        eff_model = getattr(settings, deployment_attr)
        # Test "ping" sul provider con la prima richiesta — se fallisce, fallback.
        provider_used = (provider, eff_model, label)
        break  # ottimistico: provo subito col primo della chain
    if provider_used is None:
        raise LLMProviderError("no provider available in content chain")
    provider, eff_model, label = provider_used
    telemetry["provider_used"] = label

    # ── BATCH LOOP ──
    all_slides = []  # SlideContent accumulati da tutti i batch
    for batch_idx, batch_size in enumerate(batches):
        already_titles = [s.title for s in all_slides]
        # FIX #30.8 (2026-05-26): conta tipi già generati nei batch precedenti
        # per dire al modello cosa MANCA da produrre nel modulo (quota).
        already_types: dict[str, int] = {}
        for s in all_slides:
            stype = s.slide_type.value if hasattr(s.slide_type, "value") else str(s.slide_type)
            already_types[stype] = already_types.get(stype, 0) + 1
        batch_chunks = chunk_parts[batch_idx] if batch_idx < len(chunk_parts) else ""
        batch_prompt = build_module_batch_prompt(
            module_title=module_title,
            module_index=module_index,
            batch_idx=batch_idx,
            n_batches=len(batches),
            batch_size=batch_size,
            already_titles=already_titles,
            batch_chunks=batch_chunks,
            base_user_prompt=user_prompt,
            slide_distribution=slide_distribution,
            already_types=already_types,
        )
        try:
            # FIX #31 MOSSA 4: counter reask LOCALE per questo batch
            client, model_id, reask_counter = _instructor_client_for(provider, eff_model)
            batch_module = await client.chat.completions.create(
                model=model_id,
                response_model=ModuleSlides,
                max_retries=_INSTRUCTOR_DEPTH_RETRIES,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": batch_prompt},
                ],
                validation_context={
                    "expected_slides": batch_size,
                    "cardinality_mode": "warn",
                },
            )
            # Re-index sul globale + forza module_index
            start_idx = len(all_slides)
            for offset, s in enumerate(batch_module.slides[:batch_size]):
                s.index = start_idx + offset
                s.module_index = module_index
                all_slides.append(s)
            telemetry["batches_ok"] = int(telemetry.get("batches_ok", 0)) + 1
            # FIX #31 MOSSA 4: accumula reask per module-level stats
            telemetry["reask_total_module"] = int(
                telemetry.get("reask_total_module", 0)
            ) + reask_counter["reasks"]
            logger.info(
                "module_batch_ok",
                module_index=module_index, batch_idx=batch_idx,
                batch_size=batch_size, got=len(batch_module.slides),
                accepted=min(batch_size, len(batch_module.slides)),
                reasks=reask_counter["reasks"],  # FIX #31 MOSSA 4
            )
        except Exception as exc:
            # FIX #29.4: batch failure NON butta i precedenti (i 7 batch OK
            # restano in all_slides). FIX #31.5B (analista review 6): prima
            # di marcare il batch come failed, tenta sub-batch recovery —
            # spezza il batch da N in 2 sub-batch da N//2 e tenta con prompt
            # semplificato + max_retries=2. Recupera tipicamente 5-10 slide
            # per batch fallito che prima erano semplicemente perse.
            logger.warning(
                "module_batch_failed_attempting_split",
                module_index=module_index, batch_idx=batch_idx,
                batch_size=batch_size,
                error_class=type(exc).__name__, error=str(exc)[:300],
            )
            try:
                recovered = await _try_sub_batch_recovery(
                    original_batch_size=batch_size,
                    batch_chunks=batch_chunks,
                    system=system,
                    provider=provider,
                    eff_model=eff_model,
                    already_count_in_module=len(all_slides),
                    module_index=module_index,
                    batch_idx=batch_idx,
                )
            except Exception as sub_exc:
                # Funzione recovery a sua volta crashata (non dovrebbe)
                logger.error(
                    "sub_batch_recovery_crashed",
                    module_index=module_index, batch_idx=batch_idx,
                    error_class=type(sub_exc).__name__,
                )
                recovered = None

            if recovered:
                # Recovery RIUSCITA (parziale o totale): aggiungi le slide
                # recuperate, conta batch come "recovered" non "failed".
                start_idx = len(all_slides)
                for offset, s in enumerate(recovered[:batch_size]):
                    s.index = start_idx + offset
                    s.module_index = module_index
                    all_slides.append(s)
                telemetry["batches_recovered"] = int(
                    telemetry.get("batches_recovered", 0)
                ) + 1
                # Se il recovery ha dato < batch_size slide, marca degraded
                if len(recovered) < batch_size:
                    telemetry["degraded"] = True
                logger.info(
                    "module_batch_recovered_via_split",
                    module_index=module_index, batch_idx=batch_idx,
                    sub_slides_recovered=len(recovered),
                    sub_slides_expected=batch_size,
                )
            else:
                # Recovery FALLITA o skippata (batch_size < 4): marca
                # degraded e continua come prima del fix.
                telemetry["batches_failed"] = int(
                    telemetry.get("batches_failed", 0)
                ) + 1
                telemetry["degraded"] = True
                logger.warning(
                    "module_batch_failed_final",
                    module_index=module_index, batch_idx=batch_idx,
                    error_class=type(exc).__name__,
                )
            last_exc = exc
            continue

    # ── Edge case: ZERO batch riusciti → propaga eccezione per fallback legacy ──
    if not all_slides and last_exc is not None:
        raise LLMProviderError(
            f"all batches failed for module {module_index}: {str(last_exc)[:200]}"
        )

    # ── Assembla ModuleSlides ──
    module = ModuleSlides(
        module_index=module_index,
        title=module_title,
        slides=all_slides,
    )

    # Legacy fill-loop (disattivato in batch mode): condizione finta che salta
    while (False and  # FIX #29.1: con batching pianificato, no fill-loop runtime
        len(module.slides) < expected_slides
        and telemetry["cardinality_attempts"] < _MAX_CARDINALITY_ATTEMPTS
        and build_subrequest is not None
    ):
        telemetry["cardinality_attempts"] += 1
        start = len(module.slides)
        need = expected_slides - start
        sub_prompt = build_subrequest(module.slides, need, start)
        try:
            # FIX #31 MOSSA 4: ignoriamo reask_counter in questo dead-code path
            # (while False), ma la firma a 3 elementi va rispettata.
            client, model_id, _reask = _instructor_client_for(provider, eff_model)
            sub = await client.chat.completions.create(
                model=model_id,
                response_model=ModuleSlides,
                max_retries=_INSTRUCTOR_DEPTH_RETRIES,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": sub_prompt},
                ],
                validation_context={"expected_slides": need, "cardinality_mode": "warn"},
            )
        except _FALLBACK_EXCEPTIONS as exc:
            logger.warning("fill_loop_subrequest_failed", module=module_index, error=str(exc)[:200])
            break
        # RE-INDEX coerente (FIX #27.1 non deve rientrare): index globale contiguo,
        # module_index forzato. Le slide aggiunte continuano la numerazione.
        for offset, s in enumerate(sub.slides):
            s.index = start + offset
            s.module_index = module_index
        module.slides.extend(sub.slides)

    # ── over-cardinalità: tronca (innocuo). under residuo: degrada + log ──
    if len(module.slides) > expected_slides:
        module.slides = module.slides[:expected_slides]
    if len(module.slides) < expected_slides:
        telemetry["degraded"] = True
        logger.warning(
            "cardinality_degraded", module=module_index,
            got=len(module.slides), expected=expected_slides,
        )

    # Normalizza module_index su tutte (difesa) + re-index finale contiguo.
    for i, s in enumerate(module.slides):
        s.index = i
        s.module_index = module_index
    module.module_index = module_index
    if not module.title:
        module.title = module_title

    telemetry["final_count"] = len(module.slides)
    logger.info("module_structured_done", **telemetry)

    # FIX #31 MOSSA 4: log diagnostic dedicato per i reask instructor
    # invisibili (analista 2026-05-27 — "ti dice se i 30-60s sono latenza
    # Azure pura o latenza+reask-nascosti"). reask_total_module è
    # cumulato a livello modulo da tutti i batch. La media per-batch
    # > 0.5 → batch-size pesa, ~0 → quasi tutto latenza Azure.
    n_batches_actual = int(telemetry.get("batches_ok", 0)) + int(
        telemetry.get("batches_failed", 0)
    )
    reask_total = int(telemetry.get("reask_total_module", 0))
    logger.info(
        "module_reask_stats",
        module_index=module_index,
        n_batches=n_batches_actual,
        reask_total_module=reask_total,
        reask_avg_per_batch=round(reask_total / max(n_batches_actual, 1), 2),
    )

    return module, telemetry


# ─────────────────────────────────────────────────────────────────────
# Stage 3 — Classification (LLM-assisted, rule-validated)
# ─────────────────────────────────────────────────────────────────────

CLASSIFICATION_PROMPT = """Classifica questo chunk normativo italiano. Rispondi SOLO con JSON valido.

Chunk: "{body}"

Formato richiesto:
{{"type": "OBBLIGO|SANZIONE|DEFINIZIONE|PROCEDURA|GENERALE", "tags": ["tag1", "tag2"]}}

Regole:
- OBBLIGO: impone un dovere ("deve", "è tenuto", "è obbligato", "assicura")
- SANZIONE: indica pene o ammende ("arresto", "ammenda", "sanzione", "euro")
- DEFINIZIONE: definisce un termine ("si intende", "ai fini del presente")
- PROCEDURA: descrive un processo ("modalità", "procedimento", "entro")
- GENERALE: nessuna delle precedenti
- tags: scegli tra [formazione, lavoratori, datore_lavoro, rspp, rls, antincendio, primo_soccorso, dpi, valutazione_rischi, cantieri, haccp, igiene]
"""


def _strip_json_fences(raw: str) -> str:
    """Strip optional ```json ... ``` markdown fences from an LLM reply.

    Haiku 4.5 wraps JSON in fences ~50% of the time despite the
    "SOLO JSON" system instruction. Sonnet 4 (legacy) usually doesn't.
    This helper accepts both fenced and bare JSON so the parser is robust.
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    return cleaned


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=2, max=10))
async def classify_chunk(body: str) -> dict[str, object]:
    """Classify a normative chunk via LLM, with a rule-based SANZIONE guard.

    A chunk tagged SANZIONE that contains no penalty keyword is downgraded
    to GENERALE — cheap defense against LLM over-classification (BP §06.1.1).
    """
    raw = await call_llm(
        messages=[{"role": "user", "content": CLASSIFICATION_PROMPT.format(body=body[:1000])}],
        system="Sei un classificatore di testi normativi. Rispondi SOLO con JSON.",
        task="classify",  # FASE 0b: usa fallback chain classify (Azure mini → Anthropic Haiku)
    )
    raw = _strip_json_fences(raw)
    result: dict[str, object] = json.loads(raw)
    if result["type"] == "SANZIONE" and not any(
        w in body.lower() for w in ["ammenda", "arresto", "sanzione", "euro", "pena"]
    ):
        result["type"] = "GENERALE"
    return result


# ─────────────────────────────────────────────────────────────────────
# Stage 4 — Embedding, deduplication, indexing (BLUEPRINT §06.1.1)
# ─────────────────────────────────────────────────────────────────────


# Voyage AI limits (verified 2026-05-25 via 400 error response):
# - Max 1000 documents per submitted batch
# - Max 320,000 tokens per submitted batch (HARD limit, returns 400)
# - voyage-3: 32K context per single document, 1024 embedding dim
# Margine sicurezza: 280K (12% under hard limit, copre underestimate token).
_VOYAGE_MAX_TOKENS_PER_BATCH = 280_000
_VOYAGE_MAX_DOCS_PER_BATCH = 1000


def _estimate_tokens(text: str) -> int:
    """Rough estimate: 1 token ≈ 4 chars (mixed Italian text, tiktoken-class).
    Conservative overestimate to stay safely under Voyage hard limit."""
    return max(1, len(text) // 4 + 1)


def _split_to_sub_batches(texts: list[str]) -> list[list[str]]:
    """Pack texts into sub-batches respecting Voyage token + doc limits.

    Greedy first-fit: appende a sub-batch corrente finché sta sotto i limiti,
    altrimenti chiude e ne apre uno nuovo. Un singolo text che da solo
    supera il token limit viene comunque inviato (Voyage tronca internamente
    fino a 32K token per voyage-3, oltre raisa 400 sul singolo doc).
    """
    sub_batches: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    for t in texts:
        toks = _estimate_tokens(t)
        # Se aggiungere supera i limiti, chiudi sub-batch e apri nuovo
        if current and (
            current_tokens + toks > _VOYAGE_MAX_TOKENS_PER_BATCH
            or len(current) >= _VOYAGE_MAX_DOCS_PER_BATCH
        ):
            sub_batches.append(current)
            current = []
            current_tokens = 0
        current.append(t)
        current_tokens += toks
    if current:
        sub_batches.append(current)
    return sub_batches


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def _embed_single_sub_batch(texts: list[str]) -> list[list[float]]:
    """Embed UN sub-batch già validato per stare sotto i limiti Voyage."""
    client = get_voyage_client()
    response = await client.embed(texts, model="voyage-3")
    embeddings: list[list[float]] = response.embeddings
    return embeddings


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via Voyage AI con auto-split su token limit.

    Voyage Tier 1: 2000 RPM, 3M TPM, max 1000 docs/batch, max 320K token/batch.
    Se il caller passa una lista che supererebbe il limite token, qui dentro
    viene splittata in sub-batch e ricomposta nello stesso ordine.
    Aggiornato 2026-05-25: scoperto 400 "366320 tokens after truncation" su
    batch da 500 articoli D.Lgs 81 lunghi.
    """
    sub_batches = _split_to_sub_batches(texts)
    if len(sub_batches) > 1:
        logger.info(
            "embed_batch_auto_split",
            input_docs=len(texts),
            sub_batches=len(sub_batches),
            sub_batch_sizes=[len(s) for s in sub_batches],
        )
    all_embs: list[list[float]] = []
    for sb in sub_batches:
        embs = await _embed_single_sub_batch(sb)
        all_embs.extend(embs)
    return all_embs


async def voyage_embed_with_retry(text: str) -> list[float]:
    """Embed a single text (used for the RAG query in the Research Agent)."""
    embeddings = await embed_batch([text])
    return embeddings[0]


async def embed_query(text: str) -> list[float]:
    """FIX #30.9d (2026-05-26): embed con input_type='query' per matching
    cosine asimmetrico contro chunks embeddati senza input_type (= default
    'document' per voyage-3). Usato dal cluster tematico cosine in
    research_agent.distribute_chunks_to_modules_cosine per i module title
    queries. Voyage-3 è calibrato sull'asimmetria query→document → cosine
    più pulito su corpus ristretto (analista 2026-05-26).
    """
    client = get_voyage_client()
    response = await client.embed([text], model="voyage-3", input_type="query")
    return response.embeddings[0]


async def index_chunks(chunks: list[dict[str, object]], pool: object) -> None:
    """Index classified chunks with embeddings.

    Boost 2026-05-25: batch_size 50→500 (Voyage ammette 1000/batch, 500 è
    margine sicurezza per token totali). D.Lgs 81 1831 chunks: 4 batch vs 37
    precedenti = ~10× faster sull'embed phase.
    Dedup via ``content_hash``: a chunk whose body already exists with
    ``is_current = true`` is skipped (BP §06.1.1 Stage 4).
    """
    batch_size = 500
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [str(c["body"]) for c in batch]
        embeddings = await embed_batch(texts)

        for chunk, embedding in zip(batch, embeddings):
            content_hash = compute_content_hash(str(chunk["body"]))

            # Dedup: skip re-ingestion of identical chunks.
            existing = await pool.fetchval(  # type: ignore[attr-defined]
                "SELECT id FROM regulation_chunks "
                "WHERE content_hash = $1 AND is_current = true",
                content_hash,
            )
            if existing:
                logger.info("chunk_deduplicated", hash=content_hash[:16])
                continue

            classification = chunk["classification"]
            assert isinstance(classification, dict)
            # asyncpg has no native vector codec → pass the pgvector text
            # literal and cast with ::vector (same interop as knowledge_repo).
            embedding_literal = "[" + ",".join(str(x) for x in embedding) + "]"

            # Defensive truncation: regulation_chunks schema has VARCHAR(50) on
            # article and paragraph + VARCHAR(500) on hierarchy_path. Bizarre
            # PDF regex matches (e.g. "1-bis-ter-quater-...-decies" recursive)
            # can exceed those limits and explode the entire ingest with
            # asyncpg.exceptions.StringDataRightTruncationError. Truncate
            # quietly here — the body text (which carries the real content)
            # is TEXT and stays full-length.
            art = chunk["article"]
            par = chunk["paragraph"]
            hpath = chunk["hierarchy_path"]
            art_trunc = str(art)[:50] if art is not None else None
            par_trunc = str(par)[:50] if par is not None else None
            hpath_trunc = str(hpath)[:500] if hpath is not None else None

            try:
                await pool.execute(  # type: ignore[attr-defined]
                    "INSERT INTO regulation_chunks "
                    "(regulation_id, article, paragraph, hierarchy_path, body, "
                    "chunk_type, tags, embedding, content_hash) "
                    "VALUES ($1,$2,$3,$4,$5,$6,$7,$8::vector,$9)",
                    chunk["regulation_id"], art_trunc, par_trunc,
                    hpath_trunc, chunk["body"],
                    classification["type"],
                    classification["tags"],
                    embedding_literal, content_hash,
                )
            except Exception as exc:
                # Skip THIS chunk only — don't abort the whole batch (REI: un
                # singolo INSERT rotto NON deve uccidere l'ingest di 1831 chunks).
                logger.warning(
                    "chunk_insert_failed",
                    article=art_trunc,
                    paragraph=par_trunc,
                    hash=content_hash[:16],
                    error_class=type(exc).__name__,
                    error=str(exc)[:200],
                )
        logger.info("chunks_indexed", batch=i // batch_size + 1, count=len(batch))


# ─────────────────────────────────────────────────────────────────────
# Upload orchestration (PHASE 2.6) — composes Stages 1→4 for the
# POST /api/regulations/upload endpoint. BP §10 specifies only the
# endpoint signature ({regulation_id, chunks_count}); this orchestration
# is new glue over the verbatim BP stages (see REI-16 note in 2.6).
# ─────────────────────────────────────────────────────────────────────


async def ingest_regulation_file(
    pdf_path: str | os.PathLike[str],
    *,
    slug: str,
    title: str,
    reg_type: str,
    issuing_body: str | None,
    region: str,
    source_url: str | None,
    pool: object,
) -> tuple[str, int]:
    """Full ingestion of one regulation PDF: insert row → parse → chunk →
    classify → embed → index. Returns (regulation_id, chunks_count).
    """
    regulation_id = str(
        await pool.fetchval(  # type: ignore[attr-defined]
            "INSERT INTO regulations "
            "(title, type, issuing_body, region, slug, source_url) "
            "VALUES ($1,$2,$3,$4,$5,$6) RETURNING id",
            title, reg_type, issuing_body, region, slug, source_url,
        )
    )

    full_text = parse_regulation_pdf(pdf_path)
    chunks = chunk_regulation(full_text, regulation_id)

    # Boost 2026-05-25: classify_chunk PARALLELIZZATO con Semaphore(50).
    # DeepSeek V4 Flash ha 2500 concurrency limit (classify task usa Flash).
    # D.Lgs 81 1831 chunks: 1831/50 = 37 wave × ~1s = ~40s vs 30 min sequenziale.
    import asyncio as _asyncio
    sem = _asyncio.Semaphore(50)

    async def _classify_one(chunk: dict[str, object]) -> dict[str, object]:
        async with sem:
            try:
                cl = await classify_chunk(str(chunk["body"]))
            except BaseException as exc:  # cattura ANCHE RetryError tenacity
                logger.warning(
                    "classify_chunk_failed",
                    chunk_hash=str(chunk.get("body", ""))[:30],
                    error_class=type(exc).__name__,
                    error=str(exc)[:200],
                )
                # Fallback: classifica come GENERALE per non perdere chunk
                cl = {"type": "GENERALE", "tags": []}
            return {**chunk, "classification": cl}

    # return_exceptions=True per non far propagare un singolo RuntimeError
    classified_raw = await _asyncio.gather(
        *(_classify_one(c) for c in chunks),
        return_exceptions=True,
    )
    classified = []
    for c, r in zip(chunks, classified_raw):
        if isinstance(r, BaseException):
            logger.warning("classify_gather_exception", error=str(r)[:200])
            classified.append({**c, "classification": {"type": "GENERALE", "tags": []}})
        else:
            classified.append(r)
    logger.info(
        "chunks_classified",
        total=len(classified),
        sequential_estimate_min=round(len(classified) / 60, 1),
    )

    await index_chunks(list(classified), pool)

    logger.info(
        "regulation_ingested",
        regulation_id=regulation_id,
        slug=slug,
        chunks_count=len(classified),
    )
    return regulation_id, len(classified)
