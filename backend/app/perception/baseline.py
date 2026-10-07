"""Initial visual baseline: pixel warm-up + semantic baseline, once per logical camera.

Two baselines are established together when a camera first becomes live:

PIXEL BASELINE — the OpenCV gate's rolling history. The gate needs a first
  frame plus a filled rolling buffer before its change scores are meaningful.
  (Existing gate machinery; this module only observes its scores.)

SEMANTIC BASELINE — the first Qwen observation, persisted as a memory with
  is_baseline=True. It becomes the initial known state for scene-state delta,
  so later observations derive OBJECT_MOVED/APPEARED/DISAPPEARED against a
  real "before" instead of an empty state.

Only after BOTH exist is the camera marked ready and normal change detection
(enqueueing gate-fired contexts, emitting change events) enabled.

Reconnect safety: baseline state lives on the camera runtime (survives WS
reconnects) and is re-adopted from persisted memories (survives restarts), so
a browser refresh never creates a second "initial scene".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.app.perception.buffer import RollingBuffer


class BaselineStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


@dataclass
class BaselineConfig:
    """All knobs configurable; tests shrink them, production keeps them patient."""

    warmup_min_frames: int = 5
    warmup_min_seconds: float = 3.0
    # A frame counts as "settled" when its gate score is below this.
    settled_threshold: float = 0.03
    settled_frames: int = 3
    # Bounded fallback: never wait for perfect stability longer than this.
    max_wait_seconds: float = 20.0
    # Baseline payload keeps main + context frames; no change crop (nothing to crop yet).
    context_frames: int = 3
    max_attempts: int = 5
    retry_cooldown_seconds: float = 30.0
    # After FAILED, retries continue with a longer cooldown (ingestion never stops).
    failed_retry_multiplier: float = 3.0


@dataclass
class BaselineTracker:
    """Per-logical-camera baseline state. Fed one gate score per ingested frame."""

    config: BaselineConfig = field(default_factory=BaselineConfig)
    status: BaselineStatus = BaselineStatus.PENDING
    frames_seen: int = 0
    first_frame_at: float | None = None
    settled_streak: int = 0
    attempts: int = 0
    last_attempt_at: float | None = None
    last_error: str = ""
    ready_memory_id: str | None = None
    baseline_inflight: bool = False

    # ------------------------------------------------------------- observation
    def note_frame(self, score: float, now: float) -> None:
        if self.status is BaselineStatus.READY:
            return
        if self.first_frame_at is None:
            self.first_frame_at = now
        self.frames_seen += 1
        if score < self.config.settled_threshold:
            self.settled_streak += 1
        else:
            self.settled_streak = 0

    def elapsed(self, now: float) -> float:
        if self.first_frame_at is None:
            return 0.0
        return max(0.0, now - self.first_frame_at)

    def _stable_enough(self, now: float) -> bool:
        cfg = self.config
        return (
            self.frames_seen >= cfg.warmup_min_frames
            and self.elapsed(now) >= cfg.warmup_min_seconds
            and self.settled_streak >= cfg.settled_frames
        )

    def _wait_expired(self, now: float) -> bool:
        return (
            self.frames_seen >= max(1, self.config.warmup_min_frames)
            and self.elapsed(now) >= self.config.max_wait_seconds
        )

    def _retry_allowed(self, now: float) -> bool:
        if self.last_attempt_at is None:
            return True
        cooldown = self.config.retry_cooldown_seconds
        if self.status is BaselineStatus.FAILED:
            cooldown *= self.config.failed_retry_multiplier
        return (now - self.last_attempt_at) >= cooldown

    # --------------------------------------------------------------- decisions
    def should_finalize(self, now: float) -> bool:
        """True when a baseline VLM call should be issued (exactly once per attempt)."""
        if self.status is BaselineStatus.READY or self.baseline_inflight:
            return False
        if (
            self.attempts >= self.config.max_attempts
            and self.status is BaselineStatus.PENDING
        ):
            self.status = BaselineStatus.FAILED
        if not self._retry_allowed(now):
            return False
        return self._stable_enough(now) or self._wait_expired(now)

    def mark_attempt_started(self, now: float) -> None:
        self.attempts += 1
        self.last_attempt_at = now
        self.baseline_inflight = True

    def mark_ready(self, memory_id: str) -> None:
        self.status = BaselineStatus.READY
        self.ready_memory_id = memory_id
        self.baseline_inflight = False
        self.last_error = ""

    def mark_attempt_failed(self, error: str, now: float) -> None:
        self.baseline_inflight = False
        self.last_error = error[:300]
        if self.attempts >= self.config.max_attempts:
            self.status = BaselineStatus.FAILED
        # Otherwise stays PENDING: ingestion continues, retry after cooldown.

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "frames_seen": self.frames_seen,
            "settled_streak": self.settled_streak,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "ready_memory_id": self.ready_memory_id,
        }


def baseline_config_from_settings() -> BaselineConfig:
    """Build the tracker config from environment (production knobs)."""
    from backend.app.core.config import settings

    return BaselineConfig(
        warmup_min_frames=settings.baseline_warmup_frames,
        warmup_min_seconds=settings.baseline_warmup_seconds,
        settled_threshold=settings.baseline_settled_threshold,
        settled_frames=settings.baseline_settled_frames,
        max_wait_seconds=settings.baseline_max_wait_seconds,
        context_frames=settings.baseline_context_frames,
        max_attempts=settings.baseline_max_attempts,
        retry_cooldown_seconds=settings.baseline_retry_cooldown_seconds,
    )


def build_baseline_context(
    buffer: RollingBuffer, user_id: str, camera_id: str, count: int | None = None
):
    """Assemble the baseline payload: main + context frames, no change crop."""
    from datetime import datetime, timezone

    from backend.app.core.config import settings
    from backend.app.perception.image_utils import prepare_frame_jpeg
    from backend.app.perception.pipeline import EventContext

    want: int = count if isinstance(count, int) else settings.baseline_context_frames
    frames = buffer.snapshot()
    if not frames:
        return None
    representative = RollingBuffer.select_representative(frames, count=max(1, want))
    current = representative[-1]
    earlier = representative[:-1] or [current]
    main_jpeg, _, _ = prepare_frame_jpeg(
        current.frame, settings.vlm_main_max_side, settings.vlm_jpeg_quality
    )
    context_jpegs = []
    for bf in earlier:
        jpeg, _, _ = prepare_frame_jpeg(
            bf.frame, settings.vlm_context_max_side, settings.vlm_jpeg_quality
        )
        context_jpegs.append(jpeg)
    return EventContext(
        camera_id=camera_id,
        user_id=user_id,
        timestamp=datetime.now(timezone.utc),
        main_jpeg=main_jpeg,
        context_jpegs=context_jpegs,
        crop_jpeg=None,
        score=0.0,
        is_baseline=True,
    )


def post_ingest(runtime, user_id: str, now: float, score: float) -> dict:
    """Single decision point shared by WS / gateway / pull ingestion paths.

    Feeds the baseline tracker and reports what the caller should do:
      {"emit_change": bool, "baseline_ctx": EventContext | None}
    Before the baseline is ready, normal change emission stays disabled.
    """
    tracker: BaselineTracker = runtime.baseline
    if tracker.status is BaselineStatus.READY:
        return {"emit_change": True, "baseline_ctx": None}
    tracker.note_frame(score, now)
    if tracker.should_finalize(now):
        ctx = build_baseline_context(
            runtime.buffer,
            user_id,
            runtime.source.metadata.id,
            count=tracker.config.context_frames,
        )
        if ctx is None:
            return {"emit_change": False, "baseline_ctx": None}
        tracker.mark_attempt_started(now)
        from backend.app.core.logging import log_event

        log_event(
            "baseline_started",
            status="ok",
            user_id=user_id,
            camera_id=runtime.source.metadata.id,
        )
        return {"emit_change": False, "baseline_ctx": ctx}
    return {"emit_change": False, "baseline_ctx": None}


def adopt_prior_state(runtime, user_id: str, camera_id: str) -> bool:
    """Adopt persisted memories as the baseline (reconnects + restarts).

    Idempotent: returns immediately when already ready. Returns True when the
    camera is ready (adopted or already), False when a fresh baseline is needed.
    Never creates a memory; never duplicates an initial baseline.
    """
    from backend.app.db.session import session_scope
    from backend.app.memory.service import MemoryService

    tracker: BaselineTracker = runtime.baseline
    if tracker.status is BaselineStatus.READY:
        return True
    try:
        with session_scope() as db:
            latest = MemoryService(db).memories.latest(user_id, camera_id)
            if latest is None:
                return False
            memory_id = str(latest.id)
    except Exception:
        return False
    tracker.mark_ready(memory_id)
    return True
