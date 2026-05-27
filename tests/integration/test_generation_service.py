"""generation_service tests (FASE 5.1).

Coverage:
- ``_job_semaphore`` lives in generation_service (REI-3 / FIX-7 v2.0)
- ``PIPELINE_TIMEOUT_SECONDS`` reads from settings (OPT-2)
- ``build_normative_fingerprint`` pure determinism
- ``send_ws_progress`` writes the expected UPDATE
- ``run_pipeline`` happy path (mocked pipeline + ProductionBuilder)
- ``run_pipeline`` timeout → status='failed'
- ``run_pipeline`` shutdown event → status='cancelled' + re-raise
- ``run_pipeline`` generic exception → status='failed' with truncated msg
- ``recover_interrupted_jobs`` issues the BP §09.2 UPDATE
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# WeasyPrint shim — pdf_builder is imported transitively via production_builder.
import sys

if "weasyprint" not in sys.modules:  # pragma: no cover
    sys.modules["weasyprint"] = MagicMock()

from app.services import generation_service as gs  # noqa: E402
from app.services.dependencies import get_shutdown_event  # noqa: E402
from app.services.generation_service import (  # noqa: E402
    MAX_CONCURRENT_JOBS,
    _job_semaphore,
    build_normative_fingerprint,
    recover_interrupted_jobs,
    run_pipeline,
    send_ws_progress,
)


# ─────────────── shared fixtures ───────────────


@pytest.fixture(autouse=True)
def _reset_shutdown_event() -> Any:
    """Each test starts with a clean shutdown event."""
    evt = get_shutdown_event()
    evt.clear()
    yield
    evt.clear()


def _fake_pool() -> Any:
    pool = MagicMock()
    pool.execute = AsyncMock(return_value=None)
    pool.fetchrow = AsyncMock(return_value=None)
    return pool


def _course_row() -> dict[str, Any]:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": "Corso Test",
        "course_type": "primo_soccorso_gruppo_b_c",
        "target": "discente",
        "duration_hours": 1.0,
        "region": "NAZIONALE",
        "brand_preset_id": "22222222-2222-2222-2222-222222222222",
        "outputs": ["pptx", "pdf"],
    }


def _brand_row() -> dict[str, Any]:
    return {
        "id": "22222222-2222-2222-2222-222222222222",
        "palette": {"primary": "#1a365d", "secondary": "#2b6cb0"},
    }


# ─────────────── 1. Architectural invariants (REI-3 / FIX-7 / OPT-2) ───────────────


def test_job_semaphore_is_single_permit() -> None:
    assert MAX_CONCURRENT_JOBS == 1
    assert _job_semaphore._value == 1


def test_job_semaphore_lives_in_generation_service_not_dependencies() -> None:
    """FIX-7 v2.0: the Semaphore(1) belongs to generation_service, NOT to
    dependencies.py. Mirror of the meta-test in test_production_builder."""
    from app.services import dependencies as deps

    deps_attrs = {n for n in vars(deps) if "semaphore" in n.lower()}
    assert deps_attrs == set(), (
        f"FIX-7 violation: dependencies.py holds {deps_attrs}"
    )


def test_pipeline_timeout_seconds_comes_from_settings() -> None:
    """OPT-2: PIPELINE_TIMEOUT_SECONDS reads ``settings.pipeline_timeout``,
    NOT ``os.environ['PIPELINE_TIMEOUT']``."""
    from app.config import settings

    assert gs.PIPELINE_TIMEOUT_SECONDS == settings.pipeline_timeout


# ─────────────── 2. build_normative_fingerprint — pure ───────────────


def test_fingerprint_deduplicates_refs_and_chunk_ids() -> None:
    slides = [
        {"normative_ref": "Art. 1, DM 388/2003", "source_chunk_ids": ["a", "b"]},
        {"normative_ref": "Art. 1, DM 388/2003", "source_chunk_ids": ["b", "c"]},
        {"normative_ref": "Art. 2, DM 388/2003", "source_chunk_ids": ["c"]},
    ]
    fp = build_normative_fingerprint(slides)
    assert fp["refs"] == ["Art. 1, DM 388/2003", "Art. 2, DM 388/2003"]
    assert fp["chunk_count"] == 3
    assert "generated_at" in fp


def test_fingerprint_handles_missing_or_empty_fields() -> None:
    slides = [
        {},  # nessun campo
        {"normative_ref": ""},  # ref vuoto
        {"normative_ref": None, "source_chunk_ids": None},
        {"normative_ref": "Art. 1", "source_chunk_ids": []},
    ]
    fp = build_normative_fingerprint(slides)
    assert fp["refs"] == ["Art. 1"]
    assert fp["chunk_count"] == 0


def test_fingerprint_preserves_first_occurrence_order() -> None:
    slides = [
        {"normative_ref": "C"},
        {"normative_ref": "A"},
        {"normative_ref": "B"},
        {"normative_ref": "A"},
    ]
    fp = build_normative_fingerprint(slides)
    assert fp["refs"] == ["C", "A", "B"]


# ─────────────── 3. send_ws_progress ───────────────


@pytest.mark.asyncio
async def test_send_ws_progress_writes_update() -> None:
    pool = _fake_pool()
    with patch.object(gs, "get_pool", return_value=pool):
        await send_ws_progress("job-1", 50, "research")

    pool.execute.assert_awaited_once()
    sql, p1, p2, p3 = pool.execute.await_args.args
    assert "UPDATE generation_jobs" in sql
    assert "progress_percent=$1" in sql
    assert (p1, p2, p3) == (50, "research", "job-1")


# ─────────────── 4. run_pipeline — happy path ───────────────


@asynccontextmanager
async def _fake_pipeline_ctx(*_a: Any, **_kw: Any) -> AsyncIterator[Any]:
    pipe = MagicMock()
    pipe.ainvoke = AsyncMock(
        return_value={
            "completed_modules": [
                {
                    "slides": [
                        # FASE 1: slide conforme LAYOUT_CONSTRAINTS (body 3 bullet,
                        # notes 80 parole in range 75-90 per CONTENT_TEXT).
                        {
                            "index": 0,
                            "module_index": 0,
                            "slide_type": "CONTENT_TEXT",
                            "title": "Slide 0 titolo breve",
                            "body": "Primo bullet\nSecondo bullet\nTerzo bullet",
                            "speaker_notes": " ".join(["parola"] * 80),
                            "normative_ref": "Art. 1",
                            "source_chunk_ids": ["c1"],
                            "image": {"strategy": "none"},
                            "quiz_options": None,
                            "quiz_correct": None,
                        }
                    ]
                }
            ]
        }
    )
    yield pipe


@pytest.mark.asyncio
async def test_run_pipeline_happy_path_writes_all_expected_state() -> None:
    pool = _fake_pool()
    pool.fetchrow.side_effect = [_course_row(), _brand_row()]

    fake_builder = MagicMock()
    fake_builder.build = AsyncMock(
        return_value=("/out/course_corso.pptx", "/out/course_dispensa.pdf", {})
    )

    with patch.object(gs, "get_pool", return_value=pool), patch.object(
        gs, "create_pipeline", _fake_pipeline_ctx
    ), patch.object(
        gs, "prefetch_images", AsyncMock(return_value={})
    ), patch.object(
        gs, "ProductionBuilder", return_value=fake_builder
    ):
        await run_pipeline("job-happy", "course-happy")

    # Collect every SQL fragment issued
    sqls = [call.args[0] for call in pool.execute.await_args_list]
    assert any("status='research'" in s for s in sqls)
    assert any("slide_contents_json" in s for s in sqls)
    assert any("normative_fingerprint" in s for s in sqls)
    assert any("status='building'" in s for s in sqls)
    assert any("status='completed'" in s for s in sqls)
    assert any("INSERT INTO audit_log" in s for s in sqls)

    # ProductionBuilder must receive db=pool (required for audio output path)
    kwargs = fake_builder.build.await_args.kwargs
    assert kwargs["db"] is pool
    assert kwargs["job_id"] == "job-happy"


# ─────────────── 5. timeout / cancel / exception paths ───────────────


@pytest.mark.asyncio
async def test_run_pipeline_timeout_marks_job_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timeout in the inner pipeline maps to status='failed' with the
    canonical 'Pipeline timeout dopo 30 minuti' message."""
    pool = _fake_pool()

    monkeypatch.setattr(gs, "PIPELINE_TIMEOUT_SECONDS", 0.05)

    async def _hang(_job: str, _course: str) -> None:
        await asyncio.sleep(2)

    with patch.object(gs, "get_pool", return_value=pool), patch.object(
        gs, "_run_pipeline_inner", _hang
    ):
        await run_pipeline("job-timeout", "course-x")

    failed_call = next(
        c for c in pool.execute.await_args_list if "status='failed'" in c.args[0]
    )
    assert "Pipeline timeout" in failed_call.args[0]
    assert failed_call.args[1] == "job-timeout"


