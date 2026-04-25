"""Playwright-based image search provider."""
from typing import List, Optional

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


class PlaywrightSearchProvider(SearchProvider):
    """Web scraping image search via Playwright (Bing/Google)."""

    name = "playwright"
    supports_image_search = True
    max_results = 25

    async def is_available(self) -> bool:
        try:
            from playwright.async_api import async_playwright
            return True
        except ImportError:
            return False

    async def search_by_text(
        self, query: str, max_results: Optional[int] = None
    ) -> SearchResult:
        """
        Search for images using Bing and Google via Playwright.

        Args:
            query: Search query string
            max_results: Maximum results to return (default 25)
        """
        max_results = max_results or self.max_results
        candidates = []

        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )

                # Try Bing first (more reliable)
                for page_num in range(3):
                    page = await context.new_page()
                    try:
                        bing_url = f"https://www.bing.com/images/search?q={query.replace(' ', '+')}&first={page_num * 35}"
                        await page.goto(bing_url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(2500)

                        bing_images = await page.evaluate(
                            '''({trusted, bad}) => {
                                const results = [];
                                const seen = new Set();
                                const items = document.querySelectorAll('.mimg, .iusc');
                                items.forEach(item => {
                                    let src = item.src || item.getAttribute('data-src');
                                    if (!src || src.length < 20 || seen.has(src)) return;
                                    seen.add(src);
                                    let domain = 'bing-images';
                                    try { domain = new URL(src).hostname.replace('www.', ''); } catch(e) {}
                                    if (bad.some(d => domain.includes(d))) return;
                                    let score = 5;
                                    if (trusted.some(d => domain.includes(d))) score = 9;
                                    results.push({
                                        original: src,
                                        pageUrl: '',
                                        title: item.alt || 'Wine bottle',
                                        domain,
                                        authority: score,
                                        source: 'Bing Images'
                                    });
                                });
                                return results.slice(0, 20);
                            }''',
                            {"trusted": TRUSTED_DOMAINS, "bad": BAD_DOMAINS}
                        )

                        if bing_images:
                            candidates.extend(bing_images)

                    except Exception as e:
                        print(f"[Playwright] Bing error page {page_num + 1}: {e}")
                    finally:
                        await page.close()

                    if len(candidates) >= 25:
                        break

                # Google fallback if needed
                if len(candidates) < 5:
                    page = await context.new_page()
                    try:
                        google_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=isch"
                        await page.goto(google_url, wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(2500)

                        google_images = await page.evaluate(
                            '''({trusted, bad}) => {
                                const results = [];
                                const seen = new Set();
                                const imgs = document.querySelectorAll('img[src^="https"], img[data-src^="https"]');
                                imgs.forEach(img => {
                                    const src = img.src || img.getAttribute('data-src');
                                    if (!src || src.length < 20 || seen.has(src)) return;
                                    if (src.includes('gstatic.com') || src.includes('google.com/logos')) return;
                                    seen.add(src);
                                    let domain = 'google-images';
                                    try { domain = new URL(src).hostname.replace('www.', ''); } catch(e) {}
                                    if (bad.some(d => domain.includes(d))) return;
                                    let score = 4;
                                    if (trusted.some(d => domain.includes(d))) score = 9;
                                    results.push({
                                        original: src,
                                        pageUrl: '',
                                        title: img.alt || 'Wine bottle',
                                        domain,
                                        authority: score,
                                        source: 'Google Images'
                                    });
                                });
                                return results.slice(0, 10);
                            }''',
                            {"trusted": TRUSTED_DOMAINS, "bad": BAD_DOMAINS}
                        )

                        if google_images:
                            candidates.extend(google_images)

                    except Exception as e:
                        print(f"[Playwright] Google error: {e}")
                    finally:
                        await page.close()

                await browser.close()

        except Exception as e:
            print(f"[Playwright] Browser error: {e}")

        # Convert to SearchItem format
        items = []
        seen_urls = set()

        for c in candidates[:max_results]:
            url = c.get("original", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            items.append(SearchItem(
                url=url,
                title=c.get("title", ""),
                source=c.get("source", "Playwright"),
                page_url=c.get("pageUrl", ""),
                domain=c.get("domain", ""),
                score=float(c.get("authority", 5)),
            ))

        return SearchResult(
            items=items,
            query=query,
            total_results=len(items),
            source="playwright"
        )
