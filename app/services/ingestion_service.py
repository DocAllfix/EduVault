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
_FALLBACK_CHAIN_CONTENT: list[tuple[str, str, str]] = [
    ("deepseek",     "deepseek_content_model",            "L0_deepseek_v4_pro"),
    ("azure_openai", "azure_openai_deployment_content",   "L1_azure_mini"),
    ("openai",       "openai_content_model",              "L2_openai_4o"),
    ("anthropic",    "llm_classify_model",                "L3_anthropic_haiku"),
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
    wait=wait_exponential(multiplier=5, min=5, max=60),
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

    Fallback chain per ``task="content"`` (default):
      L0 → Azure OpenAI gpt-4.1-mini  (primary, ~$0.50/corso 4h)
      L1 → Azure OpenAI gpt-4o        (premium, 5× costo, qualità ↑)
      L2 → Anthropic Sonnet 4.6       (emergenza Azure-down)

    Fallback chain per ``task="classify"``:
      L0 → Azure OpenAI gpt-4.1-mini  (classify deployment)
      L1 → Anthropic Haiku 4.5        (emergenza, no Azure premium per task semplice)

    Ogni livello ha 3 retry tenacity interni (5-60s backoff exp) sulle eccezioni
    transienti. Solo dopo aver esaurito i retry interni scaliamo al livello successivo.

    Il parametro ``model`` (legacy) viene IGNORATO se ``llm_provider="azure_openai"``
    (il modello effettivo è scelto dal fallback chain). Quando
    ``llm_provider="anthropic"``, ``model`` mantiene il vecchio comportamento.

    ``task`` distingue content_agent (chain a 3 livelli) da classify_chunk (2 livelli).
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
