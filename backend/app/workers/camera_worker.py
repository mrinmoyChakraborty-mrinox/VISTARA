"""Camera worker: consumes queued event contexts and runs the VLM pipeline.

Runs off the camera ingestion path so the WebSocket loop never blocks on inference.
"""

from __future__ import annotations

import asyncio

from backend.app.core.logging import log_event, timed
from backend.app.db.session import session_scope
from backend.app.evidence.service import EvidenceService
from backend.app.memory.service import MemoryService
from backend.app.perception.pipeline import (
    EventContext,
    make_previous_state,
    payload_images,
)
from backend.app.providers.vision import VisionProvider, VisionResult


async def process_event(
    ctx: EventContext, vision: VisionProvider
) -> tuple[VisionResult | None, str | None, list[dict]]:
    """Run one VLM analysis + persist memory/evidence. Returns (result, memory_id, events).

    Baseline contexts use the baseline prompt and persist an event-free baseline
    memory; normal contexts derive deltas against the current scene state.
    """
    frames = payload_images(ctx)
    log_event(
        "vlm_started",
        status="ok",
        camera_id=ctx.camera_id,
        user_id=ctx.user_id,
        extra={"baseline": ctx.is_baseline},
    )

    try:
        with timed() as t:
            result = await asyncio.to_thread(
                vision.analyze, frames, None, ctx.is_baseline
            )
        log_event(
            "vlm_completed",
            status="ok",
            camera_id=ctx.camera_id,
            user_id=ctx.user_id,
            latency_ms=round(t.ms, 1),
            extra={"model": result.model},
        )
    except Exception as exc:  # noqa: BLE001
        log_event(
            "vlm_failed",
            status="error",
            camera_id=ctx.camera_id,
            user_id=ctx.user_id,
            message=str(exc),
        )
        return None, None, []

    with session_scope() as db:
        service = MemoryService(db)
        previous = make_previous_state(service, ctx.user_id, ctx.camera_id)
        memory_id, events = service.create_from_perception(
            ctx.user_id,
            ctx.camera_id,
            result.perception,
            previous_state=previous,
            timestamp=ctx.timestamp,
            is_baseline=ctx.is_baseline,
        )
        evidence_id = None
        try:
            evidence = EvidenceService().persist_frame_and_record(
                db,
                ctx.user_id,
                ctx.camera_id,
                str(memory_id),
                ctx.main_jpeg,
                ctx.timestamp,
            )
            evidence_id = str(evidence.id)
            service.memories.set_evidence(ctx.user_id, str(memory_id), evidence_id)
        except Exception as exc:  # noqa: BLE001
            log_event(
                "evidence_failed", status="error", user_id=ctx.user_id, message=str(exc)
            )

    return result, str(memory_id), events


class CameraWorker:
    """Long-lived worker draining a camera runtime's event queue."""

    def __init__(self, runtime, vision: VisionProvider, on_result):
        self.runtime = runtime
        self.vision = vision
        self.on_result = on_result
        self._task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while self._running:
            ctx: EventContext = await self.runtime.event_queue.get()
            result, memory_id, events = await process_event(ctx, self.vision)
            if result is not None and self.on_result is not None:
                try:
                    await self.on_result(result, memory_id, events)
                except Exception:  # noqa: BLE001
                    pass
            self.runtime.event_queue.task_done()

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
