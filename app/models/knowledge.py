"""Knowledge Base contracts (BLUEPRINT §04.3).

Only import-path differs from BP §04.3: ``app.models.core`` instead of ``models.core``.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.models.core import ChunkType


class NormativeChunk(BaseModel):
    """Atomic unit of legislative knowledge retrieved by the RAG."""

    chunk_id: str
    regulation_id: str
    article: str | None = None
    paragraph: str | None = None
    hierarchy_path: str
    body: str
    chunk_type: ChunkType
    tags: list[str] = []
    relevance_score: float | None = None


class StylePattern(BaseModel):
    """Stylistic pattern extracted from Level 2 (approved courses).

    CONTAINS ONLY STRUCTURAL METADATA. Never full sentences, never normative
    text, never text blocks. This prevents the Level-2 self-poisoning loop
    (Model Collapse).
    """

    avg_words_per_slide: int
    preferred_slide_sequence: list[str]  # e.g. ["CONTENT_TEXT", "CONTENT_IMAGE", "QUIZ", "RECAP"]
    tone_register: str  # "tecnico-divulgativo" | "formale" | "accessibile"
    recurring_section_titles: list[str]  # e.g. ["Introduzione", "Obblighi del datore", "Riepilogo"]
    avg_quiz_per_module: float
    preferred_image_ratio: float  # fraction of slides with an image, e.g. 0.20

    # ═══ ANTI-POISONING CONSTRAINT (BP §04.3) ═══
    # This model MUST NEVER contain:
    # - Full sentences copied from prior courses
    # - Verbatim normative text
    # - Free-form text blocks of any kind
    # If a future developer adds text-bearing fields here,
    # they are breaking the anti-Model-Collapse barrier.
