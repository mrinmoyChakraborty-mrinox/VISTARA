"""Structured logging with stable event names (ARCHITECTURE/IMPLEMENTATION).

Emits single-line JSON so logs are greppable. Never logs API keys. Never logs
raw camera images (only ids, latency, status, and small counts).
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any

from backend.app.core.config import settings

_EVENT_LOGGER = "visual_memory.events"


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": round(record.created, 3),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.name),
            "message": record.getMessage(),
        }
        for key in (
            "user_id",
            "camera_id",
            "memory_id",
            "event_type",
            "latency_ms",
            "status",
            "extra",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, _JsonFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())


def log_event(
    event: str, message: str = "", level: int = logging.INFO, **fields: Any
) -> None:
    """Emit a structured event (camera_connected, vlm_completed, memory_created, ...)."""
    logger = logging.getLogger(_EVENT_LOGGER)
    logger.log(level, message or event, extra={"event": event, **fields})


class timed:
    """Context manager that records wall-clock latency in milliseconds."""

    def __init__(self) -> None:
        self.ms: float = 0.0

    def __enter__(self) -> "timed":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.ms = (time.perf_counter() - self._t0) * 1000.0
