"""GET /api/health — basic, secret-free status."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.core.config import settings

router = APIRouter(tags=["health"])


def _db_backend() -> str:
    url = settings.database_url
    if not url:
        return "unset"
    if url.startswith("sqlite"):
        return "sqlite-local"
    if "supabase" in url or url.startswith(("postgresql", "postgres")):
        return "supabase-postgres"
    return "postgres"


@router.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "backend": True,
        "environment": settings.app_env,
        "database": {
            "configured": settings.database_configured,
            "backend": _db_backend(),
        },
        "groq": {
            "configured": settings.groq_configured,
            "vlm_model": settings.groq_vlm_model,
            "chat_model": settings.groq_chat_model,
        },
        "vision": {"provider": "mock" if settings.mock_mode else "groq-qwen3.8-27b"},
        "chat": {"provider": "mock" if settings.mock_mode else "groq-gpt-oss-20b"},
        "supabase": {"configured": settings.supabase_configured},
        "websocket": {"available": True, "path": "/ws/cameras/{camera_id}"},
        "mock_mode": settings.mock_mode,
    }
