"""F-STUDIO-UX Step 0 (D-207) — unit test pptx_preview_service.

Mocked: subprocess (soffice) + pypdfium2 (render PDF page).
Verifica:
- fast path PNG cached → nessuna chiamata a soffice / pdfium
- prima invocazione → soffice viene eseguito UNA volta, PDF intermedio renominato
- seconda invocazione su stessa slide → cache hit
- seconda invocazione su slide DIVERSA, stesso rebuild_token → soffice NON viene rieseguito (PDF intermedio gia` presente)
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
    """PNG in cache → ritorno immediato senza toccare soffice/pdfium."""
    cache_dir.mkdir(parents=True)
    pre_existing = cache_dir / "0005.png"
    pre_existing.write_bytes(b"fake-png")

    with (
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
    mock_subproc.assert_not_called()
    mock_render.assert_not_called()


@pytest.mark.asyncio
async def test_first_invocation_runs_soffice_then_pdfium(
    fake_pptx: Path, cache_dir: Path
) -> None:
    """Prima invocazione: soffice produce PDF + pdfium rende la slide."""
    proc = _make_proc_mock(returncode=0)

    def fake_subproc_factory(*args: object, **kwargs: object) -> MagicMock:
        # Simula soffice scrivendo course_X.pdf nella outdir.
        # outdir e' uno degli args posizionali (--outdir <dir>).
        outdir_idx = args.index("--outdir") + 1
        produced_pdf = Path(str(args[outdir_idx])) / f"{fake_pptx.stem}.pdf"
        produced_pdf.parent.mkdir(parents=True, exist_ok=True)
        produced_pdf.write_bytes(b"fake-pdf-content")
        return proc

    def fake_render(pdf_path: Path, page_index: int, png_out: Path) -> None:
        png_out.write_bytes(b"rendered-png")

    with (
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
    assert (cache_dir / "_pptx_render.pdf").is_file(), (
        "PDF intermedio dovrebbe essere stato rinominato a _pptx_render.pdf"
    )


@pytest.mark.asyncio
async def test_second_invocation_same_slide_uses_cache(
    fake_pptx: Path, cache_dir: Path
) -> None:
    """Stesso slide_index due volte: solo la prima chiama soffice."""
    proc = _make_proc_mock(returncode=0)
    soffice_calls = 0

    def fake_subproc_factory(*args: object, **kwargs: object) -> MagicMock:
        nonlocal soffice_calls
        soffice_calls += 1
        outdir_idx = args.index("--outdir") + 1
        (Path(str(args[outdir_idx])) / f"{fake_pptx.stem}.pdf").write_bytes(b"pdf")
        return proc

    render_calls = 0

    def fake_render(pdf_path: Path, page_index: int, png_out: Path) -> None:
        nonlocal render_calls
        render_calls += 1
        png_out.write_bytes(b"png")

    with (
        patch(
            "app.services.pptx_preview_service.asyncio.create_subprocess_exec",
            side_effect=lambda *a, **kw: fake_subproc_factory(*a, **kw),
        ),
        patch(
            "app.services.pptx_preview_service._render_pdf_page_to_png",
            side_effect=fake_render,
        ),
    ):
        await render_pptx_slide_to_png(
            pptx_path=fake_pptx, cache_dir=cache_dir, slide_index=7
        )
        await render_pptx_slide_to_png(
            pptx_path=fake_pptx, cache_dir=cache_dir, slide_index=7
        )

    assert soffice_calls == 1, "soffice deve essere chiamato 1 sola volta"
    assert render_calls == 1, "pdfium render deve essere chiamato 1 sola volta"


@pytest.mark.asyncio
async def test_different_slides_same_rebuild_token_reuse_pdf(
    fake_pptx: Path, cache_dir: Path
) -> None:
    """Slide diverse, stesso rebuild_token: soffice 1 volta, pdfium 2 volte."""
    proc = _make_proc_mock(returncode=0)
    soffice_calls = 0

    def fake_subproc_factory(*args: object, **kwargs: object) -> MagicMock:
        nonlocal soffice_calls
        soffice_calls += 1
        outdir_idx = args.index("--outdir") + 1
        (Path(str(args[outdir_idx])) / f"{fake_pptx.stem}.pdf").write_bytes(b"pdf")
        return proc

    def fake_render(pdf_path: Path, page_index: int, png_out: Path) -> None:
        png_out.write_bytes(f"png-page-{page_index}".encode())

    with (
        patch(
            "app.services.pptx_preview_service.asyncio.create_subprocess_exec",
            side_effect=lambda *a, **kw: fake_subproc_factory(*a, **kw),
        ),
        patch(
            "app.services.pptx_preview_service._render_pdf_page_to_png",
            side_effect=fake_render,
        ),
    ):
        await render_pptx_slide_to_png(
            pptx_path=fake_pptx, cache_dir=cache_dir, slide_index=1
        )
        await render_pptx_slide_to_png(
            pptx_path=fake_pptx, cache_dir=cache_dir, slide_index=42
        )

    assert soffice_calls == 1, "PDF intermedio riusato → soffice 1 sola volta"
    assert (cache_dir / "0001.png").is_file()
    assert (cache_dir / "0042.png").is_file()


@pytest.mark.asyncio
async def test_soffice_timeout_raises_preview_render_error(
    fake_pptx: Path, cache_dir: Path
) -> None:
    """soffice non risponde entro timeout → PreviewRenderError."""
    proc = MagicMock()
    proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
    proc.kill = MagicMock()
    proc.wait = AsyncMock()

    with patch(
        "app.services.pptx_preview_service.asyncio.create_subprocess_exec",
        return_value=proc,
    ):
        with pytest.raises(PreviewRenderError, match="timeout"):
            await render_pptx_slide_to_png(
                pptx_path=fake_pptx, cache_dir=cache_dir, slide_index=0
            )
    proc.kill.assert_called_once()


@pytest.mark.asyncio
async def test_soffice_non_zero_exit_raises_preview_render_error(
    fake_pptx: Path, cache_dir: Path
) -> None:
    """soffice exit_code != 0 → PreviewRenderError con stderr nel messaggio."""
    proc = _make_proc_mock(returncode=1)
    proc.communicate = AsyncMock(return_value=(b"", b"libreoffice crash: missing font"))

    with patch(
        "app.services.pptx_preview_service.asyncio.create_subprocess_exec",
        return_value=proc,
    ):
        with pytest.raises(PreviewRenderError, match="exit_code=1"):
            await render_pptx_slide_to_png(
                pptx_path=fake_pptx, cache_dir=cache_dir, slide_index=0
            )


@pytest.mark.asyncio
async def test_soffice_missing_output_pdf_raises_preview_render_error(
    fake_pptx: Path, cache_dir: Path
) -> None:
    """soffice exit=0 ma PDF NON prodotto (edge case) → PreviewRenderError."""
    proc = _make_proc_mock(returncode=0)

    with patch(
        "app.services.pptx_preview_service.asyncio.create_subprocess_exec",
        return_value=proc,
    ):
        # NON scriviamo course_X.pdf nella outdir → PreviewRenderError.
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
