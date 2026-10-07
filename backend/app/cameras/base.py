"""Camera source abstraction: one ABC, explicit lifecycle, health + metrics.

Lifecycle: CREATED -> CONNECTING -> CONNECTED -> RUNNING -> (DEGRADED) -> STOPPING -> STOPPED
                                        --> RECONNECTING -/                    --> FAILED

Push sources (browser/phone/gateway) receive frames via WebSocket; pull sources
(RTSP/HLS/MJPEG) implement read_frame(). The perception pipeline only consumes
NormalizedFrame and never knows the source type.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from backend.app.cameras.frames import NormalizedFrame


class CameraLifecycle(str, Enum):
    CREATED = "created"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RUNNING = "running"
    DEGRADED = "degraded"
    RECONNECTING = "reconnecting"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


# Allowed transitions; anything else raises LifecycleError (no silent inconsistency).
_TRANSITIONS: dict[CameraLifecycle, set[CameraLifecycle]] = {
    CameraLifecycle.CREATED: {CameraLifecycle.CONNECTING, CameraLifecycle.STOPPED},
    CameraLifecycle.CONNECTING: {
        CameraLifecycle.CONNECTED,
        CameraLifecycle.FAILED,
        CameraLifecycle.STOPPING,
    },
    CameraLifecycle.CONNECTED: {
        CameraLifecycle.RUNNING,
        CameraLifecycle.RECONNECTING,
        CameraLifecycle.STOPPING,
        CameraLifecycle.FAILED,
    },
    CameraLifecycle.RUNNING: {
        CameraLifecycle.DEGRADED,
        CameraLifecycle.RECONNECTING,
        CameraLifecycle.STOPPING,
        CameraLifecycle.FAILED,
    },
    CameraLifecycle.DEGRADED: {
        CameraLifecycle.RUNNING,
        CameraLifecycle.RECONNECTING,
        CameraLifecycle.STOPPING,
        CameraLifecycle.FAILED,
    },
    CameraLifecycle.RECONNECTING: {
        CameraLifecycle.CONNECTED,
        CameraLifecycle.FAILED,
        CameraLifecycle.STOPPING,
    },
    CameraLifecycle.FAILED: {CameraLifecycle.CONNECTING, CameraLifecycle.STOPPING},
    CameraLifecycle.STOPPING: {CameraLifecycle.STOPPED},
    CameraLifecycle.STOPPED: {CameraLifecycle.CONNECTING},
}


class LifecycleError(RuntimeError):
    pass


@dataclass
class CameraMetadata:
    id: str
    user_id: str
    name: str
    source_type: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceCapabilities:
    provides_audio: bool = False
    supports_ptz: bool = False
    max_width: int = 0
    max_height: int = 0
    notes: str = ""


@dataclass
class SourceMetrics:
    frames_received: int = 0
    frames_dropped: int = 0
    reconnect_count: int = 0
    last_frame_at: datetime | None = None
    last_successful_read_at: datetime | None = None
    last_error: str = ""


@dataclass
class CameraHealth:
    connected: bool
    status: str  # lifecycle value
    last_frame_at: datetime | None = None
    detail: str = ""
    metrics: SourceMetrics | None = None


class CameraSource(ABC):
    """A logical camera source (one camera_id, one lifecycle, one health)."""

    source_kind: str = "unknown"

    def __init__(self, metadata: CameraMetadata):
        self.metadata = metadata
        self.lifecycle = CameraLifecycle.CREATED
        self.metrics = SourceMetrics()
        self.capabilities = SourceCapabilities()
        self._connected = False
        self._last_frame_at: datetime | None = None

    # ------------------------------------------------------------ lifecycle
    def transition(self, target: CameraLifecycle) -> None:
        allowed = _TRANSITIONS.get(self.lifecycle, set())
        if target not in allowed:
            raise LifecycleError(
                f"{self.lifecycle.value} -> {target.value} not allowed"
            )
        self.lifecycle = target
        self._connected = target in (
            CameraLifecycle.CONNECTED,
            CameraLifecycle.RUNNING,
            CameraLifecycle.DEGRADED,
        )

    def connect(self) -> None:
        """Establish the source (idempotent from CREATED/STOPPED/FAILED)."""
        if self.lifecycle in (CameraLifecycle.CONNECTED, CameraLifecycle.RUNNING):
            return
        self.transition(CameraLifecycle.CONNECTING)
        try:
            self._do_connect()
        except LifecycleError:
            raise
        except Exception as exc:  # noqa: BLE001
            self.metrics.last_error = str(exc)[:300]
            try:
                self.transition(CameraLifecycle.FAILED)
            except LifecycleError:
                pass
            raise

    def close(self) -> None:
        """Release all source resources (processes, sockets). Never raises."""
        try:
            self._do_close()
        except Exception:  # noqa: BLE001 - close must not raise
            pass

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    def reconnect(self) -> None:
        """Immediate reconnect attempt (caller owns backoff)."""
        self.close()
        if self.lifecycle == CameraLifecycle.CREATED:
            self.transition(CameraLifecycle.CONNECTING)
        elif self.lifecycle != CameraLifecycle.RECONNECTING:
            try:
                self.transition(CameraLifecycle.RECONNECTING)
            except LifecycleError:
                pass
        self.metrics.reconnect_count += 1
        self.connect()

    # ------------------------------------------------------------- override
    def _do_connect(self) -> None:
        self.transition(CameraLifecycle.CONNECTED)

    def _do_close(self) -> None:
        return None

    def read_frame(self) -> NormalizedFrame | None:
        """Pull sources override this. Push sources return None (frames arrive via WS)."""
        return None

    # ---------------------------------------------------------------- health
    def health(self) -> CameraHealth:
        return CameraHealth(
            connected=self._connected,
            status=self.lifecycle.value,
            last_frame_at=self._last_frame_at,
            detail=self.metrics.last_error,
            metrics=self.metrics,
        )

    def metadata_dict(self) -> dict[str, Any]:
        from backend.app.cameras.security import sanitize_config_for_api

        return {
            "id": self.metadata.id,
            "user_id": self.metadata.user_id,
            "name": self.metadata.name,
            "source_type": self.metadata.source_type,
            "config": sanitize_config_for_api(self.metadata.config),
        }

    # ------------------------------------------------- backward-compat hooks
    def mark_connected(self) -> None:
        for target in (CameraLifecycle.CONNECTING, CameraLifecycle.CONNECTED):
            try:
                self.transition(target)
            except LifecycleError:
                continue
        self._connected = True
        self._last_frame_at = datetime.now(timezone.utc)

    def mark_disconnected(self) -> None:
        try:
            if self.lifecycle not in (
                CameraLifecycle.STOPPED,
                CameraLifecycle.STOPPING,
            ):
                self.transition(CameraLifecycle.STOPPING)
                self.transition(CameraLifecycle.STOPPED)
        except LifecycleError:
            self._connected = False

    def note_frame(self) -> None:
        now = datetime.now(timezone.utc)
        self._last_frame_at = now
        self.metrics.last_frame_at = now
        self.metrics.last_successful_read_at = now
        self.metrics.frames_received += 1

    def note_dropped(self, count: int = 1) -> None:
        self.metrics.frames_dropped += count

    def note_error(self, message: str) -> None:
        self.metrics.last_error = message[:300]


class PushCameraSource(CameraSource):
    """Frames arrive over an authenticated WebSocket (browser/phone/gateway)."""

    def start(self) -> None:
        self.mark_connected()

    def stop(self) -> None:
        self.mark_disconnected()


class BrowserCameraSource(PushCameraSource):
    source_kind = "browser"


class PhoneCameraSource(PushCameraSource):
    """Phone browser paired via QR; identical transport to desktop browser."""

    source_kind = "phone"
