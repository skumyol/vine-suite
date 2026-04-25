#!/usr/bin/env python3
"""OCR Benchmark - Measure text extraction success rate and performance.

Run with installed OCR engines to get real metrics:
    pip install easyocr paddlepaddle paddleocr pytesseract
    python tests/ocr_benchmark.py
"""

import asyncio
import time
import sys
from dataclasses import dataclass
from typing import List, Dict, Any
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ocr import EasyOCRProvider, TesseractProvider, PaddleOCRProvider
from app.services.ocr.preprocessor import OCRPreprocessor


@dataclass
class BenchmarkResult:
    provider: str
    sample: str
    expected: str
    extracted: str
    confidence: float
    success: bool
    time_ms: float


BENCHMARK_SAMPLES = [
    # Simple English
    "Cabernet Sauvignon 2018",
    "Napa Valley Reserve",
    # French labels
    "Château Margaux 2015",
    "Grand Cru Classé",
    # German labels
    "Riesling Trocken 2020",
    # Italian labels
    "Barolo DOCG 2016",
    # Spanish labels
    "Rioja Reserva 2017",
    # Complex names
    "Domaine Rossignol-Trapet Latricieres-Chambertin",
    "Château Fonroque Saint-Émilion",
    "Weingut Dr. Loosen Erdener Prälat",
]


def create_test_image(text: str, width: int = 700, height: int = 200) -> bytes:
    """Create synthetic wine label image."""
    img = Image.new('RGB', (width, height), color='#f5f5f0')  # Creamy label color
    draw = ImageDraw.Draw(img)
    
    # Try to use nice fonts
    try:
        # macOS system fonts
        font = ImageFont.truetype("/System/Library/Fonts/Georgia.ttf", 36)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 36)
        except:
            font = ImageFont.load_default()
    
    # Center text
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (width - text_width) // 2
    y = height // 2 - 20
    
    # Draw with slight shadow for realism
    draw.text((x+2, y+2), text, fill='#cccccc', font=font)
    draw.text((x, y), text, fill='#1a1a1a', font=font)
    
    # Convert and add slight noise
    arr = np.array(img)
    noise = np.random.normal(0, 3, arr.shape).astype(np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    # Save to bytes
    import cv2
    _, buf = cv2.imencode('.png', cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    return buf.tobytes()


def calculate_similarity(expected: str, extracted: str) -> float:
    """Calculate text similarity (0-1)."""
    expected_words = set(expected.lower().split())
    extracted_words = set(extracted.lower().split())
    
    if not expected_words:
        return 0.0
    
    overlap = len(expected_words & extracted_words)
    return overlap / len(expected_words)


async def benchmark_provider(name: str, provider, samples: List[str]) -> Dict[str, Any]:
    """Benchmark a single OCR provider."""
    results = []
    
    if not await provider.is_available():
        return {
            "provider": name,
            "available": False,
            "results": [],
            "error": f"{name} not installed"
        }
    
    print(f"\n{'='*60}")
    print(f"Benchmarking: {name}")
    print(f"{'='*60}")
    
    for sample in samples:
        image_bytes = create_test_image(sample)
        
        start = time.perf_counter()
        try:
            result = await provider.extract_text(image_bytes)
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            similarity = calculate_similarity(sample, result.text)
            success = similarity > 0.3  # At least 30% word overlap
            
            results.append(BenchmarkResult(
                provider=name,
                sample=sample[:40],
                expected=sample,
                extracted=result.text[:60],
                confidence=result.confidence,
                success=success,
                time_ms=elapsed_ms
            ))
            
            status = "✓" if success else "✗"
            print(f"{status} '{sample[:40]:<40}' -> '{result.text[:40]:<40}' "
                  f"(sim: {similarity:.2f}, conf: {result.confidence:.2f}, {elapsed_ms:.0f}ms)")
            
        except Exception as e:
            print(f"✗ '{sample[:40]:<40}' -> ERROR: {str(e)[:40]}")
            results.append(BenchmarkResult(
                provider=name,
                sample=sample[:40],
                expected=sample,
                extracted=f"ERROR: {str(e)}",
                confidence=0.0,
                success=False,
                time_ms=0
            ))
    
    return {
        "provider": name,
        "available": True,
        "results": results
    }


async def main():
    """Run full OCR benchmark."""
    print("\n" + "="*60)
    print("OCR PROVIDER BENCHMARK")
    print("="*60)
    print(f"Samples: {len(BENCHMARK_SAMPLES)}")
    print(f"Languages: English, French, German, Italian, Spanish")
    
    providers = [
        ("EasyOCR", EasyOCRProvider()),
        ("Tesseract", TesseractProvider()),
        ("PaddleOCR", PaddleOCRProvider()),
    ]
    
    all_results = []
    
    for name, provider in providers:
        result = await benchmark_provider(name, provider, BENCHMARK_SAMPLES)
        all_results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("BENCHMARK SUMMARY")
    print("="*60)
    
    for result in all_results:
        if not result["available"]:
            print(f"\n{result['provider']}: NOT INSTALLED")
            print(f"  Install: {get_install_command(result['provider'])}")
            continue
        
        results = result["results"]
        successes = sum(1 for r in results if r.success)
        total = len(results)
        avg_time = sum(r.time_ms for r in results) / total
        avg_confidence = sum(r.confidence for r in results) / total
        
        print(f"\n{result['provider']}:")
        print(f"  Success Rate: {successes}/{total} ({successes/total*100:.0f}%)")
        print(f"  Avg Time: {avg_time:.1f}ms")
        print(f"  Avg Confidence: {avg_confidence:.2f}")
    
    # Cross-provider comparison
    available_providers = [r for r in all_results if r["available"]]
    if len(available_providers) >= 2:
        print("\n" + "-"*60)
        print("CROSS-PROVIDER COMPARISON")
        print("-"*60)
        
        for i, sample in enumerate(BENCHMARK_SAMPLES):
            print(f"\n{i+1}. '{sample}'")
            for result in available_providers:
                r = result["results"][i]
                icon = "✓" if r.success else "✗"
                print(f"   {icon} {result['provider']:<12}: '{r.extracted[:35]:<35}' "
                      f"(conf: {r.confidence:.2f})")


def get_install_command(provider: str) -> str:
    """Get install command for provider."""
    commands = {
        "EasyOCR": "pip install easyocr",
        "Tesseract": "brew install tesseract (macOS) or apt-get install tesseract-ocr",
        "PaddleOCR": "pip install paddlepaddle paddleocr",
    }
    return commands.get(provider, "See documentation")


if __name__ == "__main__":
    asyncio.run(main())
