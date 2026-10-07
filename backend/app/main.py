"""Visual Memory backend — Stage 0 skeleton.

One-command start (see Makefile / README):
    make run
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.app.config import settings

app = FastAPI(title="Visual Memory", version="0.0.0")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "stage": 0,
        "mock_mode": settings.mock_mode,
        "vlm_model": settings.vlm_model,
        "llm_model": settings.llm_model,
    }
