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
import random
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
_image_semaphore = asyncio.Semaphore(40)  # boost 2026-05-25 (#15): cache + simplify
# riducono call duplicate; 40 paralleli reggono Pexels (5 req/sec sostenuti
# burst, cache hit immediati). Tempo prefetch corso 8h: ~3min → ~30s.

# BP §07.0 line 2059 — prevents OOM from absurd image downloads.
MAX_IMAGE_BYTES = 5_000_000

IMAGES_DIR = "output/images"
DIAGRAMS_DIR = "output/diagrams"

DOWNLOAD_TIMEOUT_SECONDS = 10.0
# FASE 5 vast-hopping: viewBox SVG fisso "0 0 1760 800" → render 1:1 col box
# nx_diagram_box del template. Aspect 2.2:1 (landscape wide).
DIAGRAM_OUTPUT_WIDTH = 1760
DIAGRAM_OUTPUT_HEIGHT = 800

# FIX #25 (2026-05-26): zero-placeholder guarantee. Brand colours C.F.P.
# Montessori — used by the branded fallback when every external provider
# is exhausted, so a CONTENT_IMAGE/DIAGRAM box never renders the literal
# "[ query ]" placeholder text from the template.
BRAND_PINK = (0xC8, 0x2E, 0x6E)   # #C82E6E
BRAND_GREEN = (0x76, 0x9E, 0x2E)  # #769E2E
FALLBACK_DIR = "output/fallbacks"