@pytest.mark.asyncio
async def test_run_pipeline_marks_cancelled_on_shutdown_event() -> None:
    """When shutdown_event is set BEFORE the inner pipeline starts,
    ``_run_pipeline_inner`` raises CancelledError → run_pipeline writes
    status='cancelled' and re-raises (so asyncio task tree closes cleanly)."""
    pool = _fake_pool()
    get_shutdown_event().set()

    with patch.object(gs, "get_pool", return_value=pool):
        with pytest.raises(asyncio.CancelledError):
            await run_pipeline("job-shut", "course-x")

    cancel_call = next(
        c for c in pool.execute.await_args_list if "status='cancelled'" in c.args[0]
    )
    assert cancel_call.args[1] == "job-shut"


@pytest.mark.asyncio
async def test_run_pipeline_generic_exception_writes_truncated_message() -> None:
    pool = _fake_pool()
    long_msg = "x" * 1000

    async def _boom(_job: str, _course: str) -> None:
        raise RuntimeError(long_msg)

    with patch.object(gs, "get_pool", return_value=pool), patch.object(
        gs, "_run_pipeline_inner", _boom
    ):
        await run_pipeline("job-boom", "course-x")

    failed = next(
        c
        for c in pool.execute.await_args_list
        if "status='failed'" in c.args[0] and "error_message=$1" in c.args[0]
    )
    msg = failed.args[1]
    assert len(msg) == 500  # truncated per BP
    assert msg == "x" * 500


