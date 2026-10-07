"""HLS source over the same FFmpeg pull transport.

HLS is NOT treated as raw image files. ffmpeg handles segment polling; the
reader surfaces stale playlists as read timeouts, which the pull loop turns
into DEGRADED + reconnect. Playlist URLs go through the same SSRF policy.
"""

from __future__ import annotations

from backend.app.cameras.rtsp import RTSPCameraSource


class HLSCameraSource(RTSPCameraSource):
    source_kind = "hls"

    def _extra_input(self) -> list[str]:
        # Fail fast on playlist HTTP errors instead of hanging on stale playlists.
        return ["-http_seekable", "0"]

    def _do_connect(self) -> None:
        super()._do_connect()
        self.capabilities.notes = f"hls via ffmpeg ({self.redacted_url})"
