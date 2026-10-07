"""VLM output contract — Pydantic schema from IMPLEMENTATION.md section 7.

Canonical shape (also accepts the ARCHITECTURE.md section 12 aliases):
    { scene: {type, summary, activity, environment},
      objects: [{name, location, status, confidence}],
      events: [{type, object, from, to, confidence}] }
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Scene(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = Field(description="Scene type, e.g. 'work desk'")
    summary: str = Field(description="One-two sentence scene summary")
    activity: str = Field(default="", description="Ongoing activity")
    environment: str = Field(default="", description="Indoor/outdoor workspace etc.")


class VLMObject(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str
    location: str
    status: str = "visible"
    confidence: float = 0.0


class VLMEvent(BaseModel):
    """One physical move => exactly one event (enforced via scene-state delta, Stage 4)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    type: str = Field(
        description="object_moved | object_appeared | object_disappeared | ..."
    )
    object: str = Field(
        validation_alias="object",
        serialization_alias="object",
        description="Canonical object name",
    )
    from_location: str = Field(default="", description="Previous location")
    to_location: str = Field(default="", description="New location")
    confidence: float = 0.0

    @classmethod
    def coerce(cls, data: dict[str, Any]) -> "VLMEvent":
        """Accept ARCHITECTURE.md alias keys (object_name/from_location/to_location/from/to)."""
        d = dict(data)
        if "object" not in d and "object_name" in d:
            d["object"] = d.pop("object_name")
        if "from_location" not in d and "from" in d:
            d["from_location"] = d.pop("from")
        if "to_location" not in d and "to" in d:
            d["to_location"] = d.pop("to")
        # ARCHITECTURE nests description/confidence the same way; description is dropped (extra=ignore).
        return cls.model_validate(d)


class VLMPerception(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scene: Scene
    objects: list[VLMObject] = Field(default_factory=list)
    events: list[VLMEvent] = Field(default_factory=list)

    @classmethod
    def parse_raw_events(cls, data: dict[str, Any]) -> "VLMPerception":
        """Validate while coercing each event's alias keys."""
        d = dict(data)
        raw_events = d.get("events") or []
        coerced = [VLMEvent.coerce(e) if isinstance(e, dict) else e for e in raw_events]
        d["events"] = [e.model_dump(by_alias=True) for e in coerced]
        # Re-map by_alias dumps back to field names for final validation.
        remapped = []
        for e in d["events"]:
            if "from" in e:
                e["from_location"] = e.pop("from")
            if "to" in e:
                e["to_location"] = e.pop("to")
            remapped.append(e)
        d["events"] = remapped
        return cls.model_validate(d)


def vlm_json_schema() -> dict[str, Any]:
    """Strict-JSON-schema-compatible schema for Groq response_format=json_schema."""
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
                "required": ["type", "summary"],
                "additionalProperties": False,
            },
            "objects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "location": {"type": "string"},
                        "status": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["name", "location"],
                    "additionalProperties": False,
                },
            },
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "object": {"type": "string"},
                        "from_location": {"type": "string"},
                        "to_location": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["type", "object"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["scene", "objects", "events"],
        "additionalProperties": False,
    }


VLM_SYSTEM_PROMPT = (
    "You are the visual perception module of a memory system. "
    "Describe the scene, list the visible demo objects (ESP32, phone, notebook, bottle) "
    "with their locations, and report only real visible changes as events. "
    "Use 'last observed' wording for anything uncertain. Never invent objects."
)
