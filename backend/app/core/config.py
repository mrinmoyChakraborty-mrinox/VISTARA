"""Typed application settings (pydantic-settings) per IMPLEMENTATION/ARCHITECTURE.

Cloud-only inference via Groq. Supabase for auth/Postgres/pgvector/Storage.

Secrets (GROQ_API_KEY, SUPABASE_SERVICE_ROLE_KEY) must never reach the frontend;
only SUPABASE_URL / SUPABASE_ANON_KEY are safe for the browser (frontend holds its
own NEXT_PUBLIC_* copies).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ app
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    # Authoritative runtime mode. LOCAL = SQLite + local evidence + local auth
    # (AI still uses real Groq providers when GROQ_API_KEY is set; LOCAL != MOCK).
    # LIVE = Supabase Auth/Postgres/pgvector/Storage with fail-fast validation.
    vistara_mode: str = Field(default="local", alias="VISTARA_MODE")
    # Comma-separated browser origins allowed to call the API + open sockets
    # in non-development environments (e.g. the deployed frontend). Empty
    # preserves the previous behavior (no browser origins in prod).
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")

    # ------------------------------------------------- local demo (VISTARA_MODE=local)
    # Persistent SQLite for the local demo (DATABASE_URL wins when set).
    local_database_url: str = Field(default="", alias="LOCAL_DATABASE_URL")
    # Local evidence directory for the local demo.
    local_evidence_dir: str = Field(
        default="./data/evidence", alias="LOCAL_EVIDENCE_DIR"
    )
    # Recorded-video demo source (./video.mp4 at repo root unless overridden).
    demo_video_path: str = Field(default="./video.mp4", alias="DEMO_VIDEO_PATH")
    # Demo playback speed multiplier (1.0 = real-time). Source timestamps are
    # preserved regardless of speed.
    video_playback_speed: float = Field(default=1.0, alias="VIDEO_PLAYBACK_SPEED")
    # Loop the recorded video at EOF (same logical camera, no duplicate baseline).
    video_loop: bool = Field(default=False, alias="VIDEO_LOOP")

    # ------------------------------------------------------------- supabase
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(
        default="", alias="SUPABASE_SERVICE_ROLE_KEY"
    )
    supabase_jwt_secret: str = Field(default="", alias="SUPABASE_JWT_SECRET")
    supabase_jwt_audience: str = Field(
        default="authenticated", alias="SUPABASE_JWT_AUDIENCE"
    )
    # Storage bucket for evidence JPEGs.
    supabase_evidence_bucket: str = Field(
        default="evidence", alias="SUPABASE_EVIDENCE_BUCKET"
    )
    # Postgres connection string (Supabase pooler or direct). Required for real DB use.
    database_url: str = Field(default="", alias="DATABASE_URL")

    # ---------------------------------------------------------------- groq
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_vlm_model: str = Field(default="qwen/qwen3.8-27b", alias="GROQ_VLM_MODEL")
    groq_chat_model: str = Field(default="openai/gpt-oss-20b", alias="GROQ_CHAT_MODEL")
    groq_vlm_fallback_model: str = Field(
        default="qwen/qwen3.8-27b", alias="GROQ_VLM_FALLBACK_MODEL"
    )
    # Verified Phase 2: qwen3.8-27b with reasoning_effort="none" fails strict JSON
    # schema validation (truncated output). "low" is minimal reasoning and validated.
    groq_vlm_reasoning_effort: str = Field(
        default="low", alias="GROQ_VLM_REASONING_EFFORT"
    )

    # ------------------------------------------------------------- gate (s5)
    frame_sample_fps: int = Field(default=2, alias="FRAME_SAMPLE_FPS")
    change_threshold: float = Field(default=0.02, alias="CHANGE_THRESHOLD")
    buffer_seconds: int = Field(default=3, alias="BUFFER_SECONDS")
    pre_event_seconds: int = Field(default=3, alias="PRE_EVENT_SECONDS")
    post_event_seconds: int = Field(default=2, alias="POST_EVENT_SECONDS")
    cooldown_seconds: int = Field(default=8, alias="COOLDOWN_SECONDS")
    persistence_frames: int = Field(default=2, alias="PERSISTENCE_FRAMES")
    use_ssim: bool = Field(default=False, alias="USE_SSIM")

    # ------------------------------------------------------- vlm payload (px)
    vlm_main_max_side: int = Field(default=1024, alias="VLM_MAIN_MAX_SIDE")
    vlm_context_max_side: int = Field(default=512, alias="VLM_CONTEXT_MAX_SIDE")
    vlm_crop_max_side: int = Field(default=768, alias="VLM_CROP_MAX_SIDE")
    vlm_jpeg_quality: int = Field(default=85, alias="VLM_JPEG_QUALITY")
    vlm_crop_padding_px: int = Field(default=24, alias="VLM_CROP_PADDING_PX")

    # --------------------------------------- initial visual baseline (per camera)
    # Warm-up: minimum frames + seconds before the baseline may finalize.
    baseline_warmup_frames: int = Field(default=5, alias="BASELINE_WARMUP_FRAMES")
    baseline_warmup_seconds: float = Field(default=3.0, alias="BASELINE_WARMUP_SECONDS")
    # Stability: gate scores below this count toward a settled streak.
    baseline_settled_threshold: float = Field(
        default=0.03, alias="BASELINE_SETTLED_THRESHOLD"
    )
    baseline_settled_frames: int = Field(default=3, alias="BASELINE_SETTLED_FRAMES")
    # Bounded fallback: never wait for perfect stability longer than this.
    baseline_max_wait_seconds: float = Field(
        default=20.0, alias="BASELINE_MAX_WAIT_SECONDS"
    )
    baseline_context_frames: int = Field(default=3, alias="BASELINE_CONTEXT_FRAMES")
    baseline_max_attempts: int = Field(default=5, alias="BASELINE_MAX_ATTEMPTS")
    baseline_retry_cooldown_seconds: float = Field(
        default=30.0, alias="BASELINE_RETRY_COOLDOWN_SECONDS"
    )

    # --------------------------------------------------------------- misc
    # Force offline/mock providers (no Groq, no Supabase). Used by tests.
    mock_mode: bool = Field(default=False, alias="MOCK_MODE")
    groq_timeout_seconds: float = Field(default=60.0, alias="GROQ_TIMEOUT_SECONDS")

    # ------------------------------------------------- camera connectivity
    # WebSocket frame ingestion hardening.
    ws_max_frame_bytes: int = Field(default=5 * 1024 * 1024, alias="WS_MAX_FRAME_BYTES")
    ws_max_image_dim: int = Field(default=4096, alias="WS_MAX_IMAGE_DIM")
    # Max frames/sec accepted per camera before the ingest layer drops excess
    # (preview may be faster; AI processing stays gate-driven).
    ingest_max_fps: float = Field(default=5.0, alias="INGEST_MAX_FPS")
    # Bounded per-camera event queue (drop-oldest when full).
    event_queue_maxsize: int = Field(default=4, alias="EVENT_QUEUE_MAXSIZE")
    # Phone QR pairing sessions.
    pairing_ttl_seconds: float = Field(default=600.0, alias="PAIRING_TTL_SECONDS")
    # SSRF policy: allow private/loopback stream hosts (self-hosted LAN cameras).
    cameras_allow_private_networks: bool = Field(
        default=False, alias="CAMERAS_ALLOW_PRIVATE_NETWORKS"
    )

    # Feature flags surfaced by /api/health.
    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)

    @property
    def database_configured(self) -> bool:
        return bool(self.effective_database_url)

    @property
    def is_local(self) -> bool:
        return self.vistara_mode.strip().lower() == "local"

    @property
    def is_live(self) -> bool:
        return self.vistara_mode.strip().lower() == "live"

    @property
    def effective_database_url(self) -> str:
        """DATABASE_URL wins; then LOCAL_DATABASE_URL; then the local default
        file (local mode only). Live mode never silently falls back to SQLite."""
        if self.database_url:
            return self.database_url
        if self.local_database_url:
            return self.local_database_url
        if self.is_local:
            return "sqlite:///./data/vistara.db"
        return ""

    def validate_mode(self) -> None:
        """Fail fast on unknown modes and under-configured live mode."""
        mode = self.vistara_mode.strip().lower()
        if mode not in ("local", "live"):
            raise RuntimeError(
                f"VISTARA_MODE={self.vistara_mode!r} is invalid (expected 'local' or 'live')."
            )
        if mode == "live":
            missing = [
                name
                for name, value in (
                    ("SUPABASE_URL", self.supabase_url),
                    ("SUPABASE_ANON_KEY", self.supabase_anon_key),
                    ("SUPABASE_JWT_SECRET", self.supabase_jwt_secret),
                    ("DATABASE_URL", self.database_url),
                )
                if not value
            ]
            if missing:
                raise RuntimeError(
                    "VISTARA_MODE=live requires " + ", ".join(missing) + "."
                )
            if self.effective_database_url.startswith("sqlite"):
                raise RuntimeError("VISTARA_MODE=live refuses SQLite DATABASE_URL.")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
