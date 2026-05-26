"""Image search client — Pexels primary + Wikimedia Commons fallback (Cluster F).

Sostituisce il "vuoto" attuale del Brave Search (D125 in VERIFICATION_DEBT):
nessun provider era cablato → ogni slide CONTENT_IMAGE finiva con
"[Immagine non disponibile]" nel PPTX.

Provider scelti (vedi sezione 3.D del piano test reali):
  - **Pexels** primario: free unlimited, no attribution required, foto reali
    italiane di sicurezza/formazione (rate 200/h).
  - **Wikimedia Commons** fallback: free + CC, utile per simboli normativi
    italiani / segnaletica.

API esposta:
  ``search_image(query: str) -> str | None``
      Returns the URL of the first matching image, or None if no provider
      ha risultati (cache miss + tutti i provider zero hit / errore).

REI-13: nessun dominio hardcoded; chiavi da settings.
REI-5: minimum code — no orchestrator complesso, solo Pexels + Wikimedia
in cascata.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

logger = structlog.get_logger()

# Endpoint costanti — Pexels e Wikimedia non cambieranno
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
WIKIMEDIA_API_URL = "https://commons.wikimedia.org/w/api.php"
# FIX #18 (2026-05-25): Pixabay come provider gratuito intermedio
# Free tier: 100 req/min (5000/min con key autenticata)
# Registrazione gratuita: https://pixabay.com/api/docs/
PIXABAY_SEARCH_URL = "https://pixabay.com/api/"
# FIX #19 (2026-05-25): Openverse come provider NO-KEY
# Aggregatore WordPress di 800M+ immagini Creative Commons (Flickr, Wikimedia,
# Smithsonian, Museum collections...). Rate limit: 20/min burst, 200/day anon.
# Per noi è ideale come fallback quando Pexels (200/h) finisce.
OPENVERSE_SEARCH_URL = "https://api.openverse.org/v1/images/"

# Timeout corto: se un provider non risponde in 8s, fallback
SEARCH_TIMEOUT = 8.0


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPError)),
)
async def _search_pexels(query: str, orientation: str | None = None) -> str | None:
    """Pexels REST: GET /v1/search?query=...&per_page=1[&orientation=...].

    Returns the URL of the largest available size (``src.original``).
    None se 0 risultati o key mancante.

    ``orientation`` (FASE 4 vast-hopping): 'landscape'|'portrait'|'square',
    passato come parametro nativo Pexels per ottenere immagini con l'aspect
    ratio richiesto dall'LLM (image.aspect_hint).
    """
    if not settings.pexels_api_key:
        return None

    params: dict[str, Any] = {"query": query, "per_page": 1, "locale": "it-IT"}
    if orientation in ("landscape", "portrait", "square"):
        params["orientation"] = orientation

    async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
        try:
            resp = await client.get(
                PEXELS_SEARCH_URL,
                params=params,
                headers={"Authorization": settings.pexels_api_key},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("pexels_rate_limit", query=query)
            else:
                logger.warning(
                    "pexels_http_error",
                    query=query,
                    status=exc.response.status_code,
                )
            return None

        data: dict[str, Any] = resp.json()
        photos = data.get("photos") or []
        if not photos:
            return None
        # Pexels src dict: original, large2x, large, medium, small, portrait, ...
        # Usiamo "large" — buon compromesso qualità/dimensione (~2000px wide).
        src = photos[0].get("src") or {}
        url = src.get("large") or src.get("original")
        if not isinstance(url, str):
            return None
        logger.info("pexels_hit", query=query, url=url)
        return url


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPError)),
)
async def _search_pixabay(query: str, orientation: str | None = None) -> str | None:
    """Pixabay REST: GET /api/?key=...&q=...&per_page=3&image_type=photo.

    FIX #18 (2026-05-25): provider gratuito intermedio (Pexels → Pixabay → Wikimedia).
    Pixabay tier free: 100 req/min, no attribution required per Content License.
    Senza key: 401. Con key gratuita (https://pixabay.com/api/docs/) 5000/h.
    """
    pixabay_key = getattr(settings, "pixabay_api_key", "")
    if not pixabay_key:
        return None

    params: dict[str, Any] = {
        "key": pixabay_key,
        "q": query,
        "per_page": 3,
        "image_type": "photo",
        "safesearch": "true",
        "lang": "it",
    }
    if orientation == "landscape":
        params["orientation"] = "horizontal"
    elif orientation == "portrait":
        params["orientation"] = "vertical"

    async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
        try:
            resp = await client.get(PIXABAY_SEARCH_URL, params=params)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("pixabay_http_error", query=query, status=exc.response.status_code)
            return None
        data: dict[str, Any] = resp.json()
        hits = data.get("hits") or []
        if not hits:
            return None
        # largeImageURL = ~1280px, sufficient per slide PPTX
        url = hits[0].get("largeImageURL") or hits[0].get("webformatURL")
        if not isinstance(url, str):
            return None
        logger.info("pixabay_hit", query=query, url=url)
        return url


# FIX #22 (2026-05-25): Openverse OAuth2 token cache (TTL 12h dal token).
# Authenticated tier: 100/min burst + 10000/day (50× rate anonymous).
import time as _time
_OPENVERSE_TOKEN_CACHE: dict[str, Any] = {"token": None, "expires_at": 0}


async def _get_openverse_token() -> str | None:
    """Ritorna access_token Openverse via OAuth2 client_credentials grant.

    Cache locale TTL 12h (server-side, basta per centinaia di corsi).
    Senza client_id/secret nel config restituisce None (fallback ad anonymous).
    """
    client_id = getattr(settings, "openverse_client_id", "")
    client_secret = getattr(settings, "openverse_client_secret", "")
    if not client_id or not client_secret:
        return None

    now = _time.time()
    if _OPENVERSE_TOKEN_CACHE["token"] and _OPENVERSE_TOKEN_CACHE["expires_at"] > now + 60:
        return _OPENVERSE_TOKEN_CACHE["token"]

    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            resp = await client.post(
                "https://api.openverse.org/v1/auth_tokens/token/",
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
            token = payload.get("access_token")
            expires_in = int(payload.get("expires_in", 43200))
            if isinstance(token, str):
                _OPENVERSE_TOKEN_CACHE["token"] = token
                _OPENVERSE_TOKEN_CACHE["expires_at"] = now + expires_in
                logger.info("openverse_token_fetched", expires_in=expires_in)
                return token
    except Exception as exc:
        logger.warning("openverse_token_failed", error=str(exc))
    return None


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPError)),
)
async def _search_openverse(query: str, orientation: str | None = None) -> str | None:
    """Openverse REST: GET /v1/images/?q=...&page_size=1.

    FIX #19 (2026-05-25): provider NO-KEY (200/day anonymous, 20/min burst).
    FIX #22 (2026-05-25): se disponibile token OAuth2, usa tier authenticated
    (100/min burst, 10K/day sustained).
    """
    params: dict[str, Any] = {
        "q": query,
        "page_size": 1,
        # extension filter: solo formati renderizzabili da python-pptx
        "extension": "jpg,png,jpeg",
    }
    headers = {
        "User-Agent": "NexusEduVault/1.0 (corsi8108 formazione sicurezza lavoro)",
    }
    # Tier authenticated se token disponibile
    token = await _get_openverse_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT, headers=headers) as client:
        try:
            resp = await client.get(OPENVERSE_SEARCH_URL, params=params, follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("openverse_rate_limit", query=query)
            else:
                logger.warning("openverse_http_error", query=query, status=exc.response.status_code)
            return None
        data: dict[str, Any] = resp.json()
        results = data.get("results") or []
        if not results:
            return None
        url = results[0].get("url")
        if not isinstance(url, str):
            return None
        logger.info("openverse_hit", query=query, url=url, authenticated=bool(token))
        return url


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPError)),
)
async def _search_wikimedia(query: str) -> str | None:
    """Wikimedia Commons fallback: cerca file libera + restituisce URL HTTPS
    della miniatura grande (1200px wide).

    None se nessun risultato. Sempre safe: API gratuita senza key.
    """
    # Wikimedia API enforces a User-Agent policy (HTTP 403 senza UA proprio):
    # https://meta.wikimedia.org/wiki/User-Agent_policy
    headers = {
        "User-Agent": "NexusEduVault/1.0 (https://github.com/DocAllfix/EduVault; "
                      "contact via repo) image-search-cluster-F",
    }
    async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT, headers=headers) as client:
        try:
            # 1. Cerca file matching query
            resp = await client.get(
                WIKIMEDIA_API_URL,
                params={
                    "action": "query",
                    "format": "json",
                    "list": "search",
                    "srnamespace": "6",  # File: namespace
                    "srsearch": query,
                    "srlimit": "1",
                },
            )
            resp.raise_for_status()
            results = (resp.json().get("query") or {}).get("search") or []
            if not results:
                return None
            file_title = results[0]["title"]  # es. "File:Logo.svg"

            # 2. Risolvi URL imageinfo (thumbnail 1200px)
            resp2 = await client.get(
                WIKIMEDIA_API_URL,
                params={
                    "action": "query",
                    "format": "json",
                    "titles": file_title,
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "iiurlwidth": "1200",
                },
            )
            resp2.raise_for_status()
            pages = (resp2.json().get("query") or {}).get("pages") or {}
            for page in pages.values():
                infos = page.get("imageinfo") or []
                if infos:
                    url = infos[0].get("thumburl") or infos[0].get("url")
                    if isinstance(url, str):
                        logger.info("wikimedia_hit", query=query, url=url)
                        return url
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "wikimedia_http_error",
                query=query,
                status=exc.response.status_code,
            )
            return None
        return None


# FIX #10 (2026-05-25): cache server-side query→URL per ridurre call ripetute
# a Pexels (rate-limit 200/h). Su corso 8h con 176 CONTENT_IMAGE molte query
# si ripetono (es. "DPI cantiere" appare in 3 moduli diversi). Cache invalidata
# al restart del backend (è OK, non serve persistente).
_IMAGE_SEARCH_CACHE: dict[tuple[str, str | None], str | None] = {}


def _simplify_query(query: str) -> str | None:
    """Riduce una query multi-parola a 1-2 keyword principali per retry su zero hits.

    Strategia: rimuove stopword italiane, tiene le ultime 2 parole significative
    (di solito le più specifiche/recenti nella frase).
    Esempi:
        'segnaletica di emergenza per le vie di fuga' -> 'segnaletica emergenza'
        'kit medicazione pronto soccorso aziendale' -> 'kit medicazione'
        'cantiere' -> None (già minima)
    """
    stopwords = {"di", "del", "della", "dei", "delle", "il", "lo", "la", "i", "gli", "le",
                 "per", "con", "e", "a", "in", "su", "da", "un", "una", "uno"}
    tokens = [t.lower() for t in query.split() if t.lower() not in stopwords and len(t) > 2]
    if len(tokens) < 2:
        return None  # già minima
    return " ".join(tokens[:2])


async def search_image(query: str, orientation: str | None = None) -> str | None:
    """Cerca un'immagine in cascata: cache → Pexels → Wikimedia → Pexels(simplified).

    Restituisce l'URL del primo match, None se nessun provider trova
    risultati. Errori HTTP / timeout sono catturati e degradati a None
    (un'immagine mancante non deve far crashare la pipeline — la slide
    cadrà nel fallback "[Immagine non disponibile]" lato SlideBuilder).

    FIX #10 (2026-05-25): aggiunta cache in-memory + retry con query semplificata
    dopo 0 risultati. Target: salire da 22% a 80%+ resolved rate.

    Argomenti:
        query: 2-4 parole italiane descrittive del concetto (es.
            "casco protezione cantiere"). L'LLM le genera nel content_agent.
        orientation (FASE 4): 'landscape'|'portrait'|'square' da
            ``slide.image.aspect_hint`` — passato a Pexels per aspect matching.
    """
    if not query or not query.strip():
        return None
    q = query.strip()

    # 0. Cache hit (la stessa query ripetuta in slide diverse non spende quota)
    cache_key = (q.lower(), orientation)
    if cache_key in _IMAGE_SEARCH_CACHE:
        cached = _IMAGE_SEARCH_CACHE[cache_key]
        logger.debug("image_search_cache_hit", query=q, hit=bool(cached))
        return cached

    # 1. Pexels (preferito) con orientation hint
    try:
        url = await _search_pexels(q, orientation=orientation)
        if url:
            _IMAGE_SEARCH_CACHE[cache_key] = url
            return url
    except Exception as exc:
        logger.warning("pexels_unexpected_error", query=q, error=str(exc))

    # 2. Pixabay (FIX #18 2026-05-25): provider intermedio gratuito 5000/h
    try:
        url = await _search_pixabay(q, orientation=orientation)
        if url:
            _IMAGE_SEARCH_CACHE[cache_key] = url
            return url
    except Exception as exc:
        logger.warning("pixabay_unexpected_error", query=q, error=str(exc))

    # 3. Openverse (FIX #19 2026-05-25): NO-KEY 200/day, aggregatore 800M+ CC
    try:
        url = await _search_openverse(q, orientation=orientation)
        if url:
            _IMAGE_SEARCH_CACHE[cache_key] = url
            return url
    except Exception as exc:
        logger.warning("openverse_unexpected_error", query=q, error=str(exc))

    # 4. Wikimedia fallback (no limite)
    try:
        url = await _search_wikimedia(q)
        if url:
            _IMAGE_SEARCH_CACHE[cache_key] = url
            return url
    except Exception as exc:
        logger.warning("wikimedia_unexpected_error", query=q, error=str(exc))

    # 3. Retry Pexels con query semplificata (FIX #10)
    simplified = _simplify_query(q)
    if simplified and simplified != q.lower():
        logger.info("image_search_simplify_retry", original=q, simplified=simplified)
        try:
            url = await _search_pexels(simplified, orientation=orientation)
            if url:
                _IMAGE_SEARCH_CACHE[cache_key] = url
                return url
        except Exception as exc:
            logger.warning("pexels_retry_error", query=simplified, error=str(exc))

    # 4. Memo del fallimento (evita ripetere le stesse fallite query)
    _IMAGE_SEARCH_CACHE[cache_key] = None
    logger.info("image_search_no_results", query=q)
    return None


__all__ = ["search_image"]
