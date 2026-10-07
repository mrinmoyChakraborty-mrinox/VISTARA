"""ONVIF discovery/control layer (stdlib sockets + httpx, no new dependencies).

Responsibilities (and ONLY these):
- WS-Discovery probe over UDP multicast -> device service URLs.
- GetDeviceInformation / GetCapabilities / GetProfiles / GetStreamUri via SOAP.
- Return a usable RTSP media URI + capabilities.

ONVIF never decodes frames. The result feeds RTSPCameraSource via the factory.

All network operations have timeouts; unreachable devices, auth failures and
malformed responses are returned as structured errors, never raised into callers
that iterate many devices. Discovered credentials are never logged.
"""

from __future__ import annotations

import socket
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

NS = {
    "s": "http://www.w3.org/2003/05/soap-envelope",
    "tds": "http://www.onvif.org/ver10/device/wsdl",
    "trt": "http://www.onvif.org/ver10/media/wsdl",
    "tt": "http://www.onvif.org/ver10/schema",
    "wsd": "http://schemas.xmlsoap.org/ws/2005/04/discovery",
    "wsa": "http://schemas.xmlsoap.org/ws/2004/08/addressing",
}

WS_DISCOVERY_MULTICAST = "239.255.255.250"
WS_DISCOVERY_PORT = 3702


@dataclass
class DiscoveredDevice:
    device_service_url: str
    scopes: list[str] = field(default_factory=list)
    types: list[str] = field(default_factory=list)


@dataclass
class MediaProfile:
    token: str
    name: str = ""


@dataclass
class StreamInfo:
    rtsp_url: str
    profile_token: str


@dataclass
class OnvifError:
    device: str
    stage: str
    message: str


def ws_discovery_probe(timeout_s: float = 4.0) -> list[DiscoveredDevice]:
    """UDP multicast WS-Discovery probe. Returns responding device service URLs."""
    msg_id = f"uuid:{uuid.uuid4()}"
    probe = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
        'xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing" '
        'xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery" '
        'xmlns:tdn="http://www.onvif.org/ver10/network/wsdl">'
        "<s:Header>"
        f"<wsa:MessageID>{msg_id}</wsa:MessageID>"
        "<wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>"
        "<wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>"
        "</s:Header><s:Body><wsd:Probe><wsd:Types>tdn:NetworkVideoTransmitter</wsd:Types>"
        "</wsd:Probe></s:Body></s:Envelope>"
    ).encode()
    found: list[DiscoveredDevice] = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(timeout_s)
        try:
            sock.sendto(probe, (WS_DISCOVERY_MULTICAST, WS_DISCOVERY_PORT))
        except OSError:
            return []
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                data, _ = sock.recvfrom(65535)
            except socket.timeout:
                break
            except OSError:
                break
            device = _parse_probe_match(data)
            if device is not None:
                found.append(device)
    finally:
        sock.close()
    # Deduplicate by URL.
    seen: dict[str, DiscoveredDevice] = {}
    for d in found:
        seen.setdefault(d.device_service_url, d)
    return list(seen.values())


def _parse_probe_match(data: bytes) -> DiscoveredDevice | None:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    ns = {"s": NS["s"], "wsd": NS["wsd"]}
    xaddrs = root.find(".//wsd:ProbeMatch/wsd:XAddrs", ns)
    if xaddrs is None or not (xaddrs.text or "").strip():
        return None
    url = xaddrs.text.strip().split()[0]
    scopes_el = root.findall(".//wsd:ProbeMatch/wsd:Scopes", ns)
    scopes = " ".join((el.text or "") for el in scopes_el).split()
    return DiscoveredDevice(device_service_url=url, scopes=scopes)


def _soap_envelope(
    body: str, username: str | None = None, password: str | None = None
) -> str:
    header = ""
    if username:
        import base64
        import datetime
        import hashlib
        import os

        nonce = base64.b64encode(os.urandom(16)).decode()
        created = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        digest = base64.b64encode(
            hashlib.sha1(
                (
                    nonce.encode()
                    and base64.b64decode(nonce)
                    + created.encode()
                    + (password or "").encode()
                )
            ).digest()
        ).decode()
        header = (
            "<s:Header><wsse:Security xmlns:wsse="
            '"http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">'
            f"<wsse:UsernameToken><wsse:Username>{username}</wsse:Username>"
            f"<wsse:Password Type='http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest'>{digest}</wsse:Password>"
            f"<wsse:Nonce>{nonce}</wsse:Nonce>"
            f"<wsu:Created xmlns:wsu='http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd'>{created}</wsu:Created>"
            "</wsse:UsernameToken></wsse:Security></s:Header>"
        )
    return (
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
        f"{header}<s:Body>{body}</s:Body></s:Envelope>"
    )


