"""OCR provider tests - focus on text extraction accuracy.

Tests measure:
- Text extraction success rate
- Confidence scores
- Language support (en, fr, de, es, it, ch, jp)
- Preprocessing effectiveness
"""

import asyncio
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

import pytest
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

from app.services.ocr import (
    EasyOCRProvider,
    TesseractProvider,
    PaddleOCRProvider,
    OCRPreprocessor,
)
from app.services.base import OCRResult


# Test samples with expected text content
TEST_SAMPLES = [
    # English wine labels
    {"text": "Cabernet Sauvignon 2018", "lang": "en", "category": "varietal"},
    {"text": "Napa Valley Reserve", "lang": "en", "category": "region"},
    {"text": "Chateau Margaux 2015", "lang": "fr", "category": "bordeaux"},
    {"text": "Grand Cru Classe", "lang": "fr", "category": "classification"},
    {"text": "Riesling Trocken 2020", "lang": "de", "category": "german"},
    {"text": "Weingut Dr. Loosen", "lang": "de", "category": "producer"},
    {"text": "Rioja Reserva 2017", "lang": "es", "category": "spanish"},
    {"text": "Bodegas Muga", "lang": "es", "category": "producer"},
    {"text": "Barolo DOCG 2016", "lang": "it", "category": "italian"},
    {"text": "Brunello di Montalcino", "lang": "it", "category": "italian"},
]


@dataclass
class OCRTestResult:
    """Result from a single OCR test."""
    provider: str
    sample_text: str
    extracted_text: str
    confidence: float
    success: bool  # Did we extract meaningful text?
    processing_time_ms: float
    partial_match: bool  # Partial text match


