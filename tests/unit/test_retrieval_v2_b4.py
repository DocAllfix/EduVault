"""Unit tests per F2.14 B4 corpus-thin check.

Architettura B4 (analista sign-off 2026-05-30 (c) Caso 1):
  - Per ogni voce dello skeleton, per ogni regulation con chunks nel pool finale
    post-B3, conta n_chunks_per_regulation_per_voce.
  - Se n_chunks < B4_MIN_CHUNKS_PER_VOICE (default 3) -> regulation corpus thin
    per quella voce.
  - Behavior "block" (default sicura): rimuove i chunks della regulation dal
    pool.
  - Behavior "mark_only": NON rimuove, lascia chunks nel pool con flag log
    per metadata downstream.
  - Log strutturato per voce con n_chunks_per_regulation_per_voce SEMPRE
    emesso (anche quando NON scatta) per calibrazione su evidenza.

Test verificano:
  - Block rimuove chunks regulations sotto soglia
  - Mark_only lascia chunks ma log marca
  - Pass-through quando tutte le regulations sono sopra soglia
  - Multi-regulation: B4 valuta per-regulation indipendentemente
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.config import settings
from app.models.core import ChunkType
from app.models.knowledge import NormativeChunk
from app.services.retrieval_v2 import ScoredChunk, apply_b4_corpus_thin_check


def _make_chunk(idx: int, rid: str = "rid_main") -> NormativeChunk:
    return NormativeChunk(
        chunk_id=f"00000000-0000-0000-0000-{idx:012d}",
        regulation_id=rid,
        article=f"Art. {idx}",
        paragraph="",
        hierarchy_path=f"art{idx}",
        body=f"body chunk {idx}",
        chunk_type=ChunkType.GENERALE,
        tags=[],
        relevance_score=0.0,
    )


def _scored(idx: int, score: float, rid: str = "rid_main") -> ScoredChunk:
    return ScoredChunk(
        chunk=_make_chunk(idx, rid),
        score=score,
        source="b2_cosine_voyage",
    )


@pytest.mark.asyncio
async def test_b4_block_removes_corpus_thin_chunks() -> None:
    """ANT M0 voce simulata: DM 01/09 con n_chunks=2 (sotto soglia=3) ->
    block rimuove i 2 chunks. Altre regulations sopra soglia -> passthrough.
    """
    voice_pool = [
        # DM 03/09 (4 chunks sopra soglia 3, passthrough)
        _scored(1, 0.55, rid="rid_dm0309"),
        _scored(2, 0.50, rid="rid_dm0309"),
        _scored(3, 0.45, rid="rid_dm0309"),
        _scored(4, 0.40, rid="rid_dm0309"),
        # D.Lgs 81/08 (3 chunks AT soglia, passthrough)
        _scored(5, 0.35, rid="rid_dlgs"),
        _scored(6, 0.30, rid="rid_dlgs"),
        _scored(7, 0.25, rid="rid_dlgs"),
        # DM 01/09 (2 chunks sotto soglia, BLOCK)
        _scored(8, 0.20, rid="rid_dm0109"),
        _scored(9, 0.15, rid="rid_dm0109"),
    ]

    with patch.object(settings, "b4_min_chunks_per_voice", 3), \
         patch.object(settings, "b4_corpus_thin_behavior", "block"):
        survivors, decisions = await apply_b4_corpus_thin_check(
            voice_pool=voice_pool,
            voice_idx=1,
        )

    # DM 01/09 chunks (idx 8, 9) bloccati. Restano DM 03/09 + D.Lgs = 4+3 = 7
    assert len(survivors) == 7
    blocked_ids = {f"00000000-0000-0000-0000-{i:012d}" for i in [8, 9]}
    for sc in survivors:
        assert sc.chunk.chunk_id not in blocked_ids

    # Decisions: 3 regulations totali, 1 block + 2 passthrough_sufficient
    dec_by_rid = {d["regulation_id"]: d for d in decisions}
    assert dec_by_rid["rid_dm0109"]["decisione"] == "block"
    assert dec_by_rid["rid_dm0109"]["n_chunks"] == 2
    assert dec_by_rid["rid_dm0309"]["decisione"] == "passthrough_sufficient"
    assert dec_by_rid["rid_dm0309"]["n_chunks"] == 4
    assert dec_by_rid["rid_dlgs"]["decisione"] == "passthrough_sufficient"
    assert dec_by_rid["rid_dlgs"]["n_chunks"] == 3


@pytest.mark.asyncio
async def test_b4_mark_only_keeps_chunks_with_log() -> None:
    """Behavior mark_only: chunks corpus-thin restano nel pool, decisione
    nel log = mark_only (per propagazione metadata downstream)."""
    voice_pool = [
        _scored(1, 0.55, rid="rid_dm0309"),
        _scored(2, 0.50, rid="rid_dm0309"),
        _scored(3, 0.45, rid="rid_dm0309"),
        # DM 01/09 (2 chunks sotto soglia)
        _scored(8, 0.20, rid="rid_dm0109"),
        _scored(9, 0.15, rid="rid_dm0109"),
    ]

    with patch.object(settings, "b4_min_chunks_per_voice", 3), \
         patch.object(settings, "b4_corpus_thin_behavior", "mark_only"):
        survivors, decisions = await apply_b4_corpus_thin_check(
            voice_pool=voice_pool,
            voice_idx=1,
        )

    # mark_only: tutti i chunks restano nel pool
    assert len(survivors) == 5

    dec_by_rid = {d["regulation_id"]: d for d in decisions}
    assert dec_by_rid["rid_dm0109"]["decisione"] == "mark_only"
    assert dec_by_rid["rid_dm0309"]["decisione"] == "passthrough_sufficient"


@pytest.mark.asyncio
async def test_b4_all_passthrough_when_all_regulations_sufficient() -> None:
    """Tutte le regulations >= soglia -> tutto passthrough, nessun block/mark."""
    voice_pool = [
        _scored(i, 0.4, rid="rid_dm0309") for i in range(1, 8)  # 7 chunks
    ] + [
        _scored(i, 0.4, rid="rid_dlgs") for i in range(10, 14)  # 4 chunks
    ]

    with patch.object(settings, "b4_min_chunks_per_voice", 3), \
         patch.object(settings, "b4_corpus_thin_behavior", "block"):
        survivors, decisions = await apply_b4_corpus_thin_check(
            voice_pool=voice_pool,
            voice_idx=1,
        )

    assert len(survivors) == 11
    for d in decisions:
        assert d["decisione"] == "passthrough_sufficient"


@pytest.mark.asyncio
async def test_b4_empty_pool_returns_empty() -> None:
    """Edge case: voice_pool vuoto -> survivors vuoti, no decisions."""
    survivors, decisions = await apply_b4_corpus_thin_check(
        voice_pool=[],
        voice_idx=1,
    )
    assert survivors == []
    assert decisions == []


@pytest.mark.asyncio
async def test_b4_all_blocked_returns_empty_pool() -> None:
    """Edge case: tutte le regulations corpus thin con behavior=block ->
    pool finale vuoto (voce bloccata interamente). Downstream
    (skeleton_service) deve poter rilevare voce vuota e segnalare in
    generation_jobs.status."""
    voice_pool = [
        _scored(1, 0.5, rid="rid_dm0109"),  # 1 chunk solo
        _scored(2, 0.4, rid="rid_dm0209"),  # 1 chunk solo
    ]

    with patch.object(settings, "b4_min_chunks_per_voice", 3), \
         patch.object(settings, "b4_corpus_thin_behavior", "block"):
        survivors, decisions = await apply_b4_corpus_thin_check(
            voice_pool=voice_pool,
            voice_idx=1,
        )

    # Tutto bloccato
    assert len(survivors) == 0
    assert all(d["decisione"] == "block" for d in decisions)
