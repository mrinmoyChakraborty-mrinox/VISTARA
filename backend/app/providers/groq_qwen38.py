"""Groq Qwen3.8-27B vision provider (cloud-only). All Groq API code lives here."""

from __future__ import annotations

import json
import time

from backend.app.core.config import settings
from backend.app.core.logging import log_event
from backend.app.memory.schemas import (
    VLMPerception,
    vlm_json_schema,
)
from backend.app.perception.image_utils import tile_frames_horizontal
from backend.app.providers.vision import VisionProvider, VisionResult

_NO_OBJECTS_HINT = (
    "Report every visible object with a short spatial location. "
    "If an object seen earlier is not visible now, do not invent it and do not "
    "claim it is gone; use 'last observed' wording. "
    "Be concise to fit the output budget: locations max 6 words, descriptions max "
    "20 words, status one of visible/partially_visible/last_observed, at most "
    "8 objects, at most 4 events. Prefer the demo objects of interest "
    "(ESP32, phone, notebook, bottle) when visible."
)


def _extract_json(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = "\n".join(
            ln for ln in t.splitlines() if not ln.strip().startswith("```")
        ).strip()
    return t


class GroqQwen38VisionProvider(VisionProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        fallback_model: str | None = None,
    ):
        key = api_key if api_key is not None else settings.groq_api_key
        if not key:
            raise ValueError("GROQ_API_KEY is required for the Groq vision provider.")
        from groq import Groq

        self._client = Groq(api_key=key)
        self._model = model or settings.groq_vlm_model
        self._fallback = fallback_model or settings.groq_vlm_fallback_model
        self._reasoning_effort = settings.groq_vlm_reasoning_effort
        self._timeout = settings.groq_timeout_seconds

    @property
    def model_name(self) -> str:
        return self._model

    @staticmethod
    def _to_data_url(jpeg: bytes) -> str:
        import base64

        return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")

    def _call(
        self, frames: list[bytes], model: str, baseline: bool = False
    ) -> tuple[str, float, dict, int]:
        from backend.app.memory.schemas import (  # local alias
            VLM_BASELINE_PROMPT,
            VLM_SYSTEM_PROMPT as _sp,
        )

        user_text = (
            "Establish the INITIAL VISUAL BASELINE for this camera. "
            "Inventory the current state for future comparison. " + _NO_OBJECTS_HINT
            if baseline
            else "Analyze these camera frames in time order. " + _NO_OBJECTS_HINT
        )
        content: list[dict] = [{"type": "text", "text": user_text}]
        for jpeg in frames:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": self._to_data_url(jpeg), "detail": "auto"},
                }
            )
        t0 = time.perf_counter()
        raw = self._client.chat.completions.with_raw_response.create(
            model=model,
            messages=[
                {"role": "system", "content": VLM_BASELINE_PROMPT if baseline else _sp},
                {"role": "user", "content": content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "vlm_perception",
                    "schema": vlm_json_schema(),
                    "strict": True,
                },
            },
            reasoning_effort=self._reasoning_effort,
            temperature=0.1,
            # Phase 2 verified: free-tier OTPM limit is 1000. ~1500 stays under
            # the enforced estimate while fitting a complete scene+objects+events JSON.
            max_tokens=1500,
            timeout=self._timeout,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        headers = {
            k: v
            for k, v in dict(raw.headers).items()
            if "rate" in k.lower() or "retry" in k.lower() or k.lower().startswith("x-")
        }
        completion = raw.parse()
        text = (completion.choices[0].message.content or "").strip()
        return text, latency_ms, headers, sum(len(f) for f in frames)

    @staticmethod
    def _retryable(exc: Exception) -> bool:
        return getattr(exc, "status_code", None) in (429, 500, 502, 503, 504)

    def analyze(
        self,
        frames: list[bytes],
        previous_state: dict | None = None,
        baseline: bool = False,
    ) -> VisionResult:
        candidates = [(self._model, False)]
        if self._fallback and self._fallback != self._model:
            candidates.append((self._fallback, True))

        last_exc: Exception | None = None
        for model, is_fallback in candidates:
            for _attempt in range(2):  # initial + one retry on malformed output
                try:
                    text, latency_ms, headers, payload = self._call(
                        frames, model, baseline
                    )
                    perception = VLMPerception.parse(json.loads(_extract_json(text)))
                    log_event(
                        "vlm_completed",
                        model=model,
                        latency_ms=round(latency_ms, 1),
                        status="ok",
                        extra={
                            "objects": len(perception.objects),
                            "events": len(perception.events),
                        },
                    )
                    return VisionResult(
                        perception=perception,
                        model=model,
                        latency_ms=latency_ms,
                        used_fallback=is_fallback,
                        payload_bytes=payload,
                        raw=text,
                        headers=headers,
                    )
                except (json.JSONDecodeError, ValueError) as exc:
                    last_exc = exc
                    continue
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if self._retryable(exc):
                        break

        # Multi-image may be rejected: stitch into one image and retry once.
        if len(frames) > 1:
            try:
                tiled = tile_frames_horizontal(frames)
                text, latency_ms, headers, _ = self._call(
                    [tiled], self._model, baseline
                )
                perception = VLMPerception.parse(json.loads(_extract_json(text)))
                return VisionResult(
                    perception=perception,
                    model=self._model,
                    latency_ms=latency_ms,
                    used_tiling=True,
                    payload_bytes=len(tiled),
                    raw=text,
                    headers=headers,
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc

        log_event("vlm_failed", status="error", message=str(last_exc))
        raise RuntimeError(f"VLM analysis failed: {last_exc}")
