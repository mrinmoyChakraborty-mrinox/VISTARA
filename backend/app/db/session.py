"""Database session/engine management.

Works against Supabase Postgres (production) and SQLite (offline tests). The engine
is created lazily so importing the app never requires a live database.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _normalize_url(url: str) -> str:
    # Supabase/Heroku style "postgres://" -> SQLAlchemy "postgresql+psycopg2://"
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = _normalize_url(settings.effective_database_url)
        if not url:
            raise RuntimeError(
                "No database configured. Set DATABASE_URL (or LOCAL_DATABASE_URL "
                "in VISTARA_MODE=local) or run with MOCK_MODE/tests that inject a DB."
            )
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(
            url, pool_pre_ping=True, future=True, connect_args=connect_args
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False, future=True
        )
    return _SessionLocal


def reset_engine_for_tests(engine: Engine) -> None:
    """Point the module at an injected engine (used by the test suite)."""
    global _engine, _SessionLocal
    _engine = engine
    _SessionLocal = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False, future=True
    )


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def create_all(engine: Engine | None = None) -> None:
    """Create tables directly (tests / local dev). Supabase uses SQL migrations."""
    from backend.app.db.models import Base

    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)
    if eng.url.get_backend_name() == "sqlite":
        ensure_sqlite_columns(eng)


def ensure_sqlite_columns(engine: Engine) -> None:
    """Additive local migration: create_all() never alters existing tables, so
    a dev/demo DB file created before a new column (e.g. memories.is_baseline)
    would otherwise crash every query. Adds missing columns in place, keeping
    existing rows. Postgres/Supabase uses SQL migrations instead."""
    from sqlalchemy import inspect, text

    from backend.app.db.models import Base

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                coltype = col.type.compile(dialect=engine.dialect)
                server_default = getattr(col.server_default, "arg", None)
                client_default = getattr(col.default, "arg", None)
                if server_default is not None:
                    default = f" DEFAULT {server_default}"
                elif client_default is True:
                    default = " DEFAULT 1"
                elif client_default is False:
                    default = " DEFAULT 0"
                elif client_default is not None:
                    default = f" DEFAULT {client_default!r}"
                elif not col.nullable:
                    default = _fallback_default(coltype)
                else:
                    default = ""
                conn.execute(
                    text(
                        f"ALTER TABLE {table.name} ADD COLUMN {col.name} {coltype}{default}"
                    )
                )


def _fallback_default(coltype: str) -> str:
    name = coltype.upper()
    if "INT" in name:
        return " DEFAULT 0"
    if "CHAR" in name or "TEXT" in name or "UUID" in name:
        return " DEFAULT ''"
    if "FLOAT" in name or "REAL" in name or "DOUBLE" in name or "NUMERIC" in name:
        return " DEFAULT 0.0"
    if "BOOL" in name:
        return " DEFAULT 0"
    return ""
