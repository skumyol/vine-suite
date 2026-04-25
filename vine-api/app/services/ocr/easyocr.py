"""EasyOCR provider implementation."""
import asyncio
from typing import List, Optional

from app.services.base import OCRProvider, OCRResult

# Module-level shared reader to avoid reloading model
_EASYOCR_READER = None


def _get_reader(languages: List[str] = None):
    """Get or create shared EasyOCR reader."""
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        import easyocr
        langs = languages or ["en", "fr", "de", "it"]
        _EASYOCR_READER = easyocr.Reader(langs, gpu=False)
    return _EASYOCR_READER


class EasyOCRProvider(OCRProvider):
    """EasyOCR text extraction using the easyocr library."""

    name = "easyocr"
    supports_languages = ["en", "fr", "de", "es", "it"]
    max_image_size = 10 * 1024 * 1024

    def __init__(self, languages: Optional[List[str]] = None):
        self.languages = languages or self.supports_languages
        self._reader = None

    async def is_available(self) -> bool:
        try:
            import easyocr
            return True
        except ImportError:
            return False

    async def _extract_text_impl(self, image_bytes: bytes) -> OCRResult:
        """Engine-specific text extraction using EasyOCR."""
        if len(image_bytes) > self.max_image_size:
            raise ValueError(
                f"Image too large: {len(image_bytes)} > {self.max_image_size}"
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._extract_text_sync, image_bytes
        )

    def _extract_text_sync(self, image_bytes: bytes) -> OCRResult:
        """Synchronous OCR extraction."""
        import tempfile
        import os

        # Write to temp file (EasyOCR works better with file paths)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        try:
            reader = _get_reader(self.languages)
            results = reader.readtext(tmp_path)

            texts = []
            confidences = []
            bboxes = []

            for bbox, text, conf in results:
                if conf > 0.3:  # Filter low confidence
                    texts.append(text)
                    confidences.append(conf)
                    bboxes.append({
                        "points": bbox,
                        "confidence": conf,
                    })

            full_text = " ".join(texts)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

            # Detect language from results
            detected_lang = self._detect_language(full_text)

            return OCRResult(
                text=full_text,
                confidence=avg_conf,
                bounding_boxes=bboxes,
                language=detected_lang,
                raw_metadata={
                    "num_regions": len(texts),
                    "avg_confidence": avg_conf,
                },
            )
        finally:
            os.unlink(tmp_path)

    def _detect_language(self, text: str) -> Optional[str]:
        """Simple heuristic to detect language from text."""
        text_lower = text.lower()
        # Check for French indicators
        if any(word in text_lower for word in ["château", "domaine", "grand cru", "appellation"]):
            return "fr"
        # Check for German
        if any(word in text_lower for word in ["weingut", "trocken", "riesling"]):
            return "de"
        # Check for Italian
        if any(word in text_lower for word in ["tenuta", "cantina", "docg"]):
            return "it"
        return "en"

    async def extract_text_from_file(self, image_path: str) -> OCRResult:
        """Extract text from image file path."""
        with open(image_path, "rb") as f:
            return await self.extract_text(f.read())
