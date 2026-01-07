"""
Database connection and session management.

Provides async SQLAlchemy engine and session factory with:
- Connection pooling with configurable settings
- Health check functionality
- Retry logic for initial connections
- Proper cleanup on shutdown
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine,
)
from sqlalchemy.pool import NullPool

from config import get_settings
from logger import logger


# ─────────────────────────────────────────────────────────────────────────────
# Module-level state
# ─────────────────────────────────────────────────────────────────────────────

_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_is_initialized: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Engine & Session Factory
# ─────────────────────────────────────────────────────────────────────────────

def _get_engine() -> AsyncEngine:
    """Get or create the async engine with configured pool settings."""
    global _engine
    if _engine is None:
        settings = get_settings()
        
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DATABASE_ECHO,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            pool_pre_ping=True,  # Verify connections before use
        )
        logger.info(f"[DB] Engine created: {settings.database_host}")
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,  # Explicit flushes for better control
        )
    return _async_session_factory


# ─────────────────────────────────────────────────────────────────────────────
# Session Providers
# ─────────────────────────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.
    
    Usage:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    
    Handles commit on success, rollback on exception.
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions outside of FastAPI routes.
    
    Usage:
        async with get_db_context() as db:
            ...
    
    Handles commit on success, rollback on exception.
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ─────────────────────────────────────────────────────────────────────────────
# Initialization & Health
# ─────────────────────────────────────────────────────────────────────────────

async def check_db_health() -> dict:
    """
    Check database connection health.
    
    Returns:
        dict with 'healthy' bool and optional 'error' string
    """
    try:
        engine = _get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1 as health_check"))
            row = result.fetchone()
            if row and row[0] == 1:
                return {"healthy": True, "host": get_settings().database_host}
    except Exception as e:
        return {"healthy": False, "error": str(e)}
    
    return {"healthy": False, "error": "Unknown error"}


async def wait_for_db(max_retries: int = 5, retry_delay: float = 2.0) -> bool:
    """
    Wait for database to become available with retries.
    
    Args:
        max_retries: Maximum number of connection attempts
        retry_delay: Seconds between retries
        
    Returns:
        True if connected, False if all retries exhausted
    """
    for attempt in range(1, max_retries + 1):
        health = await check_db_health()
        if health["healthy"]:
            logger.info(f"[DB] Connected to {health['host']}")
            return True
        
        logger.warning(f"[DB] Connection attempt {attempt}/{max_retries} failed: {health.get('error', 'Unknown')}")
        
        if attempt < max_retries:
            await asyncio.sleep(retry_delay)
    
    logger.error(f"[DB] Failed to connect after {max_retries} attempts")
    return False


async def init_db(create_tables: bool = True, wait: bool = True) -> bool:
    """
    Initialize database - optionally wait for connection and create tables.
    Call this on application startup.
    
    Args:
        create_tables: If True, create tables from SQLAlchemy models
        wait: If True, wait for database to be available with retries
        
    Returns:
        True if initialization successful
    """
    global _is_initialized
    
    if _is_initialized:
        logger.debug("[DB] Already initialized")
        return True
    
    # Wait for database to be available
    if wait:
        if not await wait_for_db():
            return False
    
    # Create tables if requested
    if create_tables:
        try:
            from db.models import Base
            
            engine = _get_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("[DB] Tables created/verified")
        except Exception as e:
            logger.error(f"[DB] Table creation failed: {e}")
            return False
    
    _is_initialized = True
    logger.info("[DB] Initialization complete")
    return True


async def close_db() -> None:
    """
    Close database connections gracefully.
    Call this on application shutdown.
    """
    global _engine, _async_session_factory, _is_initialized
    
    if _engine:
        await _engine.dispose()
        logger.info("[DB] Engine disposed")
    
    _engine = None
    _async_session_factory = None
    _is_initialized = False
    logger.info("[DB] Connections closed")


# ─────────────────────────────────────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────────────────────────────────────

def is_initialized() -> bool:
    """Check if database has been initialized."""
    return _is_initialized


async def execute_raw_sql(sql: str, params: dict = None) -> list:
    """
    Execute raw SQL query (use sparingly, prefer repositories).
    
    Args:
        sql: SQL query string
        params: Optional query parameters
        
    Returns:
        List of result rows as dicts
    """
    async with get_db_context() as db:
        result = await db.execute(text(sql), params or {})
        rows = result.fetchall()
        # Convert to list of dicts
        if rows and result.keys():
            keys = result.keys()
            return [dict(zip(keys, row)) for row in rows]
        return []
