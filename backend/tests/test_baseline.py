"""Initial visual baseline tests (pixel warm-up + semantic baseline, once per camera).

Uses deterministic synthetic frames and the mock VLM. No Groq, no camera,
no Supabase, no GPU.
"""

from __future__ import annotations

import asyncio

from backend.app.cameras.manager import manager
from backend.app.db.repositories import EvidenceRepository
from backend.app.db.session import session_scope
from backend.app.memory.schemas import VLMEvent, VLMObject, VLMPerception, VLMScene
from backend.app.memory.service import MemoryService
from backend.app.perception.baseline import (
    BaselineConfig,
    BaselineStatus,
    BaselineTracker,
    adopt_prior_state,
    post_ingest,
)
from backend.app.perception.buffer import RollingBuffer
from backend.app.perception.gate import GateConfig, PerceptionGate
from backend.app.perception.pipeline import frame_to_bgr, make_previous_state
from backend.tests.conftest import frame_bytes


CAM = "00000000-0000-0000-0000-00000000b001"
USER = "baseline-user"


def _obj(name, location, status="visible", attributes=None):
    return VLMObject(
        temporary_id=f"o-{name}",
        name=name,
        location=location,
        status=status,
        attributes=attributes or {},
    )


def _perception(objects, events=None):
    return VLMPerception(
        scene=VLMScene(
            type="work desk",
            summary="A desk with electronics.",
            activity="work",
            environment="indoor",
        ),
        objects=objects,
        events=events or [],
    )


def _moved_event(obj="ESP32", frm="center of desk", to="beside laptop"):
    return VLMEvent(
        type="object_moved",
        object_name=obj,
        from_location=frm,
        to_location=to,
        description=f"{obj} moved.",
        confidence=0.9,
    )


def _strict_tracker(**overrides) -> BaselineTracker:
    cfg = BaselineConfig(
        warmup_min_frames=5,
        warmup_min_seconds=3.0,
        settled_threshold=0.03,
        settled_frames=3,
        max_wait_seconds=20.0,
        context_frames=3,
        max_attempts=5,
        retry_cooldown_seconds=30.0,
    )
    for key, value in overrides.items():
        setattr(cfg, key, value)
    return BaselineTracker(config=cfg)


def _push_frames(buffer, shifts, ts_start=0.0):
    for i, shift in enumerate(shifts):
        buffer.push(frame_to_bgr(frame_bytes(shift)), ts=ts_start + i)


# ---------------------------------------------------------------- Test 8 first:
# unstable startup must not finalize on the first frames.
def test_unstable_startup_does_not_finalize_immediately():
    tracker = _strict_tracker()
    # Four highly-unstable frames: below warm-up count AND unsettled.
    for i in range(4):
        tracker.note_frame(0.5, now=100.0 + i)
        assert not tracker.should_finalize(100.0 + i)
    assert tracker.status is BaselineStatus.PENDING


def test_stable_warmup_finalizes_and_max_wait_bounds():
    tracker = _strict_tracker()
    now = 200.0
    for i in range(5):
        tracker.note_frame(0.001, now=now + i * 0.8)
    # 5 frames seen but only 3.2s elapsed (< 3.0? no: 200+3.2=203.2, elapsed 3.2 >= 3.0)
    # settled streak is 5 >= 3 -> stable -> finalize.
    assert tracker.should_finalize(203.2)

    # Bounded fallback: chaos forever still finalizes at max_wait, never hangs startup.
    wild = _strict_tracker()
    for i in range(6):
        wild.note_frame(0.9, now=300.0 + i * 5.0)
    assert wild.should_finalize(300.0 + 25.0)


def test_no_false_change_before_baseline_ready():
    tracker = _strict_tracker()
    assert tracker.status is BaselineStatus.PENDING

    class _Runtime:
        baseline = tracker

    # Gate may fire at pixel level; semantic emission must stay disabled.
    action = post_ingest(_Runtime(), USER, 400.0, score=0.9)
    assert action["emit_change"] is False
    # ...until the camera is actually ready.
    tracker.mark_ready("mem-1")
    action = post_ingest(_Runtime(), USER, 401.0, score=0.9)
    assert action["emit_change"] is True
    assert action["baseline_ctx"] is None


