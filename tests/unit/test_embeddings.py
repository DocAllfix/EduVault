"""F5.1 — Unit test embeddings (Voyage multimodal-3 path).

Mock Voyage client interamente: NO chiamata API reale. Verifica:
  - shape output 1024-dim
  - caption opzionale appended
  - input_type forwarded
  - errore se path inesistente o immagine corrotta
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

from app.services import dependencies as deps
from app.services.embeddings import embed_image_multimodal, embed_text_for_image_query


@pytest.fixture
def fake_voyage_client():
    """AsyncClient mock con multimodal_embed che ritorna 1024-dim."""
    client = MagicMock()
    response = MagicMock()
    response.embeddings = [[0.1] * 1024]
    client.multimodal_embed = AsyncMock(return_value=response)
    deps.set_voyage_client(client)
    yield client
    deps._voyage_client = None  # reset (no global leak)


@pytest.fixture
def tiny_png(tmp_path: Path) -> Path:
    """1x1 PNG valido salvato in tmp."""
    p = tmp_path / "tiny.png"
    Image.new("RGB", (1, 1), color=(255, 0, 0)).save(p, "PNG")
    return p


@pytest.mark.asyncio
async def test_embed_image_returns_1024_dim(fake_voyage_client, tiny_png):
    emb = await embed_image_multimodal(tiny_png)
    assert len(emb) == 1024
    assert all(isinstance(x, float) for x in emb)
    fake_voyage_client.multimodal_embed.assert_called_once()


@pytest.mark.asyncio
async def test_embed_image_with_caption_appends_text(fake_voyage_client, tiny_png):
    await embed_image_multimodal(tiny_png, caption="estintore antincendio")
    call = fake_voyage_client.multimodal_embed.call_args
    # parts = inputs[0] : [PIL.Image, caption_str]
    parts = call.kwargs["inputs"][0]
    assert len(parts) == 2
    assert parts[1] == "estintore antincendio"


@pytest.mark.asyncio
async def test_embed_image_input_type_default_document(fake_voyage_client, tiny_png):
    await embed_image_multimodal(tiny_png)
    call = fake_voyage_client.multimodal_embed.call_args
    assert call.kwargs["input_type"] == "document"


@pytest.mark.asyncio
async def test_embed_image_input_type_query(fake_voyage_client, tiny_png):
    await embed_image_multimodal(tiny_png, input_type="query")
    call = fake_voyage_client.multimodal_embed.call_args
    assert call.kwargs["input_type"] == "query"


@pytest.mark.asyncio
async def test_embed_image_raises_if_not_found(fake_voyage_client, tmp_path):
    with pytest.raises(FileNotFoundError):
        await embed_image_multimodal(tmp_path / "missing.png")


@pytest.mark.asyncio
async def test_embed_image_raises_on_corrupt(fake_voyage_client, tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"not a real png")
    with pytest.raises(Exception):  # Pillow UnidentifiedImageError or similar
        await embed_image_multimodal(bad)


@pytest.mark.asyncio
async def test_embed_image_raises_on_malformed_response(fake_voyage_client, tiny_png):
    # Simulo dimension wrong: 512 invece di 1024
    bad_response = MagicMock()
    bad_response.embeddings = [[0.0] * 512]
    fake_voyage_client.multimodal_embed = AsyncMock(return_value=bad_response)
    with pytest.raises(RuntimeError, match="malformed"):
        await embed_image_multimodal(tiny_png)


@pytest.mark.asyncio
async def test_embed_text_query_returns_1024(fake_voyage_client):
    emb = await embed_text_for_image_query("estintore officina")
    assert len(emb) == 1024
    call = fake_voyage_client.multimodal_embed.call_args
    assert call.kwargs["inputs"] == [["estintore officina"]]
    assert call.kwargs["input_type"] == "query"


@pytest.mark.asyncio
async def test_embed_text_query_raises_on_malformed(fake_voyage_client):
    bad_response = MagicMock()
    bad_response.embeddings = []
    fake_voyage_client.multimodal_embed = AsyncMock(return_value=bad_response)
    with pytest.raises(RuntimeError, match="malformed"):
        await embed_text_for_image_query("ciao")
