"""Qwen VLM provider implementation via OpenRouter."""
import os
from typing import Dict, Optional

import httpx

from app.services.base import VLMProvider, VLMVerificationResult
from app.services.vlm.base import (
    build_verification_prompt,
    encode_image_base64,
    parse_verification_result,
)


class QwenVLMProvider(VLMProvider):
    """Alibaba Qwen2.5-VL via OpenRouter API."""

    name = "qwen"
    max_image_size = 20 * 1024 * 1024
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODEL = "qwen/qwen3.5-27b"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.http_referer = os.getenv("APP_URL", "http://localhost")
        self.app_name = os.getenv("APP_NAME", "vine-api")

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def verify_image(
        self, image_bytes: bytes, expected_identity: Dict[str, Optional[str]]
    ) -> VLMVerificationResult:
        if len(image_bytes) > self.max_image_size:
            raise ValueError(f"Image too large: {len(image_bytes)} > {self.max_image_size}")

        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")

        image_url = encode_image_base64(image_bytes)
        prompt = build_verification_prompt(expected_identity)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.http_referer,
            "X-Title": self.app_name,
        }

        payload = {
            "model": self.MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    self.OPENROUTER_URL, headers=headers, json=payload
                )
                response.raise_for_status()
                data = response.json()

                response_text = data["choices"][0]["message"]["content"]
                return parse_verification_result(response_text)

            except httpx.HTTPStatusError as e:
                return VLMVerificationResult(
                    matches=False,
                    confidence=0.0,
                    reasoning=f"HTTP error: {e.response.status_code}",
                    raw_metadata={"error": e.response.text},
                )
            except Exception as e:
                return VLMVerificationResult(
                    matches=False,
                    confidence=0.0,
                    reasoning=f"Error: {str(e)}",
                    raw_metadata={"error": str(e)},
                )
