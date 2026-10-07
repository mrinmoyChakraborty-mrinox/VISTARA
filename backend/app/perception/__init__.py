"""Perception package: gate, buffer, pipeline + image utils."""

from backend.app.perception.baseline import (  # noqa: F401
    BaselineConfig,
    BaselineStatus,
    BaselineTracker,
    adopt_prior_state,
    build_baseline_context,
    post_ingest,
)
from backend.app.perception.buffer import BufferedFrame, RollingBuffer  # noqa: F401
from backend.app.perception.gate import GateConfig, GateDecision, PerceptionGate  # noqa: F401
from backend.app.perception.pipeline import (  # noqa: F401
    EventContext,
    build_event_payload,
    payload_images,
)
