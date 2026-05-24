"""AudioService — FAD narration via edge-tts (Master Plan GAP-3 / OPT-1).

Schema verified against ``app/db/migrations/001_initial.sql`` lines 214-223
(MCP postgres surface not exposed in this session — same source is the
canonical schema file, REI-5):

    audio_tracks(
        id UUID PK,
        course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
        slide_index INT NOT NULL,
        narration_text TEXT NOT NULL,
        audio_path VARCHAR(500),
        duration_seconds DECIMAL(6,2),  -- max 9999.99 s (~166 min)
        voice VARCHAR(50) DEFAULT 'it-IT-DiegoNeural',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    INDEX idx_audio_course ON audio_tracks(course_id)

The 50-char voice limit fits ``it-IT-DiegoNeural`` (16 chars) and every
other Italian Edge Neural voice. There is NO unique(course_id, slide_index)
constraint — callers must not re-issue ``generate_narrations`` for the same
course or duplicates will accumulate. ``courses.audio_manifest_path`` is
also VARCHAR(500), enforced below.

OPT-1: edge-tts (Microsoft Edge Neural TTS) — gratuito, nessuna API key,
nessun vendor lock-in. NO OpenAI dependency.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import edge_tts
import structlog
from mutagen.mp3 import MP3
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.models.pipeline import SlideContent

logger = structlog.get_logger()

_AUDIO_ROOT = Path("output/audio")
_TTS_TIMEOUT_SECONDS = 30.0
_TTS_SEMAPHORE_LIMIT = 3
_TTS_RETRY_ATTEMPTS = 3
_AUDIO_PATH_MAX = 500  # courses.audio_manifest_path + audio_tracks.audio_path VARCHAR(500)


class AudioService:
    """Generate per-slide narration MP3s + sync manifest. NO OpenAI."""

    def __init__(self, voice: str = "it-IT-DiegoNeural") -> None:
        self.voice = voice
        self._semaphore = asyncio.Semaphore(_TTS_SEMAPHORE_LIMIT)

    async def generate_narrations(
        self,
        slides: list[SlideContent],
        course_id: str,
        pool: Any,
    ) -> dict[str, Any]:
        """Generate one MP3 per narratable slide + sync manifest.

        ``narration_text`` falls back to ``slide.body`` when ``speaker_notes``
        is empty. The "discorsivo rephrase" mentioned in the prompt is NOT
        implemented in v1.0 — see REI-16 discrepancy D40.

        Returns: ``{"tracks_generated": int, "tracks_skipped": int,
        "manifest_path": str | None, "course_id": str}``.
        """
        course_audio_dir = _AUDIO_ROOT / course_id
        course_audio_dir.mkdir(parents=True, exist_ok=True)

        tracks: list[dict[str, Any]] = []
        skipped = 0

        narratable = [
            s for s in slides if (s.speaker_notes or s.body or "").strip()
        ]
        results = await asyncio.gather(
            *(self._generate_one(s, course_audio_dir) for s in narratable),
            return_exceptions=False,
        )

        for slide, result in zip(narratable, results, strict=True):
            if result is None:
                skipped += 1
                continue
            audio_path_str, duration_s, narration = result
            tracks.append(
                {
                    "slide_index": slide.index,
                    "audio_file": Path(audio_path_str).name,
                    "duration_seconds": round(duration_s, 2),
                    "narration_text": narration,
                }
            )
            await pool.execute(
                "INSERT INTO audio_tracks "
                "(course_id, slide_index, narration_text, audio_path, "
                "duration_seconds, voice) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                course_id,
                slide.index,
                narration,
                audio_path_str,
                round(duration_s, 2),
                self.voice,
            )

        manifest_path = course_audio_dir / "sync_manifest.json"
        manifest = {
            "course_id": course_id,
            "total_tracks": len(tracks),
            "tracks": tracks,
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        manifest_path_str = str(manifest_path)
        if len(manifest_path_str) > _AUDIO_PATH_MAX:
            logger.warning(
                "audio_manifest_path_truncated",
                length=len(manifest_path_str),
                limit=_AUDIO_PATH_MAX,
            )
            manifest_path_str = manifest_path_str[:_AUDIO_PATH_MAX]

        await pool.execute(
            "UPDATE courses SET audio_manifest_path = $1 WHERE id = $2",
            manifest_path_str,
            course_id,
        )

        logger.info(
            "audio_narrations_generated",
            course_id=course_id,
            tracks_generated=len(tracks),
            tracks_skipped=skipped,
            voice=self.voice,
        )
        return {
            "tracks_generated": len(tracks),
            "tracks_skipped": skipped,
            "manifest_path": manifest_path_str,
            "course_id": course_id,
        }

    async def _generate_one(
        self, slide: SlideContent, course_audio_dir: Path
    ) -> tuple[str, float, str] | None:
        """Generate one MP3 with retry + per-slide fallback (log + skip).

        Returns ``(audio_path, duration_seconds, narration_text)`` on success,
        ``None`` if all retries failed — the slide is then skipped from the
        manifest and from audio_tracks (BP §07.1 line 2301 invariant: one
        broken artifact does NOT kill the build).
        """
        narration = (slide.speaker_notes or slide.body or "").strip()
        audio_path = course_audio_dir / f"slide_{slide.index:04d}.mp3"

        try:
            async with self._semaphore:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(_TTS_RETRY_ATTEMPTS),
                    wait=wait_exponential(multiplier=1, min=2, max=10),
                    retry=retry_if_exception_type(Exception),
                    reraise=True,
                ):
                    with attempt:
                        await asyncio.wait_for(
                            self._tts_save(narration, str(audio_path)),
                            timeout=_TTS_TIMEOUT_SECONDS,
                        )

            duration = MP3(str(audio_path)).info.length
            return (str(audio_path), float(duration), narration)

        except Exception as exc:
            logger.warning(
                "audio_generation_failed",
                slide_index=slide.index,
                error=str(exc),
                voice=self.voice,
            )
            # Clean up a possibly half-written file so it doesn't poison
            # mutagen on subsequent runs.
            try:
                if audio_path.is_file():
                    os.remove(audio_path)
            except OSError:
                pass
            return None

    async def _tts_save(self, narration: str, audio_path: str) -> None:
        """Thin wrapper around edge_tts.Communicate.save() — isolated so
        tests can patch a single seam."""
        communicate = edge_tts.Communicate(narration, self.voice)
        await communicate.save(audio_path)


__all__ = ["AudioService"]
