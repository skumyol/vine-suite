"""Live OCR evaluation endpoint for Docker container."""

import io
import time
import base64
from typing import List, Dict, Optional
from dataclasses import dataclass
from pydantic import BaseModel
from fastapi import APIRouter
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2

from config import OCRConfig

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# Lazy imports from main to avoid circular import
_get_easyocr = None
_get_paddle = None

def _get_easyocr_reader():
    global _get_easyocr
    if _get_easyocr is None:
        from main import get_easyocr_reader as fn
        _get_easyocr = fn
    return _get_easyocr()


def _get_paddle_ocr():
    global _get_paddle
    if _get_paddle is None:
        from main import get_paddle_ocr as fn
        _get_paddle = fn
    return _get_paddle()


router = APIRouter(prefix="/eval", tags=["evaluation"])


@dataclass
class TestSample:
    text: str
    lang: str
    category: str


TEST_SAMPLES = [
    TestSample("Cabernet Sauvignon 2018", "en", "varietal"),
    TestSample("Napa Valley Reserve", "en", "region"),
    TestSample("Chateau Margaux 2015", "fr", "bordeaux"),
    TestSample("Grand Cru Classe", "fr", "classification"),
    TestSample("Riesling Trocken 2020", "de", "german"),
    TestSample("Weingut Dr. Loosen", "de", "producer"),
    TestSample("Rioja Reserva 2017", "es", "spanish"),
    TestSample("Bodegas Muga", "es", "producer"),
    TestSample("Barolo DOCG 2016", "it", "italian"),
    TestSample("Brunello di Montalcino", "it", "italian"),
]


def create_test_image(text: str, width: int = 600, height: int = 200) -> bytes:
    """Create a synthetic wine label image with text."""
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
    except:
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
    
    # Add noise
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


class EvalResult(BaseModel):
    """Single evaluation result."""
    sample: str
    expected: str
    extracted: str
    confidence: float
    word_overlap: float
    time_ms: float
    passed: bool


class EngineResult(BaseModel):
    """Results for one OCR engine."""
    engine: str
    available: bool
    results: List[EvalResult]
    avg_confidence: float
    avg_time_ms: float
    avg_word_overlap: float
    accuracy: float


class EvaluationResponse(BaseModel):
    """Full evaluation response."""
    status: str
    total_samples: int
    engines: List[EngineResult]
    summary: Dict[str, object]


def run_easyocr_eval(samples: List[TestSample]) -> EngineResult:
    """Evaluate EasyOCR on test samples."""
    results = []
    
    try:
        reader = _get_easyocr_reader()
    except Exception as e:
        return EngineResult(
            engine="easyocr",
            available=False,
            results=[],
            avg_confidence=0.0,
            avg_time_ms=0.0,
            avg_word_overlap=0.0,
            accuracy=0.0,
        )
    
    for sample in samples:
        image_bytes = create_test_image(sample.text)
        
        start = time.perf_counter()
        try:
            img_array = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            ocr_results = reader.readtext(img)
            
            texts = [text for _, text, _ in ocr_results]
            confidences = [conf for _, _, conf in ocr_results]
            
            extracted = " ".join(texts)
            confidence = sum(confidences) / len(confidences) if confidences else 0.0
            elapsed_ms = (time.perf_counter() - start) * 1000
            overlap = word_overlap_score(sample.text, extracted)
            
            results.append(EvalResult(
                sample=sample.text,
                expected=sample.text,
                extracted=extracted,
                confidence=round(confidence, 2),
                word_overlap=round(overlap, 2),
                time_ms=round(elapsed_ms, 1),
                passed=overlap >= 0.8,
            ))
        except Exception as e:
            results.append(EvalResult(
                sample=sample.text,
                expected=sample.text,
                extracted=f"ERROR: {str(e)[:50]}",
                confidence=0.0,
                word_overlap=0.0,
                time_ms=0.0,
                passed=False,
            ))
    
    if results:
        avg_conf = sum(r.confidence for r in results) / len(results)
        avg_time = sum(r.time_ms for r in results) / len(results)
        avg_overlap = sum(r.word_overlap for r in results) / len(results)
        accuracy = sum(1 for r in results if r.passed) / len(results)
    else:
        avg_conf = avg_time = avg_overlap = accuracy = 0.0
    
    return EngineResult(
        engine="easyocr",
        available=True,
        results=results,
        avg_confidence=round(avg_conf, 2),
        avg_time_ms=round(avg_time, 1),
        avg_word_overlap=round(avg_overlap, 2),
        accuracy=round(accuracy, 2),
    )


def run_tesseract_eval(samples: List[TestSample]) -> EngineResult:
    """Evaluate Tesseract on test samples."""
    if not TESSERACT_AVAILABLE or not OCRConfig.is_engine_enabled("tesseract"):
        return EngineResult(
            engine="tesseract",
            available=False,
            results=[],
            avg_confidence=0.0,
            avg_time_ms=0.0,
            avg_word_overlap=0.0,
            accuracy=0.0,
        )
    
    results = []
    
    for sample in samples:
        image_bytes = create_test_image(sample.text)
        
        start = time.perf_counter()
        try:
            img = Image.open(io.BytesIO(image_bytes))
            
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
            texts = []
            confidences = []
            for i, text in enumerate(data['text']):
                if int(data['conf'][i]) > 0 and text.strip():
                    texts.append(text)
                    confidences.append(int(data['conf'][i]) / 100.0)
            
            extracted = " ".join(texts)
            confidence = sum(confidences) / len(confidences) if confidences else 0.0
            elapsed_ms = (time.perf_counter() - start) * 1000
            overlap = word_overlap_score(sample.text, extracted)
            
            results.append(EvalResult(
                sample=sample.text,
                expected=sample.text,
                extracted=extracted,
                confidence=round(confidence, 2),
                word_overlap=round(overlap, 2),
                time_ms=round(elapsed_ms, 1),
                passed=overlap >= 0.8,
            ))
        except Exception as e:
            results.append(EvalResult(
                sample=sample.text,
                expected=sample.text,
                extracted=f"ERROR: {str(e)[:50]}",
                confidence=0.0,
                word_overlap=0.0,
                time_ms=0.0,
                passed=False,
            ))
    
    if results:
        avg_conf = sum(r.confidence for r in results) / len(results)
        avg_time = sum(r.time_ms for r in results) / len(results)
        avg_overlap = sum(r.word_overlap for r in results) / len(results)
        accuracy = sum(1 for r in results if r.passed) / len(results)
    else:
        avg_conf = avg_time = avg_overlap = accuracy = 0.0
    
    return EngineResult(
        engine="tesseract",
        available=True,
        results=results,
        avg_confidence=round(avg_conf, 2),
        avg_time_ms=round(avg_time, 1),
        avg_word_overlap=round(avg_overlap, 2),
        accuracy=round(accuracy, 2),
    )