# FIX #31 MOSSA 1 (2026-05-27): backfill waves ELIMINATE. Analista
# 2026-05-27: "il retry ha senso solo se qualcosa può essere cambiato
# tra un tentativo e l'altro. Stessa query, stesso istante, stesso Pexels
# → niente cambia → niente retry". Le costanti BACKFILL_MAX_SECONDS e
# BACKFILL_WAVE_PAUSE_SECONDS sono state rimosse. Il glitch di rete
# transitorio è ora catturato dal singolo retry-with-jitter dentro
# _download_one_image (caso unico dove il retry porta informazione nuova).
DOWNLOAD_RETRY_JITTER_MIN = 0.3
DOWNLOAD_RETRY_JITTER_MAX = 1.2


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
    pos: int, slide: SlideContent, pool: Any, client: httpx.AsyncClient
) -> tuple[int, str | None]:
    """Download one image under the global semaphore, with cache lookup
    and Pillow integrity validation. BP §07.0 line 2076-2122.

    ``pos`` is the GLOBAL position of the slide in the prefetch list — the
    key used by image_map. FIX #26 (2026-05-26): slide.index is module-local
    (up to 14 slides share one index), so it CANNOT key image_map without
    collisions. Both prefetch and the builder enumerate the same ordered
    list, so position is the stable shared key.

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
            return (pos, cached["local_path"])

        # FIX #31 MOSSA 1 (2026-05-27): 1 try + 1 retry con jitter cattura
        # il glitch di rete transitorio (l'UNICO caso dove ritentare porta
        # informazione nuova: la rete cambia tra t0 e t0+jitter). Su 2
        # failure consecutivi → branded fallback. Niente backfill waves
        # a fine pipeline (sleep 20s × N tentativi cieco eliminato).
        assert slide.image.query_url is not None  # guarded by prefetch_images
        for attempt in range(2):  # 1 try + 1 retry, max 2 chiamate
            try:
                resp = await client.get(slide.image.query_url)
                resp.raise_for_status()

                raw_bytes = resp.content
                if len(raw_bytes) > MAX_IMAGE_BYTES:
                    logger.warning(
                        "image_too_large",
                        slide=slide.index,
                        size_mb=round(len(raw_bytes) / 1_000_000, 1),
                    )
                    return (pos, None)

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
                return (pos, local_path)

            except Exception as exc:
                if attempt == 0:
                    jitter = random.uniform(
                        DOWNLOAD_RETRY_JITTER_MIN, DOWNLOAD_RETRY_JITTER_MAX
                    )
                    logger.info(
                        "image_download_retry",
                        slide=slide.index,
                        error=str(exc)[:120],
                        jitter_s=round(jitter, 2),
                    )
                    await asyncio.sleep(jitter)
                    continue
                logger.warning(
                    "image_download_failed", slide=slide.index, error=str(exc)
                )
                return (pos, None)
        return (pos, None)  # unreachable, for type checker


def fit_image_to_box(
    image_path: str, box_w_px: int, box_h_px: int
) -> str:
    """FASE 4: ridimensiona l'immagine per ENTRARE nel box preservando aspect
    ratio (NO crop, NO squish). Letterboxing con padding bianco se l'aspect
    reale non matcha quello del box.

    Restituisce il path della versione fitted (``<orig>_fitted.png``). Se Pillow
    fallisce, ritorna il path originale (degradazione graziosa).
    """
    try:
        from PIL import ImageOps

        img = Image.open(image_path).convert("RGB")
        # ImageOps.pad scala-to-fit dentro (box_w, box_h) e riempie con color
        fitted = ImageOps.pad(
            img,
            (box_w_px, box_h_px),
            method=Image.Resampling.LANCZOS,
            color=(255, 255, 255),
            centering=(0.5, 0.5),
        )
        fitted_path = image_path.rsplit(".", 1)[0] + "_fitted.png"
        fitted.save(fitted_path, "PNG")
        return fitted_path
    except Exception as exc:
        logger.warning("image_fit_failed", path=image_path, error=str(exc))
        return image_path


def _autofix_svg(svg: str) -> str:
    """FIX #23 (2026-05-25): auto-fix SVG malformati dall'LLM prima di cairosvg.

    Problemi comuni LLM:
    - Entità HTML &amp;nbsp; / &quot; non valide in XML strict
    - <br> non chiusi
    - Caratteri unicode &#xA0; non escapati
    - Missing xmlns
    - viewBox malformato
    """
    import re as _re

    # 1. Assicura xmlns SVG
    if "xmlns=" not in svg:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)

    # 2. Assicura viewBox (cairosvg lo richiede)
    if "viewBox" not in svg:
        svg = svg.replace("<svg", '<svg viewBox="0 0 1760 800"', 1)

    # 3. Rimuovi entità HTML problematiche
    bad_entities = {
        "&nbsp;": " ",
        "&quot;": '"',
        "&apos;": "'",
        "&#160;": " ",
        "&#xA0;": " ",
        "&trade;": "(TM)",
        "&copy;": "(C)",
        "&reg;": "(R)",
        "&hellip;": "...",
        "&mdash;": "-",
        "&ndash;": "-",
        "&rsquo;": "'",
        "&lsquo;": "'",
        "&rdquo;": '"',
        "&ldquo;": '"',
    }
    for bad, good in bad_entities.items():
        svg = svg.replace(bad, good)

    # 4. Auto-close tag self-chiusi mancanti (br, hr, img, line, rect, circle, path, polyline, polygon, ellipse, use)
    for tag in ["br", "hr", "img"]:
        svg = _re.sub(rf"<{tag}([^>]*?)(?<!/)>", rf"<{tag}\1/>", svg)

    return svg


def _render_diagram_sync(pos: int, slide: SlideContent) -> tuple[int, str | None]:
    """Render inline-SVG diagram → PNG. SYNCHRONOUS (cairosvg). BP §07.0 §2125.

    ``pos`` is the global image_map key (FIX #26 — see _download_one_image).

    FIX #30.4 (2026-05-26): se slide.image.diagram_filling è valorizzato,
    usa il catalogo SVG (diagram_service.render_diagram_to_svg) — path
    PREFERRED, vincoli max_chars già applicati a monte. Altrimenti ricade
    sul legacy diagram_code (free-form, deprecated).
    """
    raw_svg: str | None = None
    # PATH 1 (preferito FIX #30.4): catalogo SVG
    if slide.image.diagram_filling:
        try:
            from app.services.diagram_service import (
                DiagramFilling,
                render_diagram_to_svg,
            )
            filling = DiagramFilling(**slide.image.diagram_filling)
            raw_svg = render_diagram_to_svg(filling)
        except Exception as exc:
            logger.warning(
                "diagram_filling_failed",
                slide=slide.index,
                error=str(exc),
                fallback="legacy_diagram_code",
            )
    # PATH 2 (legacy): diagram_code free-form
    if raw_svg is None and slide.image.diagram_code:
        raw_svg = slide.image.diagram_code
    if raw_svg is None:
        return (pos, None)
    try:
        safe_svg = sanitize_svg(raw_svg)
        # FIX #23: auto-fix SVG malformati (entità HTML, xmlns mancante, ecc.)
        safe_svg = _autofix_svg(safe_svg)
        # FIX #16 (2026-05-25): forza background bianco se l'SVG non ne ha uno.
        # Senza questo cairosvg renderizza su trasparente che LibreOffice mostra
        # come NERO. Inserisco un <rect> bianco full-area subito dopo <svg>.
        if 'fill="white"' not in safe_svg and "background" not in safe_svg.lower():
            # Estraggo viewBox per dimensioni rect, default 0 0 1760 800
            import re as _re
            vb_match = _re.search(r'viewBox="([\d.\s]+)"', safe_svg)
            if vb_match:
                vb_parts = vb_match.group(1).split()
                if len(vb_parts) == 4:
                    x, y, w, h = vb_parts
                    bg_rect = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="white"/>'
                    safe_svg = _re.sub(r"(<svg[^>]*>)", rf"\1{bg_rect}", safe_svg, count=1)
        os.makedirs(DIAGRAMS_DIR, exist_ok=True)
        local_path = f"{DIAGRAMS_DIR}/{uuid.uuid4()}.png"
        cairosvg.svg2png(
            bytestring=safe_svg.encode(),
            write_to=local_path,
            output_width=DIAGRAM_OUTPUT_WIDTH,
            output_height=DIAGRAM_OUTPUT_HEIGHT,
            background_color="white",  # belt + braces
        )
        return (pos, local_path)
    except Exception as exc:
        logger.warning(
            "diagram_render_failed", slide=slide.index, error=str(exc)
        )
        return (pos, None)


async def _resolve_query_urls(slides: list[SlideContent]) -> None:
    """FASE 4: per le slide web_search con query ma SENZA query_url, risolve
    l'URL via search_image (Pexels orientation + Wikimedia fallback).

    Muta in-place ``slide.image.query_url``. L'aspect_hint dell'LLM viene
    passato come orientation a Pexels per ottenere l'immagine con il giusto
    rapporto d'aspetto.

    FIX #9 (2026-05-25): l'LLM emette strategy con valori diversi da quanto
    documentato — visti in produzione: "pexels", "search", "generate",
    "with_query", "auto". Accetto QUALSIASI strategy non-vuota/non-"none"
    PURCHÉ ci sia image.query → l'intent è chiaro, cerchiamo l'immagine.
    """
    from app.services.image_search import search_image

    _IMAGE_SEARCH_STRATEGIES = {
        "web_search", "pexels", "search", "generate", "with_query", "auto",
        "image", "photo", "stock",
    }
    from app.models.core import SlideType
    _SLIDE_TYPES_NEED_IMAGE = {SlideType.CONTENT_IMAGE}

    # FIX #30.0-octies (2026-05-26, anticipato da #30.3 — analista richiesta
    # esplicita: "una feature immagini che rende il 17% di quello che dovrebbe
    # non è 'a tendere', è non-funzionante"). Recovery: se slide è CONTENT_IMAGE
    # E ha query valorizzata, scarica SEMPRE l'immagine — anche se l'LLM ha
    # scritto strategy="none" / "content_image" / qualsiasi altro valore non
    # canonico. Il layout CONTENT_IMAGE ha sempre un PICTURE placeholder che
    # senza foto resta vuoto, quindi l'intent è inequivocabile: vuole foto.
    to_resolve = [
        s
        for s in slides
        if s.image.query
        and not s.image.query_url
        and (
            s.image.strategy in _IMAGE_SEARCH_STRATEGIES
            or s.image.strategy not in (None, "", "none", "diagram", "inline_svg")
            or s.slide_type in _SLIDE_TYPES_NEED_IMAGE  # ← RECOVERY
        )
    ]
    if not to_resolve:
        return

    # FIX #31 MOSSA 2 (2026-05-27): dedup deterministica intra-corso.
    # _resolve_query_urls è chiamata UNA volta per corso (via
    # prefetch_images in generation_service.py), quindi `seen_urls`
    # locale a questa funzione = 1 corso = 1 set. search_image rispetta
    # un budget di max 2 riusi per URL: oltre, sceglie il successivo
    # candidato Pexels (o fallisce → branded). Risolve la regressione
    # "stessa foto DPI 8 volte su 100 CONTENT_IMAGE" vista in E2E #18.
    seen_urls: dict[str, int] = {}

    async def _one(s: SlideContent) -> None:
        url = await search_image(
            s.image.query or "",
            orientation=s.image.aspect_hint,
            seen_urls=seen_urls,
        )
        if url:
            object.__setattr__(s.image, "query_url", url)

    await asyncio.gather(*(_one(s) for s in to_resolve), return_exceptions=True)


# ─────────────────────────────────────────────────────────────────────
# FIX #25 (2026-05-26): zero-placeholder guarantee — backfill + branded
# fallback. Detection mirrors scripts/verify_course_slides.py: a
# CONTENT_IMAGE/DIAGRAM slide whose index is absent from image_map would
# render the template's "[ query ]" placeholder text. We close that gap
# in two stages, entirely inside prefetch_images so both generation and
# rebuild benefit without touching their call sites.
# ─────────────────────────────────────────────────────────────────────

# Theme keyword → pictogram glyph. Picked from the query so the fallback
# looks intentional ("designed this way"), not like a broken image. Pure
# stdlib drawing (Pillow) — no font dependency beyond the default bitmap.
# Glyphs restricted to characters guaranteed present in DejaVuSans (the
# container font) — emoji (🔥⛑☣) render as tofu □ there, so we use plain
# Unicode symbols that always resolve.
_FALLBACK_GLYPHS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("soccorso", "medic", "sanitar", "ferit", "emorrag", "cassetta", "118", "112"), "✚"),
    (("incendi", "antincendio", "fiamm", "estintore", "ustion"), "▲"),
    (("dpi", "casco", "protezion", "guant", "mascher", "occhial", "calzatur"), "◆"),
    (("segnal", "cartell", "divieto", "obbligo", "avvert"), "⚠"),
    (("elettric", "tension", "folgor"), "⚡"),
    (("chimic", "sostanz", "tossic", "veleno"), "●"),
    (("rumore", "vibrazion", "acustic"), "♪"),
    (("formazion", "corso", "aula", "lezion", "didatt"), "★"),
    (("document", "registr", "verbal", "modulo", "normativ", "legge", "decreto"), "§"),
)


def _pick_glyph(query: str) -> str:
    q = (query or "").lower()
    for keywords, glyph in _FALLBACK_GLYPHS:
        if any(k in q for k in keywords):
            return glyph
    return "■"  # neutral geometric mark (always in DejaVuSans)


def _make_branded_fallback(
    query: str, *, is_diagram: bool = False
) -> str | None:
    """Render a branded C.F.P. placeholder PNG for one image/diagram box.

    Diagonal pink→green gradient + a thematic pictogram + the query as a
    small caption at the bottom. The slide already carries its own title /
    body / caption text, so the caption here stays discreet (it only labels
    the visual, never repeats the slide title).

    Returns the local path, or None if Pillow drawing fails (caller then
    leaves the slide without an image — still no crash).
    """
    try:
        from PIL import Image as _PILImage
        from PIL import ImageDraw, ImageFont

        w, h = (DIAGRAM_OUTPUT_WIDTH, DIAGRAM_OUTPUT_HEIGHT) if is_diagram else (1280, 960)
        img = _PILImage.new("RGB", (w, h), BRAND_PINK)
        draw = ImageDraw.Draw(img)

        # Vertical gradient inside the pink family only (deep → light pink) so
        # it never veers to the muddy olive midpoint a pink→green blend gives.
        # The green stays as a brand accent bar at the bottom, not in the wash.
        top = BRAND_PINK
        bottom = (0xF2, 0xD6, 0xE3)  # light tint of #C82E6E
        step = max(1, h // 320)
        for y in range(0, h, step):
            t = y / h
            draw.rectangle(
                [0, y, w, y + step],
                fill=(
                    int(top[0] + (bottom[0] - top[0]) * t),
                    int(top[1] + (bottom[1] - top[1]) * t),
                    int(top[2] + (bottom[2] - top[2]) * t),
                ),
            )

        # Centred brand disc holding the pictogram (filled, high contrast).
        cx = w // 2
        cy = int(h * 0.40)
        disc_r = int(min(w, h) * 0.20)
        draw.ellipse(
            [cx - disc_r, cy - disc_r, cx + disc_r, cy + disc_r],
            fill=(255, 255, 255),
        )
        draw.ellipse(
            [cx - disc_r, cy - disc_r, cx + disc_r, cy + disc_r],
            outline=BRAND_PINK, width=max(8, w // 120),
        )

        # Try a TTF for the glyph + caption; degrade to default bitmap font.
        glyph = _pick_glyph(query)
        font_glyph = None
        font_caption = None
        for candidate in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ):
            try:
                font_glyph = ImageFont.truetype(candidate, size=int(disc_r * 1.1))
                font_caption = ImageFont.truetype(candidate, size=max(22, w // 30))
                break
            except OSError:
                continue
        if font_glyph is not None:
            draw.text((cx, cy), glyph, fill=BRAND_PINK, anchor="mm", font=font_glyph)
        else:
            draw.text((cx, cy), glyph, fill=BRAND_PINK, anchor="mm")

        # Brand accent bar at the bottom (green) carrying the discreet caption.
        bar_h = int(h * 0.16)
        bar_top = h - bar_h
        draw.rectangle([0, bar_top, w, h], fill=BRAND_GREEN)
        label = (query or "").strip()
        if label:
            label = (label[0].upper() + label[1:])
            if len(label) > 58:
                label = label[:55] + "…"
            ty = bar_top + bar_h // 2
            if font_caption is not None:
                draw.text((cx, ty), label, fill=(255, 255, 255), anchor="mm", font=font_caption)
            else:
                draw.text((cx, ty), label, fill=(255, 255, 255), anchor="mm")

        os.makedirs(FALLBACK_DIR, exist_ok=True)
        out_path = f"{FALLBACK_DIR}/{uuid.uuid4()}.png"
        img.save(out_path, "PNG")
        return out_path
    except Exception as exc:
        logger.warning("branded_fallback_failed", query=query[:40], error=str(exc))
        return None


def _visual_holes(
    slides: list[SlideContent], image_map: dict[int, str]
) -> list[tuple[int, SlideContent]]:
    """Slides that NEED a visual but have no local path yet → would placeholder.

    Returns ``(pos, slide)`` pairs where ``pos`` is the global position
    (image_map key — FIX #26). A slide needs a visual when its strategy is a
    web-image search or a diagram. Position absent from image_map = the box
    stays empty = template placeholder text shows. Same criterion as the
    verify script's detector.
    """
    from app.models.core import SlideType

    holes: list[tuple[int, SlideContent]] = []
    for pos, s in enumerate(slides):
        strat = s.image.strategy
        # FIX #27.6: un diagram = ha diagram_code (qualunque strategy). Una web
        # image = ha query e NON è un diagram.
        # FIX #30.3 (2026-05-26): aggiunta condizione slide_type=CONTENT_IMAGE.
        # Layout CONTENT_IMAGE ha PICTURE placeholder SEMPRE — se la slide è
        # CONTENT_IMAGE e non c'è path in image_map, è un buco che va riempito
        # SEMPRE (o con query Pexels, o con fallback brandizzato), MAI lasciare
        # il placeholder template visibile.
        # FIX #30.9f (2026-05-27): un diagram = ha diagram_code (legacy)
        # OPPURE diagram_filling (catalogo SVG, FIX #30.4).
        is_diagram = bool(s.image.diagram_code or s.image.diagram_filling)
        is_content_image = s.slide_type == SlideType.CONTENT_IMAGE
        needs_visual = (
            is_diagram
            or is_content_image  # ← NEW: layout esige immagine sempre
            or bool(s.image.query and strat not in (None, "", "none", "inline_svg"))
        )
        if needs_visual and pos not in image_map:
            holes.append((pos, s))
    return holes


async def _backfill_missing_images(
    slides: list[SlideContent], image_map: dict[int, str], pool: Any
) -> None:
    """Fill every visual hole with a branded C.F.P. fallback.

    FIX #31 MOSSA 1 (2026-05-27, analista): Stage 1 (provider retry waves)
    ELIMINATO. Era retry cieco — stessa query, stesso istante, stesso
    Pexels → niente cambia → nessuna informazione nuova → 8 wave × 20s
    = 160s buttati per ``filled_now=0`` su tutto il loop. Il glitch di
    rete transitorio (l'unico caso dove ritentare ha senso) è ora
    catturato dal singolo retry-with-jitter dentro ``_download_one_image``.

    Qui resta SOLO il fallback brandizzato per i buchi residui — zero
    attese, zero waves, zero quota recovery sleep. Mutates image_map in
    place.
    """
    holes = _visual_holes(slides, image_map)
    if not holes:
        return

    logger.info("backfill_started", holes=len(holes), stage="branded_only")

    fallback_count = 0
    # FIX #31.5A (2026-05-27, analista review 6): disaggregare counter
    # per tipo. Prima loggavamo solo branded_fallbacks=N totale, ma
    # l'analista ha scoperto che la metrica "23/23 DIAGRAM catalog"
    # era falsa perché contava `image.diagram_filling` valorizzato nel
    # DB (sempre vero, l'LLM lo emette) ma NON contava se il render
    # cairosvg avesse effettivamente prodotto PNG: i fallback DIAGRAM
    # finivano nel branded ma erano invisibili al log generico.
    diagram_fallback_count = 0
    content_image_fallback_count = 0
    for pos, s in holes:
        # FIX #30.9f (2026-05-27): include diagram_filling.
        is_diagram = bool(s.image.diagram_code or s.image.diagram_filling)
        fb = await asyncio.to_thread(
            _make_branded_fallback,
            s.image.query or s.title or "",
            is_diagram=is_diagram,
        )
        if fb:
            image_map[pos] = fb
            fallback_count += 1
            if is_diagram:
                diagram_fallback_count += 1
            else:
                content_image_fallback_count += 1

    logger.info(
        "backfill_done",
        holes_initial=len(holes),
        branded_fallbacks=fallback_count,
        diagram_fallbacks=diagram_fallback_count,  # FIX #31.5A
        content_image_fallbacks=content_image_fallback_count,  # FIX #31.5A
        unresolved=len(_visual_holes(slides, image_map)),
    )


async def prefetch_images(
    slides: list[SlideContent], pool: Any
) -> dict[int, str]:
    """Resolve every slide's visual to a LOCAL PATH before sync PPTX build.

    FASE 4: prima del download, risolve query → query_url via search_image
    (Pexels orientation + Wikimedia). Poi:
    - Web images (``strategy='web_search'`` AND ``query_url`` present) are
      downloaded under the shared httpx client + fit-to-box.
    - Diagram slides (``strategy='diagram'``) are rendered via cairosvg
      wrapped in ``asyncio.to_thread``.

    The SlideBuilder MUST receive only local paths — invariant BP §07.0 line 2148.
    """
    # FIX #26 (2026-05-26): image_map is keyed by GLOBAL position (enumerate),
    # NOT slide.index — the latter is module-local and collides (up to 14
    # slides per index). The builder enumerates the same ordered list, so
    # position is the stable shared key.
    image_map: dict[int, str] = {}

    # FASE 4: risolvi gli URL mancanti (l'LLM emette query, non query_url)
    await _resolve_query_urls(slides)

    # FIX #27.6 (2026-05-26): il discriminante DIAGRAM è la PRESENZA di
    # diagram_code, NON strategy=="diagram". L'LLM emette strategy variabili
    # ("code", "diagram", "inline_svg", "generate"...) — visto in produzione
    # slide DIAGRAM con strategy="code" che NON venivano renderizzate → box
    # vuoto. Un diagram = ha diagram_code. Una web image = ha query/query_url
    # e NON ha diagram_code.
    # FIX #30.9f (2026-05-27, analista): includere anche `diagram_filling`
    # (catalogo SVG FIX #30.4) nel filter, oltre al legacy `diagram_code`.
    # Pre-fix: i 16 DIAGRAM dell'E2E #14 4h avevano diagram_filling valorizzato
    # ma diagram_code=None → esclusi dal prefetch diagram → mai renderizzati
    # → box nx_diagram_box vuoto nel PPTX (16 slide rotte, "diagram_box vuoto"
    # come quello fix immagini di 2 iterazioni fa).
    diagram_slides = [
        (pos, s) for pos, s in enumerate(slides)
        if s.image.diagram_code or s.image.diagram_filling
    ]
    diagram_positions = {pos for pos, _ in diagram_slides}

    # FIX #9 + #27.6: web slide = query_url presente, NON è un diagram.
    web_slides = [
        (pos, s)
        for pos, s in enumerate(slides)
        if s.image.query_url and pos not in diagram_positions
    ]
    web_requested = len(web_slides)

    if web_slides:
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT_SECONDS) as client:
            web_tasks = [_download_one_image(pos, s, pool, client) for pos, s in web_slides]
            web_results = await asyncio.gather(*web_tasks, return_exceptions=True)
        for result in web_results:
            if isinstance(result, tuple) and result[1] is not None:
                image_map[result[0]] = result[1]

    if diagram_slides:
        diagram_tasks = [
            asyncio.to_thread(_render_diagram_sync, pos, s) for pos, s in diagram_slides
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

    # FIX #25 (2026-05-26): zero-placeholder guarantee. Retry the holes with
    # throttling, then fill any residual with a branded C.F.P. fallback so no
    # CONTENT_IMAGE/DIAGRAM box ever renders the template's "[ query ]" text.
    logger.info("backfill_entry", slides=len(slides), resolved=len(image_map))
    await _backfill_missing_images(slides, image_map, pool)
    logger.info("backfill_exit", final_resolved=len(image_map))

    return image_map


__all__ = [
    "DIAGRAMS_DIR",
    "DOWNLOAD_TIMEOUT_SECONDS",
    "IMAGES_DIR",
    "MAX_IMAGE_BYTES",
    "prefetch_images",
    "sanitize_svg",
]
