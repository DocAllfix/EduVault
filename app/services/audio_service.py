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


def _slide_fallback_text(s: SlideContent) -> str:
    """Flatten bullets/sezioni (FIX #28.1 schema) when speaker_notes is empty.

    Used by the narration fallback chain: ``speaker_notes`` first (preferred,
    discorsive prose), else bullets/sezioni stitched into a paragraph so the
    TTS still has something to read.
    """
    if getattr(s, "sezioni", None):
        return ". ".join(s.sezioni)
    if getattr(s, "bullets", None):
        return ". ".join(s.bullets)
    return ""

_AUDIO_ROOT = Path("output/audio")
_TTS_TIMEOUT_SECONDS = 30.0
# FIX #31 MOSSA 3 (2026-05-27, analista): sem 16→6. edge-tts è un servizio
# Microsoft Edge "free" non ufficiale — sotto raffica >6 concurrent
# restituisce reset/403 silenziosi che il retry tenacity vede come failure
# generica (no codice riconoscibile). Empiricamente 6 è il sweet-spot:
#   - sema=16: ~8 min stimati ma con N% failure silenti su batch grandi
#   - sema=6:  ~12-14 min, ZERO failure
# L'aumento di tempo è compensato dallo spostamento in background
# (MOSSA 3 D4): l'utente riceve PPTX subito, audio arriva 2-3 min dopo
# via polling endpoint. Pre-fix (storico):
#   - sema=3: 960 mp3 × 8s = ~43 min
#   - sema=8: ~16 min
#   - sema=16: ~8 min (regressivo: failure silenti)
_TTS_SEMAPHORE_LIMIT = 6
_TTS_RETRY_ATTEMPTS = 3

