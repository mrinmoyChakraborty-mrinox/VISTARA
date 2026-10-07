"""Perception package: gate, buffer, pipeline + image utils."""

from backend.app.perception.buffer import BufferedFrame, RollingBuffer  # noqa: F401
from backend.app.perception.gate import GateConfig, GateDecision, PerceptionGate  # noqa: F401
from backend.app.perception.pipeline import (  # noqa: F401
    EventContext,
    build_event_payload,
    payload_images,
)
