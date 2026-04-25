"""Mistral VLM provider via NVIDIA API."""
import os
from typing import Dict, Optional

import httpx

from app.services.base import VLMProvider, VLMVerificationResult
from app.services.vlm.base import (
    build_verification_prompt,
    encode_image_base64,
    parse_verification_result,
)


class MistralVLMProvider(VLMProvider):
    """Mistral Large via NVIDIA API."""

    name = "mistral"
    max_image_size = 20 * 1024 * 1024
    NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
    MODEL = "mistralai/mistral-large-3-675b-instruct-2512"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def verify_image(
        self, image_bytes: bytes, expected_identity: Dict[str, Optional[str]]
    ) -> VLMVerificationResult:
        if len(image_bytes) > self.max_image_size:
            raise ValueError(f"Image too large: {len(image_bytes)} > {self.max_image_size}")

        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY not set")

        image_url = encode_image_base64(image_bytes)
        prompt = build_verification_prompt(expected_identity)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
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
            "max_tokens": 2048,
            "temperature": 0.15,
            "top_p": 1.0,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    self.NVIDIA_URL, headers=headers, json=payload
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