def test_baseline_persists_inventory_and_attributes():
    objects = [
        _obj("bottle", "left side", attributes={"color": "blue"}),
        _obj("phone", "near laptop"),
        _obj("laptop", "center of desk"),
        _obj("notebook", "right side"),
        _obj("ESP32", "center of desk", attributes={"color": "green"}),
    ]
    perception = _perception(objects, events=[_moved_event()])
    with session_scope() as db:
        svc = MemoryService(db)
        mem_id, events = svc.create_from_perception(
            USER, CAM, perception, is_baseline=True
        )
        # No change events from a baseline, even when the model reports movement.
        assert events == []
        memory = svc.memories.get(USER, str(mem_id))
        assert memory is not None and memory.is_baseline is True
        stored = {
            o.normalized_name: o for o in svc.objects.list_for_memory(USER, str(mem_id))
        }
        assert set(stored) == {"bottle", "phone", "laptop", "notebook", "ESP32"}
        assert stored["bottle"].attributes.get("color") == "blue"
        assert stored["ESP32"].location == "center of desk"
        assert svc.events.list_for_memory(USER, str(mem_id)) == []


def test_change_after_baseline_derives_object_moved():
    baseline_objects = [_obj("ESP32", "center of desk"), _obj("bottle", "left side")]
    with session_scope() as db:
        svc = MemoryService(db)
        base_id, _ = svc.create_from_perception(
            USER, CAM, _perception(baseline_objects), is_baseline=True
        )
        assert base_id is not None
        previous = make_previous_state(svc, USER, CAM)
        assert previous.locations.get("ESP32") == "center of desk"

        later = _perception(
            [_obj("ESP32", "beside laptop"), _obj("bottle", "left side")]
        )
        mem_id, events = svc.create_from_perception(
            USER, CAM, later, previous_state=previous
        )
        assert len(events) == 1
        assert events[0]["type"] == "object_moved"
        assert events[0]["from_location"] == "center of desk"
        assert events[0]["to_location"] == "beside laptop"
        rows = svc.events.list_for_memory(USER, str(mem_id))
        assert len(rows) == 1 and rows[0].object_name == "ESP32"


def test_reconnect_does_not_duplicate_baseline():
    with session_scope() as db:
        svc = MemoryService(db)
        mem_id, _ = svc.create_from_perception(
            USER, CAM, _perception([_obj("ESP32", "center of desk")]), is_baseline=True
        )
        assert mem_id is not None

    async def go():
        runtime = await manager.add(CAM + "-re", USER, "Desk", "browser", {})
        try:
            assert runtime.baseline.status is BaselineStatus.PENDING
            assert adopt_prior_state(runtime, USER, CAM) is True
            assert runtime.baseline.status is BaselineStatus.READY
            # Second "connection" adopts again without creating anything.
            assert adopt_prior_state(runtime, USER, CAM) is True
        finally:
            await manager.remove(CAM + "-re")

    asyncio.run(go())
    with session_scope() as db:
        rows = MemoryService(db).memories.list(USER, camera_id=CAM)
        assert len(rows) == 1 and rows[0].is_baseline is True


def test_initial_vlm_failure_keeps_camera_alive_and_retries():
    class FailingVision:
        def analyze(self, frames, previous_state=None, baseline=False):
            raise RuntimeError("cloud unavailable")

    from backend.app.workers.camera_worker import process_event

    async def go():
        cam_id = CAM + "-fail"
        runtime = await manager.add(cam_id, USER, "Desk", "browser", {})
        try:
            buffer = RollingBuffer(maxlen=10)
            _push_frames(buffer, [0, 0, 0])
            for frame in buffer.snapshot():
                runtime.buffer.push(frame.frame, ts=frame.ts)
            # Drive the real decision path: post_ingest offers exactly one attempt...
            action = post_ingest(runtime, USER, 500.0, score=0.0)
            ctx = action["baseline_ctx"]
            assert ctx is not None and ctx.is_baseline is True
            assert runtime.baseline.attempts == 1
            # ...the worker runs it, VLM fails, the drain records the failure...
            result, memory_id, events = await process_event(ctx, FailingVision())
            assert result is None and memory_id is None and events == []
            runtime.baseline.mark_attempt_failed("cloud unavailable", 500.0)
            assert runtime.baseline.status is BaselineStatus.PENDING
            # ...no fake memory was created, and retry re-offers after cooldown.
            with session_scope() as db:
                assert MemoryService(db).memories.list(USER, camera_id=cam_id) == []
            action2 = post_ingest(runtime, USER, 500.0 + 3600.0, score=0.0)
            assert action2["baseline_ctx"] is not None
        finally:
            await manager.remove(cam_id)

    asyncio.run(go())
    with session_scope() as db:
        assert MemoryService(db).memories.list(USER, camera_id=CAM + "-fail") == []


