"""OCR providers and preprocessing."""

from app.services.ocr.client import OCRServiceClient
from app.services.ocr.easyocr import EasyOCRProvider
from app.services.ocr.ensemble import EnsembleOCRProvider
from app.services.ocr.paddle import PaddleOCRProvider
from app.services.ocr.preprocessor import OCRPreprocessor, PreprocessConfig, get_preprocessor
from app.services.ocr.tesseract import TesseractProvider

__all__ = [
    "EasyOCRProvider",
    "EnsembleOCRProvider",
    "OCRPreprocessor",
    "OCRServiceClient",
    "PaddleOCRProvider",
    "PreprocessConfig",
    "TesseractProvider",
    "get_preprocessor",
]
