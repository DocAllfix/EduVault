"""F5 — Embeddings (image + text via Voyage multimodal-3).

Pattern allineato a `ingestion_service.voyage_embed_with_retry` per il path
testuale (voyage-3, 1024 dim). Aggiunge il path multimodale (image + text
opzionale) per la image_library introdotta in F5 (vast-hopping-sketch).

Provider unico: ``voyageai.AsyncClient`` con setting
``settings.voyage_multimodal_model`` (default "voyage-multimodal-3") gia'
presente in `app/config.py:112`. Il client globale lo recupera
``get_voyage_client()`` da `app/services/dependencies.py`.

Non riusiamo ``embed_query`` perche' quello e' text-only voyage-3 input_type
query. Multimodal e' una API distinta sul medesimo client.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
from PIL import Image

from app.config import settings
from app.services.dependencies import get_voyage_client

logger = structlog.get_logger(__name__)


async def embed_image_multimodal(
    image_path: Path,
    *,
    caption: str | None = None,
    input_type: str = "document",
) -> list[float]:
    """Embed an image (optionally with a caption) via voyage-multimodal-3.

    Args:
        image_path: filesystem path to a PNG/JPEG/WebP. Validato da PIL prima
            della chiamata API (se non e' un'immagine valida, raise ValueError
            invece di mandare bytes corrotti a Voyage).
        caption: testo opzionale che accompagna l'immagine (es. nome del file
            o didascalia originale). Voyage multimodal pesa entrambi nello
            stesso embedding 1024-dim.
        input_type: "document" per seed library (default), "query" per
            search-time embedding.

    Returns:
        Lista di 1024 float32 (cosine-compatibile con HNSW pgvector).

    Raises:
        FileNotFoundError: image_path non esiste.
        ValueError: file non e' un'immagine valida (Pillow.verify()).
        RuntimeError: client Voyage non inizializzato (set_voyage_client mai chiamato).
    """
    if not image_path.exists():
        raise FileNotFoundError(f"image not found: {image_path}")

    # Validazione integrita' (REI-10 sicurezza by default).
    with Image.open(image_path) as probe:
        probe.verify()
    # verify() consuma l'oggetto: riapri per passarlo al client.
    pil_img = Image.open(image_path)

    client = get_voyage_client()
    model = settings.voyage_multimodal_model

    # Voyage multimodal accetta List[List[Union[str, PIL.Image]]]: ogni
    # sublist e' UN documento composto da N parti (immagine + testo opz.).
    parts: list[Any] = [pil_img]
    if caption:
        parts.append(caption)

    response = await client.multimodal_embed(
        inputs=[parts],
        model=model,
        input_type=input_type,
    )
    embeddings = response.embeddings
    if not embeddings or len(embeddings[0]) != 1024:
        raise RuntimeError(
            f"voyage multimodal returned malformed embedding: "
            f"len={len(embeddings) if embeddings else 0}, "
            f"dim={len(embeddings[0]) if embeddings and embeddings[0] else 0}"
        )
    return list(embeddings[0])


async def embed_text_for_image_query(text: str) -> list[float]:
    """Embed text-only query for image_library cosine search.

    Multimodal-3 produce embedding 1024-dim per testo SOLO compatibile con
    embedding immagine SOLO se entrambi passati allo stesso modello
    multimodal. NON riusare ``embed_query`` (voyage-3) qui: lo spazio
    vettoriale e' diverso.
    """
    client = get_voyage_client()
    model = settings.voyage_multimodal_model
    response = await client.multimodal_embed(
        inputs=[[text]],
        model=model,
        input_type="query",
    )
    embeddings = response.embeddings
    if not embeddings or len(embeddings[0]) != 1024:
        raise RuntimeError(
            f"voyage multimodal text query returned malformed embedding: "
            f"len={len(embeddings) if embeddings else 0}"
        )
    return list(embeddings[0])
