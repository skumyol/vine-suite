"""Async image downloader with caching and SSRF protection."""

import os
import hashlib
import re
from typing import Optional, Tuple
from urllib.parse import urlparse
import aiofiles
import httpx

from app.core.settings import get_settings


# SSRF protection: block private IP ranges and localhost
_SSRF_BLOCKED_HOSTS = re.compile(
    r"^(localhost|127\.\d+\.\d+\.\d+|0\.0\.0\.0|10\.\d+\.\d+\.\d+|"
    r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+|"
    r"169\.254\.\d+\.\d+|::1|fc00:|fd00:|fe80:)",
    re.IGNORECASE,
)

# Blocked URL schemes
_BLOCKED_SCHEMES = {"file", "ftp", "gopher", "data", "jar", "dict", "ldap"}


def _is_safe_url(url: str) -> Tuple[bool, str]:
    """Check if URL is safe to download from (SSRF protection)."""
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return False, f"Blocked scheme: {parsed.scheme}"

    hostname = parsed.hostname or ""
    if _SSRF_BLOCKED_HOSTS.match(hostname):
        return False, f"Blocked private/localhost host: {hostname}"

    return True, ""


class ImageDownloader:
    """Async image downloader with local caching."""

    def __init__(self, storage_dir: Optional[str] = None):
        settings = get_settings()
        self.storage_dir = storage_dir or os.path.join(os.getcwd(), "image_cache")
        self.original_dir = os.path.join(self.storage_dir, "original")
        self.processed_dir = os.path.join(self.storage_dir, "processed")
        self._ensure_dirs()

        self.client = httpx.AsyncClient(
            timeout=settings.download_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                ),
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Referer": "https://www.google.com/",
            },
        )
        self.max_size = settings.max_image_download_size

    def _ensure_dirs(self) -> None:
        os.makedirs(self.original_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)

    def _get_extension(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.lower()
        if ".jpg" in path or ".jpeg" in path:
            return ".jpg"
        elif ".png" in path:
            return ".png"
        elif ".gif" in path:
            return ".gif"
        elif ".webp" in path:
            return ".webp"
        return ".jpg"

    def _cache_paths(self, url: str) -> Tuple[str, str]:
        file_hash = hashlib.md5(url.encode()).hexdigest()[:16]
        ext = self._get_extension(url)
        filename = f"{file_hash}{ext}"
        return (
            os.path.join(self.original_dir, filename),
            os.path.join(self.processed_dir, filename),
        )

    async def download(self, url: str) -> dict:
        """
        Download an image from URL with caching.

        Returns dict with:
            - url: original URL
            - local_path: path to processed/cached image
            - original_path: path to original download
            - status: "downloaded", "cached", or "failed"
            - error: error message if failed
            - width, height: dimensions
            - file_size: bytes
        """
        result = {
            "url": url,
            "local_path": None,
            "original_path": None,
            "status": "failed",
            "error": None,
            "width": 0,
            "height": 0,
            "file_size": 0,
        }

        # SSRF check
        safe, reason = _is_safe_url(url)
        if not safe:
            result["error"] = f"SSRF blocked: {reason}"
            return result

        original_path, processed_path = self._cache_paths(url)

        # Check cache
        if os.path.exists(original_path):
            file_size = os.path.getsize(original_path)
            result["original_path"] = original_path
            result["local_path"] = processed_path
            result["status"] = "cached"
            result["file_size"] = file_size
            # Get dimensions from cached file
            try:
                from PIL import Image as PILImage
                with PILImage.open(original_path) as img:
                    result["width"], result["height"] = img.size
            except Exception:
                pass
            return result

        try:
            response = await self.client.get(url)
            response.raise_for_status()

            content = response.content
            content_type = response.headers.get("content-type", "")

            # Size limit
            if len(content) > self.max_size:
                result["error"] = f"Image too large: {len(content)} > {self.max_size}"
                return result

            # MIME type check
            if not content_type.startswith("image/"):
                # Fallback: check magic bytes
                if not content[:4] in (b"\xff\xd8\xff", b"\x89PNG", b"GIF8", b"RIFF"):
                    result["error"] = "Not an image (content-type and magic bytes check failed)"
                    return result

            # Save original
            async with aiofiles.open(original_path, "wb") as f:
                await f.write(content)

            # Validate dimensions with PIL
            from PIL import Image as PILImage
            with PILImage.open(original_path) as img:
                w, h = img.size
                result["width"] = w
                result["height"] = h

                # Skip tiny images
                if w < 200 or h < 200:
                    result["error"] = f"Image too small: {w}x{h}"
                    os.remove(original_path)
                    return result

            result["original_path"] = original_path
            result["local_path"] = processed_path
            result["status"] = "downloaded"
            result["file_size"] = len(content)

        except httpx.HTTPStatusError as e:
            result["error"] = f"HTTP {e.response.status_code}"
        except httpx.TimeoutException:
            result["error"] = "Timeout"
        except Exception as e:
            result["error"] = str(e)[:100]

        return result

    async def download_batch(self, urls: list[str], concurrency: int = 5) -> list[dict]:
        """Download multiple images with concurrency limit."""
        import asyncio

        sem = asyncio.Semaphore(concurrency)

        async def _dl(url: str) -> dict:
            async with sem:
                return await self.download(url)

        tasks = [_dl(url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self) -> None:
        await self.client.aclose()
