"""AudioService happy-path tests (FASE 4.6).

5 slide con speaker_notes → 5 file MP3 (mockati) + manifest JSON valido
+ 5 INSERT su audio_tracks + 1 UPDATE su courses.audio_manifest_path.
``edge_tts.Communicate`` è il punto di patch unico (seam ``AudioService._tts_save``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.core import SlideType
from app.models.pipeline import ImageStrategy, SlideContent
from app.services import audio_service as svc
from app.services.audio_service import AudioService


def _slide(
    index: int,
    *,
    speaker_notes: str | None = None,
    body: str | None = None,
) -> SlideContent:
    """FASE 1 vast-hopping: delega a make_slide centralizzato (constraints-safe).

    Se vuoi testare il fallback body→narration (speaker_notes vuote), passa
    ``speaker_notes=""`` esplicito e ``body="qualcosa di leggibile"``.
    """
    from tests._helpers import make_slide

    overrides: dict[str, object] = {
        "index": index,
        "title": f"Slide {index}",
    }
    if body is not None:
        overrides["body"] = body
    if speaker_notes is not None:
        overrides["speaker_notes"] = speaker_notes
    return make_slide(SlideType.CONTENT_TEXT, **overrides)


def _empty_pool() -> Any:
    pool = MagicMock()
    pool.execute = AsyncMock(return_value=None)
    return pool


def _fake_save_factory(audio_root: Path) -> Any:
    """Build a Communicate stub whose .save() writes a tiny non-empty file
    so MP3() doesn't crash before being patched."""

    def fake_init(self: Any, narration: str, voice: str) -> None:
        self._narration = narration
        self._voice = voice

    async def fake_save(self: Any, path: str) -> None:
        # Write some bytes so the file exists; mutagen.MP3 is patched, so
        # the content doesn't have to be a valid MP3.
        Path(path).write_bytes(b"\x00fake-mp3-bytes\x00")

    stub = MagicMock()
    stub.side_effect = lambda narration, voice: MagicMock(
        save=AsyncMock(side_effect=lambda p: Path(p).write_bytes(b"\x00fake\x00"))
    )
    _ = audio_root, fake_init, fake_save  # silence ruff
    return stub


@pytest.mark.asyncio
async def test_generate_narrations_produces_files_inserts_and_manifest(
    tmp_path: Path,
) -> None:
    slides = [_slide(i) for i in range(5)]
    pool = _empty_pool()
    course_id = "course-aaa-bbb"

    fake_mp3 = MagicMock()
    fake_mp3.info.length = 12.5

    with patch.object(svc, "_AUDIO_ROOT", tmp_path / "audio"), patch.object(
        svc.AudioService,
        "_tts_save",
        new=AsyncMock(
            side_effect=lambda narration, audio_path: Path(audio_path).write_bytes(
                b"\x00fake\x00"
            )
        ),
    ), patch.object(svc, "MP3", return_value=fake_mp3):
        service = AudioService(voice="it-IT-DiegoNeural")
        result = await service.generate_narrations(slides, course_id, pool)

    # 1. result shape
    assert result["tracks_generated"] == 5
    assert result["tracks_skipped"] == 0
    assert result["course_id"] == course_id
    manifest_path = Path(result["manifest_path"])
    assert manifest_path.is_file()

    # 2. one MP3 file per slide (mocked content, not a real MP3)
    audio_dir = tmp_path / "audio" / course_id
    mp3s = sorted(audio_dir.glob("slide_*.mp3"))
    assert len(mp3s) == 5
    assert [p.name for p in mp3s] == [
        f"slide_{i:04d}.mp3" for i in range(5)
    ]

    # 3. manifest JSON is well-formed and matches the audio files
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["course_id"] == course_id
    assert manifest["total_tracks"] == 5
    assert len(manifest["tracks"]) == 5
    for i, track in enumerate(manifest["tracks"]):
        assert track["slide_index"] == i
        assert track["audio_file"] == f"slide_{i:04d}.mp3"
        assert track["duration_seconds"] == 12.5
        # FASE 1: narration text è speaker_notes della slide; default factory
        # produce 80 "parola" parole (range valido CONTENT_TEXT 75-90).
        assert isinstance(track["narration_text"], str)
        assert len(track["narration_text"].split()) >= 75

    # 4. pool.execute: 5 INSERTs + 1 UPDATE courses.audio_manifest_path
    assert pool.execute.await_count == 6
    insert_calls = [
        c for c in pool.execute.await_args_list if "INSERT INTO audio_tracks" in c.args[0]
    ]
    update_calls = [
        c for c in pool.execute.await_args_list if "UPDATE courses" in c.args[0]
    ]
    assert len(insert_calls) == 5
    assert len(update_calls) == 1
    # The UPDATE writes the manifest path under the right course id.
    assert update_calls[0].args[1] == result["manifest_path"]
    assert update_calls[0].args[2] == course_id
    # Each INSERT carries the right voice and rounded duration.
    for call in insert_calls:
        assert call.args[1] == course_id
        assert call.args[5] == 12.5
        assert call.args[6] == "it-IT-DiegoNeural"


