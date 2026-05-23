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
import pdfplumber
import structlog
from tenacity import (
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
# LLM call (BLUEPRINT §05.5) — defined here to unblock Stage 3 (see GAP
# note in the module docstring). FASE 3.4 imports this instead of
# redefining it.
# ─────────────────────────────────────────────────────────────────────


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=60),
    retry=retry_if_exception_type((
        anthropic.RateLimitError,
        anthropic.InternalServerError,
        anthropic.APIStatusError,
    )),
)
async def call_llm(messages: list[dict[str, str]], system: str) -> str:
    """LLM call with automatic retry on 429/500/529.

    The client is created inside the function, never as a global
    (BP §05.5). Timeout comes from settings (OPT-2) instead of the BP's
    hardcoded 120.0.
    """
    client = anthropic.AsyncAnthropic(timeout=float(settings.llm_request_timeout))
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=system,
        messages=messages,  # type: ignore[arg-type]
    )
    block = response.content[0]
    return block.text if isinstance(block, anthropic.types.TextBlock) else ""


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


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=2, max=10))
async def classify_chunk(body: str) -> dict[str, object]:
    """Classify a normative chunk via LLM, with a rule-based SANZIONE guard.

    A chunk tagged SANZIONE that contains no penalty keyword is downgraded
    to GENERALE — cheap defense against LLM over-classification (BP §06.1.1).
    """
    raw = await call_llm(
        messages=[{"role": "user", "content": CLASSIFICATION_PROMPT.format(body=body[:1000])}],
        system="Sei un classificatore di testi normativi. Rispondi SOLO con JSON.",
    )
    result: dict[str, object] = json.loads(raw)
    if result["type"] == "SANZIONE" and not any(
        w in body.lower() for w in ["ammenda", "arresto", "sanzione", "euro", "pena"]
    ):
        result["type"] = "GENERALE"
    return result


# ─────────────────────────────────────────────────────────────────────
# Stage 4 — Embedding, deduplication, indexing (BLUEPRINT §06.1.1)
# ─────────────────────────────────────────────────────────────────────


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts via Voyage AI (max 50 per batch, rate limit).

    Uses ``get_voyage_client()`` from dependencies.py — never a global
    (BP §06.1.1 Stage 4).
    """
    client = get_voyage_client()
    response = await client.embed(texts, model="voyage-3")
    embeddings: list[list[float]] = response.embeddings
    return embeddings


async def voyage_embed_with_retry(text: str) -> list[float]:
    """Embed a single text (used for the RAG query in the Research Agent)."""
    embeddings = await embed_batch([text])
    return embeddings[0]


async def index_chunks(chunks: list[dict[str, object]], pool: object) -> None:
    """Index classified chunks with embeddings in batches of 50.

    Dedup via ``content_hash``: a chunk whose body already exists with
    ``is_current = true`` is skipped (BP §06.1.1 Stage 4). Each input chunk
    must already carry a ``classification`` dict from ``classify_chunk``.
    """
    batch_size = 50
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
            await pool.execute(  # type: ignore[attr-defined]
                "INSERT INTO regulation_chunks "
                "(regulation_id, article, paragraph, hierarchy_path, body, "
                "chunk_type, tags, embedding, content_hash) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,$8::vector,$9)",
                chunk["regulation_id"], chunk["article"], chunk["paragraph"],
                chunk["hierarchy_path"], chunk["body"],
                classification["type"],
                classification["tags"],
                embedding_literal, content_hash,
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

    classified: list[dict[str, object]] = []
    for chunk in chunks:
        classification = await classify_chunk(str(chunk["body"]))
        classified.append({**chunk, "classification": classification})

    await index_chunks(classified, pool)

    logger.info(
        "regulation_ingested",
        regulation_id=regulation_id,
        slug=slug,
        chunks_count=len(classified),
    )
    return regulation_id, len(classified)
