"""Ensemble OCR provider - combines results from multiple engines."""

import asyncio
from typing import List, Optional, Dict, Any
from collections import Counter

from app.services.base import OCRProvider, OCRResult
from app.services.ocr.easyocr import EasyOCRProvider
from app.services.ocr.tesseract import TesseractProvider
from app.services.ocr.paddle import PaddleOCRProvider


def _jaccard_similarity(a: str, b: str) -> float:
    """Calculate Jaccard similarity between two strings (word-level)."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a and not words_b:
        return 1.0
    if not words_a or not words_b:
        return 0.0
    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union if union > 0 else 0.0


def _select_best_result(results: List[OCRResult]) -> OCRResult:
    """Select the best result from multiple OCR engines using voting."""
    if not results:
        return OCRResult(text="", confidence=0.0)
    if len(results) == 1:
        return results[0]

    # Strategy 1: If one result has significantly higher confidence, use it
    max_conf = max(r.confidence for r in results)
    if max_conf > 0.85:
        best = max(results, key=lambda r: r.confidence)
        if best.confidence >= max_conf * 0.95:
            return best

    # Strategy 2: Find the result that most agrees with others (voting)
    best_score = -1.0
    best_idx = 0
    for i, candidate in enumerate(results):
        agreement = sum(_jaccard_similarity(candidate.text, other.text)
                        for j, other in enumerate(results) if i != j)
        score = agreement + candidate.confidence * 0.5
        if score > best_score:
            best_score = score
            best_idx = i

    winner = results[best_idx]

    # Merge bounding boxes from all results if available
    all_bboxes = []
    for r in results:
        if r.bounding_boxes:
            all_bboxes.extend(r.bounding_boxes)

    # Build merged text: use words that appear in majority of results
    word_votes: Counter[str] = Counter()
    for r in results:
        for word in r.text.split():
            word_votes[word.lower()] += 1

    # Include words voted by majority
    threshold = max(1, len(results) // 2)
    voted_words = [word for word, count in word_votes.most_common()
                   if count >= threshold]

    # If voting produces too few words, fall back to the winner's text
    merged_text = " ".join(voted_words) if len(voted_words) >= 2 else winner.text

    return OCRResult(
        text=merged_text if merged_text else winner.text,
        confidence=winner.confidence,
        language=winner.language,
        bounding_boxes=all_bboxes if all_bboxes else winner.bounding_boxes,
        raw_metadata={
            "ensemble": True,
            "num_engines": len(results),
            "engines_used": [r.raw_metadata.get("engine", "unknown") if r.raw_metadata else "unknown"
                            for r in results],
            "all_results": [
                {"text": r.text[:100], "confidence": r.confidence}
                for r in results
            ],
        },
    )


class EnsembleOCRProvider(OCRProvider):
    """Ensemble OCR that runs multiple engines and picks best result."""

    name = "ensemble"
    supports_languages = ["en", "fr", "de", "es", "it", "ch", "jp"]
    max_image_size = 15 * 1024 * 1024

    def __init__(
        self,
        providers: Optional[List[OCRProvider]] = None,
        timeout: float = 30.0,
    ):
        self.providers = providers or [
            EasyOCRProvider(),
            TesseractProvider(),
            PaddleOCRProvider(),
        ]
        self.timeout = timeout
        self._available_cache: Optional[List[bool]] = None

    async def is_available(self) -> bool:
        """Check if at least one provider is available."""
        avail = await self._check_all()
        return any(avail)

    async def _check_all(self) -> List[bool]:
        """Check availability of all providers."""
        if self._available_cache is None:
            self._available_cache = await asyncio.gather(
                *[p.is_available() for p in self.providers]
            )
        return self._available_cache

    async def _extract_text_impl(self, image_bytes: bytes) -> OCRResult:
        """Run all available providers and ensemble the results."""
        avail = await self._check_all()

        tasks = []
        for provider, is_avail in zip(self.providers, avail):
            if is_avail:
                tasks.append(self._run_with_timeout(provider, image_bytes))

        if not tasks:
            return OCRResult(text="", confidence=0.0, raw_metadata={"error": "No providers available"})

        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results: List[OCRResult] = []
        for r in results:
            if isinstance(r, Exception):
                continue
            if isinstance(r, OCRResult) and r.text.strip():
                valid_results.append(r)

        if not valid_results:
            return OCRResult(text="", confidence=0.0, raw_metadata={"error": "All providers failed"})

        return _select_best_result(valid_results)

    async def _run_with_timeout(self, provider: OCRProvider, image_bytes: bytes) -> OCRResult:
        """Run provider with timeout."""
        try:
            return await asyncio.wait_for(
                provider._extract_text_impl(image_bytes),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            # Return empty result on timeout
            return OCRResult(
                text="",
                confidence=0.0,
                raw_metadata={"error": f"{provider.name} timeout"}
            )

    async def extract_text_from_file(self, image_path: str) -> OCRResult:
        """Extract text from image file path."""
        with open(image_path, "rb") as f:
            return await self.extract_text(f.read())
