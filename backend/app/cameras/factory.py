"""Source-type registry/factory. No if/else chains scattered through the app."""

from __future__ import annotations

from typing import Any, Callable

from backend.app.cameras.base import (
    BrowserCameraSource,
    CameraMetadata,
    CameraSource,
    PhoneCameraSource,
)

Factory = Callable[[CameraMetadata], CameraSource]

_REGISTRY: dict[str, Factory] = {}


def register(source_type: str, factory: Factory) -> None:
    _REGISTRY[source_type.lower()] = factory


def registered_types() -> list[str]:
    return sorted(_REGISTRY.keys())


def create_source(
    camera_id: str,
    user_id: str,
    name: str,
    source_type: str,
    config: dict[str, Any] | None = None,
) -> CameraSource:
    stype = (source_type or "browser").lower()
    factory = _REGISTRY.get(stype)
    if factory is None:
        raise ValueError(
            f"unknown camera source_type: {source_type!r} (known: {registered_types()})"
        )
    return factory(
        CameraMetadata(
            id=camera_id,
            user_id=user_id,
            name=name,
            source_type=stype,
            config=config or {},
        )
    )


def build_camera_source(
    camera_id: str,
    user_id: str,
    name: str,
    source_type: str,
    config: dict | None = None,
) -> CameraSource:
    """Backward-compatible alias for create_source."""
    return create_source(camera_id, user_id, name, source_type, config)


# Built-in push sources are always available (no native deps).
register("browser", BrowserCameraSource)
register("phone", PhoneCameraSource)


def _register_pull_sources() -> None:
    """Register network pull sources. Import here to keep base imports light."""
    from backend.app.cameras.hls import HLSCameraSource
    from backend.app.cameras.mjpeg import MJPEGCameraSource
    from backend.app.cameras.rtsp import RTSPCameraSource

    register("rtsp", RTSPCameraSource)
    register("rtsps", RTSPCameraSource)
    register("hls", HLSCameraSource)
    register("mjpeg", MJPEGCameraSource)


_register_pull_sources()
