"""
Health check endpoints.

Phase 1: Basic health endpoint.
Phase 2: Add provider health checks.
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any

from app.core.registry import get_registry, ProviderRegistry
from app.core.settings import get_settings, Settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Basic health check endpoint.
    
    Returns:
        {"status": "ok"} if service is healthy
    """
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_check(
    registry: ProviderRegistry = Depends(get_registry)
) -> Dict[str, Any]:
    """
    Readiness probe - checks if required providers are available.
    
    Phase 1: Always returns ready (providers are stubs).
    Phase 2: Check if configured providers are available.
    """
    settings = get_settings()
    
    # Phase 1: Return basic info, no actual provider checks
    return {
        "status": "ready",
        "version": settings.app_version,
        "providers": {
            "ocr": settings.ocr_provider,
            "vlm": settings.vlm_provider,
            "search": settings.search_provider,
        }
    }


@router.get("/health/providers")
async def provider_health(
    registry: ProviderRegistry = Depends(get_registry)
) -> Dict[str, Any]:
    """
    Detailed provider health status.
    
    Returns availability status for all configured providers.
    """
    return {
        "ocr": {
            "configured": registry._ocr_name,
            "available": await registry.get_ocr().is_available(),
        },
        "vlm": {
            "configured": registry._vlm_name,
            "available": await registry.get_vlm().is_available(),
        },
        "search": {
            "configured": registry._search_name,
            "available": await registry.get_search().is_available(),
        },
    }
