"""
Shared configuration module.
Centralizes settings with validation.
"""

from typing import Optional
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings with validation."""
    # Required API keys
    ZEP_API_KEY: str
    OPENROUTER_API_KEY: str
    PINECONE_API_KEY: str
    
    # Pinecone config
    PINECONE_INDEX: str = "zep-rag"
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"
    
    # Model defaults
    DEFAULT_MODEL: str = "meta-llama/llama-3.2-3b-instruct:free"
    DEFAULT_EMBEDDING_MODEL: str = "llama-text-embed-v2"
    
    # RAG config
    RAG_TOP_K: int = 5
    RAG_NAMESPACE: str = "default"
    
    # Database config
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/zep_chat"
    DATABASE_ECHO: bool = False  # Set True for SQL query logging
    
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
