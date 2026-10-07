"""Agent tools: JSON-schema definitions + server-side execution.

Tool calls are executed server-side inside the authenticated user's scope. The
model never sees another user's data because every tool passes user_id down to
RetrievalService.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from sqlalchemy.orm import Session

from backend.app.memory.serialize import evidence_to_out
from backend.app.retrieval.service import RetrievalService

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Find memories by natural-language query and optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language search text.",
                    },
                    "camera_id": {"type": "string"},
                    "start_time": {"type": "string", "description": "ISO 8601."},
                    "end_time": {"type": "string", "description": "ISO 8601."},
                    "limit": {"type": "integer", "default": 8},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_object_history",
            "description": "Chronological observations of one object (locations over time).",
            "parameters": {
                "type": "object",
                "properties": {
                    "object": {"type": "string"},
                    "camera_id": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                },
                "required": ["object"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_last_seen",
            "description": "Most recent observed location and time for an object.",
            "parameters": {
                "type": "object",
                "properties": {
                    "object": {"type": "string"},
                    "camera_id": {"type": "string"},
                },
                "required": ["object"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_events",
            "description": "Events within a time range, optionally scoped by type/object/camera.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "event_type": {"type": "string"},
                    "object": {"type": "string"},
                    "camera_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_scene",
            "description": "Overall scene perception nearest a timestamp (or latest).",
            "parameters": {
                "type": "object",
                "properties": {
                    "timestamp": {"type": "string"},
                    "camera_id": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_memory",
            "description": "Fetch one memory by id.",
            "parameters": {
                "type": "object",
                "properties": {"memory_id": {"type": "string"}},
                "required": ["memory_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_evidence",
            "description": "Return the evidence frame(s) associated with a memory.",
            "parameters": {
                "type": "object",
                "properties": {"memory_id": {"type": "string"}},
                "required": ["memory_id"],
            },
        },
    },
]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_jsonable(o) for o in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if hasattr(obj, "model_dump"):
        return _jsonable(obj.model_dump(mode="json"))
    return obj


class ToolExecutor:
    """Executes tool calls in the authenticated user's scope."""

    def __init__(
        self, db: Session, user_id: str, query_vector: list[float] | None = None
    ):
        self.db = db
        self.user_id = user_id
        self.retrieval = RetrievalService(db)
        self.query_vector = query_vector

    def handlers(self) -> dict[str, Callable[[dict], Any]]:
        return {
            "search_memory": self._search_memory,
            "get_object_history": self._get_object_history,
            "get_last_seen": self._get_last_seen,
            "get_events": self._get_events,
            "get_scene": self._get_scene,
            "get_memory": self._get_memory,
            "get_evidence": self._get_evidence,
        }

    def execute(self, name: str, arguments: dict | None) -> dict:
        args = arguments or {}
        handler = self.handlers().get(name)
        if handler is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            return {"tool": name, "result": _jsonable(handler(args))}
        except Exception as exc:  # noqa: BLE001 - surface tool errors to the model
            return {"tool": name, "error": str(exc)}

    # ------------------------------------------------------------- handlers
    def _search_memory(self, args: dict):
        return self.retrieval.search_memory(
            self.user_id,
            query=args.get("query", ""),
            camera_id=args.get("camera_id"),
            start_time=_parse_dt(args.get("start_time")),
            end_time=_parse_dt(args.get("end_time")),
            limit=int(args.get("limit", 8)),
            query_vector=self.query_vector,
        )

    def _get_object_history(self, args: dict):
        return self.retrieval.get_object_history(
            self.user_id,
            args["object"],
            start_time=_parse_dt(args.get("start_time")),
            end_time=_parse_dt(args.get("end_time")),
        )

    def _get_last_seen(self, args: dict):
        return self.retrieval.get_last_seen(
            self.user_id, args["object"], args.get("camera_id")
        )

    def _get_events(self, args: dict):
        return self.retrieval.get_events(
            self.user_id,
            start_time=_parse_dt(args.get("start_time")),
            end_time=_parse_dt(args.get("end_time")),
            event_type=args.get("event_type"),
            object_name=args.get("object"),
            camera_id=args.get("camera_id"),
            limit=int(args.get("limit", 50)),
        )

    def _get_scene(self, args: dict):
        return self.retrieval.get_scene(
            self.user_id,
            timestamp=_parse_dt(args.get("timestamp")),
            camera_id=args.get("camera_id"),
        )

    def _get_memory(self, args: dict):
        return self.retrieval.get_memory(self.user_id, args["memory_id"])

    def _get_evidence(self, args: dict):
        rows = self.retrieval.get_evidence(self.user_id, args["memory_id"])
        out = []
        for row in rows:
            url = None
            try:
                from backend.app.evidence.service import EvidenceService

                url = EvidenceService().signed_url(row.storage_path)
            except Exception:  # noqa: BLE001
                url = None
            out.append(evidence_to_out(row, url=url))
        return out
