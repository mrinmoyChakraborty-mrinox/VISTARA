"""ONVIF discovery endpoint (server must see the LAN for results).

POST /api/discovery/onvif {timeout_s?, resolve_streams?, username?, password?}
  -> {devices: [{device_service_url, scopes, stream_url?, profile?, error?}]}

Credentials are accepted per-request, used once, and never stored or logged.
Discovery only finds devices visible from the server's network.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.cameras.onvif import OnvifClient, ws_discovery_probe
from backend.app.cameras.security import redact_url
from backend.app.core.logging import log_event
from backend.app.core.security import CurrentUser, require_user

router = APIRouter(tags=["discovery"])


class OnvifDiscoverIn(BaseModel):
    timeout_s: float = 4.0
    resolve_streams: bool = True
    username: str | None = None
    password: str | None = None


@router.post("/api/discovery/onvif")
async def discover_onvif(
    body: OnvifDiscoverIn, user: CurrentUser = Depends(require_user)
):
    timeout_s = min(max(body.timeout_s, 1.0), 15.0)
    devices = await asyncio.to_thread(ws_discovery_probe, timeout_s)
    log_event(
        "onvif_discovery",
        status="ok",
        user_id=user.id,
        extra={"devices": len(devices)},
    )
    out = []
    for device in devices:
        entry: dict = {
            "device_service_url": device.device_service_url,
            "scopes": device.scopes,
        }
        if body.resolve_streams:
            try:
                client = OnvifClient(
                    device.device_service_url,
                    username=body.username,
                    password=body.password,
                    timeout_s=8.0,
                )
                stream = await asyncio.to_thread(client.resolve_first_rtsp)
                entry["stream_url"] = redact_url(stream.rtsp_url)
                entry["profile_token"] = stream.profile_token
            except Exception as exc:  # noqa: BLE001 - per-device isolation
                entry["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        out.append(entry)
    return {"devices": out}
