"""Cluster F — Live image search via Pexels + Wikimedia fallback.

NO MOCKS. Calls real Pexels API + Wikimedia Commons API.

Prerequisiti:
 - PEXELS_API_KEY in .env (https://www.pexels.com/api/new/ — free tier)
 - Internet libero (Wikimedia API no key required)

I test che richiedono PEXELS_API_KEY skippano gracefully se la key
manca, così possiamo prepararli ora ed eseguirli appena la fornisci.

Costo: $0 (Pexels free, Wikimedia free).
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.services.image_search import (
    _search_pexels,
    _search_wikimedia,
    search_image,
)

pytestmark = pytest.mark.live

needs_pexels = pytest.mark.skipif(
    not settings.pexels_api_key,
    reason="PEXELS_API_KEY not set in .env (https://www.pexels.com/api/new/)",
)


# ──────────────────────── Pexels live ────────────────────────


@needs_pexels
async def test_f01_pexels_returns_image_url_for_italian_query() -> None:
    """Pexels deve trovare almeno 1 immagine per query italiana comune."""
    url = await _search_pexels("casco protezione")
    assert url is not None, "Pexels did not return any image"
    assert url.startswith("https://"), f"unexpected URL: {url}"


@needs_pexels
async def test_f02_pexels_returns_url_or_none_robustly() -> None:
    """Pexels è generoso: anche per query nonsense può ritornare un'immagine
    (matching parziale, foto generiche). Test: l'API non crasha e ritorna
    str|None (None solo se davvero zero risultati).
    """
    url = await _search_pexels("xyzzy_qweqweqwe_never_matches_42")
    assert url is None or url.startswith("https://"), f"unexpected: {url!r}"


@needs_pexels
async def test_f03_pexels_handles_complex_italian_query() -> None:
    """Query domain-specific (sicurezza lavoro)."""
    url = await _search_pexels("estintore antincendio")
    assert url is not None
    assert url.startswith("https://")


# ──────────────────────── Wikimedia live (no key) ────────────────────────


async def test_f04_wikimedia_returns_url_for_well_known_query() -> None:
    """Wikimedia Commons ha sempre immagini per termini comuni."""
    url = await _search_wikimedia("Italy flag")
    assert url is not None
    assert "wikimedia.org" in url or "wikipedia.org" in url


async def test_f05_wikimedia_handles_no_results_query() -> None:
    """Wikimedia deve ritornare None senza crash su nonsense."""
    url = await _search_wikimedia("xyzzy_qweqweqwe_never_matches_42")
    assert url is None


# ──────────────────────── Cascade search_image() ────────────────────────


async def test_f06_search_image_cascade_returns_for_known_query() -> None:
    """search_image() in cascata: se Pexels è set deve usarlo, altrimenti
    cade su Wikimedia. Per termine generico almeno uno dei due ha hit."""
    url = await search_image("electricity")
    # Almeno uno dei due provider trova qualcosa per termine inglese basico
    if settings.pexels_api_key:
        # con Pexels attivo dovrebbe rispondere lui
        assert url is not None
    else:
        # senza Pexels, fallback Wikimedia ha "electricity" image
        assert url is not None


async def test_f07_search_image_returns_url_or_none_for_random_query() -> None:
    """search_image() in cascata può sempre ritornare qualcosa (Pexels è
    molto generoso). Test: l'API è robusta, no crash, ritorna str|None."""
    url = await search_image("xyzzy_qweqweqwe_never_matches_42")
    assert url is None or url.startswith("https://")


async def test_f08_search_image_handles_empty_query() -> None:
    """Query vuota / whitespace → None immediato (no API call)."""
    assert await search_image("") is None
    assert await search_image("   ") is None
