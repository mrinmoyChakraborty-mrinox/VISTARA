"""VLM JSON validation + normalization tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.memory.normalization import normalize_name, object_key
from backend.app.memory.schemas import VLMPerception, vlm_json_schema


def test_valid_perception_parses():
    payload = {
        "scene": {
            "type": "work desk",
            "summary": "s",
            "activity": "a",
            "environment": "e",
        },
        "objects": [
            {
                "temporary_id": "o1",
                "name": "ESP32",
                "location": "center",
                "status": "visible",
                "attributes": {},
            }
        ],
        "events": [
            {
                "type": "object_moved",
                "object_name": "ESP32",
                "from_location": "center",
                "to_location": "right",
                "description": "moved",
                "confidence": 0.8,
            }
        ],
    }
    p = VLMPerception.parse(payload)
    assert p.scene.type == "work desk"
    assert p.events[0].to_location == "right"


def test_event_alias_object_key_accepted():
    payload = {
        "scene": {"type": "t", "summary": "s"},
        "objects": [],
        "events": [{"type": "object_moved", "object": "ESP32", "to_location": "x"}],
    }
    p = VLMPerception.parse(payload)
    assert p.events[0].object_name == "ESP32"


def test_malformed_rejected():
    with pytest.raises(ValidationError):
        VLMPerception.parse({"scene": {"type": "t"}, "objects": "nope", "events": []})


def test_schema_strict_requires_every_property():
    schema = vlm_json_schema()
    for section in ("scene", "objects", "events"):
        assert section in schema["required"]
    event_items = schema["properties"]["events"]["items"]
    assert set(event_items["required"]) == set(event_items["properties"].keys())


def test_alias_normalization():
    assert normalize_name("ESP32 development board") == "ESP32"
    assert normalize_name("mobile phone") == "phone"
    assert normalize_name("Water Bottle") == "bottle"
    assert object_key("ESP32") == "esp32"
