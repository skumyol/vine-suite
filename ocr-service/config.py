"""OCR Service Configuration - Control which engines run."""

import os
from typing import Set


class OCRConfig:
    """Configuration for OCR service."""
    
    # Which engines to enable (comma-separated: easyocr,tesseract,paddle)
    ENABLED_ENGINES: Set[str] = set(
        os.getenv("ENABLED_ENGINES", "easyocr").split(",")
    )
    
    # Default engine for /ocr/best endpoint
    DEFAULT_ENGINE: str = os.getenv("DEFAULT_ENGINE", "easyocr")
    
    # Timeout for OCR operations (seconds)
    OCR_TIMEOUT: int = int(os.getenv("OCR_TIMEOUT", "30"))
    
    # Max image size (bytes)
    MAX_IMAGE_SIZE: int = int(os.getenv("MAX_IMAGE_SIZE", "10485760"))  # 10MB
    
    # Enable GPU for PaddleOCR (if available)
    USE_GPU: bool = os.getenv("USE_GPU", "false").lower() == "true"
    
    # Memory optimization settings
    # Run garbage collection after each request to minimize memory footprint
    GC_AFTER_REQUEST: bool = os.getenv("GC_AFTER_REQUEST", "true").lower() == "true"
    
    # Limit concurrent requests to prevent memory spikes
    MAX_CONCURRENT_REQUESTS: int = int(os.getenv("MAX_CONCURRENT_REQUESTS", "3"))
    
    # Pre-allocate work pool size for consistent memory usage
    WORKER_THREADS: int = int(os.getenv("WORKER_THREADS", "2"))
    
    @classmethod
    def is_engine_enabled(cls, engine: str) -> bool:
        """Check if an engine is enabled."""
        return engine in cls.ENABLED_ENGINES
    
    @classmethod
    def get_enabled_engines(cls) -> list:
        """Get list of enabled engines."""
        # Filter to valid engines
        valid = {"easyocr", "tesseract", "paddle"}
        return [e for e in cls.ENABLED_ENGINES if e in valid]
    
    @classmethod
    def summary(cls) -> dict:
        """Get config summary for monitoring."""
        return {
            "enabled_engines": cls.get_enabled_engines(),
            "default_engine": cls.DEFAULT_ENGINE,
            "use_gpu": cls.USE_GPU,
            "gc_after_request": cls.GC_AFTER_REQUEST,
            "max_concurrent_requests": cls.MAX_CONCURRENT_REQUESTS,
            "worker_threads": cls.WORKER_THREADS,
            "max_image_size_mb": cls.MAX_IMAGE_SIZE / (1024 * 1024),
        }
