"""Local camera gateway protocol (backend side).

The gateway runs on the LAN (near RTSP/NVR/ONVIF devices) and connects OUTBOUND
over secure WSS. No public RTSP exposure, no inbound cloud connections.

Backend responsibilities only:
- register a gateway for the authenticated user -> issue a gateway token
- accept the gateway's outbound WSS (token auth, user-scoped)
- accept per-camera registration + health reports from the gateway
- accept normalized frames tagged with the gateway's external camera id and map
  them to the user's logical camera_id
- track gateway connection state + reconnects

The gateway executable itself is out of scope; this is the cloud contract.
Token store is in-memory (single process); multi-process needs DB (documented).
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field


@dataclass
class GatewayRegistration:
    gateway_id: str
    user_id: str
    name: str
    token: str
    created_at: float
    last_seen_at: float | None = None
    connected: bool = False
    # external camera id (gateway-side) -> logical camera_id (backend-side)
    cameras: dict[str, str] = field(default_factory=dict)


class GatewayError(ValueError):
    pass


class GatewayRegistry:
    def __init__(self, time_fn=None):
        self._now = time_fn or time.monotonic
        self._by_token: dict[str, GatewayRegistration] = {}
        self._by_id: dict[str, GatewayRegistration] = {}

    def register(self, user_id: str, name: str) -> GatewayRegistration:
        import uuid

        gateway_id = f"gw_{uuid.uuid4().hex[:12]}"
        reg = GatewayRegistration(
            gateway_id=gateway_id,
            user_id=user_id,
            name=name,
            token="gw_" + secrets.token_urlsafe(32),
            created_at=self._now(),
        )
        self._by_token[reg.token] = reg
        self._by_id[reg.gateway_id] = reg
        return reg

    def authenticate(self, token: str) -> GatewayRegistration:
        reg = self._by_token.get(token or "")
        if reg is None:
            raise GatewayError("unknown gateway token")
        return reg

    def mark_connected(self, gateway_id: str) -> None:
        reg = self._by_id.get(gateway_id)
        if reg is not None:
            reg.connected = True
            reg.last_seen_at = self._now()

    def mark_disconnected(self, gateway_id: str) -> None:
        reg = self._by_id.get(gateway_id)
        if reg is not None:
            reg.connected = False

    def attach_camera(
        self, gateway_id: str, external_id: str, camera_id: str, user_id: str
    ) -> None:
        reg = self._by_id.get(gateway_id)
        if reg is None or reg.user_id != user_id:
            raise GatewayError("unknown gateway")
        reg.cameras[external_id] = camera_id

    def resolve_camera(self, gateway_id: str, external_id: str) -> str | None:
        reg = self._by_id.get(gateway_id)
        if reg is None:
            return None
        return reg.cameras.get(external_id)

    def revoke(self, user_id: str, gateway_id: str) -> bool:
        reg = self._by_id.get(gateway_id)
        if reg is None or reg.user_id != user_id:
            return False
        del self._by_token[reg.token]
        del self._by_id[gateway_id]
        return True


gateways = GatewayRegistry()
