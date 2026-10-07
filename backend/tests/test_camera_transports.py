"""Unit tests: MJPEG parsing, ONVIF (mocked transport), NVR expansion, pairing, gateway."""

from __future__ import annotations

import pytest

from backend.app.cameras.gateway import GatewayError, GatewayRegistry
from backend.app.cameras.mjpeg import (
    extract_jpeg,
    parse_content_type_boundary,
    split_mjpeg_chunks,
)
from backend.app.cameras.nvr import NvrChannel, NvrSpec, expand_nvr_channels
from backend.app.cameras.onvif import (
    OnvifClient,
    _parse_probe_match,
    ws_discovery_probe,
)
from backend.app.cameras.pairing import PairingError, PairingStore


def _jpeg_bytes() -> bytes:
    import cv2
    import numpy as np

    img = np.full((48, 64, 3), 90, np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return bytes(buf)


def _part(jpeg: bytes, boundary: bytes = b"frame") -> bytes:
    return (
        b"--"
        + boundary
        + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
        + str(len(jpeg)).encode()
        + b"\r\n\r\n"
        + jpeg
        + b"\r\n"
    )


# -------------------------------------------------------------------- MJPEG
def test_split_chunks_and_extract():
    jpeg = _jpeg_bytes()
    stream = _part(jpeg) + _part(jpeg) + b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
    parts, rest = split_mjpeg_chunks(stream, b"frame")
    assert len(parts) == 2
    assert extract_jpeg(parts[0]) is not None
    assert rest.startswith(b"--frame")


def test_extract_rejects_malformed():
    assert extract_jpeg(b"no headers here") is None
    assert extract_jpeg(b"--frame\r\n\r\n" + b"\x00" * 200) is None  # no SOI/EOI
    assert extract_jpeg(b"--frame\r\n\r\n" + b"x" * 10) is None  # too small


def test_boundary_parsing():
    assert (
        parse_content_type_boundary("multipart/x-mixed-replace; boundary=frame")
        == b"frame"
    )
    assert parse_content_type_boundary('multipart; boundary="my-bound"') == b"my-bound"
    assert parse_content_type_boundary("text/html") is None


# -------------------------------------------------------------------- ONVIF
PROBE_MATCH = (
    b'<?xml version="1.0"?>'
    b'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
    b'xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery">'
    b"<s:Body><wsd:ProbeMatches><wsd:ProbeMatch>"
    b"<wsd:XAddrs>http://192.168.1.20/onvif/device_service http://[fe80::1]/x</wsd:XAddrs>"
    b"<wsd:Scopes>onvif://www.onvif.org/name/Cam1</wsd:Scopes>"
    b"</wsd:ProbeMatch></wsd:ProbeMatches></s:Body></s:Envelope>"
)


def test_probe_match_parsing():
    d = _parse_probe_match(PROBE_MATCH)
    assert (
        d is not None
        and d.device_service_url == "http://192.168.1.20/onvif/device_service"
    )
    assert _parse_probe_match(b"garbage") is None
    assert _parse_probe_match(b"<s:Envelope/>") is None


def _fake_post_factory():
    def post(url, envelope, action):
        if "GetCapabilities" in action:
            return (
                "<s:Envelope xmlns:s='http://www.w3.org/2003/05/soap-envelope'>"
                "<s:Body><tds:GetCapabilitiesResponse xmlns:tds='http://www.onvif.org/ver10/device/wsdl'>"
                "<tds:Capabilities><tds:Media><tds:XAddr>http://192.168.1.20/onvif/media</tds:XAddr>"
                "</tds:Media></tds:Capabilities></tds:GetCapabilitiesResponse></s:Body></s:Envelope>"
            )
        if "GetProfiles" in action:
            return (
                "<s:Envelope xmlns:s='http://www.w3.org/2003/05/soap-envelope'>"
                "<s:Body><trt:GetProfilesResponse xmlns:trt='http://www.onvif.org/ver10/media/wsdl'>"
                "<trt:Profiles token='p0'><trt:Name>main</trt:Name></trt:Profiles>"
                "<trt:Profiles token='p1'><trt:Name>sub</trt:Name></trt:Profiles>"
                "</trt:GetProfilesResponse></s:Body></s:Envelope>"
            )
        if "GetStreamUri" in action:
            assert "<trt:ProfileToken>p0</trt:ProfileToken>" in envelope
            return (
                "<s:Envelope xmlns:s='http://www.w3.org/2003/05/soap-envelope'>"
                "<s:Body><trt:GetStreamUriResponse xmlns:trt='http://www.onvif.org/ver10/media/wsdl'>"
                "<trt:Uri>rtsp://192.168.1.20:554/live0</trt:Uri>"
                "</trt:GetStreamUriResponse></s:Body></s:Envelope>"
            )
        raise AssertionError(f"unexpected action {action}")

    return post


def test_onvif_resolve_path_mocked():
    client = OnvifClient(
        "http://192.168.1.20/onvif/device_service", post=_fake_post_factory()
    )
    stream = client.resolve_first_rtsp()
    assert stream.rtsp_url == "rtsp://192.168.1.20:554/live0"
    assert stream.profile_token == "p0"


def test_onvif_auth_and_malformed():
    def auth_fail(url, envelope, action):
        raise PermissionError("onvif authentication failed (401/403)")

    with pytest.raises(PermissionError):
        OnvifClient("http://h/x", post=auth_fail).get_capabilities()

    def garbage(url, envelope, action):
        return "not xml at all <<<"

    with pytest.raises(ValueError):
        OnvifClient("http://h/x", post=garbage).get_capabilities()


def test_discovery_probe_handles_no_network_gracefully():
    # Must never raise on machines without multicast; may return [].
    assert isinstance(ws_discovery_probe(timeout_s=0.2), list)


# ---------------------------------------------------------------------- NVR
def test_nvr_channel_expansion():
    spec = NvrSpec(
        name="ShopNVR",
        host="192.168.1.50",
        username="admin",
        password="pw",
        channels=[NvrChannel(1, "Door"), NvrChannel(2, url="rtsp://other/x")],
    )
    cams = expand_nvr_channels(spec, "u1")
    assert len(cams) == 2
    assert all(c["source_type"] == "rtsp" for c in cams)
    assert (
        "192.168.1.50" in cams[0]["config"]["url"] and cams[0]["config"]["channel"] == 1
    )
    assert cams[1]["config"]["url"] == "rtsp://other/x"


# ------------------------------------------------------------------- pairing
def test_pairing_create_claim_replay_rejected():
    now = [1000.0]
    store = PairingStore(ttl_seconds=60.0, time_fn=lambda: now[0])
    s = store.create("u1", "cam1")
    assert s.status.value == "pending"
    claimed = store.claim(s.code, "u1")
    assert claimed.status.value == "paired"
    with pytest.raises(PairingError):  # replay rejected (single-use)
        store.claim(s.code, "u1")


def test_pairing_expiry_and_cross_user_and_revoke():
    now = [1000.0]
    store = PairingStore(ttl_seconds=60.0, time_fn=lambda: now[0])
    s = store.create("u1", "cam1")
    with pytest.raises(PairingError):
        store.claim(s.code, "intruder")  # wrong user
    now[0] += 61.0
    with pytest.raises(PairingError):
        store.claim(s.code, "u1")  # expired
    assert store.status(s.code).value == "expired"
    s2 = store.create("u1", "cam2")
    assert store.revoke("u1", s2.code) is True
    assert store.revoke("u1", "nope") is False
    with pytest.raises(PairingError):
        store.claim(s2.code, "u1")  # revoked


# ------------------------------------------------------------------- gateway
def test_gateway_register_auth_attach_revoke():
    reg = GatewayRegistry()
    g = reg.register("u1", "shop-gw")
    assert g.token.startswith("gw_")
    assert reg.authenticate(g.token).gateway_id == g.gateway_id
    with pytest.raises(GatewayError):
        reg.authenticate("bogus")
    reg.attach_camera(g.gateway_id, "ch1", "cam-1", "u1")
    assert reg.resolve_camera(g.gateway_id, "ch1") == "cam-1"
    assert reg.resolve_camera(g.gateway_id, "nope") is None
    with pytest.raises(GatewayError):
        reg.attach_camera(g.gateway_id, "ch2", "cam-2", "other-user")
    assert reg.revoke("u1", g.gateway_id) is True
    assert reg.revoke("u1", g.gateway_id) is False
