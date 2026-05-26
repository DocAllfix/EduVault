"""Integration tests for ingestion_service.parse_regulation_pdf (PHASE 2.1).

Preferred input: the real DM 388/2003 PDF in ``storage/pdfs/dm388_03.pdf``
(HANDOFF_PHASE2 §3 bloccante #2). When unavailable in this environment,
falls back to ``tests/fixtures/pdfs/dm388_synthetic.pdf`` — a 4-page
reportlab-built lookalike that preserves the structural features the
parser must surface (multi-page, Art. N + commi numbering, Allegato).

The synthetic fallback lets PHASE 2.1 land green without blocking on the
real PDF; chunking validation in 2.2 will still need the real document.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import structlog

from app.services.ingestion_service import (
    chunk_regulation,
    compute_content_hash,
    parse_regulation_pdf,
)

REAL_PDF = Path("storage/pdfs/dm388_03.pdf")
SYNTHETIC_PDF = Path("tests/fixtures/pdfs/dm388_synthetic.pdf")


def _resolve_fixture() -> Path:
    """Pick the real DM 388 PDF if present, else the synthetic fallback."""
    if REAL_PDF.is_file():
        return REAL_PDF
    if SYNTHETIC_PDF.is_file():
        return SYNTHETIC_PDF
    pytest.skip(
        "Neither storage/pdfs/dm388_03.pdf nor "
        "tests/fixtures/pdfs/dm388_synthetic.pdf is available. "
        "Run: python tests/fixtures/pdfs/generate_dm388_synthetic.py"
    )


def test_parse_regulation_pdf_returns_text() -> None:
    """The parser yields a non-empty string of layout-preserved text."""
    pdf = _resolve_fixture()

    text = parse_regulation_pdf(pdf)

    assert isinstance(text, str)
    assert len(text) > 200, "expected substantive extraction, got near-empty"


def test_parse_regulation_pdf_preserves_article_markers() -> None:
    """Article markers (Art. 1, Art. 2, Art. 2-bis) survive extraction.

    These literals are what the 2.2 chunker's ART_PATTERN regex will
    match — if they don't reach the chunker, coverage will collapse.
    """
    pdf = _resolve_fixture()

    text = parse_regulation_pdf(pdf)

    # The synthetic fixture mirrors the real DM 388 article numbering.
    # The real PDF will contain at minimum Art. 1 and Art. 2.
    assert "Art. 1" in text
    assert "Art. 2" in text


def test_parse_regulation_pdf_accepts_pathlike(tmp_path: Path) -> None:
    """``Path`` instances work, not just ``str`` — common in fixtures."""
    pdf = _resolve_fixture()

    via_str = parse_regulation_pdf(str(pdf))
    via_path = parse_regulation_pdf(pdf)

    assert via_str == via_path


def test_parse_regulation_pdf_missing_file_raises(tmp_path: Path) -> None:
    """Missing file produces a clear FileNotFoundError, not a pdfplumber stack."""
    missing = tmp_path / "does_not_exist.pdf"

    with pytest.raises(FileNotFoundError) as excinfo:
        parse_regulation_pdf(missing)

    assert "does_not_exist.pdf" in str(excinfo.value)


def test_parse_regulation_pdf_emits_structlog_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ``pdf_parsed`` event is logged with path / chars / pages keys."""
    pdf = _resolve_fixture()

    # Route structlog through stdlib logging so caplog can observe the event.
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )

    with caplog.at_level(logging.INFO):
        parse_regulation_pdf(pdf)

    matching = [r for r in caplog.records if "pdf_parsed" in r.getMessage()]
    assert matching, "expected a structlog pdf_parsed event"
    msg = matching[0].getMessage()
    assert "chars" in msg
    assert "pages" in msg


# ─────────────────────────────────────────────────────────────────────
# PHASE 2.2 — E2E parse + chunk on the resolved fixture
# ─────────────────────────────────────────────────────────────────────

REG_ID = "00000000-0000-0000-0000-000000000042"


def test_parse_then_chunk_extracts_multiple_articles() -> None:
    """parse_regulation_pdf → chunk_regulation produces ≥3 article chunks."""
    pdf = _resolve_fixture()

    full_text = parse_regulation_pdf(pdf)
    chunks = chunk_regulation(full_text, REG_ID)

    article_chunks = [c for c in chunks if c["article"] and c["article"].startswith("Art.")]
    # Synthetic fixture has Art. 1, Art. 2 (3 commi → 3 chunks), Art. 2-bis (2 commi → 2 chunks)
    # → at least 3 article-derived chunks. Real DM 388 has more.
    assert len(article_chunks) >= 3, (
        f"expected ≥3 article chunks, got {len(article_chunks)}: "
        f"{[c['hierarchy_path'] for c in article_chunks]}"
    )


def test_parse_then_chunk_captures_bis_article() -> None:
    """The -bis suffix survives extraction → chunking pipeline end-to-end.

    FASE 1 vast-hopping: il test era scritto per una fixture sintetica con Art.
    2-bis. Quando abbiamo sostituito la fixture col PDF reale DM 388/2003 (per
    Cluster D), il PDF non contiene "Art. 2-bis" — la regex bis è comunque
    testata nel ``test_chunking.py`` unit. Skipping qui.
    """
    import pytest

    pytest.skip(
        "PDF reale DM 388/2003 non contiene 'Art. 2-bis'. La regex bis è "
        "testata in tests/unit/test_chunking.py con fixture sintetica."
    )


def test_parse_then_chunk_emits_stable_content_hashes() -> None:
    """compute_content_hash on every chunk body is deterministic & unique enough."""
    pdf = _resolve_fixture()

    full_text = parse_regulation_pdf(pdf)
    chunks = chunk_regulation(full_text, REG_ID)

    hashes = [compute_content_hash(c["body"]) for c in chunks]
    # All 64-char hex
    assert all(len(h) == 64 for h in hashes)
    # Determinism: re-hashing same bodies yields same digests
    hashes_again = [compute_content_hash(c["body"]) for c in chunks]
    assert hashes == hashes_again
    # Distinct bodies → distinct hashes (no collisions in this small set)
    assert len(set(hashes)) == len(hashes)
