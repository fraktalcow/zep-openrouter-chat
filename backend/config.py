"""
Shared configuration module.
Centralizes settings to avoid circular imports between routes.
"""

from typing import Optional
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings with validation."""
    ZEP_API_KEY: str
    OPENROUTER_API_KEY: str
    
    # Optional overrides
    DEFAULT_MODEL: str = "google/gemini-2.0-flash-exp:free"
    DEFAULT_EMBEDDING_MODEL: str = "openai/text-embedding-3-small"
    RAG_SCORE_THRESHOLD: float = 0.4
    
    class Config:
        env_file = Path(__file__).parent / ".env"
        extra = "ignore"


# Lazy-loaded settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get validated settings - raises on missing required keys."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Embedding model state (shared across routes)
_embedding_model: str = "openai/text-embedding-3-small"


def get_embedding_model() -> str:
    """Get current embedding model ID."""
    return _embedding_model


def set_embedding_model(model_id: str) -> None:
    """Set embedding model ID."""
    global _embedding_model
    _embedding_model = model_id
