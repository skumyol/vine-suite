"""
Base ABC interfaces and shared implementations for service providers.

DRY design: Base classes handle common functionality, providers only override hooks.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Callable
from enum import Enum
import asyncio


class ProviderError(Exception):
    """Base exception for provider failures."""
    pass


class ProviderTimeoutError(ProviderError):
    """Provider operation timed out."""
    pass


class ProviderQuotaError(ProviderError):
    """Provider quota exhausted (rate limit or credits)."""
    pass


class ProviderConfigError(ProviderError):
    """Provider misconfigured."""
    pass


@dataclass
class OCRResult:
    """Result from OCR extraction."""
    text: str
    confidence: float = 0.0
    bounding_boxes: Optional[List[Dict[str, Any]]] = None
    language: Optional[str] = None
    raw_metadata: Optional[Dict[str, Any]] = None


@dataclass
class VLMVerificationResult:
    """Result from VLM image verification."""
    matches: bool
    confidence: float = 0.0
    extracted_fields: Optional[Dict[str, str]] = None
    reasoning: Optional[str] = None
    raw_metadata: Optional[Dict[str, Any]] = None


@dataclass
class SearchItem:
    """A single search result item."""
    url: str
    title: Optional[str] = None
    source: str = ""
    page_url: Optional[str] = None
    domain: Optional[str] = None
    score: float = 0.0
    thumbnail_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SearchResult:
    """Result from image search."""
    items: List[SearchItem]
    query: str
    total_results: int = 0
    source: Optional[str] = None
    raw_metadata: Optional[Dict[str, Any]] = None


class BaseProvider(ABC):
    """Base class with shared provider functionality."""
    
    name: str = "base"
    _impl_callable: Optional[Callable] = None
    _config_check: Optional[Callable] = None
    
    async def is_available(self) -> bool:
        """Check if provider is configured - override _config_check or this method."""
        if self._config_check:
            return await asyncio.to_thread(self._config_check) if self._config_check else False
        return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Return health status - providers can override capabilities."""
        capabilities = getattr(self, 'capabilities', {})
        return {
            "name": self.name,
            "available": await self.is_available(),
            **capabilities,
        }


class OCRProvider(BaseProvider):
    """OCR providers: EasyOCR, Tesseract, PaddleOCR."""
    
    name: str = "base"
    supports_languages: List[str] = []
    max_image_size: Optional[int] = None
    _preprocessor = None
    
    def _get_preprocessor(self):
        """Lazy-load shared OCR preprocessor."""
        if self._preprocessor is None:
            from app.services.ocr.preprocessor import get_preprocessor
            self._preprocessor = get_preprocessor()
        return self._preprocessor
    
    async def extract_text(self, image_bytes: bytes) -> OCRResult:
        """Extract text from image bytes. Override _extract_text_impl for engine-specific logic."""
        # Preprocess if available
        try:
            preprocessor = self._get_preprocessor()
            image_bytes = preprocessor.preprocess(image_bytes)
        except Exception:
            pass  # Fail open: use original bytes if preprocessing fails
        
        return await self._extract_text_impl(image_bytes)
    
    @abstractmethod
    async def _extract_text_impl(self, image_bytes: bytes) -> OCRResult:
        """Engine-specific text extraction. Implement in subclass."""
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """Return health status and capabilities."""
        base = await super().health_check()
        base.update({
            "supports_languages": self.supports_languages,
            "max_image_size": self.max_image_size,
            "preprocessing": "enabled",
        })
        return base


class VLMProvider(BaseProvider):
    """Abstract base class for Vision-Language Model providers. Implementations: Gemini, PaddleVLM, Qwen."""
    
    name: str = "base"
    max_image_size: Optional[int] = None
    supports_batch: bool = False
    
    @abstractmethod
    async def verify_image(
        self, 
        image_bytes: bytes, 
        expected_identity: Dict[str, Optional[str]]
    ) -> VLMVerificationResult:
        """Verify if image matches expected wine identity."""
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """Return health status and capabilities."""
        base = await super().health_check()
        base.update({
            "max_image_size": self.max_image_size,
            "supports_batch": self.supports_batch,
        })
        return base


class SearchProvider(BaseProvider):
    """Abstract base class for image search providers. Implementations: Playwright, SerpAPI, Google."""
    
    name: str = "base"
    max_results: int = 10
    supports_image_search: bool = True
    
    @abstractmethod
    async def search_by_text(self, query: str, max_results: Optional[int] = None) -> SearchResult:
        """Search for images by text query."""
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """Return health status and capabilities."""
        base = await super().health_check()
        base.update({
            "max_results": self.max_results,
            "supports_image_search": self.supports_image_search,
        })
        return base
