"""
Application settings and configuration.

Uses environment variables with sensible defaults.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="VINE_API_",
        env_file=".env",
        case_sensitive=False,
    )
    
    # App metadata
    app_name: str = "vine-api"
    app_version: str = "0.1.0"
    debug: bool = False
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Provider configuration (Phase 2: implement actual selection)
    ocr_provider: str = "easyocr"  # easyocr | tesseract | paddleocr
    vlm_provider: str = "gemini"   # gemini | qwen | mistral
    search_provider: str = "openserp"  # openserp | serpapi | google | playwright
    
    # API Keys
    openrouter_api_key: Optional[str] = None   # Gemini + Qwen via OpenRouter
    nvidia_api_key: Optional[str] = None         # Mistral via NVIDIA
    serpapi_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    google_search_engine_id: Optional[str] = None
    openserp_url: Optional[str] = None  # OpenSerp microservice URL
    
    # Concurrency limits (Phase 4: implement actual limiting)
    max_concurrent_searches: int = 3
    max_concurrent_downloads: int = 5
    max_concurrent_vlm_calls: int = 2
    
    # SQLite persistence (Phase 4: implement)
    database_url: str = "sqlite:///./vine_api.db"
    enable_persistence: bool = True
    
    # Image download limits
    max_image_download_size: int = 20 * 1024 * 1024  # 20MB
    download_timeout_seconds: int = 30
    
    # Security
    allowed_hosts: list[str] = ["*"]


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
