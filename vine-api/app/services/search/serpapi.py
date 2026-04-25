"""SerpAPI provider implementation."""
import os
from typing import Optional

import httpx

from app.services.base import SearchProvider, SearchResult, SearchItem


class SerpAPISearchProvider(SearchProvider):
    """SerpAPI Google Image search."""

    name = "serpapi"
    supports_image_search = True
    max_results = 20
    SERPAPI_URL = "https://serpapi.com/search"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPAPI_KEY")

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def search_by_text(
        self, query: str, max_results: Optional[int] = None
    ) -> SearchResult:
        """
        Search for images using SerpAPI Google Images.

        Args:
            query: Search query string
            max_results: Maximum results to return
        """
        if not self.api_key:
            raise ValueError("SERPAPI_KEY not set")

        max_results = max_results or self.max_results

        params = {
            "q": query,
            "tbm": "isch",  # Google Images
            "api_key": self.api_key,
            "engine": "google",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(self.SERPAPI_URL, params=params)
                response.raise_for_status()
                data = response.json()

                items = []
                images = data.get("images_results", [])

                for img in images[:max_results]:
                    url = img.get("original") or img.get("thumbnail")
                    if not url:
                        continue

                    items.append(SearchItem(
                        url=url,
                        title=img.get("title", ""),
                        source="SerpAPI/Google",
                        page_url=img.get("link", ""),
                        domain=img.get("source", ""),
                        score=5.0,  # Base score, can be enhanced
                    ))

                return SearchResult(
                    items=items,
                    query=query,
                    total_results=len(items),
                    source="serpapi"
                )

            except httpx.HTTPStatusError as e:
                return SearchResult(
                    items=[],
                    query=query,
                    total_results=0,
                    source="serpapi",
                    error=f"HTTP {e.response.status_code}"
                )
            except Exception as e:
                return SearchResult(
                    items=[],
                    query=query,
                    total_results=0,
                    source="serpapi",
                    error=str(e)
                )
