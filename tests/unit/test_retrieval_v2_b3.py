"""Unit tests per F2.13 B3 cross-Titolo decay.

Architettura B3 (analista sign-off 2026-05-30):
  - Pool top-K cosine_voyage uscito da B2 -> B3 applica decay sui chunks
    con top_section != Titolo dominante per regulation.
  - Soglia scarto = max_pool * B3_THRESHOLD_RATIO (default 0.30).
  - Decay factor = B3_DECAY_FACTOR (default 0.4).
  - Log 8 campi + flag b3_noop_reason.

Test verificano:
  - decay applicato a chunks cross-titolo + scarto se sotto soglia
  - chunks "Sconosciuto"/NULL passano senza decay
  - single-section regulations (no cross-Titolo possibile) passano intere
  - dominante per regulation calcolata correttamente
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.models.core import ChunkType
from app.models.knowledge import NormativeChunk
from app.services.retrieval_v2 import ScoredChunk, apply_b3_cross_title_decay


def _make_chunk(idx: int) -> NormativeChunk:
    return NormativeChunk(
        chunk_id=f"00000000-0000-0000-0000-{idx:012d}",
        regulation_id="11111111-1111-1111-1111-111111111111",
        article=f"Art. {idx}",
        paragraph="",
        hierarchy_path=f"art{idx}",
        body=f"body chunk {idx}",
        chunk_type=ChunkType.GENERALE,
        tags=[],
        relevance_score=0.0,
    )


def _scored(idx: int, score: float) -> ScoredChunk:
    return ScoredChunk(
        chunk=_make_chunk(idx),
        score=score,
        source="b2_cosine_voyage",
    )


def _mock_repo_with_meta(meta_rows: list[dict], reg_rows: list[dict]) -> AsyncMock:
    """Mock repo.pool.fetch che restituisce meta_rows per la prima fetch
    (chunks meta) e reg_rows per la seconda fetch (regulations slugs)."""
    mock_pool = AsyncMock()
    mock_pool.fetch = AsyncMock(side_effect=[meta_rows, reg_rows])
    repo = AsyncMock()
    repo.pool = mock_pool
    return repo


@pytest.mark.asyncio
async def test_b3_decays_cross_titolo_and_discards_below_threshold() -> None:
    """ANT M0 simulato: top_section dominante = Titolo I (4 chunks),
    Titolo IV cross-titolo = decay×0.4. Cosine alta (0.50) -> sopra soglia
    (max=0.55, soglia=0.55*0.30=0.165, decayed 0.50*0.4=0.20 > 0.165 -> keep).
    Cosine media (0.30) -> sotto soglia (decayed 0.30*0.4=0.12 < 0.165 -> discard).
    """
    pool_b2 = [
        _scored(40, 0.55),   # Titolo I dominante
        _scored(46, 0.50),   # Titolo I dominante
        _scored(15, 0.45),   # Titolo I dominante
        _scored(28, 0.40),   # Titolo I dominante
        _scored(121, 0.50),  # Titolo IV cross (decay 0.20 > soglia 0.165 -> keep)
        _scored(132, 0.30),  # Titolo IV cross (decay 0.12 < soglia 0.165 -> discard)
    ]
    meta_rows = [
        {"chunk_id": pool_b2[0].chunk.chunk_id, "rid": "rid1", "top_section": "Titolo I"},
        {"chunk_id": pool_b2[1].chunk.chunk_id, "rid": "rid1", "top_section": "Titolo I"},
        {"chunk_id": pool_b2[2].chunk.chunk_id, "rid": "rid1", "top_section": "Titolo I"},
        {"chunk_id": pool_b2[3].chunk.chunk_id, "rid": "rid1", "top_section": "Titolo I"},
        {"chunk_id": pool_b2[4].chunk.chunk_id, "rid": "rid1", "top_section": "Titolo IV"},
        {"chunk_id": pool_b2[5].chunk.chunk_id, "rid": "rid1", "top_section": "Titolo IV"},
    ]
    reg_rows = [{"rid": "rid1", "slug": "dlgs_81_08"}]
    repo = _mock_repo_with_meta(meta_rows, reg_rows)

    survivors = await apply_b3_cross_title_decay(pool_b2=pool_b2, repo=repo)

    # 4 Titolo I dominanti + 1 Titolo IV decayed-kept = 5 survivors
    assert len(survivors) == 5
    # Top resta Art. 40 con cosine 0.55 (Titolo I dominante, no decay)
    assert survivors[0].chunk.chunk_id.endswith("040")
    assert survivors[0].score == pytest.approx(0.55)
    # Art. 121 decayed-kept con score 0.50*0.4 = 0.20
    art_121 = next(sc for sc in survivors if sc.chunk.chunk_id.endswith("121"))
    assert art_121.score == pytest.approx(0.20)
    assert art_121.source == "b3_decayed"
    # Art. 132 (decayed 0.12 < soglia 0.165) NON deve esserci
    assert not any(sc.chunk.chunk_id.endswith("132") for sc in survivors)


@pytest.mark.asyncio
async def test_b3_keeps_unclassified_chunks_without_decay() -> None:
    """Chunks 'Sconosciuto' o NULL passano senza decay (esclusi dal majority vote)."""
    pool_b2 = [
        _scored(40, 0.55),
        _scored(46, 0.50),
        _scored(999, 0.45),  # Sconosciuto
    ]
    meta_rows = [
        {"chunk_id": pool_b2[0].chunk.chunk_id, "rid": "rid1", "top_section": "Titolo I"},
        {"chunk_id": pool_b2[1].chunk.chunk_id, "rid": "rid1", "top_section": "Titolo I"},
        {"chunk_id": pool_b2[2].chunk.chunk_id, "rid": "rid1", "top_section": "Sconosciuto"},
    ]
    reg_rows = [{"rid": "rid1", "slug": "dlgs_81_08"}]
    repo = _mock_repo_with_meta(meta_rows, reg_rows)

    survivors = await apply_b3_cross_title_decay(pool_b2=pool_b2, repo=repo)

    assert len(survivors) == 3
    # Sconosciuto resta col suo cosine originale (no decay)
    sconosciuto = next(sc for sc in survivors if sc.chunk.chunk_id.endswith("999"))
    assert sconosciuto.score == pytest.approx(0.45)
    assert sconosciuto.source == "b2_cosine_voyage"  # source originale, NON b3_decayed


@pytest.mark.asyncio
async def test_b3_trivial_single_section_regulation_no_decay() -> None:
    """HACCP corpus simulato: tutti chunks top_section='reg_ce_852_2004'
    (single-section). B3 pool-dominante per regulation = trivial,
    nessun decay applicato.
    """
    pool_b2 = [
        _scored(1, 0.55),
        _scored(2, 0.50),
        _scored(3, 0.45),
    ]
    meta_rows = [
        {"chunk_id": pool_b2[0].chunk.chunk_id, "rid": "rid1", "top_section": "reg_ce_852_2004"},
        {"chunk_id": pool_b2[1].chunk.chunk_id, "rid": "rid1", "top_section": "reg_ce_852_2004"},
        {"chunk_id": pool_b2[2].chunk.chunk_id, "rid": "rid1", "top_section": "reg_ce_852_2004"},
    ]
    reg_rows = [{"rid": "rid1", "slug": "reg_ce_852_2004"}]
    repo = _mock_repo_with_meta(meta_rows, reg_rows)

    survivors = await apply_b3_cross_title_decay(pool_b2=pool_b2, repo=repo)

    # Tutti passano senza decay (dominante = top_section per ogni chunk)
    assert len(survivors) == 3
    assert all(sc.source == "b2_cosine_voyage" for sc in survivors)
    assert survivors[0].score == pytest.approx(0.55)


@pytest.mark.asyncio
async def test_b3_empty_pool_returns_empty() -> None:
    """Edge case: pool B2 vuoto -> ritorna vuoto."""
    mock_pool = AsyncMock()
    repo = AsyncMock()
    repo.pool = mock_pool

    survivors = await apply_b3_cross_title_decay(pool_b2=[], repo=repo)

    assert survivors == []


@pytest.mark.asyncio
async def test_b3_skips_decay_when_insufficient_observations() -> None:
    """REGIME 3 simulato (GEN M1 Art. 236 false-discard scenario).

    Pool ANT L1-like: Accordo SR (single-section) ha 27 chunks, D.Lgs 81/08
    ha solo 3 chunks (Art. 236 Titolo IX + 2 chunks Allegati Cantieri).

    Pre-skip-low-obs: B3 calcolava Titolo IV dominante D.Lgs su 3 obs (2:1
    split), e scartava Art. 236 come cross-titolo (Titolo IX != Titolo IV).
    False-discard semantico.

    Post-skip-low-obs (B3_MIN_OBSERVATIONS=4 default): D.Lgs ha solo 3 obs
    < 4, B3 SKIP decay sui chunks D.Lgs. Art. 236 sopravvive con peso
    originale (do no harm sotto incertezza statistica). Tutti i 30 chunks
    sopravvivono.
    """
    pool_b2 = [
        _scored(1, 0.55),    # Accordo SR (27 chunks tutti score 0.30-0.55)
        _scored(2, 0.53),
        _scored(3, 0.51),
        _scored(4, 0.49),
        _scored(5, 0.47),
        _scored(6, 0.45),
        _scored(7, 0.43),
        _scored(8, 0.41),
        _scored(9, 0.39),
        _scored(10, 0.37),
        _scored(236, 0.40),  # D.Lgs Art. 236 Titolo IX (on-topic semantico)
        _scored(95, 0.38),   # D.Lgs Art. 95 Allegato XV (Titolo IV)
        _scored(96, 0.36),   # D.Lgs Art. 96 Allegato XVI (Titolo IV)
    ]
    meta_rows = [
        {"chunk_id": pool_b2[0].chunk.chunk_id, "rid": "rid_accordo", "top_section": "accordo_stato_regioni_2025"},
        {"chunk_id": pool_b2[1].chunk.chunk_id, "rid": "rid_accordo", "top_section": "accordo_stato_regioni_2025"},
        {"chunk_id": pool_b2[2].chunk.chunk_id, "rid": "rid_accordo", "top_section": "accordo_stato_regioni_2025"},
        {"chunk_id": pool_b2[3].chunk.chunk_id, "rid": "rid_accordo", "top_section": "accordo_stato_regioni_2025"},
        {"chunk_id": pool_b2[4].chunk.chunk_id, "rid": "rid_accordo", "top_section": "accordo_stato_regioni_2025"},
        {"chunk_id": pool_b2[5].chunk.chunk_id, "rid": "rid_accordo", "top_section": "accordo_stato_regioni_2025"},
        {"chunk_id": pool_b2[6].chunk.chunk_id, "rid": "rid_accordo", "top_section": "accordo_stato_regioni_2025"},
        {"chunk_id": pool_b2[7].chunk.chunk_id, "rid": "rid_accordo", "top_section": "accordo_stato_regioni_2025"},
        {"chunk_id": pool_b2[8].chunk.chunk_id, "rid": "rid_accordo", "top_section": "accordo_stato_regioni_2025"},
        {"chunk_id": pool_b2[9].chunk.chunk_id, "rid": "rid_accordo", "top_section": "accordo_stato_regioni_2025"},
        {"chunk_id": pool_b2[10].chunk.chunk_id, "rid": "rid_dlgs", "top_section": "Titolo IX"},
        {"chunk_id": pool_b2[11].chunk.chunk_id, "rid": "rid_dlgs", "top_section": "Titolo IV"},
        {"chunk_id": pool_b2[12].chunk.chunk_id, "rid": "rid_dlgs", "top_section": "Titolo IV"},
    ]
    reg_rows = [
        {"rid": "rid_accordo", "slug": "accordo_stato_regioni_2025"},
        {"rid": "rid_dlgs", "slug": "dlgs_81_08"},
    ]
    repo = _mock_repo_with_meta(meta_rows, reg_rows)

    survivors = await apply_b3_cross_title_decay(pool_b2=pool_b2, repo=repo)

    # 10 Accordo SR (single-section trivial, no decay) + 3 D.Lgs (skipped per insufficient_obs) = 13 chunks
    assert len(survivors) == 13
    # Art. 236 deve sopravvivere col cosine originale 0.40 (no decay, no discard)
    art_236 = next(sc for sc in survivors if sc.chunk.chunk_id.endswith("236"))
    assert art_236.score == pytest.approx(0.40)
    assert art_236.source == "b2_cosine_voyage"  # NON b3_decayed (skip = pass-through)
    # Allegati XV/XVI Cantieri devono sopravvivere col cosine originale (skipped)
    art_95 = next(sc for sc in survivors if sc.chunk.chunk_id.endswith("095"))
    assert art_95.score == pytest.approx(0.38)
    assert art_95.source == "b2_cosine_voyage"


@pytest.mark.asyncio
async def test_b3_per_regulation_dominante_isolated() -> None:
    """Multi-regulation: dominante calcolata PER regulation, NON globale.
    Pool ANT L1 simulato: D.Lgs 81/08 con dominante Titolo I, DM 02/09/2021
    single-section.
    """
    pool_b2 = [
        _scored(40, 0.55),    # D.Lgs Titolo I dominante
        _scored(46, 0.50),    # D.Lgs Titolo I dominante
        _scored(15, 0.45),    # D.Lgs Titolo I dominante
        _scored(121, 0.50),   # D.Lgs Titolo IV cross (decay)
        _scored(100, 0.40),   # DM 02/09 single-section
        _scored(101, 0.35),   # DM 02/09 single-section
    ]
    meta_rows = [
        {"chunk_id": pool_b2[0].chunk.chunk_id, "rid": "rid_dlgs", "top_section": "Titolo I"},
        {"chunk_id": pool_b2[1].chunk.chunk_id, "rid": "rid_dlgs", "top_section": "Titolo I"},
        {"chunk_id": pool_b2[2].chunk.chunk_id, "rid": "rid_dlgs", "top_section": "Titolo I"},
        {"chunk_id": pool_b2[3].chunk.chunk_id, "rid": "rid_dlgs", "top_section": "Titolo IV"},
        {"chunk_id": pool_b2[4].chunk.chunk_id, "rid": "rid_dm", "top_section": "dm_02_09_2021"},
        {"chunk_id": pool_b2[5].chunk.chunk_id, "rid": "rid_dm", "top_section": "dm_02_09_2021"},
    ]
    reg_rows = [
        {"rid": "rid_dlgs", "slug": "dlgs_81_08"},
        {"rid": "rid_dm", "slug": "dm_02_09_2021"},
    ]
    repo = _mock_repo_with_meta(meta_rows, reg_rows)

    survivors = await apply_b3_cross_title_decay(pool_b2=pool_b2, repo=repo)

    # 3 D.Lgs Titolo I dominanti + 1 D.Lgs Titolo IV decayed (0.50*0.4=0.20 > 0.165 soglia) +
    # 2 DM 02/09 single-section = 6 chunks (nessuno scartato qui).
    assert len(survivors) == 6
    # DM 02/09 NON deve essere decayed (trivial single-section per la sua regulation)
    dm_chunks = [sc for sc in survivors if sc.chunk.chunk_id.endswith("100") or sc.chunk.chunk_id.endswith("101")]
    assert all(sc.source == "b2_cosine_voyage" for sc in dm_chunks)
    # Art. 121 cross-titolo IV deve essere decayed
    art_121 = next(sc for sc in survivors if sc.chunk.chunk_id.endswith("121"))
    assert art_121.source == "b3_decayed"
    assert art_121.score == pytest.approx(0.50 * 0.4)


# =============================================================================
# H8b-γ3 — B3 strong dominance escalation hard_discard (analista 2026-05-31)
# =============================================================================


@pytest.mark.asyncio
async def test_b3_strong_dominance_hard_discards_cross_titolo(monkeypatch: pytest.MonkeyPatch) -> None:
    """H8b-γ3: pool dominato fortemente (≥70%) da Titolo I → chunks Titolo III
    cross-titolo HARD_DISCARD invece di decay_kept. Cura cluster #35-41 PPTX
    691405b1 post-H8 (Titolo III Attrezzature in M0 Principi).

    Pool simulato: 8 Titolo I + 2 Titolo III in regulation dlgs (ratio 8/10=80%).
    Strong dominance threshold default 0.70 → triggers hard_discard.
    Atteso: 8 Titolo I survivors, 2 Titolo III hard_discarded (NON in pool).
    """
    from app.config import settings
    monkeypatch.setattr(settings, "v2_b3_strong_dominance_enabled", True)

    pool_b2 = [
        _scored(15, 0.55),   # Titolo I dominante
        _scored(40, 0.50),
        _scored(46, 0.48),
        _scored(18, 0.45),
        _scored(20, 0.43),
        _scored(35, 0.40),
        _scored(37, 0.38),
        _scored(50, 0.35),   # 8 Titolo I = 80% dominance
        _scored(69, 0.42),   # Titolo III cross
        _scored(75, 0.41),   # Titolo III cross
    ]
    meta_rows = [
        {"chunk_id": pool_b2[i].chunk.chunk_id, "rid": "rid_dlgs",
         "top_section": "Titolo I" if i < 8 else "Titolo III"}
        for i in range(10)
    ]
    reg_rows = [{"rid": "rid_dlgs", "slug": "dlgs_81_08"}]
    repo = _mock_repo_with_meta(meta_rows, reg_rows)

    survivors = await apply_b3_cross_title_decay(pool_b2=pool_b2, repo=repo)

    # Solo 8 Titolo I sopravvivono. 2 Titolo III hard_discarded.
    assert len(survivors) == 8, f"atteso 8 survivors (solo Titolo I), trovato {len(survivors)}"
    survivor_ids = {sc.chunk.chunk_id for sc in survivors}
    # Verifica Titolo III idx 69 e 75 NON nel survivor pool
    assert pool_b2[8].chunk.chunk_id not in survivor_ids, "Titolo III idx 69 doveva essere hard_discarded"
    assert pool_b2[9].chunk.chunk_id not in survivor_ids, "Titolo III idx 75 doveva essere hard_discarded"


@pytest.mark.asyncio
async def test_b3_diversified_pool_no_hard_discard(monkeypatch: pytest.MonkeyPatch) -> None:
    """H8b-γ3: pool diversificato (no top_section ≥70%) → comportamento legacy
    (decay_kept come pre-γ3). Verifica che γ-3 NON danneggi pool legittimamente
    diversificati (es. PRE M3 voce 1 grab-bag).
    """
    from app.config import settings
    monkeypatch.setattr(settings, "v2_b3_strong_dominance_enabled", True)

    # Pool 10 chunks: 4 Titolo I (40%) + 3 Titolo IV (30%) + 3 Titolo IX (30%)
    # Max dominance = 40% < 70% threshold → no hard_discard, decay legacy
    pool_b2 = [
        _scored(15, 0.55), _scored(40, 0.50), _scored(46, 0.45), _scored(18, 0.43),  # Titolo I
        _scored(95, 0.42), _scored(121, 0.40), _scored(125, 0.38),                    # Titolo IV
        _scored(225, 0.36), _scored(236, 0.35), _scored(244, 0.33),                    # Titolo IX
    ]
    top_sections = ["Titolo I"] * 4 + ["Titolo IV"] * 3 + ["Titolo IX"] * 3
    meta_rows = [
        {"chunk_id": pool_b2[i].chunk.chunk_id, "rid": "rid_dlgs",
         "top_section": top_sections[i]}
        for i in range(10)
    ]
    reg_rows = [{"rid": "rid_dlgs", "slug": "dlgs_81_08"}]
    repo = _mock_repo_with_meta(meta_rows, reg_rows)

    survivors = await apply_b3_cross_title_decay(pool_b2=pool_b2, repo=repo)

    # Decisioni legacy: 4 Titolo I keep_same_titolo + Titolo IV/IX decayed
    # (cosine * 0.4: 0.42*0.4=0.168 vs soglia max=0.55*0.3=0.165 → quasi tutti decay_kept).
    # Nessun hard_discard atteso (max dominance 40% < 70%).
    sources = {sc.source for sc in survivors}
    assert "b3_decayed" in sources, "cross-titolo doveva essere decay_kept (no strong dominance)"
    # Tutti i Titolo I survivors devono avere source originale (b2_cosine_voyage)
    titolo_i_survivors = [sc for sc in survivors if sc.score >= 0.43]
    assert all(sc.source == "b2_cosine_voyage" for sc in titolo_i_survivors)


@pytest.mark.asyncio
async def test_b3_strong_dominance_flag_off_no_change(monkeypatch: pytest.MonkeyPatch) -> None:
    """H8b-γ3: flag v2_b3_strong_dominance_enabled=False (default) → comportamento
    identico a pre-γ3 (decay_kept anche su pool fortemente dominati). Garantisce
    safety: γ-3 e' opt-in, deploy commit non rompe runtime esistente.
    """
    from app.config import settings
    monkeypatch.setattr(settings, "v2_b3_strong_dominance_enabled", False)  # OFF

    # Pool con 8 Titolo I (80% dominance) + 2 Titolo III con cosine sufficientemente
    # alta da sopravvivere a decay legacy (cosine * 0.4 > soglia 0.165).
    # Cosine 0.50 * 0.4 = 0.20 > 0.165 → decay_kept (NO discard_below_threshold).
    pool_b2 = [
        _scored(15, 0.55), _scored(40, 0.50), _scored(46, 0.48), _scored(18, 0.45),
        _scored(20, 0.43), _scored(35, 0.40), _scored(37, 0.38), _scored(50, 0.35),
        _scored(69, 0.50), _scored(75, 0.48),  # cosine ALTA per sopravvivere decay legacy
    ]
    meta_rows = [
        {"chunk_id": pool_b2[i].chunk.chunk_id, "rid": "rid_dlgs",
         "top_section": "Titolo I" if i < 8 else "Titolo III"}
        for i in range(10)
    ]
    reg_rows = [{"rid": "rid_dlgs", "slug": "dlgs_81_08"}]
    repo = _mock_repo_with_meta(meta_rows, reg_rows)

    survivors = await apply_b3_cross_title_decay(pool_b2=pool_b2, repo=repo)

    # Flag OFF: comportamento legacy. Titolo III chunks decayed ma sopravvivono
    # (0.50*0.4=0.20 > soglia 0.55*0.3=0.165 → decay_kept).
    # Atteso 10 survivors totali (no hard_discard quando flag OFF).
    assert len(survivors) == 10, f"flag OFF: atteso 10 survivors (legacy), trovato {len(survivors)}"
    # Titolo III chunks devono essere decayed ma presenti
    survivor_ids = {sc.chunk.chunk_id: sc for sc in survivors}
    titolo_3_69 = survivor_ids.get(pool_b2[8].chunk.chunk_id)
    titolo_3_75 = survivor_ids.get(pool_b2[9].chunk.chunk_id)
    assert titolo_3_69 is not None, "flag OFF: Titolo III doveva sopravvivere"
    assert titolo_3_75 is not None
    assert titolo_3_69.source == "b3_decayed"
    assert titolo_3_75.source == "b3_decayed"
