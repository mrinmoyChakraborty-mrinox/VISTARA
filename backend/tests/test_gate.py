"""Perception gate + rolling buffer tests."""

from __future__ import annotations

from backend.app.perception.buffer import RollingBuffer
from backend.app.perception.gate import GateConfig, PerceptionGate, frame_change_score
from backend.tests.conftest import make_frame


def test_static_scene_never_fires():
    gate = PerceptionGate(GateConfig(change_threshold=0.05, persistence_frames=2))
    frame = make_frame(0)
    decisions = [gate.update(frame, now=t * 0.5) for t in range(10)]
    assert not any(d.fired for d in decisions)


def test_change_fires_then_cooldown():
    gate = PerceptionGate(
        GateConfig(change_threshold=0.005, persistence_frames=1, cooldown_seconds=8.0)
    )
    gate.update(make_frame(0), now=0.0)
    d1 = gate.update(make_frame(60), now=1.0)
    assert d1.fired
    # Subsequent changes are suppressed during cooldown.
    d2 = gate.update(make_frame(120), now=2.0)
    assert not d2.fired and d2.reason == "cooldown"


def test_persistence_requires_consecutive_frames():
    gate = PerceptionGate(GateConfig(change_threshold=0.005, persistence_frames=3))
    gate.update(make_frame(0), now=0.0)
    d = gate.update(make_frame(80), now=1.0)
    assert not d.fired and d.reason == "persistence"


def test_change_score_bounds():
    assert frame_change_score(make_frame(0), make_frame(0)) == 0.0
    assert frame_change_score(make_frame(0), make_frame(100)) > 0.0


def test_rolling_buffer_keeps_maxlen_and_selects_representative():
    buf = RollingBuffer(maxlen=5)
    for i in range(20):
        buf.push(make_frame(i), ts=float(i))
    assert len(buf) == 5
    rep = buf.select_representative(buf.snapshot(), count=3)
    assert len(rep) == 3
    ts = [f.ts for f in rep]
    assert ts == sorted(ts)  # chronological
