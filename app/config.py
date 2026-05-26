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
from typing import Literal

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
    # Cluster F: Pexels primary image provider (free tier ~200/h, no attribution)
    # https://www.pexels.com/api/new/
    pexels_api_key: str = ""
    # FIX #18 (2026-05-25): Pixabay fallback intermedio (5000/h free auth)
    # Registrazione gratuita: https://pixabay.com/api/docs/
    pixabay_api_key: str = ""
    # FIX #22 (2026-05-25): Openverse OAuth2 (100/min, 10K/day vs 20/min anon)
    # Registrazione gratuita: POST /v1/auth_tokens/register/ + verify email
    openverse_client_id: str = ""
    openverse_client_secret: str = ""

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

    # === LLM provider selection (FASE 0b vast-hopping-sketch) ===
    # Default: Azure OpenAI gpt-4.1-mini (10× cheaper than Sonnet 4.6, JSON mode
    # strict nativo, 200K TPM). Anthropic resta come L2 fallback emergenza.
    llm_provider: Literal["anthropic", "azure_openai", "openai", "deepseek"] = "deepseek"

    # OpenAI diretto (fallback L1)
    openai_api_key: str = ""
    openai_content_model: str = "gpt-4o"
    openai_classify_model: str = "gpt-4o-mini"

    # DeepSeek V4 — provider PRIMARY 2026-05-25.
    # PRO è un REASONING model: ottimo per ragionare sui constraints ma:
    # - 2-3× più costoso (token reasoning fatturati)
    # - latenza 10-30s/call (vs 5-10s flash)
    # - JSON mode talvolta conflitta (content vuoto, tutto reasoning)
    # FLASH è il non-thinking, output diretto, 3× più economico, qualità OK
    # per slide normative italiane. Pro resta L1 fallback (vedi chain in
    # ingestion_service) e per override manuale corsi complessi.
    deepseek_api_key: str = ""
    deepseek_content_model: str = "deepseek-v4-flash"  # default non-thinking
    deepseek_classify_model: str = "deepseek-v4-flash"
    deepseek_premium_model: str = "deepseek-v4-pro"    # reasoning per override

    # === Azure OpenAI (primary L0 + premium L1 fallback) ===
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment_content: str = "gpt-4.1-mini"   # L0: primary
    azure_openai_deployment_classify: str = "gpt-4.1-mini"  # classify_chunk
    azure_openai_deployment_premium: str = "gpt-4o"         # L1: fallback premium

    # === Anthropic (legacy + L2 fallback emergenza) ===
    # llm_classify_model / llm_content_model = nomi dei modelli Anthropic usati SOLO
    # quando llm_provider="anthropic" oppure quando il fallback raggiunge L2.
    llm_classify_model: str = "claude-haiku-4-5-20251001"
    llm_content_model: str = "claude-sonnet-4-6"
    llm_content_model_fallback: str = "claude-sonnet-4-6"   # L2 emergenza content_agent

    # === Parallelizzazione moduli (R6 mitigation, FASE 0b) ===
    # DeepSeek V4 Flash ha 2500 concurrency, V4 Pro 500. Settiamo 100 paralleli:
    # ben oltre 24 moduli del corso 8h (1 wave), margine 4× per SPLIT retry.
    content_agent_concurrency: int = 100

    # === TTS — OPT-1: edge-tts, no API key required ===
    tts_voice: str = "it-IT-DiegoNeural"

    # === Branding ===
    organization_name: str = "corsi8108"

    # === Seed (BP §02.7 + REI-13: domain NOT decided) ===
    # Used by scripts/seed.py on first run only.
    # Email host is intentionally a placeholder until PHASE 7 (REI-13).
    admin_bootstrap_email: str = "admin@<DOMAIN_TBD>"
    admin_bootstrap_password: str = "CHANGE_ME"

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
