"""PostgreSQL connection pool (BLUEPRINT §02.3).

VPS constraint: PostgreSQL single-instance with max_connections=100.
LangGraph checkpointer uses its own connections, so cap the application
pool at 20. The app connects as ``nexus_app`` (NOT ``nexus_admin``) —
the role split is enforced at SQL level (BP D-13).
"""

from __future__ import annotations

import asyncpg

from app.config import settings


async def create_pool() -> asyncpg.Pool:
    """Create the asyncpg pool used across the application.

    Called once in ``app.main.startup()``.
    """
    return await asyncpg.create_pool(
        dsn=settings.database_url,  # nexus_app role
        min_size=5,
        max_size=20,
        command_timeout=60,
    )
