"""FIX #31.5B (2026-05-27) — Test sub-batch recovery.

In E2E #23 M1 ha perso 27 slide (2 batch falliti × ~13 slide cad)
perché instructor.max_retries=5 si esauriva e batch veniva droppato.

_try_sub_batch_recovery spezza il batch fallito in 2 sub-batch più
piccoli con prompt semplificato + max_retries=2.

Test:
1. batch_size < 4 → skip recovery (return None)
2. sub-batch riusciti → ritorna slide recuperate
3. sub-batch falliti → ritorna None
4. recovery parziale (1 sub OK, 1 sub fail) → ritorna le slide OK
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.core import SlideType
from app.models.pipeline import ImageStrategy, ModuleSlides, SlideContent
from app.services import ingestion_service as svc


def _make_test_slide(idx: int = 0) -> SlideContent:
    """Slide CONTENT_TEXT minimale valida."""
    return SlideContent(
        index=idx,
        module_index=0,
        slide_type=SlideType.CONTENT_TEXT,
        title=f"Test slide {idx}",
        bullets=[
            "Primo bullet del contenuto formativo",
            "Secondo bullet del contenuto formativo",
            "Terzo bullet del contenuto formativo",
            "Quarto bullet del contenuto formativo",
        ],
        speaker_notes=(
            "Speaker notes lunghe abbastanza per soddisfare il minimum di "
            "novanta parole del validator pydantic configurato in core.py. "
            "Aggiungo testo formativo aggiuntivo con riferimento normativo "
            "al D.Lgs. 81/08 e esempi pratici della formazione professionale "
            "sulla sicurezza nei luoghi di lavoro per discenti del corso "
            "specifico basso rischio, copertura competenze attese."
        ),
        image=ImageStrategy(strategy="none"),
    )


@pytest.mark.asyncio
async def test_sub_batch_skipped_when_too_small() -> None:
    """batch_size < 4 → skip recovery, return None immediato."""
    result = await svc._try_sub_batch_recovery(
        original_batch_size=3,
        batch_chunks="chunk x",
        system="sys",
        provider="azure_openai",
        eff_model="gpt-4.1-mini",
        already_count_in_module=10,
        module_index=0,
        batch_idx=0,
    )
    assert result is None


@pytest.mark.asyncio
async def test_sub_batch_split_recovers_when_both_succeed() -> None:
    """batch_size=10 → 2 sub-batch da 5 OK → ritorna 10 slide."""
    # Mock instructor client + create call
    slides_a = [_make_test_slide(i) for i in range(5)]
    slides_b = [_make_test_slide(i + 5) for i in range(5)]

    fake_module_a = ModuleSlides(module_index=1, title="Test M1", slides=slides_a)
    fake_module_b = ModuleSlides(module_index=1, title="Test M1", slides=slides_b)

    create_mock = AsyncMock(side_effect=[fake_module_a, fake_module_b])
    fake_client = MagicMock()
    fake_client.chat.completions.create = create_mock

    with patch.object(
        svc, "_instructor_client_for",
        return_value=(fake_client, "gpt-4.1-mini", {"reasks": 0}),
    ):
        result = await svc._try_sub_batch_recovery(
            original_batch_size=10,
            batch_chunks="chunk content",
            system="sys",
            provider="azure_openai",
            eff_model="gpt-4.1-mini",
            already_count_in_module=20,
            module_index=1,
            batch_idx=2,
        )

    assert result is not None
    assert len(result) == 10
    # Verifica che entrambi i sub-batch siano stati chiamati con
    # batch_size dimezzato (5)
    assert create_mock.call_count == 2


@pytest.mark.asyncio
async def test_sub_batch_partial_recovery_returns_partial_slides() -> None:
    """1 sub-batch OK + 1 sub-batch fail → ritorna SOLO le slide OK."""
    slides_a = [_make_test_slide(i) for i in range(5)]

    create_mock = AsyncMock(
        side_effect=[
            ModuleSlides(module_index=1, title="Test M1", slides=slides_a),  # sub 0 OK
            Exception("fake LLM error sub 1"),  # sub 1 fail
        ]
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create = create_mock

    with patch.object(
        svc, "_instructor_client_for",
        return_value=(fake_client, "gpt-4.1-mini", {"reasks": 0}),
    ):
        result = await svc._try_sub_batch_recovery(
            original_batch_size=10,
            batch_chunks="chunk content",
            system="sys",
            provider="azure_openai",
            eff_model="gpt-4.1-mini",
            already_count_in_module=20,
            module_index=1,
            batch_idx=2,
        )

    assert result is not None
    assert len(result) == 5  # solo le slide del sub 0


@pytest.mark.asyncio
async def test_sub_batch_both_fail_returns_none() -> None:
    """Tutti i sub-batch falliscono → ritorna None (batch perso)."""
    create_mock = AsyncMock(side_effect=Exception("LLM error"))
    fake_client = MagicMock()
    fake_client.chat.completions.create = create_mock

    with patch.object(
        svc, "_instructor_client_for",
        return_value=(fake_client, "gpt-4.1-mini", {"reasks": 0}),
    ):
        result = await svc._try_sub_batch_recovery(
            original_batch_size=10,
            batch_chunks="chunk content",
            system="sys",
            provider="azure_openai",
            eff_model="gpt-4.1-mini",
            already_count_in_module=20,
            module_index=1,
            batch_idx=2,
        )

    assert result is None
    # Verifica che entrambi i sub-batch siano stati tentati
    assert create_mock.call_count == 2


@pytest.mark.asyncio
async def test_sub_batch_uses_max_retries_2_not_5() -> None:
    """Sub-batch deve usare max_retries=2 (vs 5 del main batch)."""
    slides_a = [_make_test_slide(i) for i in range(5)]
    create_mock = AsyncMock(return_value=ModuleSlides(module_index=1, title="Test M1", slides=slides_a))
    fake_client = MagicMock()
    fake_client.chat.completions.create = create_mock

    with patch.object(
        svc, "_instructor_client_for",
        return_value=(fake_client, "gpt-4.1-mini", {"reasks": 0}),
    ):
        await svc._try_sub_batch_recovery(
            original_batch_size=10,
            batch_chunks="chunks",
            system="sys",
            provider="azure_openai",
            eff_model="gpt-4.1-mini",
            already_count_in_module=20,
            module_index=1,
            batch_idx=2,
        )

    # Ispezione argument della prima chiamata
    first_call_kwargs = create_mock.call_args_list[0].kwargs
    assert first_call_kwargs.get("max_retries") == 2
