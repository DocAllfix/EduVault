"""F-STUDIO-UX Step 0 (2026-06-01 / D-207) — PPTX-fedele preview service.

Renderizza una singola slide del PPTX scaricabile come PNG, lazy + cached:

  PPTX (python-pptx, immagini reali) ──soffice headless──▶ PDF intermedio
                                                            │
                                                            ▼
                                                  pypdfium2 page → PNG

Il PDF intermedio (``_pptx_render.pdf``) viene generato UNA volta per
``rebuild_token`` (Unix timestamp di ``courses.last_rebuilt_at``), quindi le
slide successive sono servite quasi istantaneamente (solo extract della
singola pagina, ~50-150ms ciascuna).

Cache layout (riusato dall'endpoint preview esistente in courses.py):
    output/previews/{course_id}/{rebuild_token}/
        _pptx_render.pdf       ← prodotto da soffice, riusato per tutte le slide
        _pptx_render.lock      ← file di lock per serializzare invocazioni soffice
        {idx:04d}.png          ← cache della singola slide
        ...

Razionale: il PPTX (slide_builder.py:227+) è la fonte di verità del prodotto
scaricabile. Il PDF dispensa Jinja2 (pdf_builder.py) e` testo-only — divergeva
dal PPTX. Renderizzando il PPTX via LibreOffice headless otteniamo PNG che
riflettono al 100% ciò che il cliente scaricherà.

LibreOffice è già installato nel Dockerfile (libreoffice-impress + libreoffice-core,
linee 17-18). Zero apt-deps nuove.

Fallback: se ``soffice`` non è disponibile o fallisce, il caller (endpoint
preview) può usare ``settings.preview_source = "pdf_dispensa"`` per tornare al
comportamento legacy (pypdfium2 sul PDF dispensa Jinja2).
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Timeout soffice — un PPTX di 342 slide può richiedere 30-60s su Railway,
# ma diamo margine generoso per corsi 8h (642 slide) o macchine cold.
_SOFFICE_TIMEOUT_S = 240

# Render DPI: stesso scale del path legacy (1.6 → ~153 DPI, leggibile su retina
# senza far esplodere la dimensione della cache).
_PDFIUM_RENDER_SCALE = 1.6

# Lock async per serializzare le invocazioni soffice nello stesso processo —
# LibreOffice headless ha problemi noti con istanze concorrenti che condividono
# lo stesso user profile. Per process pool / multi-worker servirebbe un lock
# filesystem-level, ma per il deploy single-worker Railway è sufficiente.
_soffice_lock = asyncio.Lock()


class PreviewRenderError(RuntimeError):
    """Raised when the LibreOffice → PDF conversion fails irrecoverably.

    Caller (endpoint preview) può catturare questo errore per fall-back al path
    legacy ``pdf_dispensa`` senza propagare 500 all'utente.
    """


async def render_pptx_slide_to_png(
    *,
    pptx_path: Path,
    cache_dir: Path,
    slide_index: int,
) -> Path:
    """Renderizza la slide ``slide_index`` del PPTX come PNG, riusando la cache.

    Args:
        pptx_path: percorso del file ``.pptx`` (deve esistere su disco — il caller
            estrae da ``courses.pptx_path`` e valida l'esistenza).
        cache_dir: directory di cache della preview (caller esistente in
            ``courses.py:966`` calcola già il path con ``rebuild_token``):
            ``output/previews/{course_id}/{rebuild_token}/``.
        slide_index: indice 0-based della slide (allineato all'indicizzazione
            di ``pypdfium2`` su PDF prodotto da soffice).

    Returns:
        ``Path`` al file PNG. Esiste su disco al ritorno.

    Raises:
        PreviewRenderError: se soffice fallisce o produce un PDF malformato.
        FileNotFoundError: se ``pptx_path`` non esiste.
    """
    if not pptx_path.is_file():
        raise FileNotFoundError(f"PPTX non trovato: {pptx_path}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    png_path = cache_dir / f"{slide_index:04d}.png"

    # Fast path: PNG già in cache → nessuna conversione necessaria.
    if png_path.is_file():
        return png_path

    pdf_intermediate = cache_dir / "_pptx_render.pdf"

    # Genera il PDF intermedio (una sola volta per rebuild_token) sotto lock.
    if not pdf_intermediate.is_file():
        async with _soffice_lock:
            # Re-check sotto lock per evitare double-render se due richieste
            # arrivano insieme (race window prima dell'acquisizione lock).
            if not pdf_intermediate.is_file():
                await _convert_pptx_to_pdf(pptx_path, cache_dir)

    if not pdf_intermediate.is_file():
        raise PreviewRenderError(
            f"PDF intermedio non prodotto da soffice: atteso {pdf_intermediate}"
        )

    # Render della singola pagina (CPU-bound, mettiamo in thread per non
    # bloccare l'event loop su corsi con preview chiamate concorrenti).
    await asyncio.to_thread(
        _render_pdf_page_to_png, pdf_intermediate, slide_index, png_path
    )

    return png_path


async def _convert_pptx_to_pdf(pptx_path: Path, out_dir: Path) -> None:
    """Esegue ``soffice --headless --convert-to pdf`` in un subprocess.

    soffice produce il PDF nella ``out_dir`` con lo stesso basename del PPTX
    (es. ``my_course.pptx`` → ``my_course.pdf``). Dopo la conversione lo
    rinominiamo in ``_pptx_render.pdf`` per stabilizzare il path indipendente
    dal nome del PPTX.

    Il working directory di soffice deve essere ``out_dir`` per evitare
    contenzione su lock files in user profile condivisi tra istanze.
    """
    # Profilo utente isolato per questa conversione: previene il classico
    # "Office is already running" se più container/processi usano lo stesso
    # /root/.config/libreoffice. Usiamo la cache dir come user profile temp.
    profile_dir = out_dir / ".soffice_profile"
    profile_dir.mkdir(exist_ok=True)
    user_profile_url = f"-env:UserInstallation=file://{profile_dir.as_posix()}"

    cmd = [
        "soffice",
        user_profile_url,
        "--headless",
        "--norestore",
        "--nologo",
        "--nofirststartwizard",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(pptx_path),
    ]

    logger.info(
        "soffice_convert_started",
        pptx=str(pptx_path),
        outdir=str(out_dir),
    )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "HOME": str(profile_dir)},
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(), timeout=_SOFFICE_TIMEOUT_S
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise PreviewRenderError(
            f"soffice timeout dopo {_SOFFICE_TIMEOUT_S}s su {pptx_path.name}"
        )

    if proc.returncode != 0:
        raise PreviewRenderError(
            f"soffice exit_code={proc.returncode} stderr={stderr_b.decode(errors='replace')[:500]}"
        )

    # soffice scrive il PDF con stesso basename del PPTX nella outdir.
    produced_pdf = out_dir / f"{pptx_path.stem}.pdf"
    if not produced_pdf.is_file():
        raise PreviewRenderError(
            f"soffice non ha prodotto il PDF atteso: {produced_pdf}"
        )

    # Rinomina al path stabile usato dal caller per i lookup cache.
    stable_pdf = out_dir / "_pptx_render.pdf"
    produced_pdf.rename(stable_pdf)

    logger.info(
        "soffice_convert_completed",
        pdf=str(stable_pdf),
        size_bytes=stable_pdf.stat().st_size,
    )


def _render_pdf_page_to_png(
    pdf_path: Path, page_index: int, png_out: Path
) -> None:
    """Rendering CPU-bound di una singola pagina PDF → PNG via pypdfium2.

    Funzione sincrona: il chiamante la incapsula in ``asyncio.to_thread``.
    """
    import pypdfium2 as pdfium  # type: ignore[import-untyped]

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        if page_index < 0 or page_index >= len(pdf):
            raise PreviewRenderError(
                f"slide {page_index} fuori range PDF ({len(pdf)} pagine)"
            )
        page = pdf[page_index]
        pil_image = page.render(scale=_PDFIUM_RENDER_SCALE).to_pil()
        pil_image.save(png_out, format="PNG", optimize=True)
    finally:
        pdf.close()