# FASE 6 vast-hopping: target durata narrazione per slide (regola 30s/slide
# PacingEngine + tolleranza). Fuori range → flag off_target (no auto-retry v1,
# l'utente regenera manualmente dalla Course Studio FASE 10).
_TARGET_DURATION_MIN = 25.0
_TARGET_DURATION_MAX = 35.0
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

        ``narration_text`` falls back to flattened bullets/sezioni
        (FIX #28.1 schema) when ``speaker_notes`` is empty. The "discorsivo
        rephrase" mentioned in the prompt is NOT implemented in v1.0 — see
        REI-16 discrepancy D40.

        Returns: ``{"tracks_generated": int, "tracks_skipped": int,
        "manifest_path": str | None, "course_id": str}``.
        """
        course_audio_dir = _AUDIO_ROOT / course_id
        course_audio_dir.mkdir(parents=True, exist_ok=True)

        tracks: list[dict[str, Any]] = []
        skipped = 0

        narratable = [
            s for s in slides if (s.speaker_notes or _slide_fallback_text(s)).strip()
        ]
        results = await asyncio.gather(
            *(self._generate_one(s, course_audio_dir) for s in narratable),
            return_exceptions=False,
        )

        off_target_count = 0
        for slide, result in zip(narratable, results, strict=True):
            if result is None:
                skipped += 1
                continue
            audio_path_str, duration_s, narration, off_target = result
            if off_target:
                off_target_count += 1
            tracks.append(
                {
                    "module_index": slide.module_index,
                    "slide_index": slide.index,
                    "audio_file": Path(audio_path_str).name,
                    "duration_seconds": round(duration_s, 2),
                    "narration_text": narration,
                    "off_target": off_target,
                }
            )
            from app.config import settings as _s

            provider_used = (
                "azure"
                if _s.v2_audio_provider_azure and _s.azure_speech_key
                else "edge"
            )
            # F-AUDIO-FIX 2026-06-01: include module_index per dedup univoca
            # (slide.index e' module-relative; col solo slide_index collidono
            # tutti i moduli sul medesimo slot — vedi migration 014).
            await pool.execute(
                "INSERT INTO audio_tracks "
                "(course_id, module_index, slide_index, narration_text, audio_path, "
                "duration_seconds, voice, off_target, provider) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                course_id,
                slide.module_index,
                slide.index,
                narration,
                audio_path_str,
                round(duration_s, 2),
                self.voice,
                off_target,
                provider_used,
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
            off_target_count=off_target_count,  # FASE 6
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
    ) -> tuple[str, float, str, bool] | None:
        """Generate one MP3 with retry + per-slide fallback (log + skip).

        Returns ``(audio_path, duration_seconds, narration_text, off_target)``
        on success, ``None`` if all retries failed — la slide è skippata dal
        manifest e da audio_tracks (BP §07.1 line 2301: un artefatto rotto NON
        uccide la build).

        FASE 6: ``off_target`` è True se la durata è fuori 25-35s (la slide
        narra troppo veloce/lento rispetto alla regola 30s/slide).
        """
        narration = (slide.speaker_notes or _slide_fallback_text(slide)).strip()
        # F-AUDIO-FIX 2026-06-01: filename include module_index, perche` slide.index
        # e' module-relative (0..N per modulo). Senza prefisso modulo i moduli
        # successivi sovrascrivono i file dei precedenti — bug osservato in prod:
        # solo l'ultimo modulo aveva MP3 playable. Migration 014 + INSERT/SELECT.
        audio_path = (
            course_audio_dir
            / f"mod_{slide.module_index:02d}_slide_{slide.index:04d}.mp3"
        )

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

            duration = float(MP3(str(audio_path)).info.length)
            off_target = not (_TARGET_DURATION_MIN <= duration <= _TARGET_DURATION_MAX)
            if off_target:
                logger.info(
                    "audio_duration_off_target",
                    slide_index=slide.index,
                    duration=round(duration, 1),
                    target=f"{_TARGET_DURATION_MIN}-{_TARGET_DURATION_MAX}s",
                )
            return (str(audio_path), duration, narration, off_target)

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
        """Thin wrapper around TTS provider save() — isolated so tests
        can patch a single seam.

        F7.1 (vast-hopping post-MVP 2026-05-31): selettore provider.
        Default edge-tts (free, no key). Se `settings.v2_audio_provider_azure`
        True E `settings.azure_speech_key` valorizzato → Azure Speech SDK
        con SSML completo (via app.services.ssml.text_to_ssml). Fallback
        automatico a edge-tts se azure-cognitiveservices-speech NON
        installato o se Azure raises (es. quota / key invalida).
        """
        from app.config import settings

        if settings.v2_audio_provider_azure and settings.azure_speech_key:
            try:
                await _azure_tts_save(
                    narration, audio_path, self.voice, settings.azure_speech_region
                )
                return
            except Exception as exc:
                logger.warning(
                    "azure_tts_fallback_to_edge",
                    error_class=type(exc).__name__,
                    error_msg=str(exc)[:200],
                )
                # fallthrough to edge-tts

        # Default path: edge-tts (no SSML, plain text)
        communicate = edge_tts.Communicate(narration, self.voice)
        await communicate.save(audio_path)


async def _azure_tts_save(
    narration: str, audio_path: str, voice: str, region: str
) -> None:
    """F7.3 — Azure Speech SDK wrapper con SSML.

    Import gated dentro la funzione: il pacchetto
    `azure-cognitiveservices-speech` e' OPTIONAL (non in pyproject base),
    da installare con `pip install azure-cognitiveservices-speech` per
    abilitare il provider. Se ImportError → eccezione catturata dal caller
    che falla automaticamente su edge-tts.
    """
    try:
        import azure.cognitiveservices.speech as speechsdk  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "azure-cognitiveservices-speech NON installato. "
            "Install: pip install azure-cognitiveservices-speech"
        ) from exc

    from app.config import settings
    from app.services.ssml import text_to_ssml

    speech_config = speechsdk.SpeechConfig(
        subscription=settings.azure_speech_key, region=region
    )
    audio_config = speechsdk.audio.AudioOutputConfig(filename=audio_path)
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=audio_config
    )
    ssml = text_to_ssml(narration, voice)

    # Azure SDK e' sync; wrap in asyncio.to_thread per non bloccare event loop
    result = await asyncio.to_thread(synthesizer.speak_ssml, ssml)

    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        raise RuntimeError(
            f"Azure TTS synthesis failed: {result.reason} "
            f"(details: {result.cancellation_details if result.reason == speechsdk.ResultReason.Canceled else 'n/a'})"
        )


__all__ = ["AudioService"]
