"""
Vine API - Unified wine image analysis service.

FastAPI application merging vine2 and vine-rec backends.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import get_settings
from app.api import health, analyze, eval

settings = get_settings()

app = FastAPI(
    title="Vine API",
    description="Unified wine image analysis service (vine2 + vine-rec)",
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_hosts,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)                          # /health, /health/ready, /health/providers
app.include_router(health.router, prefix="/api/v1")       # /api/v1/health, /api/v1/health/ready, /api/v1/health/providers
app.include_router(analyze.router, prefix="/api/v1")
app.include_router(eval.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint - returns API info."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs" if settings.debug else None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
