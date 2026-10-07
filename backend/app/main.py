"""Visual Memory — FastAPI application entrypoint.

Run:
    uvicorn backend.app.main:app --reload --port 8000
    # or: make run
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import (
    cameras,
    chat,
    discovery,
    events,
    evidence,
    gateway,
    health,
    memories,
    objects,
    pairing,
    ws,
)
from backend.app.core.config import settings
from backend.app.core.logging import configure_logging, log_event

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Local SQLite (dev/mock/test): create tables automatically.
    # Supabase/Postgres uses SQL migrations (supabase/migrations/0001_init.sql).
    if settings.database_url.startswith("sqlite"):
        try:
            from backend.app.db.session import create_all, get_engine

            create_all(get_engine())
        except Exception as exc:  # noqa: BLE001
            log_event("db_init_failed", status="error", message=str(exc))
    # Deploy-time misconfiguration should scream in the logs, not fail
    # silently in the browser: without CORS_ORIGINS no browser origin can
    # reach the API when APP_ENV is not development.
    if settings.app_env != "development" and not _prod_origins():
        log_event(
            "cors_no_origins",
            status="error",
            message="APP_ENV=%s but CORS_ORIGINS is empty: browsers will be blocked."
            % settings.app_env,
        )
    if not settings.supabase_url or not settings.database_url:
        log_event(
            "supabase_not_configured",
            status="error",
            message="SUPABASE_URL/DATABASE_URL missing: running on local fallback (no real Auth/DB).",
        )
    yield


def _prod_origins() -> list[str]:
    return [o.strip() for o in settings.cors_origins.split(",") if o.strip()]


app = FastAPI(
    title="Visual Memory API",
    version="0.1.0",
    lifespan=lifespan,
    description=(
        "Backend for Visual Memory. Open-weight AI via Groq: "
        "VLM qwen/qwen3.8-27b, chat openai/gpt-oss-20b. "
        "Auth + Postgres + pgvector + Storage via Supabase. "
        "Embeddings are generated client-side (Qwen3-Embedding-0.6B)."
    ),
)

# The frontend is a separate app (teammate-owned). Development allows all
# origins; otherwise only the origins listed in CORS_ORIGINS are allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else _prod_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(cameras.router)
app.include_router(memories.router)
app.include_router(objects.router)
app.include_router(events.router)
app.include_router(evidence.router)
app.include_router(chat.router)
app.include_router(pairing.router)
app.include_router(gateway.router)
app.include_router(discovery.router)
app.include_router(ws.router)


@app.get("/")
def root() -> dict:
    return {
        "name": "Visual Memory API",
        "docs": "/docs",
        "health": "/api/health",
        "ws": "/ws/cameras/{camera_id}",
    }
