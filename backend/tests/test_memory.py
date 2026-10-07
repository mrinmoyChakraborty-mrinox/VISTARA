"""Memory creation, scene-state delta, object history, hybrid retrieval tests."""

from __future__ import annotations


from backend.app.db.session import session_scope
from backend.app.memory.service import MemoryService, SceneState, compute_delta
from backend.app.memory.schemas import (
    VLMObject,
    VLMPerception,
    VLMScene,
    VLMEvent,
)
from backend.app.retrieval.service import RetrievalService
from backend.tests.conftest import auth, create_camera


def _perception(esp32_loc: str, moved: bool = False) -> VLMPerception:
    events = []
    if moved:
        events = [
            VLMEvent(
                type="object_moved",
                object_name="ESP32",
                from_location="center of desk",
                to_location=esp32_loc,
                description="ESP32 moved",
                confidence=0.9,
            )
        ]
    return VLMPerception(
        scene=VLMScene(
            type="work desk", summary="desk", activity="work", environment="indoor"
        ),
        objects=[
            VLMObject(
                temporary_id="o1", name="ESP32", location=esp32_loc, status="visible"
            ),
            VLMObject(
                temporary_id="o2", name="phone", location="left", status="visible"
            ),
        ],
        events=events,
    )


def test_one_move_creates_one_event():
    prev = SceneState(locations={"ESP32": "center of desk", "phone": "left"})
    # VLM also lists the ESP32 as an object at the new place; delta must not double-count.
    delta = compute_delta(prev, _perception("beside laptop", moved=True))
    assert len(delta.events) == 1
    assert delta.events[0]["object_name"] == "ESP32"


def test_delta_detects_unreported_move():
    prev = SceneState(locations={"ESP32": "center of desk"})
    delta = compute_delta(prev, _perception("beside laptop", moved=False))
    assert len(delta.events) == 1
    assert delta.events[0]["from_location"] == "center of desk"
    assert delta.events[0]["to_location"] == "beside laptop"


def test_no_change_no_event():
    prev = SceneState(locations={"ESP32": "center of desk", "phone": "left"})
    delta = compute_delta(prev, _perception("center of desk", moved=False))
    assert delta.events == []


def test_memory_creation_and_history(client):
    cam = create_camera(client, "C", user="user-a")
    with session_scope() as db:
        svc = MemoryService(db)
        mem_id, events = svc.create_from_perception(
            "user-a", cam, _perception("center of desk")
        )
        assert events == []
        mem_id2, events2 = svc.create_from_perception(
            "user-a",
            cam,
            _perception("beside laptop", moved=True),
            previous_state=SceneState(
                locations={"ESP32": "center of desk", "phone": "left"}
            ),
        )
        assert len(events2) == 1
        history = svc.history.list("user-a", "esp32")
        assert len(history) == 2
        assert history[-1].location == "beside laptop"


def test_object_history_and_last_seen(client):
    cam = create_camera(client, "C2", user="user-a")
    with session_scope() as db:
        svc = MemoryService(db)
        svc.create_from_perception("user-a", cam, _perception("center of desk"))
        svc.create_from_perception(
            "user-a", cam, _perception("beside laptop", moved=True)
        )
        retrieval = RetrievalService(db)
        hist = retrieval.get_object_history("user-a", "ESP32")
        assert hist["object"] == "ESP32"
        assert len(hist["entries"]) == 2
        last = retrieval.get_last_seen("user-a", "ESP32")
        assert last["found"] and last["location"] == "beside laptop"
        assert "last observed" in last["statement"]


def test_user_isolation_in_retrieval(client):
    cam = create_camera(client, "C3", user="user-a")
    with session_scope() as db:
        MemoryService(db).create_from_perception(
            "user-a", cam, _perception("center of desk")
        )
        assert RetrievalService(db).get_last_seen("user-b", "ESP32")["found"] is False
        assert (
            RetrievalService(db).get_object_history("user-b", "ESP32")["entries"] == []
        )


def test_hybrid_search_metadata_then_vector(client):
    cam = create_camera(client, "C4", user="user-a")
    with session_scope() as db:
        mem_id, _ = MemoryService(db).create_from_perception(
            "user-a", cam, _perception("center of desk")
        )
        retrieval = RetrievalService(db)
        results = retrieval.search_memory("user-a", query="ESP32")
        assert any(str(r.id) == str(mem_id) for r in results)
        # user-b sees nothing
        assert retrieval.search_memory("user-b", query="ESP32") == []


def test_events_endpoint_user_scoped(client):
    cam = create_camera(client, "C5", user="user-a")
    with session_scope() as db:
        MemoryService(db).create_from_perception(
            "user-a", cam, _perception("beside laptop", moved=True)
        )
    res_a = client.get("/api/events", headers=auth("user-a")).json()
    res_b = client.get("/api/events", headers=auth("user-b")).json()
    assert len(res_a) == 1 and res_b == []
