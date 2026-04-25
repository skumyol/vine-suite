#!/bin/bash
# Download OCR models locally for fast container builds

set -e

echo "========================================"
echo "Setting up OCR model cache"
echo "========================================"

MODEL_DIR="$HOME/.cache/ocr-models"
mkdir -p "$MODEL_DIR"/{easyocr,paddle}

cd /Users/skumyol/Documents/GitHub/vine-suite/vine-api

echo ""
echo "Installing OCR packages locally (for model download)..."
if [ -d "backend/.venv" ]; then
    source backend/.venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "No venv found, creating one..."
    python3 -m venv .venv
    source .venv/bin/activate
fi

pip install -q easyocr paddleocr pillow numpy

echo ""
echo "Downloading EasyOCR models..."
python3 -c "
import easyocr
import os
os.makedirs('$MODEL_DIR/easyocr', exist_ok=True)
reader = easyocr.Reader(
    ['en', 'fr', 'de', 'es', 'it'],
    model_storage_directory='$MODEL_DIR/easyocr',
    download_enabled=True
)
print('EasyOCR models downloaded to $MODEL_DIR/easyocr')
"

echo ""
echo "Downloading PaddleOCR models..."
python3 -c "
from paddleocr import PaddleOCR
import os
os.makedirs('$MODEL_DIR/paddle', exist_ok=True)
ocr = PaddleOCR(
    use_angle_cls=True,
    lang='en',
    det_model_dir='$MODEL_DIR/paddle/det',
    rec_model_dir='$MODEL_DIR/paddle/rec',
    cls_model_dir='$MODEL_DIR/paddle/cls'
)
print('PaddleOCR models downloaded to $MODEL_DIR/paddle')
"

echo ""
echo "========================================"
echo "Model cache complete at:"
echo "  $MODEL_DIR"
echo ""
echo "Disk usage:"
du -sh "$MODEL_DIR"/* 2>/dev/null || true
echo "========================================"
echo ""
echo "Now you can build the container:"
echo "  docker-compose build ocr-service"
echo "  docker-compose up -d ocr-service"
