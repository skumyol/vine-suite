"""OCR Microservice - All engines pre-warmed, hot in memory."""

import io
import time
import os
import gc
import asyncio
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config import OCRConfig

# Global engine instances - eagerly loaded at startup
_easyocr_reader = None
_paddle_ocr = None


def _warmup_easyocr():
    """Load EasyOCR into memory."""
    global _easyocr_reader
    if OCRConfig.is_engine_enabled("easyocr"):
        print("[WARMUP] Loading EasyOCR...", flush=True)
        import easyocr
        # Use mounted model directory if available
        model_dir = os.getenv("EASYOCR_MODULE_PATH", None)
        _easyocr_reader = easyocr.Reader(
            ['en', 'fr', 'de', 'es', 'it'],
            model_storage_directory=model_dir,
            download_enabled=(model_dir is None)  # Only download if no cache
        )
        print("[WARMUP] EasyOCR ready", flush=True)


def _warmup_tesseract():
    """Verify Tesseract is available."""
    if OCRConfig.is_engine_enabled("tesseract"):
        print("[WARMUP] Checking Tesseract...", flush=True)
        import pytesseract
        version = pytesseract.get_tesseract_version()
        print(f"[WARMUP] Tesseract ready (v{version})", flush=True)


def _warmup_paddle():
    """Load PaddleOCR into memory."""
    global _paddle_ocr
    if OCRConfig.is_engine_enabled("paddle"):
        print("[WARMUP] Loading PaddleOCR...", flush=True)
        from paddleocr import PaddleOCR
        # Use mounted model directory if available
        base_dir = os.getenv("PADDLE_OCR_MODEL_DIR", None)
        kwargs = {
            "use_angle_cls": True,
            "lang": 'en',
        }
        if base_dir:
            kwargs["det_model_dir"] = f"{base_dir}/det"
            kwargs["rec_model_dir"] = f"{base_dir}/rec"
            kwargs["cls_model_dir"] = f"{base_dir}/cls"
        _paddle_ocr = PaddleOCR(**kwargs)
        print("[WARMUP] PaddleOCR ready", flush=True)


