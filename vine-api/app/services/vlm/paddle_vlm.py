"""PaddleVLM provider - Phase 4."""
from typing import Dict, Optional
from app.services.base import VLMProvider, VLMVerificationResult


class PaddleVLMProvider(VLMProvider):
    """PaddlePaddle VLM."""
    
    name = "paddlevlm"
    max_image_size = 10 * 1024 * 1024
    supports_batch = False
    
    async def verify_image(self, image_bytes: bytes, expected_identity: Dict[str, Optional[str]]) -> VLMVerificationResult:
        raise NotImplementedError("Phase 4: Implement PaddleVLM")