def run_paddle_eval(samples: List[TestSample]) -> EngineResult:
    """Evaluate PaddleOCR on test samples."""
    try:
        ocr = _get_paddle_ocr()
    except Exception as e:
        return EngineResult(
            engine="paddle",
            available=False,
            results=[],
            avg_confidence=0.0,
            avg_time_ms=0.0,
            avg_word_overlap=0.0,
            accuracy=0.0,
        )
    
    results = []
    
    for sample in samples:
        image_bytes = create_test_image(sample.text)
        
        start = time.perf_counter()
        try:
            # Save to temp file for PaddleOCR
            temp_path = "/tmp/paddle_eval.png"
            with open(temp_path, "wb") as f:
                f.write(image_bytes)
            
            ocr_result = ocr.ocr(temp_path)
            
            texts = []
            confidences = []
            if ocr_result and ocr_result[0]:
                for line in ocr_result[0]:
                    if line:
                        text = line[1][0]
                        conf = line[1][1]
                        texts.append(text)
                        confidences.append(conf)
            
            extracted = " ".join(texts)
            confidence = sum(confidences) / len(confidences) if confidences else 0.0
            elapsed_ms = (time.perf_counter() - start) * 1000
            overlap = word_overlap_score(sample.text, extracted)
            
            results.append(EvalResult(
                sample=sample.text,
                expected=sample.text,
                extracted=extracted,
                confidence=round(confidence, 2),
                word_overlap=round(overlap, 2),
                time_ms=round(elapsed_ms, 1),
                passed=overlap >= 0.8,
            ))
        except Exception as e:
            results.append(EvalResult(
                sample=sample.text,
                expected=sample.text,
                extracted=f"ERROR: {str(e)[:50]}",
                confidence=0.0,
                word_overlap=0.0,
                time_ms=0.0,
                passed=False,
            ))
    
    if results:
        avg_conf = sum(r.confidence for r in results) / len(results)
        avg_time = sum(r.time_ms for r in results) / len(results)
        avg_overlap = sum(r.word_overlap for r in results) / len(results)
        accuracy = sum(1 for r in results if r.passed) / len(results)
    else:
        avg_conf = avg_time = avg_overlap = accuracy = 0.0
    
    return EngineResult(
        engine="paddle",
        available=True,
        results=results,
        avg_confidence=round(avg_conf, 2),
        avg_time_ms=round(avg_time, 1),
        avg_word_overlap=round(avg_overlap, 2),
        accuracy=round(accuracy, 2),
    )


@router.get("/run", response_model=EvaluationResponse)
async def run_evaluation() -> EvaluationResponse:
    """
    Run live OCR evaluation on all enabled engines.
    
    Tests each engine on 10 synthetic wine label images and returns
    accuracy metrics, timing, and confidence scores.
    """
    samples = TEST_SAMPLES
    
    engines = []
    
    # Run EasyOCR
    if OCRConfig.is_engine_enabled("easyocr"):
        engines.append(run_easyocr_eval(samples))
    
    # Run Tesseract
    if OCRConfig.is_engine_enabled("tesseract"):
        engines.append(run_tesseract_eval(samples))
    
    # Run PaddleOCR
    if OCRConfig.is_engine_enabled("paddle"):
        engines.append(run_paddle_eval(samples))
    
    # Summary
    available_engines = [e for e in engines if e.available]
    if available_engines:
        overall_accuracy = sum(e.accuracy for e in available_engines) / len(available_engines)
        best_engine = max(available_engines, key=lambda e: e.accuracy)
        avg_time = sum(e.avg_time_ms for e in available_engines) / len(available_engines)
    else:
        overall_accuracy = 0.0
        best_engine = None
        avg_time = 0.0
    
    summary = {
        "engines_tested": len(engines),
        "engines_available": len(available_engines),
        "overall_accuracy": round(overall_accuracy, 2),
        "best_engine": best_engine.engine if best_engine else None,
        "best_accuracy": round(best_engine.accuracy, 2) if best_engine else 0.0,
        "avg_time_ms": round(avg_time, 1),
    }
    
    return EvaluationResponse(
        status="success",
        total_samples=len(samples),
        engines=engines,
        summary=summary,
    )


@router.get("/quick")
async def quick_evaluation():
    """
    Quick evaluation - returns summary only (faster).
    """
    response = await run_evaluation()
    return {
        "status": response.status,
        "summary": response.summary,
        "engine_scores": {
            e.engine: {
                "available": e.available,
                "accuracy": e.accuracy,
                "avg_time_ms": e.avg_time_ms,
            }
            for e in response.engines
        },
    }
