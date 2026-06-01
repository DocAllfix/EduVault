"""F-STUDIO-UX Step 0 v2 (D-207) — unit test pptx_preview_service single-slide.

Mocked: _extract_single_slide_to_pptx (python-pptx), subprocess (soffice),
_render_pdf_page_to_png (pypdfium2).

Verifica:
- fast path PNG cached → nessuna chiamata a soffice / pdfium / extract
- prima invocazione → extract + soffice + pdfium chiamati 1 volta ciascuno
- cleanup workspace temp dopo successo (best-effort)
- cleanup workspace temp dopo errore soffice
- soffice timeout → solleva PreviewRenderError
- soffice non zero exit → solleva PreviewRenderError
- soffice non produce il PDF atteso → solleva PreviewRenderError
- pptx_path missing → FileNotFoundError
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.pptx_preview_service import (
    PreviewRenderError,
    render_pptx_slide_to_png,
)


@pytest.fixture
def fake_pptx(tmp_path: Path) -> Path:
    """Crea un file fittizio .pptx (vuoto) e ritorna il path."""
    pptx = tmp_path / "course_X.pptx"
    pptx.write_bytes(b"fake-pptx-content")
    return pptx


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """Cache dir vuota per la singola chiamata."""
    return tmp_path / "previews_cache"


def _make_proc_mock(returncode: int = 0) -> MagicMock:
    """Mock di asyncio.subprocess.Process con communicate() async."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(b"stdout", b"stderr"))
    proc.kill = MagicMock()
    proc.wait = AsyncMock()
    return proc


@pytest.mark.asyncio
async def test_fast_path_png_already_cached(
    fake_pptx: Path, cache_dir: Path
) -> None:
    """PNG in cache → ritorno immediato senza toccare extract/soffice/pdfium."""
    cache_dir.mkdir(parents=True)
    pre_existing = cache_dir / "0005.png"
    pre_existing.write_bytes(b"fake-png")

    with (
        patch(
            "app.services.pptx_preview_service._extract_single_slide_to_pptx"
        ) as mock_extract,
        patch(
            "app.services.pptx_preview_service.asyncio.create_subprocess_exec"
        ) as mock_subproc,
        patch(
            "app.services.pptx_preview_service._render_pdf_page_to_png"
        ) as mock_render,
    ):
        result = await render_pptx_slide_to_png(
            pptx_path=fake_pptx, cache_dir=cache_dir, slide_index=5
        )

    assert result == pre_existing
    mock_extract.assert_not_called()
    mock_subproc.assert_not_called()
    mock_render.assert_not_called()


@pytest.mark.asyncio
async def test_first_invocation_runs_full_pipeline(
    fake_pptx: Path, cache_dir: Path
) -> None:
    """Prima invocazione: extract → soffice → pdfium tutti chiamati 1 volta."""
    proc = _make_proc_mock(returncode=0)

    extract_calls = 0
    render_calls = 0

    def fake_extract(
        source: Path, idx: int, dest: Path
    ) -> None:
        nonlocal extract_calls
        extract_calls += 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"mini-pptx")

    def fake_subproc_factory(*args: object, **kwargs: object) -> MagicMock:
        # Simula soffice scrivendo single_slide.pdf in outdir.
        outdir_idx = args.index("--outdir") + 1
        produced_pdf = Path(str(args[outdir_idx])) / "single_slide.pdf"
        produced_pdf.parent.mkdir(parents=True, exist_ok=True)
        produced_pdf.write_bytes(b"fake-pdf")
        return proc

    def fake_render(pdf_path: Path, page_index: int, png_out: Path) -> None:
        nonlocal render_calls
        render_calls += 1
        png_out.write_bytes(b"rendered-png")

    with (
        patch(
            "app.services.pptx_preview_service._extract_single_slide_to_pptx",
            side_effect=fake_extract,
        ),
        patch(
            "app.services.pptx_preview_service.asyncio.create_subprocess_exec",
            side_effect=lambda *a, **kw: fake_subproc_factory(*a, **kw),
        ),
        patch(
            "app.services.pptx_preview_service._render_pdf_page_to_png",
            side_effect=fake_render,
        ),
    ):
        result = await render_pptx_slide_to_png(
            pptx_path=fake_pptx, cache_dir=cache_dir, slide_index=3
        )

    assert result.is_file()
    assert result.name == "0003.png"
    assert extract_calls == 1, "extract chiamato 1 sola volta"
    assert render_calls == 1, "pdfium render chiamato 1 sola volta"
    # Cleanup workspace temp eseguito (best-effort): la dir .tmp_0003 non esiste piu`.
    assert not (cache_dir / ".tmp_0003").exists()


