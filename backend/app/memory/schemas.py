"""Memory domain schemas.

Includes:
- The VLM output contract (ARCHITECTURE §12 / Phase-1 §8) with Pydantic validation.
- API-facing schemas for memories/objects/events/evidence.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------- VLM
class VLMAttributes(BaseModel):
    model_config = ConfigDict(extra="allow")


class VLMObject(BaseModel):
    model_config = ConfigDict(extra="ignore")

    temporary_id: str = ""
    name: str
    location: str
    status: str = "visible"
    attributes: dict[str, Any] = Field(default_factory=dict)


class VLMEvent(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    type: str
    object_name: str = Field(default="", validation_alias="object_name")
    from_location: str = ""
    to_location: str = ""
    description: str = ""
    confidence: float = 0.0

    @classmethod
    def coerce(cls, data: dict[str, Any]) -> "VLMEvent":
        d = dict(data)
        if not d.get("object_name") and "object" in d:
            d["object_name"] = d.pop("object")
        return cls.model_validate(d)


class VLMScene(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str
    summary: str
    activity: str = ""
    environment: str = ""


class VLMPerception(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scene: VLMScene
    objects: list[VLMObject] = Field(default_factory=list)
    events: list[VLMEvent] = Field(default_factory=list)

    @classmethod
    def parse(cls, data: dict[str, Any]) -> "VLMPerception":
        d = dict(data)
        raw_events = d.get("events") or []
        d["events"] = [VLMEvent.coerce(e) for e in raw_events if isinstance(e, dict)]
        return cls.model_validate(d)


def vlm_json_schema() -> dict[str, Any]:
    """Groq strict JSON schema. Required lists every property (strict-mode rule)."""
    return {
        "type": "object",
        "properties": {
            "scene": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "summary": {"type": "string"},
                    "activity": {"type": "string"},
                    "environment": {"type": "string"},
                },
                "required": ["type", "summary", "activity", "environment"],
                "additionalProperties": False,
            },
            "objects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "temporary_id": {"type": "string"},
                        "name": {"type": "string"},
                        "location": {"type": "string"},
                        "status": {"type": "string"},
                        "attributes": {"type": "object"},
                    },
                    "required": [
                        "temporary_id",
                        "name",
                        "location",
                        "status",
                        "attributes",
                    ],
                    "additionalProperties": False,
                },
            },
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "object_name": {"type": "string"},
                        "from_location": {"type": "string"},
                        "to_location": {"type": "string"},
                        "description": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": [
                        "type",
                        "object_name",
                        "from_location",
                        "to_location",
                        "description",
                        "confidence",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["scene", "objects", "events"],
        "additionalProperties": False,
    }


VLM_SYSTEM_PROMPT = (
    "You are the visual perception module of a visual memory system. "
    "You analyze a small ordered set of camera frames and return strict JSON only.\n"
    "Rules:\n"
    "- NEVER invent objects. Only report objects you can actually see.\n"
    "- Separate observation from inference; do not speculate about causes.\n"
    "- Produce three layers: overall scene perception, granular object perception, "
    "and meaningful events (only real observed changes).\n"
    "- Use 'last observed' semantics: if an object may be occluded or certainty is "
    "unavailable, say so instead of claiming it is definitely gone.\n"
    "- Locations are short spatial phrases (e.g. 'center of desk', 'beside laptop').\n"
    "- If nothing changed, return an empty events array.\n"
    "- Return JSON matching the schema exactly. No prose, no markdown, no commentary."
)


# --------------------------------------------------------------------- API
class SceneOut(BaseModel):
    type: str
    summary: str
    activity: str
    environment: str


class MemoryObjectOut(BaseModel):
    id: uuid.UUID
    memory_id: uuid.UUID
    name: str
    normalized_name: str
    location: str
    status: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class MemoryEventOut(BaseModel):
    id: uuid.UUID
    memory_id: uuid.UUID
    camera_id: uuid.UUID
    timestamp: datetime
    event_type: str
    object_name: str
    from_location: str
    to_location: str
    description: str
    confidence: float


class EvidenceOut(BaseModel):
    id: uuid.UUID
    memory_id: uuid.UUID
    camera_id: uuid.UUID
    timestamp: datetime
    storage_path: str
    mime_type: str
    url: str | None = None


class MemoryOut(BaseModel):
    id: uuid.UUID
    camera_id: uuid.UUID
    timestamp: datetime
    scene: SceneOut
    objects: list[MemoryObjectOut] = Field(default_factory=list)
    events: list[MemoryEventOut] = Field(default_factory=list)
    confidence: float
    evidence_id: uuid.UUID | None = None
    created_at: datetime


class EmbeddingIn(BaseModel):
    embedding: list[float] = Field(min_length=1024, max_length=1024)


class ObjectHistoryEntry(BaseModel):
    timestamp: datetime
    camera_id: uuid.UUID
    location: str
    status: str
    memory_id: uuid.UUID


class ObjectHistoryOut(BaseModel):
    object: str
    first_seen: datetime | None
    last_seen: datetime | None
    entries: list[ObjectHistoryEntry]
