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
        url = _normalize_url(settings.database_url)
        if not url:
            raise RuntimeError(
                "DATABASE_URL is not configured. Set it in .env (Supabase Postgres "
                "connection string) or run with MOCK_MODE/tests that inject a DB."
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

    Base.metadata.create_all(bind=engine or get_engine())
