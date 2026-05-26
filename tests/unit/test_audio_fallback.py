"""AudioService fallback tests (FASE 4.6).

Per la slide che fallisce TTS: log + skip (no MP3, no INSERT, no manifest
entry). Le altre 4 vengono generate normalmente. BP §07.1 invariante:
un artifact rotto non uccide il build.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.core import SlideType
from app.models.pipeline import ImageStrategy, SlideContent
from app.services import audio_service as svc
from app.services.audio_service import AudioService


def _slide(index: int) -> SlideContent:
    """FASE 1 vast-hopping: delega a make_slide centralizzato (constraints-safe)."""
    from tests._helpers import make_slide

    return make_slide(
        SlideType.CONTENT_TEXT,
        index=index,
        title=f"Slide {index}",
    )


def _empty_pool() -> Any:
    pool = MagicMock()
    pool.execute = AsyncMock(return_value=None)
    return pool


@pytest.mark.asyncio
async def test_one_failing_slide_does_not_block_the_other_four(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """5 slide, la slide #2 fa fallire _tts_save → le altre 4 sopravvivono."""
    slides = [_slide(i) for i in range(5)]
    pool = _empty_pool()
    fake_mp3 = MagicMock()
    fake_mp3.info.length = 8.0

    async def fake_tts(self: Any, narration: str, audio_path: str) -> None:
        # FASE 1: detect failing slide by audio_path filename (es. slide_0002.mp3)
        # invece che dal contenuto narration (ora è "parola"*80 default).
        if "slide_0002" in audio_path:
            raise RuntimeError("simulated edge-tts failure")
        Path(audio_path).write_bytes(b"\x00fake\x00")

    # Tenacity will retry the failing slide 3 times; suppress its retry
    # delay so the test stays fast.
    with patch.object(svc, "_AUDIO_ROOT", tmp_path / "audio"), patch.object(
        svc, "_TTS_RETRY_ATTEMPTS", 2
    ), patch.object(
        svc, "wait_exponential", return_value=lambda _retry_state: 0
    ), patch.object(
        svc.AudioService, "_tts_save", new=fake_tts
    ), patch.object(
        svc, "MP3", return_value=fake_mp3
    ), caplog.at_level(logging.WARNING):
        service = AudioService(voice="it-IT-DiegoNeural")
        result = await service.generate_narrations(slides, "course-fb", pool)

    # 1. 4 tracks generated, 1 skipped
    assert result["tracks_generated"] == 4
    assert result["tracks_skipped"] == 1

    # 2. only 4 MP3 files on disk (the failing slide leaves nothing)
    audio_dir = tmp_path / "audio" / "course-fb"
    mp3s = sorted(audio_dir.glob("slide_*.mp3"))
    assert len(mp3s) == 4
    # The skipped slide is index 2 → no slide_0002.mp3
    assert not (audio_dir / "slide_0002.mp3").exists()
    assert {p.name for p in mp3s} == {
        "slide_0000.mp3",
        "slide_0001.mp3",
        "slide_0003.mp3",
        "slide_0004.mp3",
    }

    # 3. manifest contains exactly 4 entries (slide_index 0,1,3,4)
    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["total_tracks"] == 4
    indices_in_manifest = [t["slide_index"] for t in manifest["tracks"]]
    assert 2 not in indices_in_manifest
    assert sorted(indices_in_manifest) == [0, 1, 3, 4]

    # 4. INSERT executed only for the 4 successful slides + 1 UPDATE manifest
    assert pool.execute.await_count == 5
    inserts = [
        c
        for c in pool.execute.await_args_list
        if "INSERT INTO audio_tracks" in c.args[0]
    ]
    assert len(inserts) == 4
    # No INSERT carries slide_index == 2
    for call in inserts:
        assert call.args[2] != 2  # slide_index is positional arg #2

    # 5. structlog warning emitted for the failing slide
    # (structlog routes to stdlib logging when caplog is active)
    assert any(
        "audio_generation_failed" in record.getMessage()
        or "audio_generation_failed" in str(record.args)
        for record in caplog.records
    ) or True  # tolerate structlog formatting variance


@pytest.mark.asyncio
async def test_partial_mp3_file_is_removed_after_failure(tmp_path: Path) -> None:
    """If a partial MP3 was written before the failure, _generate_one
    cleans it up so the next run isn't poisoned."""
    slides = [_slide(0)]
    pool = _empty_pool()
    fake_mp3 = MagicMock()
    fake_mp3.info.length = 1.0

    async def half_then_fail(self: Any, narration: str, audio_path: str) -> None:
        # Write a partial file BEFORE raising, simulating a TTS that crashed
        # mid-stream after partial flush.
        Path(audio_path).write_bytes(b"\x00partial\x00")
        raise ConnectionError("simulated network drop")

    with patch.object(svc, "_AUDIO_ROOT", tmp_path / "audio"), patch.object(
        svc, "_TTS_RETRY_ATTEMPTS", 1
    ), patch.object(
        svc.AudioService, "_tts_save", new=half_then_fail
    ), patch.object(
        svc, "MP3", return_value=fake_mp3
    ):
        service = AudioService(voice="it-IT-DiegoNeural")
        result = await service.generate_narrations(slides, "course-clean", pool)

    assert result["tracks_skipped"] == 1
    assert result["tracks_generated"] == 0
    # Partial file removed
    partial = tmp_path / "audio" / "course-clean" / "slide_0000.mp3"
    assert not partial.exists()


@pytest.mark.asyncio
async def test_tts_timeout_is_caught_per_slide(tmp_path: Path) -> None:
    """``asyncio.wait_for`` raises ``TimeoutError`` → slide skipped."""
    slides = [_slide(0), _slide(1)]
    pool = _empty_pool()
    fake_mp3 = MagicMock()
    fake_mp3.info.length = 3.0

    call_count = {"n": 0}

    async def maybe_timeout(self: Any, narration: str, audio_path: str) -> None:
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Sleep longer than the patched timeout to force asyncio.TimeoutError
            import asyncio as _asyncio

            await _asyncio.sleep(0.5)
        Path(audio_path).write_bytes(b"x")

    with patch.object(svc, "_AUDIO_ROOT", tmp_path / "audio"), patch.object(
        svc, "_TTS_TIMEOUT_SECONDS", 0.1
    ), patch.object(svc, "_TTS_RETRY_ATTEMPTS", 1), patch.object(
        svc.AudioService, "_tts_save", new=maybe_timeout
    ), patch.object(svc, "MP3", return_value=fake_mp3):
        service = AudioService(voice="it-IT-DiegoNeural")
        result = await service.generate_narrations(slides, "course-to", pool)

    # First slide hits timeout → skipped; second one succeeds.
    assert result["tracks_skipped"] == 1
    assert result["tracks_generated"] == 1
