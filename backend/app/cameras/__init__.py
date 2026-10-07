"""Cameras package: base source abstraction, manager, browser/RTSP adapters."""

from backend.app.cameras.base import (  # noqa: F401
    BrowserCameraSource,
    CameraHealth,
    CameraMetadata,
    CameraSource,
    RTSPCameraSource,
    build_camera_source,
)
from backend.app.cameras.manager import CameraManager, CameraRuntime, manager  # noqa: F401
