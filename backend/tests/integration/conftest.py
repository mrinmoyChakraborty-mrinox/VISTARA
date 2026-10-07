"""Integration tests — require real Groq/Supabase. Skipped when unavailable.

Run all integration tests:   pytest -m integration
Run offline only (default):  pytest

These are NOT part of normal offline CI.
"""

from __future__ import annotations

import pytest

from backend.app.core.config import settings


def groq_available() -> bool:
    return bool(settings.groq_api_key)


def supabase_db_available() -> bool:
    return bool(settings.database_url) and not settings.database_url.startswith(
        "sqlite"
    )


requires_groq = pytest.mark.skipif(
    not groq_available(), reason="GROQ_API_KEY not configured"
)
requires_supabase_db = pytest.mark.skipif(
    not supabase_db_available(),
    reason="DATABASE_URL is not a real Supabase Postgres URL",
)
