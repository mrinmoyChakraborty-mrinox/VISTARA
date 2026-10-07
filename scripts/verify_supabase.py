"""Verify a REAL Supabase database after running the migration.

Run:
    python scripts/verify_supabase.py

Reads DATABASE_URL from .env. Prints a safe, value-free report. Exit code 1 if any
required check fails. Does NOT print connection strings or secrets.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

from backend.app.core.config import settings
from backend.app.db.session import _normalize_url

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
RLS_TABLES = EXPECTED_TABLES


def main() -> int:
    url = settings.database_url
    if not url or url.startswith("sqlite"):
        print("BLOCKER: DATABASE_URL is not a real Postgres URL (sqlite/unset).")
        print(
            "Set DATABASE_URL to your Supabase connection string in .env, then re-run."
        )
        return 1

    engine = create_engine(_normalize_url(url))
    ok = True
    with engine.connect() as conn:
        # extension
        ext = conn.execute(
            text("select extname from pg_extension where extname = 'vector'")
        ).scalar()
        print(f"[extension] pgvector: {'present' if ext else 'MISSING'}")
        ok &= bool(ext)

        # tables
        rows = (
            conn.execute(
                text(
                    "select table_name from information_schema.tables "
                    "where table_schema = 'public' and table_name = any(:t)"
                ),
                {"t": EXPECTED_TABLES},
            )
            .scalars()
            .all()
        )
        missing = sorted(set(EXPECTED_TABLES) - set(rows))
        print(f"[tables] {len(rows)}/{len(EXPECTED_TABLES)} present")
        if missing:
            print("  MISSING:", ", ".join(missing))
            ok = False

        # embedding type
        coltype = conn.execute(
            text(
                "select format_type(a.atttypid, a.atttypmod) from pg_attribute a "
                "join pg_class c on c.oid = a.attrelid "
                "where c.relname = 'memories' and a.attname = 'embedding'"
            )
        ).scalar()
        print(f"[memories.embedding] {coltype}")
        ok &= coltype is not None and "vector(1024)" in str(coltype)

        # RLS enabled
        rls = conn.execute(
            text(
                "select relname, relrowsecurity from pg_class "
                "where relname = any(:t) and relkind = 'r'"
            ),
            {"t": RLS_TABLES},
        ).all()
        rls_off = [r for r, enabled in rls if not enabled]
        print(f"[rls] enabled on {len(rls) - len(rls_off)}/{len(RLS_TABLES)} tables")
        if rls_off:
            print("  RLS DISABLED:", ", ".join(rls_off))
            ok = False

        # policies
        pol = conn.execute(
            text(
                "select tablename, count(*) from pg_policies "
                "where schemaname = 'public' group by tablename"
            )
        ).all()
        print(f"[policies] {len(pol)} tables have policies")
        ok &= len(pol) >= len(RLS_TABLES)

        # bucket
        bucket = conn.execute(
            text("select id, public from storage.buckets where id = :b"),
            {"b": settings.supabase_evidence_bucket},
        ).all()
        if bucket:
            b = bucket[0]
            print(f"[storage] bucket '{b[0]}' present, public={b[1]}")
            ok &= b[1] is False
        else:
            print(f"[storage] bucket '{settings.supabase_evidence_bucket}' MISSING")
            ok = False

        # foreign keys
        fks = conn.execute(
            text(
                "select count(*) from information_schema.table_constraints "
                "where constraint_type = 'FOREIGN KEY' and table_schema = 'public'"
            )
        ).scalar()
        print(f"[foreign keys] {fks} foreign-key constraints")
        ok = ok and bool(fks) and int(fks) > 0

        # indexes
        idx = conn.execute(
            text("select count(*) from pg_indexes where schemaname = 'public'")
        ).scalar()
        print(f"[indexes] {idx} indexes in public schema")
        ok = ok and bool(idx) and int(idx) > 0

    print("\nRESULT:", "ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
