"""Groq VLM provider (cloud-only).

- Model: VLM_MODEL (default qwen/qwen3-vl-32b), fallback VLM_FALLBACK_MODEL.
- Reasoning disabled: reasoning_effort="none" (Groq docs: qwen3-vl default is none).
- Structured output: response_format={"type":"json_schema", ...} with the s7 schema.
- Multi-image: one user message with N image_url data-URL parts.
- Retry once on malformed JSON; fallback model on 429/5xx.
- Rate-limit headers captured via with_raw_response.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field

from backend.app.inference.base import VLMProvider
from backend.app.inference.schemas import (
    VLM_SYSTEM_PROMPT,
    VLMPerception,
    vlm_json_schema,
)


def jpeg_to_data_url(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")


@dataclass
class VLMResult:
    perception: VLMPerception
    model_used: str
    latency_s: float
    payload_bytes: int
    used_fallback: bool = False
    used_tiling: bool = False
    rate_limit_headers: dict = field(default_factory=dict)


def _extract_json(text: str) -> str:
    """Tolerate fenced ```json blocks; return raw JSON string."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        t = "\n".join(lines).strip()
    return t


class GroqVLMProvider(VLMProvider):
    def __init__(self, api_key: str, model: str, fallback_model: str):
        if not api_key:
            raise ValueError("GROQ_API_KEY is required for live VLM calls.")
        from groq import Groq  # deferred so offline tooling still imports

        self._client = Groq(api_key=api_key)
        self.model = model
        self.fallback_model = fallback_model

    def _call_once(
        self, image_data_urls: list[str], model: str, detail: str = "auto"
    ) -> tuple[str, float, dict]:
        content: list[dict] = [
            {
                "type": "text",
                "text": (
                    "Analyze these camera frame(s) in time order. "
                    "Return scene + objects + events JSON. "
                    "Demo objects of interest: ESP32, phone, notebook, bottle. "
                    "Locations must be short spatial phrases (e.g. 'center of desk')."
                ),
            }
        ]
        for url in image_data_urls:
            content.append(
                {"type": "image_url", "image_url": {"url": url, "detail": detail}}
            )
        t0 = time.perf_counter()
        raw = self._client.chat.completions.with_raw_response.create(
            model=model,
            messages=[
                {"role": "system", "content": VLM_SYSTEM_PROMPT},
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
            reasoning_effort="none",
            temperature=0.1,
            max_tokens=800,
        )
        latency = time.perf_counter() - t0
        headers = {
            k: v
            for k, v in dict(raw.headers).items()
            if "rate" in k.lower()
            or "limit" in k.lower()
            or "retry" in k.lower()
            or k.lower().startswith("x-")
        }
        completion = raw.parse()
        text = (completion.choices[0].message.content or "").strip()
        return text, latency, headers

    @staticmethod
    def _is_retryable_status(exc: Exception) -> bool:
        status = getattr(exc, "status_code", None)
        return status in (429, 500, 502, 503, 504)

    def analyze(
        self,
        frames: list[bytes],
        detail: str = "auto",
        allow_tiling_fallback: bool = True,
    ) -> VLMResult:
        from backend.app.perception.image_utils import tile_frames_horizontal

        urls = [jpeg_to_data_url(f) for f in frames]
        payload_bytes = sum(len(f) for f in frames)
        errors: list[str] = []

        candidates = [(self.model, False)]
        if self.fallback_model and self.fallback_model != self.model:
            candidates.append((self.fallback_model, True))

        last_exc: Exception | None = None
        for model, is_fallback in candidates:
            for attempt in range(2):  # initial + one retry on malformed output
                try:
                    text, latency, headers = self._call_once(urls, model, detail)
                    perception = VLMPerception.parse_raw_events(
                        json.loads(_extract_json(text))
                    )
                    return VLMResult(
                        perception=perception,
                        model_used=model,
                        latency_s=latency,
                        payload_bytes=payload_bytes,
                        used_fallback=is_fallback,
                        rate_limit_headers=headers,
                    )
                except (json.JSONDecodeError, ValueError) as e:
                    errors.append(f"{model} attempt{attempt}: malformed ({e})")
                    last_exc = e
                    continue  # retry once (same model), then fall through
                except Exception as e:  # noqa: BLE001 — provider dispatch
                    last_exc = e
                    if self._is_retryable_status(e):
                        break  # try next model (fallback)
                    # Multi-image rejection on primary -> tiling fallback below.
                    if (
                        allow_tiling_fallback
                        and len(frames) > 1
                        and not is_fallback
                        and "image" in str(e).lower()
                    ):
                        break
                    raise

        # Tiling fallback: stitch N frames side-by-side into ONE image, retry primary once.
        if allow_tiling_fallback and len(frames) > 1:
            tiled = tile_frames_horizontal(frames)
            try:
                text, latency, headers = self._call_once(
                    [jpeg_to_data_url(tiled)], self.model, detail
                )
                perception = VLMPerception.parse_raw_events(
                    json.loads(_extract_json(text))
                )
                return VLMResult(
                    perception=perception,
                    model_used=self.model,
                    latency_s=latency,
                    payload_bytes=len(tiled),
                    used_tiling=True,
                    rate_limit_headers=headers,
                )
            except Exception as e:  # noqa: BLE001
                last_exc = e

        raise RuntimeError(
            f"VLM analysis failed after retries/fallbacks: {'; '.join(errors) or last_exc}"
        )
