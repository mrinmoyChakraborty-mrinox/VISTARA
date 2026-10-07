"""Recorded-video camera source for the local demo (VISTARA_MODE=local).

A recorded file behaves like a live camera: paced reads preserve source-time
semantics, frames flow through the SAME pipeline (NormalizedFrame -> bounded
queue -> OpenCV gate -> rolling buffer -> baseline -> multi-frame Qwen), and
EOF is an explicit STOPPED state, never a crash or an infinite reconnect loop.

No second pipeline: this subclasses PullCameraSource and reuses
manager.start_source's bridge, so perception/memory/evidence code is shared
with live cameras.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.app.cameras.frames import NormalizedFrame, make_normalized_frame
from backend.app.cameras.pull import PullCameraSource
from backend.app.core.config import settings
from backend.app.core.logging import log_event

ALLOWED_VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}


def resolve_video_path(raw: str | None) -> Path:
    """Resolve the configured video path. Raises ValueError with a clear reason."""
    candidate = (raw or "").strip() or settings.demo_video_path
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.exists():
        raise ValueError(f"demo video not found: {path}")
    if not path.is_file():
        raise ValueError(f"demo video is not a file: {path}")
    if path.suffix.lower() not in ALLOWED_VIDEO_SUFFIXES:
        raise ValueError(
            f"unsupported demo video format {path.suffix!r} "
            f"(allowed: {sorted(ALLOWED_VIDEO_SUFFIXES)})"
        )
    return path


def video_metadata(path: Path) -> dict[str, Any]:
    """Open the file read-only and report fps/size/count. Raises ValueError."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise ValueError(f"cv2 cannot open demo video: {path}")
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    finally:
        cap.release()
    if fps <= 0 or width <= 0 or height <= 0:
        raise ValueError(f"demo video has no readable stream: {path}")
    return {
        "path": str(path),
        "fps": fps,
        "width": width,
        "height": height,
        "frames": count,
    }


class VideoFileCameraSource(PullCameraSource):
    """Sequential recorded-video reader with source-time semantics."""

    source_kind = "video_file"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cfg = self.metadata.config or {}
        self._path = resolve_video_path(cfg.get("path"))
        try:
            self._speed = float(
                cfg.get("playback_speed", settings.video_playback_speed)
            )
        except (TypeError, ValueError):
            self._speed = 1.0
        if self._speed <= 0:
            self._speed = 1.0
        loop_cfg = cfg.get("loop", settings.video_loop)
        self._loop = (
            bool(loop_cfg)
            if isinstance(loop_cfg, bool)
            else str(loop_cfg).lower() in ("1", "true", "yes")
        )
        self.sample_fps = float(settings.frame_sample_fps or 2)
        self._cap = None
        self._meta: dict[str, Any] = {}
        self._start_wall = 0.0
        self._last_read_mono = 0.0
        self.eof_reached = False
        self.capabilities.notes = f"recorded video {self._path.name}"

    # ------------------------------------------------------- transport hooks
    def open_transport(self) -> None:
        import cv2

        self._meta = video_metadata(self._path)
        self._cap = cv2.VideoCapture(str(self._path))
        if not self._cap.isOpened():
            self._cap = None
            raise ValueError(f"cv2 cannot open demo video: {self._path}")
        self._start_wall = time.time()
        self._last_read_mono = 0.0
        self.eof_reached = False
        meta = self._meta
        self.capabilities.max_width = meta["width"]
        self.capabilities.max_height = meta["height"]
        log_event(
            "demo_video_started",
            status="ok",
            user_id=self.metadata.user_id,
            camera_id=self.metadata.id,
            extra={
                "path": str(self._path),
                "fps": round(meta["fps"], 2),
                "frames": meta["frames"],
                "speed": self._speed,
                "loop": self._loop,
            },
        )

    def close_transport(self) -> None:
        cap, self._cap = self._cap, None
        if cap is not None:
            try:
                cap.release()
            except Exception:  # noqa: BLE001 - close must not raise
                pass

    def _do_close(self) -> None:
        super()._do_close()
        self.close_transport()
        log_event(
            "demo_video_stopped",
            status="closed",
            user_id=self.metadata.user_id,
            camera_id=self.metadata.id,
        )

    def _do_connect(self) -> None:
        # Validate eagerly so POST /start fails with a clear 4xx/5xx instead of
        # a silent FAILED runtime.
        video_metadata(self._path)
        super()._do_connect()

    # ----------------------------------------------------------------- read
    def read_frame(self) -> NormalizedFrame | None:
        """Return the next paced frame, or None at EOF (loop rewinds instead)."""
        cap = self._cap
        if cap is None:
            return None
        interval = 1.0 / max(self.sample_fps * self._speed, 0.1)
        now = time.monotonic()
        if self._last_read_mono:
            wait = interval - (now - self._last_read_mono)
            if wait > 0:
                time.sleep(wait)
        ok, bgr = cap.read()
        self._last_read_mono = time.monotonic()
        if not ok or bgr is None:
            if self._loop:
                cap.set(0, 0)  # CAP_PROP_POS_FRAMES
                self._last_read_mono = 0.0
                log_event(
                    "demo_video_loop",
                    status="ok",
                    user_id=self.metadata.user_id,
                    camera_id=self.metadata.id,
                )
                return None
            self.eof_reached = True
            return None
        media_pos = 0.0
        try:
            import cv2

            media_pos = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
        except Exception:  # noqa: BLE001
            media_pos = 0.0
        source_ts = datetime.fromtimestamp(
            self._start_wall + media_pos, tz=timezone.utc
        )
        return make_normalized_frame(
            self.metadata.id,
            bgr,
            source_ts=source_ts,
            source_metadata={
                "kind": self.source_kind,
                "path": str(self._path),
                "media_pos": round(media_pos, 3),
            },
        )

    async def _reconnect_pause(self) -> None:
        # EOF is explicit completion, not a transport failure: stop cleanly
        # instead of backing off and reopening forever.
        if self.eof_reached and not self._loop:
            self._running = False
            self.note_error("eof: video completed")
            log_event(
                "demo_video_eof",
                status="completed",
                user_id=self.metadata.user_id,
                camera_id=self.metadata.id,
            )
            try:
                from backend.app.cameras.base import CameraLifecycle

                if self.lifecycle == CameraLifecycle.RUNNING:
                    self.transition(CameraLifecycle.STOPPING)
                    self.transition(CameraLifecycle.STOPPED)
            except Exception:  # noqa: BLE001
                pass
            self.close_transport()
            return
        await super()._reconnect_pause()
