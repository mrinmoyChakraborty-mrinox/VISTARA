"""Shared test fixtures: offline DB + mock providers. No Groq, camera, Supabase or GPU."""

from __future__ import annotations

import os
import tempfile

# Must be set before backend modules import settings / evidence service.
os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("EVIDENCE_DIR", tempfile.mkdtemp(prefix="vm_evidence_"))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from backend.app.core.config import settings  # noqa: E402
from backend.app.db import session as db_session  # noqa: E402
from backend.app.providers.mock import MockChatProvider, MockVisionProvider  # noqa: E402

# Tune the gate so a synthetic two-frame change reliably fires in tests.
settings.mock_mode = True
settings.change_threshold = 0.005
settings.persistence_frames = 1
settings.cooldown_seconds = 0.0
# Tests send frames back-to-back; disable ingest sampling interference (0 = unlimited).
settings.ingest_max_fps = 0.0
settings.vlm_main_max_side = 512
settings.vlm_context_max_side = 256
settings.vlm_crop_max_side = 256
# Fast baselines in tests: 1 settled frame finalizes immediately.
settings.baseline_warmup_frames = 1
settings.baseline_warmup_seconds = 0.0
settings.baseline_settled_threshold = 0.5
settings.baseline_settled_frames = 1
settings.baseline_max_wait_seconds = 0.0
settings.baseline_context_frames = 2
settings.baseline_max_attempts = 3
settings.baseline_retry_cooldown_seconds = 0.0


@pytest.fixture(autouse=True)
def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    db_session.reset_engine_for_tests(engine)
    db_session.create_all(engine)
    yield engine


@pytest.fixture(autouse=True)
def _camera_manager_reset():
    from backend.app.cameras.manager import manager

    manager.reset_for_tests()
    yield
    manager.reset_for_tests()


@pytest.fixture()
def client():
    from backend.app.api import deps
    from backend.app.main import app

    deps.set_vision_provider(MockVisionProvider())
    deps.set_chat_provider(MockChatProvider())
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def vision_provider():
    return MockVisionProvider()


@pytest.fixture()
def chat_provider():
    return MockChatProvider()


def auth(user: str = "user-a") -> dict:
    return {"Authorization": f"Bearer mock:{user}"}


def make_frame(shift: int = 0) -> np.ndarray:
    """Simple synthetic frame; shifting a block changes the gate score."""
    img = np.full((240, 320, 3), 40, np.uint8)
    img[80:160, 40 + shift : 120 + shift] = (0, 200, 0)
    return img


def frame_bytes(shift: int = 0) -> bytes:
    import cv2

    ok, buf = cv2.imencode(".jpg", make_frame(shift))
    assert ok
    return bytes(buf)


def create_camera(client, name: str = "Desk cam", user: str = "user-a") -> str:
    res = client.post("/api/cameras", json={"name": name}, headers=auth(user))
    assert res.status_code == 201, res.text
    return res.json()["id"]