def _run_dummy_ocr():
    """Run a tiny dummy OCR to warm caches and ensure everything works."""
    dummy = Image.new('RGB', (100, 50), color='white')
    from PIL import ImageDraw
    draw = ImageDraw.Draw(dummy)
    draw.text((10, 10), "test", fill='black')
    
    buf = io.BytesIO()
    dummy.save(buf, format='PNG')
    buf.seek(0)
    
    if _easyocr_reader:
        _easyocr_reader.readtext(np.array(dummy))
        print("[WARMUP] EasyOCR cache primed", flush=True)
    
    if OCRConfig.is_engine_enabled("tesseract"):
        import pytesseract
        pytesseract.image_to_string(dummy)
        print("[WARMUP] Tesseract cache primed", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eagerly load all enabled engines before accepting requests."""
    print(f"\n{'='*60}", flush=True)
    print("OCR Service Starting - Warming up engines...", flush=True)
    print(f"Enabled engines: {OCRConfig.get_enabled_engines()}", flush=True)
    print(f"{'='*60}\n", flush=True)
    
    start = time.perf_counter()
    
    # Load all engines in parallel threads (they're CPU-bound imports)
    import threading
    threads = []
    
    if OCRConfig.is_engine_enabled("easyocr"):
        t = threading.Thread(target=_warmup_easyocr)
        t.start()
        threads.append(t)
    
    if OCRConfig.is_engine_enabled("tesseract"):
        t = threading.Thread(target=_warmup_tesseract)
        t.start()
        threads.append(t)
    
    if OCRConfig.is_engine_enabled("paddle"):
        t = threading.Thread(target=_warmup_paddle)
        t.start()
        threads.append(t)
    
    # Wait for all engines to load
    for t in threads:
        t.join()
    
    # Prime caches with a tiny OCR run
    _run_dummy_ocr()
    
    # Force garbage collection to clean up warmup artifacts
    gc.collect()
    
    elapsed = (time.perf_counter() - start) * 1000
    print(f"\n{'='*60}", flush=True)
    print(f"All engines warmed up in {elapsed:.0f}ms - Ready for requests", flush=True)
    print(f"{'='*60}\n", flush=True)
    
    yield
    
    # Shutdown
    print("OCR Service shutting down", flush=True)


app = FastAPI(title="OCR Service", version="2.0.0", lifespan=lifespan)

# Include evaluation router
from evaluation import router as eval_router
app.include_router(eval_router)


class OCRResult(BaseModel):
    """OCR extraction result."""
    text: str
    confidence: float = 0.0
    engine: str
    language: str = "en"
    processing_time_ms: float
    bounding_boxes: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    engines: Dict[str, str]
    version: str = "1.0.0"


def check_engine_enabled(engine: str):
    """Check if engine is enabled in config."""
    if not OCRConfig.is_engine_enabled(engine):
        raise HTTPException(
            status_code=503,
            detail=f"Engine '{engine}' is disabled. Enabled: {OCRConfig.get_enabled_engines()}"
        )


def get_easyocr_reader():
    """Return pre-warmed EasyOCR reader."""
    global _easyocr_reader
    if _easyocr_reader is None:
        raise HTTPException(status_code=503, detail="EasyOCR not loaded")
    return _easyocr_reader


def get_paddle_ocr():
    """Return pre-warmed PaddleOCR instance."""
    global _paddle_ocr
    if _paddle_ocr is None:
        raise HTTPException(status_code=503, detail="PaddleOCR not loaded")
    return _paddle_ocr


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """Preprocess image for OCR."""
    image = Image.open(io.BytesIO(image_bytes))
    
    # Convert to RGB if necessary
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Resize if too large
    max_dim = 2000
    if max(image.size) > max_dim:
        ratio = max_dim / max(image.size)
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    return np.array(image)


@app.post("/ocr/easyocr", response_model=OCRResult)
async def ocr_easyocr(
    file: UploadFile = File(...),
    language: str = "en"
):
    """Extract text using EasyOCR."""
    check_engine_enabled("easyocr")
    start = time.perf_counter()
    
    try:
        contents = await file.read()
        image = preprocess_image(contents)
        
        reader = get_easyocr_reader()
        results = reader.readtext(image)
        
        texts = []
        confidences = []
        bboxes = []
        
        for bbox, text, conf in results:
            texts.append(text)
            confidences.append(float(conf))
            # Convert numpy arrays to Python lists for JSON serialization
            coords = [[int(coord[0]), int(coord[1])] for coord in bbox]
            bboxes.append({
                "coords": coords,
                "text": text,
                "confidence": float(conf)
            })
        
        full_text = " ".join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        
        result = OCRResult(
            text=full_text,
            confidence=avg_conf,
            engine="easyocr",
            language=language,
            processing_time_ms=(time.perf_counter() - start) * 1000,
            bounding_boxes=bboxes
        )
        # Use jsonable_encoder to handle numpy types
        return JSONResponse(content=jsonable_encoder(result))
        
    except Exception as e:
        return OCRResult(
            text="",
            confidence=0.0,
            engine="easyocr",
            language=language,
            processing_time_ms=(time.perf_counter() - start) * 1000,
            error=str(e)
        )


@app.post("/ocr/tesseract", response_model=OCRResult)
async def ocr_tesseract(
    file: UploadFile = File(...),
    language: str = "eng"
):
    """Extract text using Tesseract."""
    check_engine_enabled("tesseract")
    start = time.perf_counter()
    
    try:
        import pytesseract
        from pytesseract import Output
        
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Get detailed data including bounding boxes
        data = pytesseract.image_to_data(image, lang=language, output_type=Output.DICT)
        
        texts = []
        confidences = []
        bboxes = []
        
        for i in range(len(data['text'])):
            conf = int(data['conf'][i])
            text = data['text'][i]
            
            if conf > 0 and text.strip():
                texts.append(text)
                confidences.append(conf / 100.0)
                bboxes.append({
                    "x": data['left'][i],
                    "y": data['top'][i],
                    "width": data['width'][i],
                    "height": data['height'][i],
                    "text": text,
                    "confidence": conf / 100.0
                })
        
        full_text = " ".join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        
        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            engine="tesseract",
            language=language,
            processing_time_ms=(time.perf_counter() - start) * 1000,
            bounding_boxes=bboxes
        )
        
    except Exception as e:
        return OCRResult(
            text="",
            confidence=0.0,
            engine="tesseract",
            language=language,
            processing_time_ms=(time.perf_counter() - start) * 1000,
            error=str(e)
        )


@app.post("/ocr/paddle", response_model=OCRResult)
async def ocr_paddle(
    file: UploadFile = File(...),
    language: str = "en"
):
    """Extract text using PaddleOCR."""
    check_engine_enabled("paddle")
    start = time.perf_counter()
    
    try:
        contents = await file.read()
        
        # Save temporarily for PaddleOCR
        temp_path = "/tmp/temp_ocr_image.png"
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        ocr = get_paddle_ocr()
        result = ocr.ocr(temp_path)
        
        texts = []
        confidences = []
        bboxes = []
        
        if result and result[0]:
            for line in result[0]:
                bbox = line[0]
                text = line[1][0]
                conf = line[1][1]
                
                texts.append(text)
                confidences.append(conf)
                bboxes.append({
                    "coords": bbox,
                    "text": text,
                    "confidence": conf
                })
        
        full_text = " ".join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        
        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            engine="paddle",
            language=language,
            processing_time_ms=(time.perf_counter() - start) * 1000,
            bounding_boxes=bboxes
        )
        
    except Exception as e:
        return OCRResult(
            text="",
            confidence=0.0,
            engine="paddle",
            language=language,
            processing_time_ms=(time.perf_counter() - start) * 1000,
            error=str(e)
        )


@app.post("/ocr/best", response_model=OCRResult)
async def ocr_best(file: UploadFile = File(...)):
    """Try all enabled engines and return best result."""
    engines = OCRConfig.get_enabled_engines()
    results = []
    
    contents = await file.read()
    
    for engine in engines:
        try:
            # Create new UploadFile-like object
            from fastapi import UploadFile
            import io
            
            fake_file = UploadFile(
                filename=file.filename,
                file=io.BytesIO(contents)
            )
            
            if engine == "easyocr":
                result = await ocr_easyocr(fake_file)
            elif engine == "tesseract":
                result = await ocr_tesseract(fake_file)
            else:
                result = await ocr_paddle(fake_file)
            
            if not result.error and result.confidence > 0:
                results.append(result)
                
        except Exception as e:
            continue
    
    if not results:
        return OCRResult(
            text="",
            confidence=0.0,
            engine="none",
            error="All OCR engines failed"
        )
    
    # Return result with highest confidence
    best = max(results, key=lambda r: r.confidence)
    return best


import psutil


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check OCR engine availability."""
    engines_status = {}
    
    for engine in ["easyocr", "tesseract", "paddle"]:
        if not OCRConfig.is_engine_enabled(engine):
            engines_status[engine] = "disabled"
        else:
            # Check if actually loaded/working
            try:
                if engine == "easyocr":
                    get_easyocr_reader()
                elif engine == "tesseract":
                    import pytesseract
                    pytesseract.get_tesseract_version()
                elif engine == "paddle":
                    get_paddle_ocr()
                engines_status[engine] = "ready"
            except Exception as e:
                engines_status[engine] = f"error: {str(e)[:50]}"
    
    enabled_count = sum(1 for s in engines_status.values() if s == "ready")
    total_enabled = len([e for e in ["easyocr", "tesseract", "paddle"] if OCRConfig.is_engine_enabled(e)])
    
    return HealthResponse(
        status=f"ready ({enabled_count}/{total_enabled})" if enabled_count > 0 else "no engines ready",
        engines=engines_status
    )


@app.get("/stats")
async def stats():
    """Memory and performance statistics."""
    process = psutil.Process()
    mem = process.memory_info()
    
    # Trigger GC and get memory info
    gc.collect()
    
    return {
        "memory": {
            "rss_mb": round(mem.rss / 1024 / 1024, 1),
            "vms_mb": round(mem.vms / 1024 / 1024, 1),
            "percent": round(process.memory_percent(), 1),
        },
        "cpu_percent": round(process.cpu_percent(), 1),
        "engines_loaded": {
            "easyocr": _easyocr_reader is not None,
            "paddle": _paddle_ocr is not None,
            "tesseract": OCRConfig.is_engine_enabled("tesseract"),
        },
        "config": OCRConfig.summary(),
        "uptime_seconds": round(time.time() - process.create_time(), 1),
    }


@app.get("/")
async def root():
    """Service info."""
    return {
        "service": "OCR Microservice",
        "version": "2.0.0",
        "features": {
            "prewarmed_engines": True,
            "memory_optimized": True,
            "concurrent_request_limit": OCRConfig.MAX_CONCURRENT_REQUESTS,
        },
        "enabled_engines": OCRConfig.get_enabled_engines(),
        "languages": ["en", "fr", "de", "es", "it", "ch_sim", "ja"],
        "endpoints": {
            "easyocr": "/ocr/easyocr",
            "tesseract": "/ocr/tesseract",
            "paddle": "/ocr/paddle",
            "best": "/ocr/best",
            "health": "/health",
            "stats": "/stats",
        }
    }
