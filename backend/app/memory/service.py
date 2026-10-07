"""Memory service: turn validated VLM output into persisted semantic memory.

Key behaviours:
- Memory is written immediately after valid VLM output; embedding generation is NOT
  on the hot path (browser posts the vector later via /embedding).
- Scene-state delta ensures one physical move yields exactly one event.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.core.logging import log_event
from backend.app.db.repositories import (
    MemoryEventRepository,
    MemoryObjectRepository,
    MemoryRepository,
    ObjectHistoryRepository,
)
from backend.app.memory.normalization import normalize_name, object_key
from backend.app.memory.schemas import VLMPerception


@dataclass
class SceneState:
    """Compact previous semantic state: normalized object -> location."""

    locations: dict[str, str] = field(default_factory=dict)

    def update(self, perception: VLMPerception) -> None:
        self.locations = {
            normalize_name(o.name): o.location for o in perception.objects
        }


@dataclass
class DeltaResult:
    events: list[dict] = field(default_factory=list)


def compute_delta(previous: SceneState, perception: VLMPerception) -> DeltaResult:
    """Compare new perception against previous state -> at most one event per moved object.

    VLM-reported changes win (they carry from/to + description). Object-location
    differences add moves the VLM did not report. Actions that did not change
    location produce no event.
    """
    events: list[dict] = []
    seen_objects: set[str] = set()

    for ev in perception.events:
        name = normalize_name(ev.object_name)
        if not name or name in seen_objects:
            continue
        seen_objects.add(name)
        events.append(
            {
                "type": ev.type or "object_moved",
                "object_name": normalize_name(ev.object_name),
                "from_location": ev.from_location or previous.locations.get(name, ""),
                "to_location": ev.to_location
                or next(
                    (
                        o.location
                        for o in perception.objects
                        if normalize_name(o.name) == name
                    ),
                    "",
                ),
                "description": ev.description,
                "confidence": ev.confidence,
            }
        )

    for obj in perception.objects:
        name = normalize_name(obj.name)
        if name in seen_objects:
            continue
        prev_loc = previous.locations.get(name)
        if prev_loc is not None and prev_loc != obj.location:
            seen_objects.add(name)
            events.append(
                {
                    "type": "object_moved",
                    "object_name": name,
                    "from_location": prev_loc,
                    "to_location": obj.location,
                    "description": f"{name} moved from {prev_loc} to {obj.location}.",
                    "confidence": 0.7,
                }
            )

    return DeltaResult(events=events)


class MemoryService:
    def __init__(self, db: Session):
        self.db = db
        self.memories = MemoryRepository(db)
        self.objects = MemoryObjectRepository(db)
        self.events = MemoryEventRepository(db)
        self.history = ObjectHistoryRepository(db)

    def create_from_perception(
        self,
        user_id: str,
        camera_id: str,
        perception: VLMPerception,
        previous_state: SceneState | None = None,
        timestamp: datetime | None = None,
        is_baseline: bool = False,
    ) -> tuple[uuid.UUID, list[dict]]:
        ts = timestamp or datetime.now(timezone.utc)
        state = previous_state or SceneState()
        confidence = self._scene_confidence(perception)

        memory = self.memories.create(
            user_id=user_id,
            camera_id=camera_id,
            timestamp=ts,
            scene_type=perception.scene.type,
            scene_summary=perception.scene.summary,
            activity=perception.scene.activity,
            environment=perception.scene.environment,
            confidence=confidence,
            is_baseline=is_baseline,
        )

        for obj in perception.objects:
            norm = normalize_name(obj.name)
            self.objects.add(
                user_id=user_id,
                memory_id=str(memory.id),
                name=obj.name,
                normalized_name=norm,
                location=obj.location,
                status=obj.status,
                attributes=obj.attributes,
            )
            self.history.add(
                user_id=user_id,
                object_key=object_key(norm),
                camera_id=camera_id,
                memory_id=str(memory.id),
                timestamp=ts,
                location=obj.location,
                status=obj.status,
            )

        # The initial baseline inventories state; it never emits change events,
        # even if the model reports movement on first sight.
        delta = DeltaResult() if is_baseline else compute_delta(state, perception)
        for ev in delta.events:
            self.events.add(
                user_id=user_id,
                memory_id=str(memory.id),
                camera_id=camera_id,
                timestamp=ts,
                event_type=ev["type"],
                object_name=ev["object_name"],
                from_location=ev["from_location"],
                to_location=ev["to_location"],
                description=ev["description"],
                confidence=ev["confidence"],
            )

        log_event(
            "memory_created",
            status="ok",
            user_id=user_id,
            camera_id=camera_id,
            memory_id=str(memory.id),
            extra={
                "objects": len(perception.objects),
                "events": len(delta.events),
                "is_baseline": is_baseline,
            },
        )
        return memory.id, delta.events

    @staticmethod
    def _scene_confidence(perception: VLMPerception) -> float:
        scores = [e.confidence for e in perception.events if e.confidence]
        return round(sum(scores) / len(scores), 3) if scores else 0.5