@pytest.mark.asyncio
async def test_workspace_cleanup_after_soffice_error(
    fake_pptx: Path, cache_dir: Path
) -> None:
    """Cleanup workspace temp esegue anche dopo errore soffice."""
    proc = _make_proc_mock(returncode=1)
    proc.communicate = AsyncMock(
        return_value=(b"", b"libreoffice crash: missing font")
    )

    def fake_extract(source: Path, idx: int, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"mini-pptx")

    with (
        patch(
            "app.services.pptx_preview_service._extract_single_slide_to_pptx",
            side_effect=fake_extract,
        ),
        patch(
            "app.services.pptx_preview_service.asyncio.create_subprocess_exec",
            return_value=proc,
        ),
    ):
        with pytest.raises(PreviewRenderError, match="exit_code=1"):
            await render_pptx_slide_to_png(
                pptx_path=fake_pptx, cache_dir=cache_dir, slide_index=7
            )

    # Workspace temp cleanup eseguito anche su errore.
    assert not (cache_dir / ".tmp_0007").exists()


@pytest.mark.asyncio
async def test_soffice_timeout_raises_preview_render_error(
    fake_pptx: Path, cache_dir: Path
) -> None:
    """soffice non risponde entro timeout → PreviewRenderError."""
    proc = MagicMock()
    proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
    proc.kill = MagicMock()
    proc.wait = AsyncMock()

    def fake_extract(source: Path, idx: int, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"mini-pptx")

    with (
        patch(
            "app.services.pptx_preview_service._extract_single_slide_to_pptx",
            side_effect=fake_extract,
        ),
        patch(
            "app.services.pptx_preview_service.asyncio.create_subprocess_exec",
            return_value=proc,
        ),
    ):
        with pytest.raises(PreviewRenderError, match="timeout"):
            await render_pptx_slide_to_png(
                pptx_path=fake_pptx, cache_dir=cache_dir, slide_index=0
            )
    proc.kill.assert_called_once()


@pytest.mark.asyncio
async def test_soffice_missing_output_pdf_raises_preview_render_error(
    fake_pptx: Path, cache_dir: Path
) -> None:
    """soffice exit=0 ma PDF NON prodotto → PreviewRenderError."""
    proc = _make_proc_mock(returncode=0)

    def fake_extract(source: Path, idx: int, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"mini-pptx")

    with (
        patch(
            "app.services.pptx_preview_service._extract_single_slide_to_pptx",
            side_effect=fake_extract,
        ),
        patch(
            "app.services.pptx_preview_service.asyncio.create_subprocess_exec",
            return_value=proc,
        ),
    ):
        # NON scriviamo single_slide.pdf nella outdir → PreviewRenderError.
        with pytest.raises(PreviewRenderError, match="non ha prodotto il PDF"):
            await render_pptx_slide_to_png(
                pptx_path=fake_pptx, cache_dir=cache_dir, slide_index=0
            )


@pytest.mark.asyncio
async def test_pptx_path_missing_raises_file_not_found(
    cache_dir: Path, tmp_path: Path
) -> None:
    """PPTX non esiste su disco → FileNotFoundError."""
    nonexistent = tmp_path / "missing.pptx"
    with pytest.raises(FileNotFoundError):
        await render_pptx_slide_to_png(
            pptx_path=nonexistent, cache_dir=cache_dir, slide_index=0
        )
