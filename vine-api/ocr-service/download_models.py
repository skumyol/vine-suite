#!/usr/bin/env python3
"""Download OCR models locally to cache between builds."""

import os
import sys
from pathlib import Path

# Model directories
MODEL_DIR = Path.home() / ".cache" / "ocr-models"
EASYOCR_DIR = MODEL_DIR / "easyocr"
PADDLE_DIR = MODEL_DIR / "paddle"

def download_easyocr():
    """Download EasyOCR models."""
    print("[DOWNLOAD] EasyOCR models...")
    import easyocr
    # This triggers model download
    reader = easyocr.Reader(['en', 'fr', 'de', 'es', 'it', 'ja'])
    print("[DOWNLOAD] EasyOCR models cached")
    return True

def download_paddle():
    """Download PaddleOCR models."""
    print("[DOWNLOAD] PaddleOCR models...")
    from paddleocr import PaddleOCR
    # This triggers model download
    ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False)
    print("[DOWNLOAD] PaddleOCR models cached")
    return True

def main():
    """Download all OCR models."""
    print("=" * 60)
    print("Downloading OCR models for local caching")
    print(f"Cache dir: {MODEL_DIR}")
    print("=" * 60)
    
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    try:
        results['easyocr'] = download_easyocr()
    except Exception as e:
        print(f"[ERROR] EasyOCR: {e}")
        results['easyocr'] = False
    
    try:
        results['paddle'] = download_paddle()
    except Exception as e:
        print(f"[ERROR] PaddleOCR: {e}")
        results['paddle'] = False
    
    print("\n" + "=" * 60)
    print("Download Summary:")
    for name, success in results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {name}")
    print("=" * 60)
    
    return 0 if all(results.values()) else 1

if __name__ == "__main__":
    sys.exit(main())
