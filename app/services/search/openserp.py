"""OpenSerp microservice client for image search."""

import os
import traceback
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

        Uses OpenSerp's /mega/image endpoint to search Google and Bing
        in parallel, then deduplicates and ranks results.
        Falls back to individual engine calls if mega fails.

        Args:
            query: Search query string
            max_results: Maximum results to return
        """
        max_results = max_results or self.max_results
        search_query = f"{query} wine bottle"

        # Try mega/image first (parallel Google + Bing)
        candidates = await self._try_mega_search(search_query, max_results)

        # If mega failed, fall back to individual engines
        if not candidates:
            print(f"[OpenSerp] mega/image failed, trying individual engines")
            candidates = await self._try_individual_search(search_query, max_results)

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

    async def _try_mega_search(self, search_query: str, max_results: int):
        """Try the mega/image endpoint (parallel Google + Bing)."""
        candidates = []
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.get(
                    f"{self.base_url}/mega/image",
                    params={
                        "text": search_query,
                        "engines": "bing",  # Google blocks headless browsers consistently
                        "limit": max(10, max_results * 2),
                        "lang": "EN",
                    },
                    timeout=90.0,
                )
                resp.raise_for_status()
                data = resp.json()
                candidates = self._parse_image_results(data)
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                err_data = e.response.json()
                detail = f" ({err_data.get('error', '')}: {err_data.get('message', '')})"
            except Exception:
                detail = ""
            print(f"[OpenSerp] mega/image HTTP {e.response.status_code}{detail}")
        except httpx.TimeoutException as e:
            print(f"[OpenSerp] mega/image timeout: {type(e).__name__}")
        except Exception as e:
            print(f"[OpenSerp] mega/image {type(e).__name__}: {e}")
        return candidates

    async def _try_individual_search(self, search_query: str, max_results: int):
        """Fall back to individual engine calls."""
        candidates = []
        for engine in ["bing"]:  # Google blocks headless browsers consistently
            if len(candidates) >= max_results:
                break
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    resp = await client.get(
                        f"{self.base_url}/{engine}/image",
                        params={
                            "text": search_query,
                            "limit": max(10, max_results * 2),
                            "lang": "EN",
                        },
                        timeout=90.0,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    candidates.extend(self._parse_image_results(data))
            except httpx.HTTPStatusError as e:
                print(f"[OpenSerp] {engine}/image HTTP {e.response.status_code}")
            except Exception as e:
                print(f"[OpenSerp] {engine}/image {type(e).__name__}: {e}")
        return candidates

    def _parse_image_results(self, data: dict):
        """Parse OpenSerp image search response into SearchItem list."""
        candidates = []
        results = data.get("results", [])

        for item in results:
            image_data = item.get("image", {})
            image_url = image_data.get("url", "")
            if not image_url:
                continue

            source = item.get("source", {})
            page_url = source.get("page_url", "") or image_url
            domain = source.get("domain", "") or self._extract_domain(image_url)

            # Skip bad domains
            if any(bad in domain.lower() for bad in BAD_DOMAINS):
                continue

            # Score based on domain trust
            score = 5.0
            if any(trusted in domain.lower() for trusted in TRUSTED_DOMAINS):
                score = 9.0

            # Boost by rank (lower rank = higher score boost)
            rank = item.get("rank", 99)
            score += max(0, (10 - rank) * 0.5)

            candidates.append(SearchItem(
                url=image_url,
                title=item.get("title", ""),
                source=f"OpenSerp/{item.get('engine', 'unknown').capitalize()}",
                page_url=page_url,
                domain=domain,
                score=score,
                thumbnail_url=image_data.get("thumbnail", ""),
            ))

        return candidates

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
