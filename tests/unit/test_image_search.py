"""FIX #31 MOSSA 2 — image_search dedup tests.

Coverage:
1. ``_search_pexels`` returns ``list[str]`` (was ``str | None``).
2. ``search_image`` with ``seen_urls`` enforces per-course reuse budget=2.
3. ``search_image`` exhausts Pexels candidates then falls back to Pixabay.
4. ``search_image`` backward-compat: ``seen_urls=None`` → first URL wins.
5. Cache shape is now ``list[str]`` (no breaking change because in-memory
   pure, see FIX #31 plan verification).

All tests mock httpx — no live network.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import image_search as svc
from app.services.image_search import (
    _PER_COURSE_URL_REUSE_BUDGET,
    _IMAGE_SEARCH_CACHE,
    search_image,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Each test starts with a clean cache so cross-test pollution is impossible."""
    _IMAGE_SEARCH_CACHE.clear()


# ─────────────── _search_pexels signature ───────────────


@pytest.mark.asyncio
async def test_search_pexels_returns_list_of_urls() -> None:
    """FIX #31 MOSSA 2: _search_pexels ora ritorna list[str] (era str|None)."""
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json = MagicMock(return_value={
        "photos": [
            {"src": {"large": f"https://example.com/p{i}.jpg"}} for i in range(5)
        ]
    })

    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_resp)
    fake_client_ctx = MagicMock()
    fake_client_ctx.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch.object(svc.settings, "pexels_api_key", "fake-key"), \
         patch.object(svc.httpx, "AsyncClient", return_value=fake_client_ctx):
        urls = await svc._search_pexels("test query", orientation="landscape")

    assert isinstance(urls, list)
    assert len(urls) == 5
    assert all(u.startswith("https://example.com/p") for u in urls)


@pytest.mark.asyncio
async def test_search_pexels_returns_empty_list_on_no_results() -> None:
    """No results → empty list (not None)."""
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json = MagicMock(return_value={"photos": []})

    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_resp)
    fake_client_ctx = MagicMock()
    fake_client_ctx.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client_ctx.__aexit__ = AsyncMock(return_value=None)

    with patch.object(svc.settings, "pexels_api_key", "fake-key"), \
         patch.object(svc.httpx, "AsyncClient", return_value=fake_client_ctx):
        urls = await svc._search_pexels("zero hits query")

    assert urls == []


# ─────────────── search_image dedup with seen_urls ───────────────


@pytest.mark.asyncio
async def test_search_image_dedup_respects_reuse_budget() -> None:
    """FIX #31 MOSSA 2: search_image rispetta budget di riuso URL=2 per corso.

    Mock _search_pexels → ["A","B","C","D","E"]. 4 chiamate consecutive
    con stesso seen_urls → expect (A, A, B, B) perché ogni URL può essere
    riusato max 2 volte prima di scalare al successivo.
    """
    candidates = [f"https://example.com/{c}.jpg" for c in "ABCDE"]

    with patch.object(svc, "_search_pexels", new=AsyncMock(return_value=candidates)):
        seen: dict[str, int] = {}
        results = []
        for _ in range(4):
            url = await search_image("dpi cantiere", seen_urls=seen)
            results.append(url)

    assert results[0] == candidates[0]  # A primo uso
    assert results[1] == candidates[0]  # A secondo uso (budget=2)
    assert results[2] == candidates[1]  # B primo uso (A saturato)
    assert results[3] == candidates[1]  # B secondo uso

    # Counter consistency
    assert seen[candidates[0]] == 2
    assert seen[candidates[1]] == 2
    assert _PER_COURSE_URL_REUSE_BUDGET == 2  # contract guard


@pytest.mark.asyncio
async def test_search_image_exhausts_pexels_then_falls_back_to_pixabay() -> None:
    """Se TUTTI i candidati Pexels sono saturati dal budget per il corso,
    search_image scala a Pixabay invece di ritornare None."""
    pexels_urls = [f"https://pexels.com/p{i}.jpg" for i in range(3)]
    pixabay_url = "https://pixabay.com/different.jpg"

    # Pre-saturazione seen_urls: tutti i 3 URL Pexels già usati 2 volte
    seen = {u: 2 for u in pexels_urls}

    with patch.object(svc, "_search_pexels", new=AsyncMock(return_value=pexels_urls)), \
         patch.object(svc, "_search_pixabay", new=AsyncMock(return_value=pixabay_url)), \
         patch.object(svc, "_search_openverse", new=AsyncMock(return_value=None)), \
         patch.object(svc, "_search_wikimedia", new=AsyncMock(return_value=None)):
        url = await search_image("test query", seen_urls=seen)

    assert url == pixabay_url
    assert seen[pixabay_url] == 1  # ora Pixabay è registrato anche lui


@pytest.mark.asyncio
async def test_search_image_backward_compat_when_seen_urls_none() -> None:
    """seen_urls=None → comportamento pre-fix (primo URL della lista vince
    sempre, nessun dedup applicato)."""
    candidates = [f"https://example.com/{c}.jpg" for c in "ABCDE"]

    with patch.object(svc, "_search_pexels", new=AsyncMock(return_value=candidates)):
        # 5 chiamate identiche, NESSUN seen_urls → tutte tornano A
        urls = [await search_image("test") for _ in range(5)]

    assert all(u == candidates[0] for u in urls)


@pytest.mark.asyncio
async def test_search_image_cache_is_list_of_urls() -> None:
    """FIX #31 MOSSA 2: cache shape cambia da str|None a list[str]."""
    candidates = [f"https://example.com/{i}.jpg" for i in range(3)]

    with patch.object(svc, "_search_pexels", new=AsyncMock(return_value=candidates)):
        await search_image("cache test", orientation="landscape")

    assert ("cache test", "landscape") in _IMAGE_SEARCH_CACHE
    cached = _IMAGE_SEARCH_CACHE[("cache test", "landscape")]
    assert isinstance(cached, list)
    assert cached == candidates


@pytest.mark.asyncio
async def test_search_image_empty_query_returns_none() -> None:
    """Edge case: query vuota → None senza toccare alcun provider."""
    with patch.object(svc, "_search_pexels", new=AsyncMock()) as p:
        url = await search_image("", seen_urls={})
    assert url is None
    p.assert_not_called()
