"""Serialization helpers: ORM rows -> API schemas (user-scoped at the repo layer)."""

from __future__ import annotations

from backend.app.db.models import Evidence, Memory, MemoryEvent, MemoryObject
from backend.app.memory.schemas import (
    EvidenceOut,
    MemoryEventOut,
    MemoryObjectOut,
    MemoryOut,
    SceneOut,
)


def memory_to_out(memory: Memory) -> MemoryOut:
    return MemoryOut(
        id=memory.id,
        camera_id=memory.camera_id,
        timestamp=memory.timestamp,
        scene=SceneOut(
            type=memory.scene_type,
            summary=memory.scene_summary,
            activity=memory.activity,
            environment=memory.environment,
        ),
        objects=[object_to_out(o) for o in getattr(memory, "objects", []) or []],
        events=[event_to_out(e) for e in getattr(memory, "events", []) or []],
        confidence=memory.confidence,
        evidence_id=memory.evidence_id,
        is_baseline=bool(getattr(memory, "is_baseline", False)),
        created_at=memory.created_at,
    )


def object_to_out(obj: MemoryObject) -> MemoryObjectOut:
    return MemoryObjectOut(
        id=obj.id,
        memory_id=obj.memory_id,
        name=obj.name,
        normalized_name=obj.normalized_name,
        location=obj.location,
        status=obj.status,
        attributes=obj.attributes or {},
    )


def event_to_out(event: MemoryEvent) -> MemoryEventOut:
    return MemoryEventOut(
        id=event.id,
        memory_id=event.memory_id,
        camera_id=event.camera_id,
        timestamp=event.timestamp,
        event_type=event.event_type,
        object_name=event.object_name,
        from_location=event.from_location,
        to_location=event.to_location,
        description=event.description,
        confidence=event.confidence,
    )


def evidence_to_out(evidence: Evidence, url: str | None = None) -> EvidenceOut:
    return EvidenceOut(
        id=evidence.id,
        memory_id=evidence.memory_id,
        camera_id=evidence.camera_id,
        timestamp=evidence.timestamp,
        storage_path=evidence.storage_path,
        mime_type=evidence.mime_type,
        url=url,
    )
