"""ONVIF real-device smoke test (Phase: camera hardening).

Probes the LOCAL network for ONVIF devices and, for each one found, resolves
capabilities -> profiles -> RTSP stream URI. Credentials are taken from env
(ONVIF_USER / ONVIF_PASSWORD), used once, never stored or logged.

Usage:
    $env:ONVIF_USER='admin'; $env:ONVIF_PASSWORD='...'
    python scripts/onvif_smoke.py [--timeout 6] [--no-resolve]

Exit 0 always (this is discovery diagnostics, not CI); prints what it found.
No physical camera is required for CI — this script is for on-site validation.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.cameras.onvif import OnvifClient, ws_discovery_probe
from backend.app.cameras.security import redact_url


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=6.0)
    ap.add_argument("--no-resolve", action="store_true")
    args = ap.parse_args()

    print(f"probing for ONVIF devices (timeout={args.timeout}s) ...")
    devices = ws_discovery_probe(timeout_s=args.timeout)
    print(f"found {len(devices)} device(s)")
    user = os.getenv("ONVIF_USER") or None
    for d in devices:
        print(f"  - {d.device_service_url}")
        if d.scopes:
            print(f"    scopes: {' '.join(d.scopes[:6])}")
        if args.no_resolve:
            continue
        try:
            stream = OnvifClient(
                d.device_service_url,
                username=user,
                password=os.getenv("ONVIF_PASSWORD"),
            ).resolve_first_rtsp()
            print(
                f"    rtsp: {redact_url(stream.rtsp_url)} (profile {stream.profile_token})"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"    resolve failed: {type(exc).__name__}: {str(exc)[:150]}")
    if not devices:
        print("no ONVIF devices visible from this host/network.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