def test_failed_status_after_exhausted_attempts_but_ingest_continues():
    tracker = BaselineTracker(
        config=BaselineConfig(
            warmup_min_frames=1,
            warmup_min_seconds=0.0,
            settled_threshold=0.5,
            settled_frames=1,
            max_wait_seconds=0.0,
            max_attempts=2,
            retry_cooldown_seconds=10.0,
            failed_retry_multiplier=3.0,
        )
    )
    now = 600.0
    tracker.note_frame(0.0, now)
    assert tracker.should_finalize(now)
    tracker.mark_attempt_started(now)
    tracker.mark_attempt_failed("boom", now)
    assert tracker.status is BaselineStatus.PENDING
    # Second attempt allowed after cooldown.
    now += 11.0
    tracker.note_frame(0.0, now)
    assert tracker.should_finalize(now)
    tracker.mark_attempt_started(now)
    tracker.mark_attempt_failed("boom", now)
    assert tracker.status is BaselineStatus.FAILED
    # Ingestion still accepted; a later retry window reopens (longer cooldown).
    tracker.note_frame(0.0, now + 1.0)
    assert not tracker.should_finalize(now + 1.0)
    assert tracker.should_finalize(now + 31.0)


def test_full_flow_baseline_then_moved():
    """End-to-end: connect -> warm -> baseline persisted -> change -> OBJECT_MOVED."""
    flow_cfg = BaselineConfig(
        warmup_min_frames=3,
        warmup_min_seconds=0.0,
        settled_threshold=0.5,
        settled_frames=2,
        max_wait_seconds=1000.0,
        context_frames=2,
        max_attempts=3,
        retry_cooldown_seconds=0.0,
    )

    async def go():
        from backend.app.providers.mock import MockVisionProvider

        cam_id = CAM + "-flow"
        runtime = await manager.add(
            cam_id, USER, "Desk", "browser", {}, baseline_config=flow_cfg
        )
        try:
            gate = PerceptionGate(
                GateConfig(change_threshold=0.005, persistence_frames=1)
            )
            # 1-3. connect + warm buffer with stable frames; first two must not finalize.
            ctx = None
            for i, shift in enumerate([0, 0, 0]):
                frame = frame_to_bgr(frame_bytes(shift))
                runtime.buffer.push(frame, ts=float(i))
                score = _score_of(frame)
                action = post_ingest(runtime, USER, 700.0 + i, score)
                if i < 2:
                    assert action["baseline_ctx"] is None, "must not finalize too early"
                    assert action["emit_change"] is False
                else:
                    ctx = action["baseline_ctx"]
            assert ctx is not None and ctx.is_baseline is True

            # 4-7. baseline VLM (mock) -> persisted memory + evidence + ready.
            vision = MockVisionProvider()
            vision.next_perception = _perception(
                [_obj("ESP32", "center of desk"), _obj("bottle", "left side")]
            )
            from backend.app.workers.camera_worker import process_event

            result, memory_id, events = await process_event(ctx, vision)
            assert result is not None and events == []
            runtime.baseline.mark_ready(memory_id)
            assert runtime.baseline.status is BaselineStatus.READY

            with session_scope() as db:
                svc = MemoryService(db)
                memory = svc.memories.get(USER, memory_id)
                assert memory is not None and memory.is_baseline is True
                assert len(svc.objects.list_for_memory(USER, memory_id)) == 2
                assert len(EvidenceRepository(db).for_memory(USER, memory_id)) == 1

            # 8-9. changed scene: gate must fire on real pixel change.
            moved = frame_to_bgr(frame_bytes(80))
            decision = gate.update(frame_to_bgr(frame_bytes(0)), now=800.0)
            assert not decision.fired  # warm-up frame
            decision = gate.update(moved, now=801.0)
            assert decision.fired

            # 10-11. normal observation through the worker path.
            vision.next_perception = _perception(
                [_obj("ESP32", "beside laptop"), _obj("bottle", "left side")],
                events=[_moved_event()],
            )
            from backend.app.perception.pipeline import build_event_payload

            runtime.buffer.push(moved, ts=802.0)
            normal = build_event_payload(runtime.buffer)
            assert normal is not None and not normal.is_baseline
            # Production handlers stamp identity onto the context; mirror that here.
            normal.camera_id = cam_id
            normal.user_id = USER
            result2, memory_id2, events2 = await process_event(normal, vision)

            # 12-15. delta against baseline -> exactly one OBJECT_MOVED, persisted + linked.
            assert len(events2) == 1
            assert events2[0]["type"] == "object_moved"
            assert events2[0]["from_location"] == "center of desk"
            assert events2[0]["to_location"] == "beside laptop"
            with session_scope() as db:
                svc = MemoryService(db)
                assert svc.memories.get(USER, memory_id2).is_baseline is False
                rows = svc.events.list_for_memory(USER, memory_id2)
                assert len(rows) == 1
                assert len(EvidenceRepository(db).for_memory(USER, memory_id2)) == 1
        finally:
            await manager.remove(cam_id)

    asyncio.run(go())


def _score_of(frame) -> float:
    import cv2
    import numpy as np

    small = cv2.resize(frame, (160, 120))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blank = np.zeros_like(gray)
    diff = cv2.absdiff(gray, blank)
    return float(np.mean(diff)) / 255.0
