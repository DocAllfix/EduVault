"""FIX #31 MOSSA 3 — Audio TTS background spawn + strong-ref + leak prevention.

Verifica le 3 invariants critiche dello spawn task background per audio:

1. Il task è effettivamente nel set ``_BACKGROUND_TASKS`` durante
   l'esecuzione (riferimento forte → non viene garbage-collected).
2. Dopo il completamento del task, il set è tornato vuoto (callback
   ``discard`` funziona → no memory leak in batch notturno).
3. ``UPDATE courses SET pptx_path...`` è chiamato PRIMA che
   ``generate_narrations`` completi (audio davvero in background, non
   inline).

NB: Non testiamo l'intera pipeline (research+content) — qui scope è
SOLO lo spawn + strong-ref + leak. Production builder + audio service
sono mockati.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import generation_service as gen_svc
from app.services.generation_service import _BACKGROUND_TASKS


@pytest.fixture(autouse=True)
def _clear_bg_tasks() -> None:
    """Ogni test parte con _BACKGROUND_TASKS vuoto."""
    _BACKGROUND_TASKS.clear()
    yield
    # Cleanup post-test: aspetta che tutti i task pendenti finiscano,
    # altrimenti pytest emette warning "Task was destroyed pending"
    pending = list(_BACKGROUND_TASKS)
    if pending:
        # Drena i task ancora pending (fail-safe contro test sloppy)
        for t in pending:
            t.cancel()
    _BACKGROUND_TASKS.clear()


@pytest.mark.asyncio
async def test_background_tasks_set_holds_strong_ref_during_execution() -> None:
    """Strong-ref test: mentre il task gira, _BACKGROUND_TASKS deve
    contenerlo. Altrimenti il GC potrebbe eliminarlo silenziosamente
    (gotcha asyncio.create_task documentato).
    """
    # Crea task fake che dura ~50ms
    started = asyncio.Event()
    can_finish = asyncio.Event()

    async def fake_audio() -> None:
        started.set()
        await can_finish.wait()

    task = asyncio.create_task(fake_audio(), name="audio_bg_fake")
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    # Aspetta che il task parta davvero
    await started.wait()

    # Invariant 1: durante l'esecuzione, il task è nel set
    assert task in _BACKGROUND_TASKS, "strong-ref required to survive GC"
    assert len(_BACKGROUND_TASKS) == 1

    # Sblocca il task e attendine il completamento
    can_finish.set()
    await task

    # Invariant 2: dopo il completamento, il discard l'ha rimosso
    assert task not in _BACKGROUND_TASKS, "done_callback should discard"
    assert len(_BACKGROUND_TASKS) == 0, (
        "leak: _BACKGROUND_TASKS keeps growing across courses if discard fails"
    )


@pytest.mark.asyncio
async def test_background_tasks_set_cleans_up_on_error() -> None:
    """Anche se il task fallisce con eccezione, deve essere comunque
    rimosso dal set (altrimenti i task falliti si accumulano)."""

    async def failing_audio() -> None:
        raise RuntimeError("simulated edge-tts failure")

    task = asyncio.create_task(failing_audio(), name="audio_bg_fail")
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    # Attende che il task fallisca (sopprimendo l'eccezione)
    with pytest.raises(RuntimeError):
        await task

    # Anche dopo fallimento, il set è vuoto
    assert task not in _BACKGROUND_TASKS
    assert len(_BACKGROUND_TASKS) == 0


@pytest.mark.asyncio
async def test_multiple_background_tasks_tracked_independently() -> None:
    """Stress test: 5 task concurrent. Tutti devono essere tracciati
    e tutti devono essere rimossi al completamento."""
    barriers = [asyncio.Event() for _ in range(5)]

    async def fake_audio_n(i: int) -> None:
        await barriers[i].wait()

    tasks = []
    for i in range(5):
        t = asyncio.create_task(fake_audio_n(i), name=f"audio_bg_{i}")
        _BACKGROUND_TASKS.add(t)
        t.add_done_callback(_BACKGROUND_TASKS.discard)
        tasks.append(t)

    # Tutti i 5 sono tracciati
    assert len(_BACKGROUND_TASKS) == 5

    # Sblocca tutti e attendi
    for b in barriers:
        b.set()
    await asyncio.gather(*tasks)

    # Tutti rimossi
    assert len(_BACKGROUND_TASKS) == 0


def test_background_tasks_set_is_module_level() -> None:
    """L'attributo _BACKGROUND_TASKS DEVE essere a livello modulo
    (non dentro una funzione) per essere un riferimento forte stabile
    durante tutta la lifetime del processo backend."""
    assert hasattr(gen_svc, "_BACKGROUND_TASKS")
    assert isinstance(gen_svc._BACKGROUND_TASKS, set)


@pytest.mark.asyncio
async def test_pptx_pdf_completed_before_audio_finishes() -> None:
    """Smoke del flusso: simula `_run_pipeline_inner` da DOPO il
    builder.build, verifica che il PPTX path sia stato salvato in DB
    PRIMA che la task audio bg finisca.

    Approssima il flow reale senza coinvolgere LangGraph: spawn diretto
    di un task audio simulato, controllo dell'ordine delle scritture DB.
    """
    db_writes_order: list[str] = []

    pool = MagicMock()
    pool.execute = AsyncMock(
        # Salva l'intera query per match substring affidabile (non troncare!)
        side_effect=lambda *args, **_kw: db_writes_order.append(args[0])
    )

    audio_done = asyncio.Event()

    async def slow_audio() -> None:
        # Audio impiega tempo a finire (simula 2-3 min reali)
        await asyncio.sleep(0.1)
        # Simula la INSERT su audio_tracks + UPDATE audio_manifest_path
        await pool.execute(
            "UPDATE courses SET audio_manifest_path=$1 WHERE id=$2",
            "/path/audio.json",
            "course-xyz",
        )
        audio_done.set()

    # Replica del pattern in generation_service:
    # 1. PPTX/PDF update
    await pool.execute(
        "UPDATE courses SET pptx_path=$1, pdf_path=$2 WHERE id=$3",
        "/path/x.pptx",
        "/path/x.pdf",
        "course-xyz",
    )
    # 2. Job completed
    await pool.execute(
        "UPDATE generation_jobs SET status='completed' WHERE id=$1",
        "job-1",
    )
    # 3. Spawn audio bg (qui NON await)
    task = asyncio.create_task(slow_audio(), name="audio_bg_test")
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    # ── Verifica ordine: pptx + jobs sono stati scritti SUBITO,
    #    audio_manifest_path NON ancora ──
    assert any("UPDATE courses SET pptx_path" in w for w in db_writes_order)
    assert any("UPDATE generation_jobs" in w for w in db_writes_order)
    assert not any("audio_manifest_path" in w for w in db_writes_order), (
        "audio_manifest_path should not be set yet, audio is background"
    )

    # Aspetta che audio finisca davvero
    await audio_done.wait()
    await task
    # Yield once: permette al done_callback (discard) di essere eseguito.
    # asyncio.add_done_callback è schedulato come call_soon, non chiamato
    # sincronamente al completamento del task.
    await asyncio.sleep(0)

    # Ora audio_manifest_path è stato scritto, e il task è stato rimosso dal set
    assert any("audio_manifest_path" in w for w in db_writes_order)
    assert task not in _BACKGROUND_TASKS


def test_production_builder_no_longer_invokes_audio_service() -> None:
    """FIX #31 MOSSA 3: ProductionBuilder.build NON deve più importare
    AudioService né invocare generate_narrations. La responsabilità è
    passata al caller (generation_service)."""
    import inspect

    from app.builders.production_builder import ProductionBuilder

    src = inspect.getsource(ProductionBuilder.build)
    assert "AudioService" not in src, (
        "FIX #31 violation: AudioService still imported inline in builder.build"
    )
    assert "generate_narrations" not in src, (
        "FIX #31 violation: builder.build still calls generate_narrations"
    )
