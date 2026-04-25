"""Google Custom Search provider - Phase 4."""
from typing import Optional
from app.services.base import SearchProvider, SearchResult


class GoogleSearchProvider(SearchProvider):
    """Google Custom Search API."""
    
    name = "google"
    max_results = 10
    supports_image_search = True
    
    def __init__(self, api_key: Optional[str] = None, search_engine_id: Optional[str] = None):
        self._api_key = api_key
        self._search_engine_id = search_engine_id
    
    async def search_by_text(self, query: str, max_results: Optional[int] = None) -> SearchResult:
        raise NotImplementedError("Phase 4: Implement Google Search")
    
    async def is_available(self) -> bool:
        return bool(self._api_key and self._search_engine_id)
