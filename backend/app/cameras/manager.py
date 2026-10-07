"""In-memory registry of active camera sources + their rolling buffers/gates.

One process, one registry. The camera loop holds a reference so VLM inference
never blocks ingestion (perception work happens in the worker).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from backend.app.cameras.base import CameraSource, build_camera_source
from backend.app.perception.buffer import RollingBuffer
from backend.app.perception.gate import GateConfig, PerceptionGate


@dataclass
class CameraRuntime:
    source: CameraSource
    buffer: RollingBuffer
    gate: PerceptionGate
    event_queue: "asyncio.Queue" = field(default_factory=asyncio.Queue)
    task: "asyncio.Task | None" = None


class CameraManager:
    def __init__(self):
        self._runtimes: dict[str, CameraRuntime] = {}
        self._lock = asyncio.Lock()

    async def add(
        self,
        camera_id: str,
        user_id: str,
        name: str,
        source_type: str,
        config: dict | None,
        buffer_maxlen: int = 60,
        gate_config: GateConfig | None = None,
    ) -> CameraRuntime:
        async with self._lock:
            source = build_camera_source(camera_id, user_id, name, source_type, config)
            runtime = CameraRuntime(
                source=source,
                buffer=RollingBuffer(maxlen=buffer_maxlen),
                gate=PerceptionGate(gate_config),
            )
            self._runtimes[camera_id] = runtime
            return runtime

    def get(self, camera_id: str) -> CameraRuntime | None:
        return self._runtimes.get(camera_id)

    def require_owned(self, camera_id: str, user_id: str) -> CameraRuntime | None:
        runtime = self._runtimes.get(camera_id)
        if runtime is None or runtime.source.metadata.user_id != user_id:
            return None
        return runtime

    async def remove(self, camera_id: str) -> None:
        async with self._lock:
            runtime = self._runtimes.pop(camera_id, None)
        if runtime and runtime.task:
            runtime.task.cancel()

    def all(self) -> list[CameraRuntime]:
        return list(self._runtimes.values())


manager = CameraManager()