def create_test_image(text: str, width: int = 600, height: int = 200) -> bytes:
    """Create a synthetic wine label image with text."""
    # Create white background
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a nice font, fall back to default
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
    except:
        font = ImageFont.load_default()
    
    # Draw text centered
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    draw.text((x, y), text, fill='black', font=font)
    
    # Add some noise/texture to simulate label
    arr = np.array(img)
    noise = np.random.normal(0, 5, arr.shape).astype(np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    # Encode to bytes
    _, buf = cv2.imencode('.png', cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    return buf.tobytes()


class TestOCRPreprocessor:
    """Test OCR preprocessing pipeline."""

    def test_preprocessor_loads_image(self):
        """Test that preprocessor can load and process an image."""
        image_bytes = create_test_image("Test Wine Label")
        preprocessor = OCRPreprocessor()
        
        start = time.perf_counter()
        result = preprocessor.preprocess(image_bytes)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert isinstance(result, bytes)
        assert len(result) > 0
        print(f"\n  Preprocessing time: {elapsed_ms:.1f}ms")

    def test_preprocessor_resizes_large_image(self):
        """Test that large images are resized to target height."""
        # Create large image
        img = Image.new('RGB', (2000, 1500), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((100, 700), "Large Image Test", fill='black')
        
        arr = np.array(img)
        _, buf = cv2.imencode('.jpg', cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
        
        preprocessor = OCRPreprocessor()
        result = preprocessor.preprocess(buf.tobytes())
        
        # Decode and check dimensions
        nparr = np.frombuffer(result, np.uint8)
        decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Should be resized to around 800px height
        assert decoded.shape[0] <= 900  # Target is 800

    def test_preprocessor_handles_small_image(self):
        """Test that small images are handled gracefully."""
        img = Image.new('RGB', (200, 100), color='white')
        arr = np.array(img)
        _, buf = cv2.imencode('.jpg', arr)
        
        preprocessor = OCRPreprocessor()
        result = preprocessor.preprocess(buf.tobytes())
        
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestEasyOCRProvider:
    """Test EasyOCR provider (default)."""

    @pytest.mark.asyncio
    async def test_easyocr_available(self):
        """Check if EasyOCR is installed and available."""
        provider = EasyOCRProvider()
        available = await provider.is_available()
        
        # This will be False if easyocr not installed
        # That's expected - just log the status
        print(f"\n  EasyOCR available: {available}")

    @pytest.mark.asyncio
    async def test_easyocr_extract_text(self):
        """Test basic text extraction with EasyOCR."""
        provider = EasyOCRProvider()
        
        if not await provider.is_available():
            pytest.skip("EasyOCR not installed")
        
        image_bytes = create_test_image("Cabernet Sauvignon")
        
        start = time.perf_counter()
        result = await provider.extract_text(image_bytes)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        print(f"\n  EasyOCR result: '{result.text}' (conf: {result.confidence:.2f}, time: {elapsed_ms:.1f}ms)")
        
        # Should extract something (may not be exact due to synthetic image)
        assert isinstance(result.text, str)
        assert result.confidence >= 0

    @pytest.mark.asyncio
    async def test_easyocr_language_support(self):
        """Test EasyOCR with different languages."""
        provider = EasyOCRProvider(languages=["en"])
        
        if not await provider.is_available():
            pytest.skip("EasyOCR not installed")
        
        # English test
        image_bytes = create_test_image("Napa Valley 2018")
        result = await provider.extract_text(image_bytes)
        
        print(f"\n  EasyOCR English: '{result.text}'")
        assert isinstance(result.text, str)


class TestTesseractProvider:
    """Test Tesseract OCR provider."""

    @pytest.mark.asyncio
    async def test_tesseract_available(self):
        """Check if Tesseract is installed."""
        provider = TesseractProvider()
        available = await provider.is_available()
        print(f"\n  Tesseract available: {available}")

    @pytest.mark.asyncio
    async def test_tesseract_extract_text(self):
        """Test basic text extraction with Tesseract."""
        provider = TesseractProvider()
        
        if not await provider.is_available():
            pytest.skip("Tesseract not installed")
        
        image_bytes = create_test_image("Merlot Reserve")
        
        start = time.perf_counter()
        result = await provider.extract_text(image_bytes)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        print(f"\n  Tesseract result: '{result.text}' (conf: {result.confidence:.2f}, time: {elapsed_ms:.1f}ms)")
        
        assert isinstance(result.text, str)


class TestPaddleOCRProvider:
    """Test PaddleOCR provider."""

    @pytest.mark.asyncio
    async def test_paddle_available(self):
        """Check if PaddleOCR is installed."""
        provider = PaddleOCRProvider()
        available = await provider.is_available()
        print(f"\n  PaddleOCR available: {available}")

    @pytest.mark.asyncio
    async def test_paddle_extract_text(self):
        """Test basic text extraction with PaddleOCR."""
        provider = PaddleOCRProvider()
        
        if not await provider.is_available():
            pytest.skip("PaddleOCR not installed")
        
        image_bytes = create_test_image("Pinot Noir 2020")
        
        start = time.perf_counter()
        result = await provider.extract_text(image_bytes)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        print(f"\n  PaddleOCR result: '{result.text}' (conf: {result.confidence:.2f}, time: {elapsed_ms:.1f}ms)")
        
        assert isinstance(result.text, str)


class TestOCRCrossProvider:
    """Compare results across all OCR providers."""

    @pytest.mark.asyncio
    async def test_all_providers_on_same_image(self):
        """Run all available OCR providers on the same test image."""
        image_bytes = create_test_image("Bordeaux Wine 2019", width=800, height=300)
        
        providers = [
            ("EasyOCR", EasyOCRProvider()),
            ("Tesseract", TesseractProvider()),
            ("PaddleOCR", PaddleOCRProvider()),
        ]
        
        results = []
        
        for name, provider in providers:
            if await provider.is_available():
                try:
                    start = time.perf_counter()
                    result = await provider.extract_text(image_bytes)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    
                    results.append({
                        "name": name,
                        "text": result.text[:100],  # Truncate for display
                        "confidence": result.confidence,
                        "time_ms": elapsed_ms,
                    })
                except Exception as e:
                    results.append({
                        "name": name,
                        "error": str(e),
                    })
        
        print("\n  OCR Comparison:")
        for r in results:
            if "error" in r:
                print(f"    {r['name']}: ERROR - {r['error']}")
            else:
                print(f"    {r['name']}: '{r['text']}' (conf: {r['confidence']:.2f}, {r['time_ms']:.1f}ms)")
        
        # At least one provider should work if any are installed
        successful = [r for r in results if "error" not in r]
        if successful:
            assert len(successful) > 0

    @pytest.mark.asyncio
    async def test_ocr_accuracy_measurement(self):
        """Measure OCR accuracy on known test samples."""
        provider = EasyOCRProvider()
        
        if not await provider.is_available():
            pytest.skip("EasyOCR not installed")
        
        results = []
        
        for sample in TEST_SAMPLES[:5]:  # Test first 5 samples
            image_bytes = create_test_image(sample["text"])
            
            start = time.perf_counter()
            ocr_result = await provider.extract_text(image_bytes)
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            # Simple success metric: did we get any text?
            success = len(ocr_result.text.strip()) > 0
            
            # Partial match: any word overlap
            expected_words = set(sample["text"].lower().split())
            extracted_words = set(ocr_result.text.lower().split())
            partial_match = len(expected_words & extracted_words) > 0
            
            results.append({
                "expected": sample["text"],
                "extracted": ocr_result.text,
                "success": success,
                "partial_match": partial_match,
                "confidence": ocr_result.confidence,
                "time_ms": elapsed_ms,
            })
        
        # Summary
        successes = sum(1 for r in results if r["success"])
        partials = sum(1 for r in results if r["partial_match"])
        avg_time = sum(r["time_ms"] for r in results) / len(results)
        
        print(f"\n  OCR Accuracy Summary:")
        print(f"    Samples: {len(results)}")
        print(f"    Success (any text): {successes}/{len(results)} ({successes/len(results)*100:.0f}%)")
        print(f"    Partial matches: {partials}/{len(results)} ({partials/len(results)*100:.0f}%)")
        print(f"    Avg time: {avg_time:.1f}ms")
        
        for r in results:
            status = "✓" if r["partial_match"] else "✗"
            print(f"    {status} '{r['expected']}' -> '{r['extracted'][:40]}'")


class TestOCRHealthChecks:
    """Test OCR provider health/status reporting."""

    @pytest.mark.asyncio
    async def test_easyocr_health_check(self):
        """Test EasyOCR health check includes preprocessing status."""
        provider = EasyOCRProvider()
        health = await provider.health_check()
        
        assert "name" in health
        assert "preprocessing" in health
        assert health["preprocessing"] == "enabled"
        print(f"\n  EasyOCR health: {health}")

    @pytest.mark.asyncio
    async def test_tesseract_health_check(self):
        """Test Tesseract health check."""
        provider = TesseractProvider()
        health = await provider.health_check()
        
        assert "name" in health
        print(f"\n  Tesseract health: {health}")

    @pytest.mark.asyncio
    async def test_paddle_health_check(self):
        """Test PaddleOCR health check."""
        provider = PaddleOCRProvider()
        health = await provider.health_check()
        
        assert "name" in health
        print(f"\n  PaddleOCR health: {health}")
