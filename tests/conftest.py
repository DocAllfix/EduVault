"""Pytest configuration shared by integration and unit tests.

Provides minimum env vars required by ``app.config.Settings`` so that
``app.main`` can be imported without a real .env file. These values
are dummies and MUST NOT match anything real — tests stub external
calls (Voyage, Anthropic, Postgres) before exercising any code that
would use them.
"""

from __future__ import annotations

import os

# Defaults must be set BEFORE app.config is imported anywhere.
os.environ.setdefault(
    "DATABASE_URL", "postgresql://nexus_app:test@localhost:5432/nexus_test"
)
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("VOYAGE_API_KEY", "test-voyage-key")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-not-used-for-anything-real")
