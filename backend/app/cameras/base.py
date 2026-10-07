"""Camera source abstraction + browser/RTSP implementations/placeholders."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CameraMetadata:
    id: str
    user_id: str
    name: str
    source_type: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class CameraHealth:
    connected: bool
    status: str
    last_frame_at: datetime | None = None
    detail: str = ""


class CameraSource(ABC):
    """A logical camera source. Browser frames arrive via WebSocket; RTSP later."""

    def __init__(self, metadata: CameraMetadata):
        self.metadata = metadata
        self._connected = False
        self._last_frame_at: datetime | None = None

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    def health(self) -> CameraHealth:
        return CameraHealth(
            connected=self._connected,
            status="active" if self._connected else "idle",
            last_frame_at=self._last_frame_at,
        )

    def metadata_dict(self) -> dict[str, Any]:
        return {
            "id": self.metadata.id,
            "user_id": self.metadata.user_id,
            "name": self.metadata.name,
            "source_type": self.metadata.source_type,
            "config": self.metadata.config,
        }

    def mark_connected(self) -> None:
        self._connected = True
        self._last_frame_at = datetime.now(timezone.utc)

    def mark_disconnected(self) -> None:
        self._connected = False

    def note_frame(self) -> None:
        self._last_frame_at = datetime.now(timezone.utc)


class BrowserCameraSource(CameraSource):
    """Camera whose frames are pushed by the browser over a WebSocket."""

    def start(self) -> None:
        self._connected = True

    def stop(self) -> None:
        self._connected = False


class RTSPCameraSource(CameraSource):
    """Placeholder for future RTSP support. Not implemented for the MVP."""

    def start(self) -> None:
        raise NotImplementedError("RTSP camera support is out of scope for the MVP.")

    def stop(self) -> None:
        raise NotImplementedError("RTSP camera support is out of scope for the MVP.")


def build_camera_source(
    camera_id: str,
    user_id: str,
    name: str,
    source_type: str,
    config: dict | None = None,
) -> CameraSource:
    meta = CameraMetadata(
        id=camera_id,
        user_id=user_id,
        name=name,
        source_type=source_type,
        config=config or {},
    )
    if source_type == "rtsp":
        return RTSPCameraSource(meta)
    return BrowserCameraSource(meta)
