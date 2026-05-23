"""Core enums shared across the project (BLUEPRINT §04.1)."""

from __future__ import annotations

from enum import Enum


class TargetType(str, Enum):
    DISCENTE = "discente"
    FORMATORE = "formatore"


class SlideDensity(str, Enum):
    LEGGERA = "leggera"
    STANDARD = "standard"
    INTENSIVA = "intensiva"


class SlideType(str, Enum):
    TITLE = "TITLE"
    CONTENT_TEXT = "CONTENT_TEXT"
    CONTENT_IMAGE = "CONTENT_IMAGE"
    DIAGRAM = "DIAGRAM"
    QUIZ = "QUIZ"
    CASE_STUDY = "CASE_STUDY"
    RECAP = "RECAP"
    CLOSING = "CLOSING"


class ChunkType(str, Enum):
    OBBLIGO = "OBBLIGO"
    SANZIONE = "SANZIONE"
    DEFINIZIONE = "DEFINIZIONE"
    PROCEDURA = "PROCEDURA"
    GENERALE = "GENERALE"
