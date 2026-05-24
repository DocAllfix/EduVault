"""Image Service — pre-fetch + SVG sanitization + diagram render (BP §07.0).

Three responsibilities:

1. Download web images concurrently (``Semaphore(5)``) with a shared
   ``httpx.AsyncClient``, validate integrity with Pillow.load(), persist via
   ``image_cache`` (de-duplication on ``query``), enforce a 5 MB size cap.

2. Render inline-SVG diagrams (NOT Mermaid) to PNG with cairosvg, wrapped
   in ``asyncio.to_thread`` since cairosvg is synchronous.

3. ``sanitize_svg`` is INLINE in this module — FIX-2 / BP §07.0: NO separate
   ``utils/svg_sanitizer.py`` file. Strips <script>, <foreignObject>, remote
   xlink:href, and on*=… event handlers before the SVG reaches cairosvg.

Returns ``image_map: dict[int, str]`` mapping slide index → local PNG path.
The SlideBuilder (FASE 4.2) receives ONLY local paths, never URLs.
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import uuid
from typing import Any

import cairosvg
import httpx
import structlog
from PIL import Image

from app.models.pipeline import SlideContent

logger = structlog.get_logger()

# BP §07.0 line 2056 — guards python-pptx-unrelated I/O concurrency,
# NOT the python-pptx Semaphore(1) REI-3 (that one lives in generation_service).
_image_semaphore = asyncio.Semaphore(5)

# BP §07.0 line 2059 — prevents OOM from absurd image downloads.
MAX_IMAGE_BYTES = 5_000_000

IMAGES_DIR = "output/images"
DIAGRAMS_DIR = "output/diagrams"

DOWNLOAD_TIMEOUT_SECONDS = 10.0
DIAGRAM_OUTPUT_WIDTH = 1200
DIAGRAM_OUTPUT_HEIGHT = 800


def sanitize_svg(svg_code: str) -> str:
    """Strip dangerous constructs from LLM-generated SVG. FIX-2 / BP §07.0.

    SVG is a full XML format that supports <script>, <foreignObject>,
    remote xlink:href (SSRF via cairosvg), and event handlers. An LLM
    emitting malicious SVG — or a prompt-injection inside a normative
    chunk — could otherwise cause SSRF or unexpected rendering.

    Removed:
        - ``<script>…</script>`` (incl. multiline, DOTALL)
        - ``<foreignObject>…</foreignObject>``
        - ``xlink:href="http(s)://…"`` (remote refs only — keeps fragment refs)
        - ``on*=…`` event handler attributes
    """
    svg_code = re.sub(r"<script[^>]*>.*?</script>", "", svg_code, flags=re.DOTALL)
    svg_code = re.sub(
        r"<foreignObject[^>]*>.*?</foreignObject>", "", svg_code, flags=re.DOTALL
    )
    svg_code = re.sub(
        r"xlink:href\s*=\s*[\"']https?://[^\"']*[\"']", "", svg_code
    )
    svg_code = re.sub(r"on\w+\s*=\s*[\"'][^\"']*[\"']", "", svg_code)
    return svg_code


async def _download_one_image(
    slide: SlideContent, pool: Any, client: httpx.AsyncClient
) -> tuple[int, str | None]:
    """Download one image under the global semaphore, with cache lookup
    and Pillow integrity validation. BP §07.0 line 2076-2122.

    The httpx client is the SHARED one created by ``prefetch_images`` —
    no new client per call (connection-pool reuse).
    """
    async with _image_semaphore:
        cached = await pool.fetchrow(
            "SELECT local_path FROM image_cache WHERE query=$1",
            slide.image.query,
        )
        if cached:
            await pool.execute(
                "UPDATE image_cache SET usage_count = usage_count + 1 WHERE query=$1",
                slide.image.query,
            )
            return (slide.index, cached["local_path"])

        try:
            assert slide.image.query_url is not None  # guarded by prefetch_images
            resp = await client.get(slide.image.query_url)
            resp.raise_for_status()

            raw_bytes = resp.content
            if len(raw_bytes) > MAX_IMAGE_BYTES:
                logger.warning(
                    "image_too_large",
                    slide=slide.index,
                    size_mb=round(len(raw_bytes) / 1_000_000, 1),
                )
                return (slide.index, None)

            # BP §07.0 line 2106-2107: img.load() forces full decode and
            # raises on corrupt streams — strictly stronger than verify()
            # which only checks the header.
            img = Image.open(io.BytesIO(raw_bytes))
            img.load()

            os.makedirs(IMAGES_DIR, exist_ok=True)
            local_path = f"{IMAGES_DIR}/{uuid.uuid4()}.png"
            img.convert("RGB").save(local_path, "PNG")

            await pool.execute(
                "INSERT INTO image_cache (query, image_url, local_path, format) "
                "VALUES ($1, $2, $3, 'png')",
                slide.image.query,
                str(slide.image.query_url),
                local_path,
            )
            return (slide.index, local_path)

        except Exception as exc:
            logger.warning(
                "image_download_failed", slide=slide.index, error=str(exc)
            )
            return (slide.index, None)


def _render_diagram_sync(slide: SlideContent) -> tuple[int, str | None]:
    """Render inline-SVG diagram → PNG. SYNCHRONOUS (cairosvg). BP §07.0 §2125.

    The Content Agent (FASE 3.4) emits SVG directly (NOT Mermaid). The SVG is
    sanitized before reaching cairosvg.
    """
    if not slide.image.diagram_code:
        return (slide.index, None)
    try:
        safe_svg = sanitize_svg(slide.image.diagram_code)
        os.makedirs(DIAGRAMS_DIR, exist_ok=True)
        local_path = f"{DIAGRAMS_DIR}/{uuid.uuid4()}.png"
        cairosvg.svg2png(
            bytestring=safe_svg.encode(),
            write_to=local_path,
            output_width=DIAGRAM_OUTPUT_WIDTH,
            output_height=DIAGRAM_OUTPUT_HEIGHT,
        )
        return (slide.index, local_path)
    except Exception as exc:
        logger.warning(
            "diagram_render_failed", slide=slide.index, error=str(exc)
        )
        return (slide.index, None)


async def prefetch_images(
    slides: list[SlideContent], pool: Any
) -> dict[int, str]:
    """Resolve every slide's visual to a LOCAL PATH before sync PPTX build.

    - Web images (``strategy='web_search'`` AND ``query_url`` present) are
      downloaded under the shared httpx client.
    - Diagram slides (``strategy='diagram'``) are rendered via cairosvg
      wrapped in ``asyncio.to_thread``.

    The SlideBuilder (FASE 4.2) MUST receive only local paths — invariant
    BP §07.0 line 2148.
    """
    image_map: dict[int, str] = {}

    web_slides = [
        s
        for s in slides
        if s.image.strategy == "web_search" and s.image.query_url
    ]
    web_requested = len(web_slides)

    if web_slides:
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT_SECONDS) as client:
            web_tasks = [_download_one_image(s, pool, client) for s in web_slides]
            web_results = await asyncio.gather(*web_tasks, return_exceptions=True)
        for result in web_results:
            if isinstance(result, tuple) and result[1] is not None:
                image_map[result[0]] = result[1]

    diagram_slides = [s for s in slides if s.image.strategy == "diagram"]
    if diagram_slides:
        diagram_tasks = [
            asyncio.to_thread(_render_diagram_sync, s) for s in diagram_slides
        ]
        diagram_results = await asyncio.gather(*diagram_tasks, return_exceptions=True)
        for result in diagram_results:
            if isinstance(result, tuple) and result[1] is not None:
                image_map[result[0]] = result[1]

    logger.info(
        "images_prefetched",
        web_requested=web_requested,
        diagrams=len(diagram_slides),
        total_resolved=len(image_map),
    )
    return image_map


__all__ = [
    "DIAGRAMS_DIR",
    "DOWNLOAD_TIMEOUT_SECONDS",
    "IMAGES_DIR",
    "MAX_IMAGE_BYTES",
    "prefetch_images",
    "sanitize_svg",
]
