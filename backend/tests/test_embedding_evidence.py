"""Embedding update authorization + evidence authorization tests."""

from __future__ import annotations

from backend.app.db.session import session_scope
from backend.app.evidence.service import EvidenceService
from backend.app.memory.schemas import VLMObject, VLMPerception, VLMScene
from backend.app.memory.service import MemoryService
from backend.tests.conftest import auth, create_camera, frame_bytes


def _p():
    return VLMPerception(
        scene=VLMScene(type="t", summary="s"),
        objects=[
            VLMObject(
                temporary_id="o", name="ESP32", location="center", status="visible"
            )
        ],
        events=[],
    )


def test_embedding_update_requires_1024(client):
    cam = create_camera(client, "E", user="user-a")
    with session_scope() as db:
        mem_id, _ = MemoryService(db).create_from_perception("user-a", cam, _p())
    res = client.post(
        f"/api/memories/{mem_id}/embedding",
        json={"embedding": [0.0] * 10},
        headers=auth("user-a"),
    )
    assert res.status_code == 422


def test_embedding_update_ok_and_other_user_blocked(client):
    cam = create_camera(client, "E2", user="user-a")
    with session_scope() as db:
        mem_id, _ = MemoryService(db).create_from_perception("user-a", cam, _p())
    ok = client.post(
        f"/api/memories/{mem_id}/embedding",
        json={"embedding": [0.1] * 1024},
        headers=auth("user-a"),
    )
    assert ok.status_code == 200
    blocked = client.post(
        f"/api/memories/{mem_id}/embedding",
        json={"embedding": [0.1] * 1024},
        headers=auth("user-b"),
    )
    assert blocked.status_code == 404


def test_evidence_authorization(client):
    cam = create_camera(client, "EV", user="user-a")
    with session_scope() as db:
        mem_id, _ = MemoryService(db).create_from_perception("user-a", cam, _p())
        record = EvidenceService().persist_frame_and_record(
            db,
            "user-a",
            cam,
            str(mem_id),
            frame_bytes(0),
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        evidence_id = str(record.id)
    # Owner can access (offline fallback returns JSON metadata).
    owner = client.get(f"/api/evidence/{evidence_id}", headers=auth("user-a"))
    assert owner.status_code == 200
    # Another user cannot.
    other = client.get(f"/api/evidence/{evidence_id}", headers=auth("user-b"))
    assert other.status_code == 404
