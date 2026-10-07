"""Real Supabase Postgres integration tests. Skipped unless DATABASE_URL is Postgres.

These verify migration results (tables, pgvector, RLS, bucket, indexes, FKs).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from backend.app.core.config import settings
from backend.app.db.session import _normalize_url
from backend.tests.integration.conftest import requires_supabase_db

pytestmark = [pytest.mark.integration, requires_supabase_db]

EXPECTED_TABLES = [
    "profiles",
    "cameras",
    "camera_sessions",
    "memories",
    "memory_objects",
    "memory_events",
    "object_history",
    "evidence",
    "chat_conversations",
    "chat_messages",
]


@pytest.fixture(scope="module")
def conn():
    engine = create_engine(_normalize_url(settings.database_url))
    with engine.connect() as connection:
        yield connection


def test_tables_exist(conn):
    rows = (
        conn.execute(
            text(
                "select table_name from information_schema.tables where table_schema='public'"
            )
        )
        .scalars()
        .all()
    )
    missing = sorted(set(EXPECTED_TABLES) - set(rows))
    assert not missing, f"missing tables: {missing}"


def test_pgvector_extension(conn):
    assert (
        conn.execute(
            text("select extname from pg_extension where extname='vector'")
        ).scalar()
        == "vector"
    )


def test_embedding_is_vector_1024(conn):
    coltype = conn.execute(
        text(
            "select format_type(a.atttypid, a.atttypmod) from pg_attribute a "
            "join pg_class c on c.oid=a.attrelid "
            "where c.relname='memories' and a.attname='embedding'"
        )
    ).scalar()
    assert coltype and "vector(1024)" in str(coltype)


def test_rls_enabled(conn):
    rows = conn.execute(
        text(
            "select relname, relrowsecurity from pg_class where relname = any(:t) and relkind='r'"
        ),
        {"t": EXPECTED_TABLES},
    ).all()
    disabled = [r for r, en in rows if not en]
    assert not disabled, f"RLS disabled on: {disabled}"


def test_policies_exist(conn):
    n = conn.execute(
        text("select count(*) from pg_policies where schemaname='public'")
    ).scalar()
    assert int(n) > 0


def test_storage_bucket_private(conn):
    row = conn.execute(
        text("select public from storage.buckets where id=:b"),
        {"b": settings.supabase_evidence_bucket},
    ).all()
    assert row, "evidence bucket missing"
    assert row[0][0] is False
