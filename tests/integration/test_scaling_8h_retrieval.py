"""FIX #31.8 (2026-05-27, analista review 11) — test scaling retrieval 8h+.

Tre leve insieme:
  A — top_k_per_module scalabile con duration_hours (call-site).
  B — MIN_RELEVANCE adattivo per modulo (rescue sotto-quota).
  C — Dedup quota-aware (pin top QUOTA_MIN chunk pre-dedup).

Validano Demo #3 Preposti 8h × 6 moduli (patologie corpus-sottile su M3
"Incidenti mancati" + dedup-zero-sum su M1/M4/M5). Devono essere
retrocompatibili coi 4h × 4 moduli ben distinti (E25, Generale).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.research_agent import retrieve_chunks_per_module
from app.models.core import ChunkType
from app.models.knowledge import NormativeChunk
from app.models.pipeline import ModuleSpec, PacingPlan


def _chunk(cid: str, body: str, score: float) -> NormativeChunk:
    return NormativeChunk(
        chunk_id=cid,
        regulation_id="reg-test",
        article="42",
        paragraph="1",
        hierarchy_path="art. 42",
        body=body,
        chunk_type=ChunkType.OBBLIGO,
        tags=[],
        relevance_score=score,
    )


def _pacing_plan(*titles: str) -> PacingPlan:
    modules = [
        ModuleSpec(
            module_index=i,
            title=t,
            slide_count=80,
            slide_distribution={"CONTENT_TEXT": 80},
        )
        for i, t in enumerate(titles)
    ]
    return PacingPlan(
        total_slides=sum(m.slide_count for m in modules), modules=modules
    )


def _mock_repo(chunks_per_query: list[list[NormativeChunk]]) -> Any:
    repo = MagicMock()
    calls: list[dict[str, Any]] = []

    async def _search(*, query_embedding, regulation_ids, region, top_k):
        idx = len(calls)
        calls.append({"top_k": top_k, "module_idx": idx})
        return list(chunks_per_query[idx]) if idx < len(chunks_per_query) else []

    repo.search_chunks = _search
    repo._calls = calls
    return repo


# ─────────────── LEVA A — top_k scalabile (test del call-site) ───────────────
#
# La formula `min(150, int(35 + 8 * duration_hours))` è nel call-site di
# research_agent.py (non dentro retrieve_chunks_per_module). Quindi testiamo
# il MATH della formula direttamente.


class TestLevaAFormulaTopKDuration:
    """Verifica formula top_k = min(150, int(35 + 8 * duration_hours))."""

    def _top_k(self, hours: float) -> int:
        return min(150, int(35 + 8 * hours))

    def test_4h_yields_67(self) -> None:
        """4h → 67 (≈ vecchio 70, retrocompat E25, Demo #2 Generale)."""
        assert self._top_k(4.0) == 67

    def test_8h_yields_99(self) -> None:
        """8h → 99 (+41% vs vecchio 70, copre Preposti 6 moduli)."""
        assert self._top_k(8.0) == 99

    def test_16h_capped_at_150(self) -> None:
        """16h → 163 → cap 150 (vincolo strutturale, mitigato da B+C)."""
        assert self._top_k(16.0) == 150

    def test_32h_capped_at_150(self) -> None:
        """32h → 291 → cap 150 (catalog cliente max)."""
        assert self._top_k(32.0) == 150


# ─────────────── LEVA B — MIN_RELEVANCE adattivo per modulo ───────────────


@pytest.mark.asyncio
class TestLevaBAdaptiveMinRelevance:
    """Quando un modulo è svuotato sotto soglia gate (30) dal filtro
    statico, ricalcola MIN come P25 dei chunk raw e ri-applica."""

    async def test_starved_module_rescued_by_adaptive_p25(self) -> None:
        """M0 con 70 chunk a score [0.21..0.29] → statico MIN=0.3 droppa
        tutto → leva B attiva → P25 ≈ 0.22 → ~50 chunk salvati."""
        # 70 chunk con score crescente 0.20..0.29 (tutti sotto 0.3)
        chunks_raw = [
            _chunk(f"c{i}", f"body {i}", score=0.20 + i * 0.001)
            for i in range(70)
        ]
        plan = _pacing_plan("M3 Incidenti mancati")
        repo = _mock_repo([chunks_raw])

        with patch(
            "app.services.ingestion_service.embed_query",
            new=AsyncMock(return_value=[0.1] * 1024),
        ):
            result = await retrieve_chunks_per_module(
                pacing_plan=plan,
                regulation_ids=["reg-test"],
                region="NAZIONALE",
                knowledge_repo=repo,
                top_k_per_module=70,
                min_relevance=0.3,  # tutti i chunk SONO sotto soglia statica
            )

        # Pre-fix sarebbe stato: 0 chunk (tutti < 0.3) → grab-bag
        # Post-fix: ~52 chunk salvati dal P25 (top 75% per score)
        assert len(result[0]) >= 30, (
            f"Leva B doveva salvare ≥30 chunk, ricevuti {len(result[0])}"
        )
        # Sanity: tutti i chunk salvati hanno score > P25 (0.20 + 17*0.001 ≈ 0.217)
        for c in result[0]:
            assert (c.relevance_score or 0) > 0.21

    async def test_well_covered_module_no_op(self) -> None:
        """M0 con 70 chunk a score [0.4..0.65] → filtro statico passa
        TUTTI → leva B NON attiva (no rescue needed)."""
        chunks_raw = [
            _chunk(f"c{i}", f"body {i}", score=0.4 + i * 0.003)
            for i in range(70)
        ]
        plan = _pacing_plan("M0 DPI")
        repo = _mock_repo([chunks_raw])

        with patch(
            "app.services.ingestion_service.embed_query",
            new=AsyncMock(return_value=[0.1] * 1024),
        ):
            result = await retrieve_chunks_per_module(
                pacing_plan=plan,
                regulation_ids=["reg-test"],
                region="NAZIONALE",
                knowledge_repo=repo,
                top_k_per_module=70,
                min_relevance=0.3,
            )

        # Tutti 70 chunk passano filtro statico, nessuna leva B
        assert len(result[0]) == 70


# ─────────────── LEVA C — Dedup quota-aware anti-starvation ───────────────


@pytest.mark.asyncio
class TestLevaCQuotaAwareDedup:
    """Garantisce QUOTA_MIN=30 chunk per modulo PRIMA della dedup
    cosine winner. Risolve dedup-zero-sum su moduli adiacenti."""

    async def test_weak_module_protected_by_quota(self) -> None:
        """Patologia Preposti M1: M0 dominante (50 chunk forti score 0.7)
        + M1 debole (33 chunk con stessi chunk_id ma score 0.5). Pre-fix
        dedup cosine: M1 perde 30 chunk a M0 → 3 chunk solo. Post-fix
        quota=30: M1 pin 30 chunk → quota garantita."""
        # M0: 50 chunk forti su tema esclusivo (score 0.7)
        m0_chunks = [
            _chunk(f"m0-only-{i}", f"M0 exclusive {i}", score=0.7)
            for i in range(50)
        ]
        # M1: 3 chunk forti propri (0.65) + 30 chunk CONTESI con M0 (score 0.5
        # in M1, ma in M0 quegli stessi 30 sono score 0.6 → M0 vince cosine)
        m1_chunks_own = [
            _chunk(f"m1-own-{i}", f"M1 unique {i}", score=0.65)
            for i in range(3)
        ]
        m1_chunks_contested = [
            _chunk(f"contested-{i}", f"Common topic {i}", score=0.5)
            for i in range(30)
        ]
        m0_chunks_contested_high = [
            _chunk(f"contested-{i}", f"Common topic {i}", score=0.6)
            for i in range(30)
        ]
        # M0 raw = 50 own + 30 contested. M1 raw = 3 own + 30 contested.
        plan = _pacing_plan("M0 forte", "M1 debole")
        repo = _mock_repo(
            [
                m0_chunks + m0_chunks_contested_high,  # M0: 80 chunk raw
                m1_chunks_own + m1_chunks_contested,  # M1: 33 chunk raw
            ]
        )

        with patch(
            "app.services.ingestion_service.embed_query",
            new=AsyncMock(return_value=[0.1] * 1024),
        ):
            result = await retrieve_chunks_per_module(
                pacing_plan=plan,
                regulation_ids=["reg-test"],
                region="NAZIONALE",
                knowledge_repo=repo,
                top_k_per_module=80,
                min_relevance=0.0,
            )

        # M1 DEVE avere ≥30 chunk grazie alla quota pin (era 3 pre-fix)
        assert len(result[1]) >= 30, (
            f"Leva C doveva proteggere M1 con quota=30, "
            f"ricevuti {len(result[1])}"
        )
        # M0 ha comunque i suoi 50 own intatti
        assert len(result[0]) >= 50

    async def test_all_modules_above_quota_dedup_normal(self) -> None:
        """Retrocompat 4h × 4 moduli ben distinti: ognuno con 60 chunk
        UNICI (zero contention), tutti sopra quota=30 → dedup come prima
        (effetto leva C = zero)."""
        plans = ["M0 DPI", "M1 Rischi", "M2 Emergenza", "M3 Segnaletica"]
        modules_chunks = []
        for m_idx in range(4):
            modules_chunks.append(
                [
                    _chunk(f"m{m_idx}-c{i}", f"M{m_idx} body {i}", score=0.5)
                    for i in range(60)
                ]
            )
        plan = _pacing_plan(*plans)
        repo = _mock_repo(modules_chunks)

        with patch(
            "app.services.ingestion_service.embed_query",
            new=AsyncMock(return_value=[0.1] * 1024),
        ):
            result = await retrieve_chunks_per_module(
                pacing_plan=plan,
                regulation_ids=["reg-test"],
                region="NAZIONALE",
                knowledge_repo=repo,
                top_k_per_module=60,
                min_relevance=0.0,
            )

        # Tutti 4 moduli devono avere 60 chunk (zero contention, zero
        # dedup, comportamento identico a #31.1 pre-leva-C)
        for m_idx in range(4):
            assert len(result[m_idx]) == 60, (
                f"M{m_idx} ha {len(result[m_idx])} chunk, atteso 60 "
                f"(zero contention)"
            )