class OnvifClient:
    """Minimal device+media ONVIF client. Transport-injectable for tests."""

    def __init__(
        self,
        device_service_url: str,
        username: str | None = None,
        password: str | None = None,
        timeout_s: float = 8.0,
        post=None,
    ):
        self.device_service_url = device_service_url
        self.username = username
        self.password = password
        self.timeout_s = timeout_s
        self._post = post  # (url, envelope, action) -> response text (tests)
        self.media_service_url: str | None = None

    def _call(self, url: str, body: str, action: str) -> ET.Element:
        envelope = _soap_envelope(body, self.username, self.password)
        if self._post is not None:
            text = self._post(url, envelope, action)
        else:
            import httpx

            headers = {
                "Content-Type": "application/soap+xml; charset=utf-8",
                "SOAPAction": action,
            }
            try:
                resp = httpx.post(
                    url, content=envelope, headers=headers, timeout=self.timeout_s
                )
            except Exception as exc:
                raise ConnectionError(f"onvif transport failed: {exc}") from exc
            if resp.status_code in (401, 403):
                raise PermissionError("onvif authentication failed (401/403)")
            if resp.status_code >= 400:
                raise ConnectionError(f"onvif http {resp.status_code}")
            text = resp.text
        try:
            return ET.fromstring(text)
        except ET.ParseError as exc:
            raise ValueError(f"malformed onvif response: {exc}") from exc

    def get_capabilities(self) -> dict:
        root = self._call(
            self.device_service_url,
            '<tds:GetCapabilities xmlns:tds="http://www.onvif.org/ver10/device/wsdl"/>',
            "http://www.onvif.org/ver10/device/wsdl/GetCapabilities",
        )
        media = root.find(
            ".//{http://www.onvif.org/ver10/device/wsdl}Capabilities/{http://www.onvif.org/ver10/device/wsdl}Media/{http://www.onvif.org/ver10/device/wsdl}XAddr"
        )
        if media is not None and (media.text or "").strip():
            self.media_service_url = media.text.strip()
        else:
            # Fall back: media service usually shares the device endpoint path.
            self.media_service_url = self.device_service_url
        return {"media_service_url": self.media_service_url}

    def get_profiles(self) -> list[MediaProfile]:
        url = self.media_service_url or self.device_service_url
        root = self._call(
            url,
            '<trt:GetProfiles xmlns:trt="http://www.onvif.org/ver10/media/wsdl"/>',
            "http://www.onvif.org/ver10/media/wsdl/GetProfiles",
        )
        profiles: list[MediaProfile] = []
        for p in root.findall(".//{http://www.onvif.org/ver10/media/wsdl}Profiles"):
            token = p.get("token", "")
            name_el = p.find("{http://www.onvif.org/ver10/media/wsdl}Name")
            profiles.append(
                MediaProfile(
                    token=token,
                    name=(name_el.text if name_el is not None else "") or "",
                )
            )
        return [p for p in profiles if p.token]

    def get_stream_uri(self, profile_token: str, protocol: str = "RTSP") -> StreamInfo:
        url = self.media_service_url or self.device_service_url
        body = (
            '<trt:GetStreamUri xmlns:trt="http://www.onvif.org/ver10/media/wsdl">'
            "<trt:StreamSetup><tt:Stream xmlns:tt='http://www.onvif.org/ver10/schema'>RTP-Unicast</tt:Stream>"
            f"<tt:Transport xmlns:tt='http://www.onvif.org/ver10/schema'><tt:Protocol>{protocol}</tt:Protocol></tt:Transport>"
            "</trt:StreamSetup>"
            f"<trt:ProfileToken>{profile_token}</trt:ProfileToken>"
            "</trt:GetStreamUri>"
        )
        root = self._call(
            url, body, "http://www.onvif.org/ver10/media/wsdl/GetStreamUri"
        )
        uri = root.find(".//{http://www.onvif.org/ver10/media/wsdl}Uri")
        if uri is None or not (uri.text or "").strip():
            raise ValueError("onvif returned no stream URI")
        return StreamInfo(rtsp_url=uri.text.strip(), profile_token=profile_token)

    def resolve_first_rtsp(self) -> StreamInfo:
        """Capabilities -> first profile -> RTSP URI. The standard resolve path."""
        self.get_capabilities()
        profiles = self.get_profiles()
        if not profiles:
            raise ValueError("onvif device returned no media profiles")
        return self.get_stream_uri(profiles[0].token)
