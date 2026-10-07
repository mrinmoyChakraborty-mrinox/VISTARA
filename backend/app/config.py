"""Visual Memory backend configuration.

Cloud-only inference (this prompt wins over docs):
  - VLM:          VLM_MODEL (default qwen/qwen3-vl-32b)
  - VLM fallback: VLM_FALLBACK_MODEL (default qwen/qwen3-vl-32b)
  - Chat:         LLM_MODEL (default openai/gpt-oss-20b)
All through one GROQ_API_KEY. No local models, no GPU dependency.

Gate/storage settings come from IMPLEMENTATION.md section 5.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _getenv(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _getfloat(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


def _getint(key: str, default: int) -> int:
    try:
        return int(float(os.getenv(key, str(default))))
    except ValueError:
        return default


def _getbool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: _getenv("APP_ENV", "development"))

    # Inference (Groq cloud only)
    groq_api_key: str = field(default_factory=lambda: _getenv("GROQ_API_KEY", ""))
    vlm_model: str = field(
        default_factory=lambda: _getenv("VLM_MODEL", "qwen/qwen3-vl-32b")
    )
    vlm_fallback_model: str = field(
        default_factory=lambda: _getenv("VLM_FALLBACK_MODEL", "qwen/qwen3-vl-32b")
    )
    llm_model: str = field(
        default_factory=lambda: _getenv("LLM_MODEL", "openai/gpt-oss-20b")
    )

    # Auth (Stage 2: seeded demo user + static token header)
    demo_auth_token: str = field(
        default_factory=lambda: _getenv("DEMO_AUTH_TOKEN", "demo-token-change-me")
    )

    # Storage
    database_url: str = field(
        default_factory=lambda: _getenv("DATABASE_URL", "sqlite:///./data/app.db")
    )
    evidence_dir: Path = field(
        default_factory=lambda: Path(_getenv("EVIDENCE_DIR", "./data/evidence"))
    )

    # Perception gate (IMPLEMENTATION.md s5 starting points)
    frame_sample_fps: int = field(
        default_factory=lambda: _getint("FRAME_SAMPLE_FPS", 3)
    )
    change_threshold: float = field(
        default_factory=lambda: _getfloat("CHANGE_THRESHOLD", 0.12)
    )
    event_cooldown_seconds: int = field(
        default_factory=lambda: _getint("EVENT_COOLDOWN_SECONDS", 8)
    )
    pre_event_seconds: int = field(
        default_factory=lambda: _getint("PRE_EVENT_SECONDS", 3)
    )
    post_event_seconds: int = field(
        default_factory=lambda: _getint("POST_EVENT_SECONDS", 1)
    )

    mock_mode: bool = field(default_factory=lambda: _getbool("MOCK_MODE", False))


settings = Settings()
