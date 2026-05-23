"""Typed environment configuration (OPT-2 v3.0).

Single source of truth for all environment variables. Every other module
MUST use `from app.config import settings` — direct `os.environ[]` access
is forbidden (OPT-2).

This file deliberately follows pydantic-settings v2 (not the legacy
module-level constants pattern shown in BLUEPRINT §02.5/§02.6, which
predates OPT-2). Field names map 1:1 to upper-case env vars per
pydantic-settings default behavior (e.g. ``database_url`` <- ``DATABASE_URL``).
"""

from __future__ import annotations

import logging

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings, validated at startup."""

    # === Database (BP §02.6) ===
    database_url: str  # postgresql://nexus_app:...@postgres:5432/nexus
    database_admin_url: str = ""  # seed.py + migrations only (nexus_admin)

    # === API keys (BP §02.6) ===
    anthropic_api_key: str
    voyage_api_key: str
    brave_search_api_key: str = ""

    # === Auth — single JWT secret, token type in payload (BP §08.1) ===
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    jwt_refresh_expiry_days: int = 7

    # === CORS — explicit origin, never wildcard (REI-10) ===
    frontend_url: str = "http://localhost:3000"

    # === Pipeline (BP §1.4 D-02 — MAX_CONCURRENT_JOBS must stay 1) ===
    pipeline_timeout: int = 1800
    llm_request_timeout: int = 120
    max_concurrent_jobs: int = 1

    # === TTS — OPT-1: edge-tts, no API key required ===
    tts_voice: str = "it-IT-DiegoNeural"

    # === Branding ===
    organization_name: str = "corsi8108"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()


def configure_logging() -> None:
    """Configure structlog (REI-7: structured JSON logs, never print()).

    Called once in app.main.startup() per BLUEPRINT §02.5.
    """
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
