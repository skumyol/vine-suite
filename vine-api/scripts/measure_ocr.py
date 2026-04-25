#!/usr/bin/env python3
"""Measure OCR baseline performance across all providers."""

import asyncio
import time
from dataclasses import dataclass
from typing import List, Dict

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

import sys
sys.path.insert(0, '/Users/skumyol/Documents/GitHub/vine-suite/vine-api')

from app.services.ocr import (
    EasyOCRProvider,
    EnsembleOCRProvider,
    TesseractProvider,
    PaddleOCRProvider,
    OCRPreprocessor,
)
from app.services.base import OCRResult


TEST_SAMPLES = [
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


def create_test_image(text: str, width: int = 600, height: int = 200) -> bytes:
    """Create a synthetic wine label image with text."""
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
    except:
        font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    draw.text((x, y), text, fill='black', font=font)
    
    arr = np.array(img)
    noise = np.random.normal(0, 5, arr.shape).astype(np.int16)
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    _, buf = cv2.imencode('.png', cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    return buf.tobytes()


def word_overlap_score(expected: str, extracted: str) -> float:
    """Calculate word overlap between expected and extracted text."""
    expected_words = set(expected.lower().split())
    extracted_words = set(extracted.lower().split())
    if not expected_words:
        return 0.0
    return len(expected_words & extracted_words) / len(expected_words)


@dataclass
class ProviderResult:
    provider: str
    sample_text: str
    extracted: str
    confidence: float
    time_ms: float
    word_overlap: float


async def test_provider(provider, name: str, samples: List[dict]) -> List[ProviderResult]:
    """Test a single provider on all samples."""
    results = []
    
    if not await provider.is_available():
        print(f"  {name}: Not available")
        return results
    
    for sample in samples:
        image_bytes = create_test_image(sample["text"])
        
        start = time.perf_counter()
        try:
            ocr_result = await provider.extract_text(image_bytes)
            elapsed_ms = (time.perf_counter() - start) * 1000
            
            overlap = word_overlap_score(sample["text"], ocr_result.text)
            results.append(ProviderResult(
                provider=name,
                sample_text=sample["text"],
                extracted=ocr_result.text,
                confidence=ocr_result.confidence,
                time_ms=elapsed_ms,
                word_overlap=overlap,
            ))
        except Exception as e:
            results.append(ProviderResult(
                provider=name,
                sample_text=sample["text"],
                extracted=f"ERROR: {e}",
                confidence=0.0,
                time_ms=0.0,
                word_overlap=0.0,
            ))
    
    return results


def print_results(results: List[ProviderResult]):
    """Print formatted results table."""
    if not results:
        print("  No results")
        return
    
    provider = results[0].provider
    avg_conf = sum(r.confidence for r in results) / len(results)
    avg_time = sum(r.time_ms for r in results) / len(results)
    avg_overlap = sum(r.word_overlap for r in results) / len(results)
    perfect = sum(1 for r in results if r.word_overlap >= 0.8)
    partial = sum(1 for r in results if 0.3 <= r.word_overlap < 0.8)
    failed = sum(1 for r in results if r.word_overlap < 0.3)
    
    print(f"\n  {provider} Summary:")
    print(f"    Avg Confidence: {avg_conf:.2f}")
    print(f"    Avg Time: {avg_time:.1f}ms")
    print(f"    Word Overlap: {avg_overlap:.2%}")
    print(f"    Perfect (≥80%): {perfect}/{len(results)}")
    print(f"    Partial (30-79%): {partial}/{len(results)}")
    print(f"    Failed (<30%): {failed}/{len(results)}")
    print(f"\n  Detailed Results:")
    for r in results:
        status = "✓" if r.word_overlap >= 0.8 else "~" if r.word_overlap >= 0.3 else "✗"
        print(f"    {status} '{r.sample_text[:30]:<30}' -> '{r.extracted[:40]}' (overlap: {r.word_overlap:.0%})")


async def main():
    print("=" * 70)
    print("OCR PIPELINE BASELINE MEASUREMENT")
    print("=" * 70)
    
    providers = [
        ("EasyOCR", EasyOCRProvider()),
        ("Tesseract", TesseractProvider()),
        ("PaddleOCR", PaddleOCRProvider()),
        ("Ensemble", EnsembleOCRProvider()),
    ]
    
    all_results = {}
    
    for name, provider in providers:
        print(f"\nTesting {name}...")
        results = await test_provider(provider, name, TEST_SAMPLES)
        if results:
            all_results[name] = results
            print_results(results)
    
    print("\n" + "=" * 70)
    print("CROSS-PROVIDER COMPARISON")
    print("=" * 70)
    
    if all_results:
        print(f"\n{'Provider':<12} {'Avg Conf':<10} {'Avg Time':<10} {'Overlap':<10} {'Perfect':<10}")
        print("-" * 60)
        for name, results in all_results.items():
            avg_conf = sum(r.confidence for r in results) / len(results)
            avg_time = sum(r.time_ms for r in results) / len(results)
            avg_overlap = sum(r.word_overlap for r in results) / len(results)
            perfect = sum(1 for r in results if r.word_overlap >= 0.8)
            print(f"{name:<12} {avg_conf:<10.2f} {avg_time:<10.1f} {avg_overlap:<10.2%} {perfect}/{len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
