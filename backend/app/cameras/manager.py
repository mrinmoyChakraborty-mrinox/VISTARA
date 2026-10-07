"""CameraManager: multi-camera registry with lifecycle, supervision, and health.

- One process, one registry. Each camera has an independent lifecycle, a bounded
  event queue (drop-oldest + counter), and an isolated worker task: one broken
  camera can never terminate the others.
- Frame queues are BOUNDED. When overloaded, the oldest intermediate contexts
  are dropped (newest kept) and counted; the OpenCV gate still decides VLM calls,
  so more frames never means more inference.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from backend.app.cameras.base import CameraLifecycle, CameraSource
from backend.app.cameras.factory import create_source
from backend.app.core.logging import log_event
from backend.app.perception.baseline import (
    BaselineConfig,
    BaselineTracker,
    baseline_config_from_settings,
)
from backend.app.perception.buffer import RollingBuffer
from backend.app.perception.gate import GateConfig, PerceptionGate


@dataclass
class CameraRuntime:
    source: CameraSource
    buffer: RollingBuffer
    gate: PerceptionGate
    event_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=4))
    task: asyncio.Task | None = None
    worker_task: asyncio.Task | None = None
    listeners: list[asyncio.Queue] = field(default_factory=list)
    frames_ingested: int = 0
    frames_dropped_queue: int = 0
    last_error: str = ""
    # Initial visual baseline state (pixel warm-up + semantic baseline).
    # Lives on the logical camera runtime: survives WS reconnects; re-adopted
    # from persisted memories after restarts. Exactly one baseline per camera.
    baseline: BaselineTracker = field(default_factory=BaselineTracker)


class CameraManager:
    def __init__(self):
        self._runtimes: dict[str, CameraRuntime] = {}
        self._lock = asyncio.Lock()

    async def add(
        self,
        camera_id: str,
        user_id: str,
        name: str,
        source_type: str,
        config: dict | None,
        buffer_maxlen: int = 60,
        gate_config: GateConfig | None = None,
        event_queue_maxsize: int = 4,
        allow_private_networks: bool | None = None,
        baseline_config: BaselineConfig | None = None,
    ) -> CameraRuntime:
        from backend.app.core.config import settings as _settings

        async with self._lock:
            existing = self._runtimes.get(camera_id)
            if existing is not None:
                return existing
            source = create_source(camera_id, user_id, name, source_type, config)
            # Deployment SSRF policy is server-side, never camera config (untrusted).
            if allow_private_networks is None:
                allow_private_networks = _settings.cameras_allow_private_networks
            if hasattr(source, "_allow_private"):
                source._allow_private = allow_private_networks
            runtime = CameraRuntime(
                source=source,
                buffer=RollingBuffer(maxlen=buffer_maxlen),
                gate=PerceptionGate(gate_config),
                event_queue=asyncio.Queue(maxsize=event_queue_maxsize),
                baseline=BaselineTracker(
                    config=baseline_config or baseline_config_from_settings()
                ),
            )
            self._runtimes[camera_id] = runtime
            log_event(
                "camera_connect_started",
                status="ok",
                user_id=user_id,
                camera_id=camera_id,
            )
            return runtime

    def get(self, camera_id: str) -> CameraRuntime | None:
        return self._runtimes.get(camera_id)

    def require_owned(self, camera_id: str, user_id: str) -> CameraRuntime | None:
        runtime = self._runtimes.get(camera_id)
        if runtime is None or runtime.source.metadata.user_id != user_id:
            return None
        return runtime

    async def remove(self, camera_id: str) -> None:
        async with self._lock:
            runtime = self._runtimes.pop(camera_id, None)
        if runtime is not None:
            await self._shutdown_runtime(runtime)

    @staticmethod
    async def _shutdown_runtime(runtime: CameraRuntime) -> None:
        try:
            runtime.source.stop()
        except Exception:  # noqa: BLE001
            pass
        runtime.source.close()
        for attr in ("task", "worker_task"):
            task = getattr(runtime, attr)
            setattr(runtime, attr, None)
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        runtime.listeners.clear()
        # Drain so a removed camera releases queued contexts.
        while True:
            try:
                runtime.event_queue.get_nowait()
                runtime.event_queue.task_done()
            except asyncio.QueueEmpty:
                break

    def all(self) -> list[CameraRuntime]:
        return list(self._runtimes.values())

    def reset_for_tests(self) -> None:
        """Cancel all tasks and drop all runtimes. Test-only; not for production use."""
        for runtime in list(self._runtimes.values()):
            for attr in ("task", "worker_task"):
                task = getattr(runtime, attr, None)
                setattr(runtime, attr, None)
                if task is not None:
                    try:
                        task.cancel()
                    except Exception:  # noqa: BLE001
                        pass
            try:
                runtime.source.close()
            except Exception:  # noqa: BLE001
                pass
            runtime.listeners.clear()
        self._runtimes.clear()

    # ------------------------------------------------- pull-source driving
    async def start_source(self, runtime: CameraRuntime) -> None:
        """Connect (blocking bits in a thread) + attach pipeline bridge + start loop.

        Only meaningful for pull sources (RTSP/HLS/MJPEG); push sources are driven
        by their WebSocket and ignore this.
        """
        from backend.app.cameras.pull import PullCameraSource

        source = runtime.source
        if not isinstance(source, PullCameraSource):
            return
        user_id = source.metadata.user_id

        def _bridge(nframe) -> None:
            import time as _time

            from backend.app.api.ingest import ingest_pull_frame
            from backend.app.perception.baseline import (
                BaselineStatus,
                post_ingest,
            )

            baseline_ready = runtime.baseline.status is BaselineStatus.READY
            result = ingest_pull_frame(runtime, nframe, user_id, offer=baseline_ready)
            if not result.get("ok"):
                return
            action = post_ingest(runtime, user_id, _time.monotonic(), result["score"])
            if action["baseline_ctx"] is not None:
                self.offer_event(runtime, action["baseline_ctx"])

        source.on_frame = _bridge
        try:
            await asyncio.to_thread(source.connect)
        except Exception as exc:
            log_event(
                "camera_reconnect_failed",
                status="error",
                user_id=user_id,
                camera_id=source.metadata.id,
                message=str(exc)[:200],
            )
            raise
        # Restarts adopt persisted memories instead of re-baselining.
        from backend.app.perception.baseline import adopt_prior_state as _adopt

        _adopt(runtime, user_id, source.metadata.id)
        source.start()
        log_event(
            "camera_connected",
            status="ok",
            user_id=user_id,
            camera_id=source.metadata.id,
        )

    async def stop_source(self, runtime: CameraRuntime) -> None:
        source = runtime.source
        try:
            source.stop()
        except Exception:  # noqa: BLE001
            pass
        task = getattr(source, "_run_task", None)
        if task is not None and not task.done():
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception:  # noqa: BLE001
                pass
        source.close()

    # ------------------------------------------------------- event queue I/O
    @staticmethod
    def offer_event(runtime: CameraRuntime, ctx) -> bool:
        """Bounded put: drop oldest when full, keep newest. Returns True if queued."""
        try:
            runtime.event_queue.put_nowait(ctx)
            return True
        except asyncio.QueueFull:
            try:
                runtime.event_queue.get_nowait()
                runtime.event_queue.task_done()
            except asyncio.QueueEmpty:
                pass
            runtime.frames_dropped_queue += 1
            runtime.source.note_dropped()
            try:
                runtime.event_queue.put_nowait(ctx)
                return True
            except asyncio.QueueFull:
                return False

    # ---------------------------------------------------------------- health
    def health(self, camera_id: str) -> dict[str, Any] | None:
        runtime = self._runtimes.get(camera_id)
        if runtime is None:
            return None
        source = runtime.source
        return {
            "camera_id": camera_id,
            "lifecycle": source.lifecycle.value,
            "connected": source.health().connected,
            "source_type": source.metadata.source_type,
            "last_frame_at": _iso(source.metrics.last_frame_at),
            "last_successful_read_at": _iso(source.metrics.last_successful_read_at),
            "frames_received": source.metrics.frames_received,
            "frames_dropped": source.metrics.frames_dropped,
            "frames_dropped_queue": runtime.frames_dropped_queue,
            "frames_ingested": runtime.frames_ingested,
            "reconnect_count": source.metrics.reconnect_count,
            "last_error": source.metrics.last_error,
            "queue_depth": runtime.event_queue.qsize(),
            "stale": self.is_stale(camera_id),
            "baseline_status": runtime.baseline.status.value,
            "baseline_memory_id": runtime.baseline.ready_memory_id,
            "baseline_attempts": runtime.baseline.attempts,
        }

    def is_stale(self, camera_id: str, after_seconds: float = 30.0) -> bool:
        runtime = self._runtimes.get(camera_id)
        if runtime is None:
            return False
        last = runtime.source.metrics.last_frame_at
        if last is None:
            return runtime.source.lifecycle in (
                CameraLifecycle.RUNNING,
                CameraLifecycle.CONNECTED,
            )
        age = (datetime.now(timezone.utc) - last).total_seconds()
        return age > after_seconds and runtime.source.lifecycle in (
            CameraLifecycle.RUNNING,
            CameraLifecycle.CONNECTED,
            CameraLifecycle.DEGRADED,
        )

    # ------------------------------------------------- listener broadcast
    def add_listener(self, runtime: CameraRuntime) -> asyncio.Queue:
        """Attach a socket listener; worker results are broadcast to all of them."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=16)
        runtime.listeners.append(queue)
        return queue

    def remove_listener(self, runtime: CameraRuntime, queue: asyncio.Queue) -> None:
        try:
            runtime.listeners.remove(queue)
        except ValueError:
            pass

    def broadcast(self, runtime: CameraRuntime, payload: dict) -> None:
        for queue in list(runtime.listeners):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(payload)
                except asyncio.QueueEmpty:
                    pass

    def ensure_worker(self, runtime, vision) -> None:
        """Exactly one VLM worker per camera; shared by all its connections."""
        if runtime.worker_task is not None and not runtime.worker_task.done():
            return

        from backend.app.workers.camera_worker import process_event

        async def _drain() -> None:
            while True:
                ctx = await runtime.event_queue.get()
                try:
                    result, memory_id, events = await process_event(ctx, vision)
                except Exception as exc:  # noqa: BLE001 - per-camera isolation
                    runtime.last_error = str(exc)[:300]
                    log_event(
                        "camera_error",
                        status="error",
                        camera_id=ctx.camera_id,
                        message=str(exc)[:300],
                    )
                    result, memory_id, events = None, None, []
                finally:
                    runtime.event_queue.task_done()
                # Baseline bookkeeping: ready on success (exactly once per camera),
                # bounded retry on failure. Ingestion never stops either way.
                if ctx.is_baseline:
                    import time as _time

                    if memory_id is not None:
                        runtime.baseline.mark_ready(memory_id)
                        log_event(
                            "baseline_ready",
                            status="ok",
                            user_id=ctx.user_id,
                            camera_id=ctx.camera_id,
                            extra={"memory_id": memory_id},
                        )
                    else:
                        runtime.baseline.mark_attempt_failed(
                            "vlm_failed", _time.monotonic()
                        )
                if result is not None:
                    self.broadcast(
                        runtime,
                        {
                            "type": "memory_created",
                            "memory_id": memory_id,
                            "summary": result.perception.scene.summary,
                            "events": events,
                            "baseline": bool(ctx.is_baseline),
                        },
                    )

        runtime.worker_task = self.supervise(_drain, runtime.source.metadata.id)

    # ------------------------------------------------------------ supervision
    def supervise(
        self, coro_factory: Callable[[], Any], camera_id: str
    ) -> asyncio.Task:
        """Run a per-camera coroutine with isolation: crashes are logged, never propagated."""

        async def _guarded():
            try:
                await coro_factory()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - isolate per camera
                runtime = self._runtimes.get(camera_id)
                if runtime is not None:
                    runtime.last_error = str(exc)[:300]
                    runtime.source.note_error(str(exc))
                log_event(
                    "camera_error",
                    status="error",
                    camera_id=camera_id,
                    message=str(exc)[:300],
                )

        task = asyncio.create_task(_guarded())
        runtime = self._runtimes.get(camera_id)
        if runtime is not None:
            runtime.task = task
        return task


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


manager = CameraManager()
