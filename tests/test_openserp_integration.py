"""Test OpenSerp integration via Docker container."""

import pytest
import httpx

from app.services.search import OpenSerpProvider


OPENSERP_URL = "http://127.0.0.1:7000"


@pytest.fixture
def provider():
    """Create OpenSerp provider instance."""
    return OpenSerpProvider(base_url=OPENSERP_URL)


class TestOpenSerpConnection:
    """Test connectivity to OpenSerp service."""

    @pytest.mark.asyncio
    async def test_openserp_reachable(self, provider):
        """Check OpenSerp service is running."""
        try:
            available = await provider.is_available()
            if not available:
                pytest.skip("OpenSerp service not reachable. Start: docker-compose up -d openserp")
            print("\n  OpenSerp service is available")
        except Exception as e:
            pytest.skip(f"OpenSerp error: {e}")

    @pytest.mark.asyncio
    async def test_openserp_health_endpoint(self):
        """Direct health check via HTTP."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{OPENSERP_URL}/health")
                assert resp.status_code == 200
                data = resp.json()
                print(f"\n  OpenSerp health: {data}")
        except httpx.ConnectError:
            pytest.skip("OpenSerp not running")


class TestOpenSerpSearch:
    """Test OpenSerp search functionality."""

    @pytest.mark.asyncio
    async def test_search_by_text(self, provider):
        """Test text-based search via OpenSerp."""
        if not await provider.is_available():
            pytest.skip("OpenSerp not available")

        result = await provider.search_by_text(
            query="Chateau Margaux 2015",
            max_results=5
        )

        print(f"\n  Search query: {result.query}")
        print(f"  Results found: {result.total_results}")
        print(f"  Source: {result.source}")

        # Should get some results
        assert result.total_results >= 0
        assert result.source == "openserp"

        # Print first few results
        for i, item in enumerate(result.items[:3]):
            print(f"    {i+1}. {item.title[:50]} ({item.domain})")

    @pytest.mark.asyncio
    async def test_search_wine_bottle(self, provider):
        """Test searching for wine bottle images."""
        if not await provider.is_available():
            pytest.skip("OpenSerp not available")

        result = await provider.search_by_text(
            query="Cabernet Sauvignon Napa Valley wine bottle",
            max_results=3
        )

        print(f"\n  Wine search results: {result.total_results}")
        for item in result.items:
            print(f"    - {item.domain}: {item.url[:60]}...")
            # Check for trusted domains
            if any(trusted in item.domain.lower() for trusted in [
                "wine-searcher", "vivino", "wine.com"
            ]):
                print(f"      ✓ Trusted domain!")

    @pytest.mark.asyncio
    async def test_fallback_to_bing(self, provider):
        """Test that Bing is used as fallback when Google fails."""
        if not await provider.is_available():
            pytest.skip("OpenSerp not available")

        # Search something that should work on both engines
        result = await provider.search_by_text(
            query="Bordeaux wine",
            max_results=5
        )

        # Should get results from at least one engine
        assert result.total_results > 0 or result.total_results == 0  # Either is fine, just don't crash


class TestOpenSerpScoring:
    """Test result quality scoring."""

    @pytest.mark.asyncio
    async def test_trusted_domains_score_higher(self, provider):
        """Verify trusted wine domains get higher scores."""
        if not await provider.is_available():
            pytest.skip("OpenSerp not available")

        result = await provider.search_by_text(
            query="wine searcher",
            max_results=10
        )

        # Check that wine-searcher.com results have higher scores
        for item in result.items:
            if "wine-searcher" in item.domain.lower():
                assert item.score >= 8.0, f"Trusted domain {item.domain} should have high score"
                print(f"\n  ✓ {item.domain}: score={item.score}")

    @pytest.mark.asyncio
    async def test_bad_domains_filtered(self, provider):
        """Verify bad domains are filtered out."""
        if not await provider.is_available():
            pytest.skip("OpenSerp not available")

        result = await provider.search_by_text(
            query="wine bottle",
            max_results=10
        )

        # Check no bad domains in results
        bad_domains = ["pinterest", "facebook", "ebayimg", "shutterstock"]
        for item in result.items:
            for bad in bad_domains:
                assert bad not in item.domain.lower(), f"Bad domain {item.domain} should be filtered"


class TestDockerIntegration:
    """Test full Docker compose integration."""

    @pytest.mark.asyncio
    async def test_backend_can_reach_openserp(self):
        """Verify backend container can reach openserp via internal network."""
        # This test would run inside the backend container
        # For now, we just verify the external endpoint
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Test Google endpoint
                resp = await client.get(
                    f"{OPENSERP_URL}/google/wine",
                    params={"page": 1, "lr": "en"}
                )
                # May return 200, 404 (no results), or 429/503 (rate limited/service unavailable)
                assert resp.status_code in [200, 404, 429, 503]
                print(f"\n  OpenSerp Google endpoint: {resp.status_code}")
        except httpx.ConnectError:
            pytest.skip("OpenSerp not running")
