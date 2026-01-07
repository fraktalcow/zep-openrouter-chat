"""
Shared configuration module.
Centralizes settings with validation.
"""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    """Application settings with validation."""
    
    # ─────────────────────────────────────────────────────────────────────────
    # Required API keys
    # ─────────────────────────────────────────────────────────────────────────
    ZEP_API_KEY: str
    OPENROUTER_API_KEY: str
    PINECONE_API_KEY: str
    
    # ─────────────────────────────────────────────────────────────────────────
    # Pinecone config
    # ─────────────────────────────────────────────────────────────────────────
    PINECONE_INDEX: str = "zep-rag"
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"
    
    # ─────────────────────────────────────────────────────────────────────────
    # Model defaults
    # ─────────────────────────────────────────────────────────────────────────
    DEFAULT_MODEL: str = "meta-llama/llama-3.2-3b-instruct:free"
    DEFAULT_EMBEDDING_MODEL: str = "llama-text-embed-v2"
    
    # ─────────────────────────────────────────────────────────────────────────
    # RAG config
    # ─────────────────────────────────────────────────────────────────────────
    RAG_TOP_K: int = 5
    RAG_NAMESPACE: str = "default"
    
    # ─────────────────────────────────────────────────────────────────────────
    # Database config
    # ─────────────────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/zep_chat",
        description="PostgreSQL connection string with asyncpg driver"
    )
    DATABASE_POOL_SIZE: int = Field(default=5, ge=1, le=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=10, ge=0, le=30)
    DATABASE_ECHO: bool = False  # Set True for SQL query logging
    DATABASE_POOL_TIMEOUT: int = Field(default=30, description="Seconds to wait for pool connection")
    DATABASE_POOL_RECYCLE: int = Field(default=1800, description="Recycle connections after seconds")
    
    @property
    def database_host(self) -> str:
        """Extract host from DATABASE_URL for logging."""
        try:
            # postgresql+asyncpg://user:pass@host:port/db
            return self.DATABASE_URL.split("@")[-1].split("/")[0]
        except Exception:
            return "unknown"
    
    class Config:
        env_file = Path(__file__).parent / ".env"
        extra = "ignore"


# Lazy-loaded settings
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get validated settings - raises on missing keys."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings cache (useful for testing)."""
    global _settings
    _settings = None

