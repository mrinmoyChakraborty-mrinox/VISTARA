"""Camera connectivity security: SSRF policy + secret redaction.

SSRF POLICY (documented for operators):
- Stream URLs are untrusted user input. A malicious URL could target localhost,
  private ranges, or cloud metadata endpoints.
- Default stance is DENY-PRIVATE: loopback, link-local (incl. 169.254.169.254),
  and RFC1918/ULA ranges are rejected UNLESS explicitly allowed.
- Legitimate local cameras/NVRs live on private networks, so the policy is
  configurable: set CAMERAS_ALLOW_PRIVATE_NETWORKS=true when the deployment
  intentionally serves LAN cameras (typical self-hosted setup). Default false.
- Regardless of the flag, these are NEVER allowed: non-rtsp(s)/http(s) schemes
  (no file://, no gopher://, no ftp://), empty hosts, and URLs that fail to parse.
- Credentials embedded in RTSP URLs are NEVER logged (see redact_url); they are
  stored only inside the camera's server-side config, never returned to clients.

This module has no backend imports so tests stay light.
"""

from __future__ import annotations

import urllib.parse

ALLOWED_SCHEMES = {"rtsp", "rtsps", "http", "https"}

# Cloud metadata endpoints that must never be reachable via a camera URL.
METADATA_IPS = {
    "169.254.169.254",  # AWS/GCP/Azure metadata
    "100.100.100.200",  # Alibaba metadata
    "fd00:ec2::254",
}


class StreamURLRejected(ValueError):
    pass


def _host_is_ip(host: str):
    import ipaddress as _ip

    try:
        return _ip.ip_address(host.strip("[]"))
    except ValueError:
        return None


def validate_stream_url(url: str, allow_private_networks: bool = False) -> str:
    """Validate an operator/user-supplied stream URL. Returns the normalized URL.

    Raises StreamURLRejected for anything outside policy. Never logs the URL;
    callers must use redact_url() if they need observability.
    """
    if not url or not isinstance(url, str) or len(url) > 2048:
        raise StreamURLRejected("empty or oversized URL")
    try:
        parts = urllib.parse.urlsplit(url.strip())
    except ValueError as exc:
        raise StreamURLRejected(f"unparseable URL: {exc}") from exc

    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise StreamURLRejected(f"scheme not allowed: {scheme or '(none)'}")
    host = (parts.hostname or "").strip()
    if not host:
        raise StreamURLRejected("missing host")

    ip = _host_is_ip(host)
    if host.lower() in ("localhost",) or (
        ip is not None and (ip.is_loopback or ip.is_link_local)
    ):
        if not allow_private_networks:
            raise StreamURLRejected("loopback/link-local hosts require explicit opt-in")
    elif ip is not None and ip.is_private:
        if not allow_private_networks:
            raise StreamURLRejected("private-network hosts require explicit opt-in")
    if ip is not None and str(ip) in METADATA_IPS:
        raise StreamURLRejected("cloud metadata endpoints are never allowed")
    # Hostnames cannot be resolved here without DNS (avoid blocking); resolution-time
    # rebinding is accepted as residual risk and documented, since the deployment
    # either allows private networks explicitly or rejects them at connect time.
    return url.strip()


def redact_url(url: str) -> str:
    """Redact userinfo (credentials) from a URL for safe logging/API exposure."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return "<unparseable-url>"
    if not parts.username and not parts.password:
        return url
    netloc = parts.hostname or ""
    if parts.port:
        netloc += f":{parts.port}"
    who = parts.username or ""
    if parts.password:
        who += ":***"
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            f"{who}@{netloc}" if who else netloc,
            parts.path,
            parts.query,
            parts.fragment,
        )
    )


def sanitize_config_for_api(config: dict) -> dict:
    """Return a copy of camera config with credential-bearing URLs redacted."""
    out = dict(config or {})
    for key in ("url", "stream_url", "rtsp_url", "snapshot_url"):
        if isinstance(out.get(key), str):
            out[key] = redact_url(out[key])
    return out


def scrub_exceptions(text: str) -> str:
    """Scrub userinfo credentials out of an error string (library errors may embed URLs)."""
    import re

    return re.sub(r"://[^@\s/]+@", "://***@", text)
