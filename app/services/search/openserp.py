"""OpenSerp microservice client for image search."""

import os
from typing import Optional

import httpx

from app.services.base import SearchProvider, SearchResult, SearchItem


# Trusted and bad domains for image quality scoring
TRUSTED_DOMAINS = [
    "wine-searcher.com", "vivino.com", "wine.com", "klwines.com",
    "totalwine.com", "kandl.com", "winefolly.com", "cellartracker.com",
    "winemag.com", "robertparker.com", "jancisrobinson.com"
]
BAD_DOMAINS = [
    "pinterest", "facebook", "ebayimg", "alicdn", "1688", "alibaba",
    "shutterstock", "gettyimages", "alamy", "dreamstime"
]


class OpenSerpProvider(SearchProvider):
    """Client for OpenSerp Go microservice (Google/Bing image search)."""

    name = "openserp"
    supports_image_search = True
    max_results = 25

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv("OPENSERP_URL", "http://localhost:8080")).rstrip("/")

    async def is_available(self) -> bool:
        """Check if OpenSerp service is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def search_by_text(
        self, query: str, max_results: Optional[int] = None
    ) -> SearchResult:
        """
        Search for images using OpenSerp microservice.

        Args:
            query: Search query string
            max_results: Maximum results to return
        """
        max_results = max_results or self.max_results

        # Try Google first, then Bing as fallback
        candidates = []

        for engine in ["google", "bing"]:
            if len(candidates) >= max_results:
                break

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    # OpenSerp uses /:engine/:query pattern
                    # For image search, we add "images" to query or use tbm=isch equivalent
                    search_query = f"{query} wine bottle"

                    resp = await client.get(
                        f"{self.base_url}/{engine}/{search_query}",
                        params={
                            "page": 0,
                            "lr": "en",
                        },
                        timeout=30.0,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    # Parse results based on OpenSerp response format
                    # Results typically have title, link, description
                    results = data.get("results", [])

                    for item in results[:15]:
                        url = item.get("link") or item.get("url", "")
                        if not url:
                            continue

                        # Skip bad domains
                        domain = self._extract_domain(url)
                        if any(bad in domain.lower() for bad in BAD_DOMAINS):
                            continue

                        # Score based on domain trust
                        score = 5.0
                        if any(trusted in domain.lower() for trusted in TRUSTED_DOMAINS):
                            score = 9.0

                        candidates.append(SearchItem(
                            url=url,
                            title=item.get("title", ""),
                            source=f"OpenSerp/{engine.capitalize()}",
                            page_url=url,
                            domain=domain,
                            score=score,
                        ))

            except httpx.HTTPStatusError as e:
                # Log but continue to next engine
                print(f"[OpenSerp] {engine} error: HTTP {e.response.status_code}")
            except Exception as e:
                print(f"[OpenSerp] {engine} error: {e}")

        # Deduplicate by URL
        seen = set()
        unique = []
        for c in candidates:
            if c.url not in seen:
                seen.add(c.url)
                unique.append(c)

        return SearchResult(
            items=unique[:max_results],
            query=query,
            total_results=len(unique),
            source="openserp",
        )

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")
        except Exception:
            return "unknown"
