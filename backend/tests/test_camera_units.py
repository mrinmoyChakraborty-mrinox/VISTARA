"""Unit tests: frames, security/SSRF, backoff, lifecycle, factory, transports."""

from __future__ import annotations

import numpy as np
import pytest

from backend.app.cameras.base import (
    BrowserCameraSource,
    CameraLifecycle,
    CameraMetadata,
    LifecycleError,
)
from backend.app.cameras.factory import create_source, registered_types
from backend.app.cameras.frames import (
    FrameValidationError,
    make_normalized_frame,
    validate_frame_array,
)
from backend.app.cameras.reconnect import BackoffPolicy, backoff_schedule
from backend.app.cameras.security import (
    StreamURLRejected,
    redact_url,
    sanitize_config_for_api,
    validate_stream_url,
)


def _meta(**kw):
    base = {"id": "c1", "user_id": "u1", "name": "C", "source_type": "browser"}
    base.update(kw)
    return CameraMetadata(**base)


def _bgr(w=320, h=240):
    return np.full((h, w, 3), 40, np.uint8)


# ------------------------------------------------------------------- frames
def test_validate_frame_ok():
    assert validate_frame_array(_bgr()) == (320, 240)


def test_validate_frame_rejects_bad_shapes():
    with pytest.raises(FrameValidationError):
        validate_frame_array(np.zeros((10, 10), np.uint8))
    with pytest.raises(FrameValidationError):
        validate_frame_array(np.zeros((0, 10, 3), np.uint8))
    with pytest.raises(FrameValidationError):
        validate_frame_array(np.zeros((10, 10, 3), dtype=np.float32))
    with pytest.raises(FrameValidationError):
        validate_frame_array(_bgr(5000, 10), max_dim=4096)


def test_make_normalized_frame_carries_provenance():
    f = make_normalized_frame("cam", _bgr(), seq=7, source_metadata={"kind": "browser"})
    assert f.camera_id == "cam" and f.seq == 7 and f.width == 320


# ------------------------------------------------------------------- security
def test_ssrf_blocks_by_default():
    for bad in [
        "rtsp://localhost:554/x",
        "rtsp://127.0.0.1/x",
        "rtsp://192.168.1.10/x",
        "rtsp://10.0.0.5/x",
        "http://169.254.169.254/latest",
        "file:///etc/passwd",
        "gopher://x/y",
        "",
        "not a url",
    ]:
        with pytest.raises(StreamURLRejected):
            validate_stream_url(bad)


def test_ssrf_allows_public_and_opt_in_private():
    assert validate_stream_url("rtsp://camera.example.com:554/stream")
    assert validate_stream_url("https://example.com/live.m3u8")
    assert validate_stream_url("rtsp://192.168.1.10/x", allow_private_networks=True)
    # Metadata endpoints are never allowed, even with opt-in.
    with pytest.raises(StreamURLRejected):
        validate_stream_url("http://169.254.169.254/", allow_private_networks=True)


def test_redact_url_never_leaks_password():
    red = redact_url("rtsp://admin:s3cret@192.168.1.10:554/stream")
    assert "s3cret" not in red and "admin" in red and ":***@" in red
    assert redact_url("rtsp://host/x") == "rtsp://host/x"
    assert sanitize_config_for_api({"url": "rtsp://a:b@h/x", "fps": 2})["url"].endswith(
        "/x"
    )


# ------------------------------------------------------------------- backoff
def test_backoff_schedule_bounded():
    assert backoff_schedule(steps=6) == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0]
    assert backoff_schedule(steps=8)[-1] == 30.0  # capped, never infinite growth


def test_backoff_resets_after_success():
    p = BackoffPolicy()
    p.next_delay()
    p.next_delay()
    p.reset()
    assert p.attempt == 0


# ------------------------------------------------------------------- lifecycle
def test_lifecycle_valid_path():
    src = BrowserCameraSource(_meta())
    assert src.lifecycle == CameraLifecycle.CREATED
    src.connect()  # push sources connect trivially
    assert src.lifecycle == CameraLifecycle.CONNECTED
    src.start()
    src.stop()
    assert src.lifecycle == CameraLifecycle.STOPPED


def test_lifecycle_rejects_inconsistent_transitions():
    src = BrowserCameraSource(_meta())
    with pytest.raises(LifecycleError):
        src.transition(CameraLifecycle.RUNNING)  # CREATED -> RUNNING illegal


def test_health_reflects_lifecycle_and_metrics():
    src = BrowserCameraSource(_meta())
    src.start()
    src.note_frame()
    src.note_dropped(2)
    h = src.health()
    assert h.metrics.frames_received == 1 and h.metrics.frames_dropped == 2


# ------------------------------------------------------------------- factory
def test_factory_registry():
    assert {"browser", "phone", "rtsp", "hls", "mjpeg"} <= set(registered_types())
    assert create_source("c", "u", "n", "browser").source_kind == "browser"
    assert create_source("c", "u", "n", "phone").source_kind == "phone"
    assert (
        create_source("c", "u", "n", "RTSP", {"url": "rtsp://h/x"}).source_kind
        == "rtsp"
    )
    with pytest.raises(ValueError):
        create_source("c", "u", "n", "nope")
