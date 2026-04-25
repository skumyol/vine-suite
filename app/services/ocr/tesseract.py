"""Tesseract OCR provider implementation."""
import asyncio
import tempfile
import os
from typing import List, Optional

from app.services.base import OCRProvider, OCRResult


class TesseractProvider(OCRProvider):
    """Tesseract OCR text extraction using pytesseract."""

    name = "tesseract"
    supports_languages = ["eng", "fra", "deu", "ita", "spa"]
    max_image_size = 20 * 1024 * 1024

    def __init__(self, languages: Optional[List[str]] = None):
        self.languages = languages or self.supports_languages
        self.lang_string = "+".join(self.languages)

    async def is_available(self) -> bool:
        try:
            import pytesseract
            from PIL import Image
            return True
        except ImportError:
            return False

    async def _extract_text_impl(self, image_bytes: bytes) -> OCRResult:
        """Engine-specific text extraction using Tesseract OCR."""
        if len(image_bytes) > self.max_image_size:
            raise ValueError(
                f"Image too large: {len(image_bytes)} > {self.max_image_size}"
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._extract_text_sync, image_bytes
        )

    def _extract_text_sync(self, image_bytes: bytes) -> OCRResult:
        """Synchronous Tesseract extraction."""
        import pytesseract
        from PIL import Image
        import io

        # Load image from bytes
        image = Image.open(io.BytesIO(image_bytes))

        # Run OCR with config for better accuracy
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÀ-ÿ\'- '
        text = pytesseract.image_to_string(image, lang=self.lang_string, config=custom_config)

        # Get confidence data
        data = pytesseract.image_to_data(
            image, lang=self.lang_string, output_type=pytesseract.Output.DICT
        )

        # Calculate average confidence
        confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        avg_conf = avg_conf / 100.0  # Normalize to 0-1

        # Extract bounding boxes
        bboxes = []
        for i in range(len(data['text'])):
            if int(data['conf'][i]) > 30:
                bboxes.append({
                    "text": data['text'][i],
                    "confidence": data['conf'][i] / 100.0,
                    "x": data['left'][i],
                    "y": data['top'][i],
                    "width": data['width'][i],
                    "height": data['height'][i],
                })

        return OCRResult(
            text=text.strip(),
            confidence=avg_conf,
            bounding_boxes=bboxes,
            language=self._detect_language(text),
            raw_metadata={
                "num_words": len([w for w in data['text'] if w.strip()]),
                "avg_confidence": avg_conf,
            },
        )

    def _detect_language(self, text: str) -> Optional[str]:
        """Simple language detection."""
        text_lower = text.lower()
        if any(word in text_lower for word in ["château", "domaine", "grand cru"]):
            return "fra"
        if any(word in text_lower for word in ["weingut", "trocken", "riesling"]):
            return "deu"
        if any(word in text_lower for word in ["tenuta", "cantina", "docg"]):
            return "ita"
        return "eng"

    async def extract_text_from_file(self, image_path: str) -> OCRResult:
        """Extract text from image file path."""
        with open(image_path, "rb") as f:
            return await self.extract_text(f.read())