@pytest.mark.asyncio
async def test_generate_narrations_skips_slides_without_text(
    tmp_path: Path,
) -> None:
    """Slides whose speaker_notes AND body are both empty/whitespace are
    skipped — they don't get an MP3, an INSERT, or a manifest entry."""
    # FASE 1: bypass strict validator per slide intermedia "edge" (notes vuote
    # da DB legacy o edit post-validation). Il codice runtime deve skipparla.
    empty_slide = _slide(1)
    object.__setattr__(empty_slide, "body", "   ")
    object.__setattr__(empty_slide, "speaker_notes", "   ")
    slides = [
        _slide(0),
        empty_slide,
        _slide(2),
    ]
    pool = _empty_pool()
    fake_mp3 = MagicMock()
    fake_mp3.info.length = 5.0

    with patch.object(svc, "_AUDIO_ROOT", tmp_path / "audio"), patch.object(
        svc.AudioService,
        "_tts_save",
        new=AsyncMock(
            side_effect=lambda narration, audio_path: Path(audio_path).write_bytes(b"x")
        ),
    ), patch.object(svc, "MP3", return_value=fake_mp3):
        service = AudioService(voice="it-IT-DiegoNeural")
        result = await service.generate_narrations(slides, "course-x", pool)

    assert result["tracks_generated"] == 2
    # 2 INSERT + 1 UPDATE
    assert pool.execute.await_count == 3


@pytest.mark.asyncio
async def test_narration_falls_back_to_body_when_speaker_notes_empty(
    tmp_path: Path,
) -> None:
    # FASE 1: il validator strict non ammette speaker_notes vuote per CONTENT_TEXT,
    # ma il codice runtime deve gestire questo edge case (slide da DB legacy o edit
    # post-validation). Bypass via object.__setattr__.
    slide = _slide(0)
    object.__setattr__(slide, "speaker_notes", "")
    object.__setattr__(slide, "body", "Testo del body usato come fallback.")
    slides = [slide]
    pool = _empty_pool()
    fake_mp3 = MagicMock()
    fake_mp3.info.length = 4.0
    captured: dict[str, str] = {}

    async def fake_save(self: Any, narration: str, audio_path: str) -> None:
        captured["narration"] = narration
        Path(audio_path).write_bytes(b"x")

    with patch.object(svc, "_AUDIO_ROOT", tmp_path / "audio"), patch.object(
        svc.AudioService,
        "_tts_save",
        new=fake_save,
    ), patch.object(svc, "MP3", return_value=fake_mp3):
        service = AudioService(voice="it-IT-DiegoNeural")
        await service.generate_narrations(slides, "course-fb", pool)

    assert captured["narration"] == "Testo del body usato come fallback."


@pytest.mark.asyncio
async def test_voice_is_propagated_to_communicate(tmp_path: Path) -> None:
    """The voice configured in __init__ must reach edge_tts.Communicate."""
    slides = [_slide(0)]
    pool = _empty_pool()
    fake_mp3 = MagicMock()
    fake_mp3.info.length = 3.0

    fake_communicate = MagicMock(save=AsyncMock())
    with patch.object(svc, "_AUDIO_ROOT", tmp_path / "audio"), patch(
        "app.services.audio_service.edge_tts.Communicate",
        return_value=fake_communicate,
    ) as cls, patch.object(svc, "MP3", return_value=fake_mp3):
        service = AudioService(voice="it-IT-IsabellaNeural")
        await service.generate_narrations(slides, "course-v", pool)

    # First positional/kwarg of Communicate(...) is the narration text;
    # the second is the voice. Verify voice came through unchanged.
    args, kwargs = cls.call_args
    voice_arg = args[1] if len(args) >= 2 else kwargs.get("voice")
    assert voice_arg == "it-IT-IsabellaNeural"


@pytest.mark.asyncio
async def test_manifest_path_is_persisted_in_courses_table(tmp_path: Path) -> None:
    slides = [_slide(0)]
    pool = _empty_pool()
    fake_mp3 = MagicMock()
    fake_mp3.info.length = 2.0

    with patch.object(svc, "_AUDIO_ROOT", tmp_path / "audio"), patch.object(
        svc.AudioService,
        "_tts_save",
        new=AsyncMock(
            side_effect=lambda narration, audio_path: Path(audio_path).write_bytes(b"x")
        ),
    ), patch.object(svc, "MP3", return_value=fake_mp3):
        service = AudioService()
        result = await service.generate_narrations(slides, "course-persist", pool)

    update_call = next(
        c for c in pool.execute.await_args_list if "UPDATE courses" in c.args[0]
    )
    assert update_call.args[0].strip().startswith("UPDATE courses")
    assert update_call.args[1] == result["manifest_path"]
    assert update_call.args[2] == "course-persist"


# ─────────────── 6. structural meta-test (OPT-1 — no OpenAI) ───────────────


def test_audio_service_does_not_import_openai() -> None:
    """OPT-1 invariant: no OpenAI dependency. AST-based check skips docstrings
    so the rule is enforced against real CODE, not narrative prose."""
    import ast
    import inspect

    src = inspect.getsource(svc)
    tree = ast.parse(src)

    class _StripDocstrings(ast.NodeTransformer):
        def _strip(self, node: Any) -> Any:
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:] or [ast.Pass()]
            return node

        def visit_Module(self, node: ast.Module) -> Any:
            self.generic_visit(node)
            return self._strip(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
            self.generic_visit(node)
            return self._strip(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
            self.generic_visit(node)
            return self._strip(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> Any:
            self.generic_visit(node)
            return self._strip(node)

    stripped = ast.unparse(_StripDocstrings().visit(tree))
    assert "openai" not in stripped.lower(), (
        "OPT-1 violation: OpenAI reference found in production code"
    )
    assert "import edge_tts" in stripped
