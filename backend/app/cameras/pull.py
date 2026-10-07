"""Pull-source runner: polling loop with reconnect backoff, stale detection, sampling.

One asyncio task per source. A source failure never touches other cameras:
the loop degrades, backs off, and recovers or fails that source only.
"""

from __future__ import annotations

import asyncio
import time
from typing import Callable

from backend.app.cameras.base import CameraLifecycle, CameraSource
from backend.app.cameras.frames import NormalizedFrame, make_normalized_frame
from backend.app.cameras.reconnect import BackoffPolicy


class PullCameraSource(CameraSource):
    """Base for RTSP/HLS/MJPEG: override read_frame(); the runner handles the rest."""

    stale_after_seconds: float = 15.0
    sample_fps: float = 2.0

    def __init__(self, *args, backoff: BackoffPolicy | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._backoff = backoff or BackoffPolicy()
        self._run_task: asyncio.Task | None = None
        self._running = False
        self._last_emit = 0.0
        self._seq = 0
        self.on_frame: Callable[[NormalizedFrame], None] | None = None

    # ------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self.lifecycle not in (CameraLifecycle.CONNECTED,):
            raise RuntimeError(
                f"connect() before start() (state={self.lifecycle.value})"
            )
        self.transition(CameraLifecycle.RUNNING)
        self._running = True
        self._run_task = asyncio.create_task(self._run_loop())

    def stop(self) -> None:
        self._running = False
        if self.lifecycle not in (CameraLifecycle.STOPPED, CameraLifecycle.STOPPING):
            try:
                self.transition(CameraLifecycle.STOPPING)
                self.transition(CameraLifecycle.STOPPED)
            except Exception:  # noqa: BLE001
                pass
        self.close()

    def _do_close(self) -> None:
        task, self._run_task = self._run_task, None
        if task and not task.done():
            task.cancel()

    # ---------------------------------------------------------------- loop
    async def _run_loop(self) -> None:
        try:
            while self._running:
                try:
                    frame = await asyncio.to_thread(self.read_frame)
                except Exception as exc:  # noqa: BLE001 - per-camera isolation
                    self.note_error(f"read failed: {exc}")
                    await self._reconnect_pause()
                    continue
                if frame is None:
                    await self._reconnect_pause()
                    continue
                self._backoff.reset()
                self._emit(frame)
                self._check_stale()
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001 - never kill the loop host
            self.note_error(f"loop crashed: {exc}")

    def _emit(self, frame: NormalizedFrame) -> None:
        now = time.monotonic()
        min_interval = 1.0 / max(self.sample_fps, 0.1)
        if now - self._last_emit < min_interval:
            self.note_dropped()
            return
        self._last_emit = now
        self._seq += 1
        frame.seq = self._seq
        self.note_frame()
        if self.lifecycle == CameraLifecycle.DEGRADED:
            try:
                self.transition(CameraLifecycle.RUNNING)
            except Exception:  # noqa: BLE001
                pass
        if self.on_frame is not None:
            try:
                self.on_frame(frame)
            except Exception as exc:  # noqa: BLE001
                self.note_error(f"frame handler failed: {exc}")

    async def _reconnect_pause(self) -> None:
        self.note_error("no frame (timeout/corrupt/exit)")
        try:
            if self.lifecycle == CameraLifecycle.RUNNING:
                self.transition(CameraLifecycle.DEGRADED)
        except Exception:  # noqa: BLE001
            pass
        self.metrics.reconnect_count += 1
        delay = self._backoff.next_delay()
        try:
            self.close_transport()
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(delay)
        try:
            self.open_transport()
            self._backoff.reset()
        except Exception as exc:  # noqa: BLE001
            self.note_error(f"reopen failed: {exc}")

    def _check_stale(self) -> None:
        last = self.metrics.last_successful_read_at
        if last is None:
            return
        import datetime

        age = (datetime.datetime.now(datetime.timezone.utc) - last).total_seconds()
        if age > self.stale_after_seconds and self.lifecycle == CameraLifecycle.RUNNING:
            try:
                self.transition(CameraLifecycle.DEGRADED)
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------- transport hooks
    def open_transport(self) -> None:
        return None

    def close_transport(self) -> None:
        return None

    def push_bgr(
        self,
        bgr,
        source_metadata: dict | None = None,
    ) -> None:
        """Adapter helper: wrap a decoded BGR array and emit through sampling."""
        from backend.app.cameras.frames import (
            FrameValidationError,
            validate_frame_array,
        )

        try:
            w, h = validate_frame_array(bgr)
        except FrameValidationError as exc:
            self.note_error(f"invalid frame: {exc}")
            self.note_dropped()
            return
        self._emit(
            make_normalized_frame(
                self.metadata.id,
                bgr,
                source_metadata=source_metadata or {"kind": self.source_kind},
            )
        )
