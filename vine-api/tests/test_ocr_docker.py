"""OCR tests via Docker microservice.

Requires: docker-compose up -d ocr-service
"""

import io
import time
from typing import List, Dict, Any

import pytest
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import httpx

from app.services.ocr import OCRServiceClient, OCRPreprocessor


OCR_SERVICE_URL = "http://localhost:8001"


def create_test_image(text: str, width: int = 600, height: int = 200) -> bytes:
    """Create a synthetic wine label image with text."""
    img = Image.new('RGB', (width, height), color='#f5f5f0')
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Georgia.ttf", 32)
    except:
        font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (width - text_width) // 2
    y = height // 2 - 20
    
    draw.text((x+1, y+1), text, fill='#cccccc', font=font)
    draw.text((x, y), text, fill='#1a1a1a', font=font)
    
    arr = np.array(img)
    noise = np.random.normal(0, 3, arr.shape).astype(np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    _, buf = cv2.imencode('.png', cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    return buf.tobytes()


@pytest.fixture(scope="module")
def client():
    """OCR service client fixture."""
    return OCRServiceClient(base_url=OCR_SERVICE_URL)


class TestOCRServiceConnection:
    """Test connectivity to OCR service."""

    def test_service_reachable(self):
        """Check OCR service is running."""
        try:
            r = httpx.get(f"{OCR_SERVICE_URL}/health", timeout=5)
            assert r.status_code == 200
            data = r.json()
            assert "engines" in data
            print(f"\n  Service health: {data['status']}")
            print(f"  Engines: {data['engines']}")
        except httpx.ConnectError:
            pytest.skip("OCR service not running. Start: docker-compose up -d ocr-service")

    def test_service_info(self):
        """Get service version and capabilities."""
        r = httpx.get(f"{OCR_SERVICE_URL}/", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "OCR Microservice"
        print(f"\n  Version: {data['version']}")
        print(f"  Features: {data.get('features', {})}")

    def test_service_stats(self):
        """Check memory usage of pre-warmed engines."""
        r = httpx.get(f"{OCR_SERVICE_URL}/stats", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert "memory" in data
        mem = data["memory"]
        print(f"\n  Memory RSS: {mem['rss_mb']}MB")
        print(f"  Memory VMS: {mem['vms_mb']}MB")
        print(f"  CPU: {data['cpu_percent']}%")
        print(f"  Uptime: {data['uptime_seconds']}s")
        # All engines should be loaded (pre-warmed)
        assert data["engines_loaded"]["easyocr"] is True


class TestOCRServiceExtraction:
    """Test text extraction via OCR service."""

    @pytest.mark.asyncio
    async def test_easyocr_endpoint(self, client):
        """Test EasyOCR endpoint."""
        image_bytes = create_test_image("Cabernet Sauvignon 2018")
        
        files = {"file": ("test.png", io.BytesIO(image_bytes), "image/png")}
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(f"{OCR_SERVICE_URL}/ocr/easyocr", files=files)
        
        if r.status_code == 503:
            pytest.skip("EasyOCR engine disabled in service")
        
        assert r.status_code == 200
        data = r.json()
        assert "text" in data
        assert "confidence" in data
        print(f"\n  EasyOCR: '{data['text']}' (conf: {data['confidence']:.2f})")
        assert len(data["text"]) > 0

    @pytest.mark.asyncio
    async def test_tesseract_endpoint(self, client):
        """Test Tesseract endpoint."""
        image_bytes = create_test_image("Napa Valley Reserve")
        
        files = {"file": ("test.png", io.BytesIO(image_bytes), "image/png")}
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.post(f"{OCR_SERVICE_URL}/ocr/tesseract", files=files)
        
        if r.status_code == 503:
            pytest.skip("Tesseract engine disabled in service")
        
        assert r.status_code == 200
        data = r.json()
        print(f"\n  Tesseract: '{data['text']}' (conf: {data['confidence']:.2f})")
        assert "text" in data

    @pytest.mark.asyncio
    async def test_paddle_endpoint(self, client):
        """Test PaddleOCR endpoint."""
        image_bytes = create_test_image("Pinot Noir 2020")
        
        files = {"file": ("test.png", io.BytesIO(image_bytes), "image/png")}
        async with httpx.AsyncClient(timeout=60) as http:
            r = await http.post(f"{OCR_SERVICE_URL}/ocr/paddle", files=files)
        
        if r.status_code == 503:
            pytest.skip("PaddleOCR engine disabled in service")
        
        assert r.status_code == 200
        data = r.json()
        print(f"\n  PaddleOCR: '{data['text']}' (conf: {data['confidence']:.2f})")
        assert "text" in data

    @pytest.mark.asyncio
    async def test_best_endpoint(self, client):
        """Test best-of-all endpoint."""
        image_bytes = create_test_image("Bordeaux Wine 2019", width=800, height=300)
        
        files = {"file": ("test.png", io.BytesIO(image_bytes), "image/png")}
        async with httpx.AsyncClient(timeout=60) as http:
            r = await http.post(f"{OCR_SERVICE_URL}/ocr/best", files=files)
        
        assert r.status_code == 200
        data = r.json()
        print(f"\n  Best engine: {data['engine']}")
        print(f"  Text: '{data['text']}'")
        print(f"  Confidence: {data['confidence']:.2f}")
        print(f"  Time: {data['processing_time_ms']:.0f}ms")
        assert "text" in data
        assert data["engine"] in ["easyocr", "tesseract", "paddle"]


class TestOCRServiceClient:
    """Test Python client wrapper for OCR service."""

    @pytest.mark.asyncio
    async def test_client_available(self, client):
        """Test client can connect to service."""
        available = await client.is_available()
        if not available:
            pytest.skip("OCR service not available")
        print("\n  OCR service client connected")

    @pytest.mark.asyncio
    async def test_client_extract_text(self, client):
        """Test client extracts text through service."""
        if not await client.is_available():
            pytest.skip("OCR service not available")
        
        image_bytes = create_test_image("Chateau Margaux 2015")
        
        result = await client.extract_text(image_bytes)
        
        print(f"\n  Client result: '{result.text}'")
        print(f"  Confidence: {result.confidence:.2f}")
        assert len(result.text) > 0
        assert result.confidence >= 0

    @pytest.mark.asyncio
    async def test_client_health(self, client):
        """Test client health check includes service info."""
        health = await client.health_check()
        print(f"\n  Client health: {health}")
        assert "name" in health
        assert health.get("preprocessing") == "enabled"


class TestOCRCrossProvider:
    """Compare results across all OCR engines via service."""

    @pytest.mark.asyncio
    async def test_compare_all_engines(self, client):
        """Run all engines on same image and compare."""
        if not await client.is_available():
            pytest.skip("OCR service not available")
        
        image_bytes = create_test_image("Merlot Reserve 2017", width=800, height=300)
        
        engines = ["easyocr", "tesseract", "paddle"]
        results = []
        
        for engine in engines:
            files = {"file": ("test.png", io.BytesIO(image_bytes), "image/png")}
            async with httpx.AsyncClient(timeout=30) as http:
                r = await http.post(f"{OCR_SERVICE_URL}/ocr/{engine}", files=files)
            
            if r.status_code == 200:
                data = r.json()
                results.append({
                    "engine": engine,
                    "text": data["text"],
                    "confidence": data["confidence"],
                    "time_ms": data["processing_time_ms"],
                })
            elif r.status_code == 503:
                results.append({"engine": engine, "disabled": True})
        
        print("\n  OCR Comparison:")
        for r in results:
            if r.get("disabled"):
                print(f"    {r['engine']}: disabled")
            else:
                print(f"    {r['engine']}: '{r['text'][:35]}' "
                      f"(conf: {r['confidence']:.2f}, {r['time_ms']:.0f}ms)")
        
        # At least one engine should return text
        successful = [r for r in results if not r.get("disabled") and len(r.get("text", "")) > 0]
        assert len(successful) > 0


class TestOCRAccuracy:
    """Measure OCR accuracy on known test samples."""

    TEST_SAMPLES = [
        ("Cabernet Sauvignon 2018", "en"),
        ("Chateau Margaux 2015", "fr"),
        ("Riesling Trocken 2020", "de"),
        ("Rioja Reserva 2017", "es"),
        ("Barolo DOCG 2016", "it"),
    ]

    @pytest.mark.asyncio
    async def test_accuracy_best_endpoint(self, client):
        """Test /ocr/best accuracy across multiple languages."""
        if not await client.is_available():
            pytest.skip("OCR service not available")
        
        results = []
        
        for text, lang in self.TEST_SAMPLES:
            image_bytes = create_test_image(text)
            
            files = {"file": ("test.png", io.BytesIO(image_bytes), "image/png")}
            start = time.perf_counter()
            async with httpx.AsyncClient(timeout=60) as http:
                r = await http.post(f"{OCR_SERVICE_URL}/ocr/best", files=files)
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            data = r.json()
            
            # Simple metric: did we extract any text?
            success = len(data["text"].strip()) > 0
            
            # Partial match: word overlap
            expected_words = set(text.lower().split())
            extracted_words = set(data["text"].lower().split())
            overlap = len(expected_words & extracted_words)
            
            results.append({
                "expected": text,
                "extracted": data["text"],
                "engine": data["engine"],
                "success": success,
                "overlap": overlap,
                "total_words": len(expected_words),
                "time_ms": data["processing_time_ms"],
                "total_time_ms": elapsed_ms,
            })
        
        # Summary
        successes = sum(1 for r in results if r["success"])
        avg_time = sum(r["time_ms"] for r in results) / len(results)
        
        print(f"\n  OCR Accuracy Summary:")
        print(f"    Samples: {len(results)}")
        print(f"    Success (any text): {successes}/{len(results)} ({successes/len(results)*100:.0f}%)")
        print(f"    Avg OCR time: {avg_time:.0f}ms")
        
        for r in results:
            status = "✓" if r["success"] else "✗"
            pct = r["overlap"] / r["total_words"] * 100 if r["total_words"] > 0 else 0
            print(f"    {status} '{r['expected'][:30]:<30}' -> '{r['extracted'][:30]:<30}' "
                  f"({r['engine']}, {pct:.0f}% words, {r['time_ms']:.0f}ms)")
        
        assert successes > 0  # At least some text extracted
