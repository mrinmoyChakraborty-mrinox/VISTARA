"""Real Groq Qwen3.8-27B vision integration test. Skipped without GROQ_API_KEY."""

from __future__ import annotations

import os

import pytest

from backend.app.memory.schemas import VLMPerception
from backend.app.perception.image_utils import prepare_frame_jpeg
from backend.tests.integration.conftest import requires_groq

pytestmark = [pytest.mark.integration, requires_groq]

TEST_IMAGE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "test.jpeg")


def _frame() -> bytes:
    import cv2

    img = cv2.imread(TEST_IMAGE)
    if img is None:
        pytest.skip("test.jpeg not available")
    blob, _, _ = prepare_frame_jpeg(img, 768, 85)
    return blob


def test_real_vlm_returns_valid_structured_json():
    from backend.app.providers.groq_qwen38 import GroqQwen38VisionProvider

    provider = GroqQwen38VisionProvider()
    result = provider.analyze([_frame()])
    assert result.model  # real model id
    assert result.latency_ms > 0
    # Pydantic already validated inside the provider; assert the shape.
    assert isinstance(result.perception, VLMPerception)
    assert result.perception.scene.type
    assert result.perception.scene.summary
    assert isinstance(result.perception.objects, list)
    assert isinstance(result.perception.events, list)
