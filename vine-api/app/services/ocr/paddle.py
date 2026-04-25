"""PaddleOCR provider implementation."""
import asyncio
import io
from typing import List, Optional

import numpy as np
from PIL import Image

from app.services.base import OCRProvider, OCRResult

# Module-level shared engine
_PADDLE_OCR = None


def _get_paddle_engine(lang: str = "en"):
    """Get or create shared PaddleOCR engine."""
    global _PADDLE_OCR
    if _PADDLE_OCR is None:
        from paddleocr import PaddleOCR
        _PADDLE_OCR = PaddleOCR(
            use_angle_cls=True,
            lang=lang,
        )
    return _PADDLE_OCR


class PaddleOCRProvider(OCRProvider):
    """PaddleOCR text extraction using PaddleOCR library."""

    name = "paddleocr"
    supports_languages = ["en", "ch", "korean", "japan", "ch_tra", "latin", "arabic", "cyrillic"]
    max_image_size = 15 * 1024 * 1024

    def __init__(self, language: str = "en"):
        self.language = language
        self._engine = None

    async def is_available(self) -> bool:
        try:
            from paddleocr import PaddleOCR
            return True
        except ImportError:
            return False

    async def _extract_text_impl(self, image_bytes: bytes) -> OCRResult:
        """Engine-specific text extraction using PaddleOCR."""
        if len(image_bytes) > self.max_image_size:
            raise ValueError(
                f"Image too large: {len(image_bytes)} > {self.max_image_size}"
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._extract_text_sync, image_bytes
        )

    def _extract_text_sync(self, image_bytes: bytes) -> OCRResult:
        """Synchronous PaddleOCR extraction."""
        # Load image
        image = Image.open(io.BytesIO(image_bytes))
        image_array = np.array(image)

        # Get engine
        engine = _get_paddle_engine(self.language)

        # Run OCR
        result = engine.ocr(image_array, cls=True)

        texts = []
        confidences = []
        bboxes = []

        if result[0]:
            for line in result[0]:
                if line:
                    bbox = line[0]
                    text = line[1][0]
                    conf = line[1][1]

                    texts.append(text)
                    confidences.append(conf)
                    bboxes.append({
                        "points": bbox,
                        "text": text,
                        "confidence": conf,
                    })

        full_text = " ".join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            bounding_boxes=bboxes,
            language=self.language,
            raw_metadata={
                "num_lines": len(texts),
                "avg_confidence": avg_conf,
            },
        )

    async def extract_text_from_file(self, image_path: str) -> OCRResult:
        """Extract text from image file path."""
        with open(image_path, "rb") as f:
            return await self.extract_text(f.read())
