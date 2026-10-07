"""GET /api/health — basic, secret-free status."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "backend": True,
        "environment": settings.app_env,
        "database": {
            "configured": settings.database_configured,
            "backend": "supabase-postgres" if settings.database_configured else "unset",
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
