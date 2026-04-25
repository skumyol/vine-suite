"""OCR Service Client - HTTP client for OCR microservice."""

import os
from typing import Optional
import httpx

from app.services.base import OCRProvider, OCRResult
from app.services.ocr.preprocessor import OCRPreprocessor


class OCRServiceClient(OCRProvider):
    """
    Client for OCR microservice.
    
    Calls external OCR container via HTTP instead of running engines locally.
    This allows easy scaling and deployment.
    """
    
    name = "ocr-service"
    supports_languages = ["en", "fr", "de", "es", "it", "ch", "jp"]
    max_image_size = 10 * 1024 * 1024  # 10MB
    
    def __init__(self, base_url: Optional[str] = None, engine: str = "best"):
        """
        Initialize OCR service client.
        
        Args:
            base_url: OCR service URL (default: http://localhost:8001)
            engine: Which engine to use (easyocr, tesseract, paddle, best)
        """
        self.base_url = base_url or os.getenv("OCR_SERVICE_URL", "http://localhost:8001")
        self.engine = engine
        self._preprocessor = OCRPreprocessor()
    
    async def is_available(self) -> bool:
        """Check if OCR service is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except:
            return False
    
    async def _extract_text_impl(self, image_bytes: bytes) -> OCRResult:
        """Call OCR service to extract text."""
        # Preprocess locally before sending
        processed = self._preprocessor.preprocess(image_bytes)
        
        # Call OCR service
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"file": ("image.png", processed, "image/png")}
            
            response = await client.post(
                f"{self.base_url}/ocr/{self.engine}",
                files=files
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("error"):
                raise Exception(f"OCR service error: {data['error']}")
            
            return OCRResult(
                text=data["text"],
                confidence=data["confidence"],
                language=data.get("language", "en"),
                bounding_boxes=data.get("bounding_boxes"),
                raw_metadata={
                    "engine": data["engine"],
                    "processing_time_ms": data["processing_time_ms"],
                }
            )
    
    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """Extract text with preprocessing."""
        return await self._extract_text_impl(image_bytes)
    
    async def health_check(self) -> dict:
        """Get health status from OCR service."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                data = response.json()
                return {
                    "name": self.name,
                    "available": True,
                    "service_status": data.get("status"),
                    "engines": data.get("engines", {}),
                    "engine": self.engine,
                    "preprocessing": "enabled",
                }
        except Exception as e:
            return {
                "name": self.name,
                "available": False,
                "error": str(e),
            }