# ─────────────── 6. fingerprint is persisted BEFORE the build ───────────────


@pytest.mark.asyncio
async def test_fingerprint_is_written_before_production_build() -> None:
    """BP §09.1 invariant: slide_contents_json + normative_fingerprint are
    persisted PRIOR to ProductionBuilder.build so a crash mid-build leaves
    enough state to resume / inspect."""
    pool = _fake_pool()
    pool.fetchrow.side_effect = [_course_row(), _brand_row()]

    order: list[str] = []

    async def track_execute(sql: str, *_p: Any) -> None:
        if "normative_fingerprint" in sql:
            order.append("FINGERPRINT")
        if "status='building'" in sql:
            order.append("BUILDING")

    pool.execute.side_effect = track_execute

    fake_builder = MagicMock()

    async def _build(**_kw: Any) -> tuple[str, str, dict[str, Any]]:
        order.append("BUILD_CALLED")
        return ("/p.pptx", "/p.pdf", {})

    fake_builder.build = _build

    with patch.object(gs, "get_pool", return_value=pool), patch.object(
        gs, "create_pipeline", _fake_pipeline_ctx
    ), patch.object(
        gs, "prefetch_images", AsyncMock(return_value={})
    ), patch.object(
        gs, "ProductionBuilder", return_value=fake_builder
    ):
        await run_pipeline("job-order", "course-order")

    # FINGERPRINT must come strictly before BUILD_CALLED.
    fp_pos = order.index("FINGERPRINT")
    build_pos = order.index("BUILD_CALLED")
    assert fp_pos < build_pos


# ─────────────── 7. recover_interrupted_jobs ───────────────


@pytest.mark.asyncio
async def test_recover_interrupted_jobs_executes_reset_update() -> None:
    pool = MagicMock()
    pool.execute = AsyncMock(return_value="UPDATE 3")

    await recover_interrupted_jobs(pool)

    pool.execute.assert_awaited_once()
    sql = pool.execute.await_args.args[0]
    assert "UPDATE generation_jobs" in sql
    assert "status='failed'" in sql
    assert "'research'" in sql and "'content'" in sql and "'building'" in sql


@pytest.mark.asyncio
async def test_recover_interrupted_jobs_noop_when_no_rows() -> None:
    pool = MagicMock()
    pool.execute = AsyncMock(return_value="UPDATE 0")
    # Should not warn-log (no rows); just complete cleanly.
    await recover_interrupted_jobs(pool)
    pool.execute.assert_awaited_once()


# ─────────────── 8. structural meta-tests ───────────────


def test_audit_log_insert_uses_pipeline_metrics_action() -> None:
    """BP §09.1 line 2862: telemetry rows in audit_log must use the
    canonical action string 'pipeline_metrics'. Search via source so a
    rename triggers CI failure (Delta-Update / dashboards rely on it)."""
    import inspect

    src = inspect.getsource(gs)
    assert "'pipeline_metrics'" in src or '"pipeline_metrics"' in src


def test_initial_state_matches_bp_05_2_eight_fields() -> None:
    """BP §05.2 invariant: NexusPipelineState has EXACTLY 8 fields. The
    initial_state dict in _run_pipeline_inner must populate the same 8."""
    import inspect

    src = inspect.getsource(gs._run_pipeline_inner)
    for key in (
        "course_request",
        "brand_config",
        "course_context",
        "pacing_plan",
        "completed_modules",
        "current_module_index",
        "job_id",
        "errors",
    ):
        assert f'"{key}":' in src, f"missing key {key!r} in initial_state"


def test_fingerprint_serializes_to_json_safely() -> None:
    """The fingerprint dict goes through ``json.dumps`` — ensure it's
    serialisable (no datetime/set objects leaking through)."""
    fp = build_normative_fingerprint(
        [{"normative_ref": "X", "source_chunk_ids": ["a"]}]
    )
    encoded = json.dumps(fp)
    decoded = json.loads(encoded)
    assert decoded["refs"] == ["X"]
    assert decoded["chunk_count"] == 1
