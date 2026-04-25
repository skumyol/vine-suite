"""
Provider registry with dependency injection.

Manages provider instances and configuration.
"""

from typing import Dict, Type, Optional
from app.services.base import OCRProvider, VLMProvider, SearchProvider
from app.services.ocr import EasyOCRProvider, EnsembleOCRProvider, TesseractProvider, PaddleOCRProvider
from app.services.vlm import GeminiVLMProvider, MistralVLMProvider, PaddleVLMProvider, QwenVLMProvider
from app.services.search import PlaywrightSearchProvider, SerpAPISearchProvider, GoogleSearchProvider, OpenSerpProvider


class ProviderRegistry:
    """
    Registry for managing provider instances.
    
    Provides lazy initialization and configuration-based selection.
    """
    
    # Provider class mappings
    OCR_PROVIDERS: Dict[str, Type[OCRProvider]] = {
        "easyocr": EasyOCRProvider,
        "tesseract": TesseractProvider,
        "paddleocr": PaddleOCRProvider,
        "ensemble": EnsembleOCRProvider,
    }
    
    VLM_PROVIDERS: Dict[str, Type[VLMProvider]] = {
        "gemini": GeminiVLMProvider,
        "mistral": MistralVLMProvider,
        "paddlevlm": PaddleVLMProvider,
        "qwen": QwenVLMProvider,
    }
    
    SEARCH_PROVIDERS: Dict[str, Type[SearchProvider]] = {
        "playwright": PlaywrightSearchProvider,
        "serpapi": SerpAPISearchProvider,
        "google": GoogleSearchProvider,
        "openserp": OpenSerpProvider,
    }
    
    def __init__(
        self,
        ocr_provider: str = "easyocr",
        vlm_provider: str = "gemini",
        search_provider: str = "openserp",
    ):
        """
        Initialize registry with provider selections.
        
        Args:
            ocr_provider: Name of OCR provider to use
            vlm_provider: Name of VLM provider to use
            search_provider: Name of search provider to use
        """
        self._ocr_name = ocr_provider
        self._vlm_name = vlm_provider
        self._search_name = search_provider
        
        # Cached instances
        self._ocr_instance: Optional[OCRProvider] = None
        self._vlm_instance: Optional[VLMProvider] = None
        self._search_instance: Optional[SearchProvider] = None
    
    def get_ocr(self) -> OCRProvider:
        """Get configured OCR provider instance (lazy initialization)."""
        if self._ocr_instance is None:
            provider_class = self.OCR_PROVIDERS.get(self._ocr_name)
            if provider_class is None:
                raise ValueError(f"Unknown OCR provider: {self._ocr_name}")
            self._ocr_instance = provider_class()
        return self._ocr_instance
    
    def get_vlm(self) -> VLMProvider:
        """Get configured VLM provider instance (lazy initialization)."""
        if self._vlm_instance is None:
            provider_class = self.VLM_PROVIDERS.get(self._vlm_name)
            if provider_class is None:
                raise ValueError(f"Unknown VLM provider: {self._vlm_name}")
            self._vlm_instance = provider_class()
        return self._vlm_instance
    
    def get_search(self) -> SearchProvider:
        """Get configured search provider instance (lazy initialization)."""
        if self._search_instance is None:
            provider_class = self.SEARCH_PROVIDERS.get(self._search_name)
            if provider_class is None:
                raise ValueError(f"Unknown search provider: {self._search_name}")
            self._search_instance = provider_class()
        return self._search_instance
    
    async def list_available_ocr(self) -> Dict[str, bool]:
        """List all OCR providers and their availability status."""
        results = {}
        for name, provider_class in self.OCR_PROVIDERS.items():
            results[name] = await provider_class().is_available()
        return results
    
    async def list_available_vlm(self) -> Dict[str, bool]:
        """List all VLM providers and their availability status."""
        results = {}
        for name, provider_class in self.VLM_PROVIDERS.items():
            results[name] = await provider_class().is_available()
        return results
    
    async def list_available_search(self) -> Dict[str, bool]:
        """List all search providers and their availability status."""
        results = {}
        for name, provider_class in self.SEARCH_PROVIDERS.items():
            results[name] = await provider_class().is_available()
        return results
    
    async def health_check(self) -> Dict[str, any]:
        """Run health checks on all providers."""
        return {
            "ocr": {
                "configured": self._ocr_name,
                "available": await self.get_ocr().is_available(),
                "all": self.list_available_ocr(),
            },
            "vlm": {
                "configured": self._vlm_name,
                "available": await self.get_vlm().is_available(),
                "all": self.list_available_vlm(),
            },
            "search": {
                "configured": self._search_name,
                "available": await self.get_search().is_available(),
                "all": self.list_available_search(),
            },
        }


# Global registry instance (will be initialized with config in Phase 3)
_registry: Optional[ProviderRegistry] = None


def get_registry() -> ProviderRegistry:
    """Get or create the global provider registry."""
    global _registry
    if _registry is None:
        # Phase 1: Default configuration (all stubs return unavailable)
        _registry = ProviderRegistry()
    return _registry


def set_registry(registry: ProviderRegistry) -> None:
    """Set the global registry (for testing/dependency injection)."""
    global _registry
    _registry = registry
