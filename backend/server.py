"""
FastAPI server with PostgreSQL and Zep integration.

Serves:
- Static frontend files
- API routes for chat, sessions, graph, and memory
"""

import uvicorn
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from logger import logger
from routes import api_router

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = (BASE_DIR / "../frontend").resolve()
ASSETS_DIR = (BASE_DIR / "../assets").resolve()


# ─────────────────────────────────────────────────────────────────────────────
# Lifespan Context Manager (modern replacement for on_event)
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown lifecycle events.
    Using the modern lifespan context manager pattern.
    """
    # ─────────────────────────────────────────────────────────────────────────
    # STARTUP
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Server starting...")
    logger.info("=" * 60)
    
    db_ready = False
    
    # Initialize database
    try:
        from db import init_db, check_db_health
        
        # Try to connect with retries
        db_ready = await init_db(create_tables=True, wait=True)
        
        if db_ready:
            health = await check_db_health()
            logger.info(f"Database: {health.get('host', 'connected')}")
        else:
            logger.warning("Database initialization failed - some features may be unavailable")
            
    except Exception as e:
        logger.warning(f"Database init skipped: {e}")
        logger.warning("The application will run without database persistence")
    
    # Sync existing Zep sessions to PostgreSQL (if DB is ready)
    if db_ready:
        try:
            from sync_service import sync_zep_sessions_to_db
            stats = await sync_zep_sessions_to_db(limit=50)
            if stats["synced"] > 0:
                logger.info(f"Synced {stats['synced']} sessions from Zep to DB")
            elif stats["skipped"] > 0:
                logger.info(f"Sessions already synced ({stats['skipped']} existing)")
        except Exception as e:
            logger.warning(f"Session sync skipped: {e}")
    
    logger.info("=" * 60)
    logger.info("Server ready!")
    logger.info("=" * 60)
    
    yield  # Server is running
    
    # ─────────────────────────────────────────────────────────────────────────
    # SHUTDOWN
    # ─────────────────────────────────────────────────────────────────────────
    logger.info("Server shutting down...")
    
    try:
        from db import close_db
        await close_db()
    except Exception as e:
        logger.warning(f"Database cleanup error: {e}")
    
    logger.info("Goodbye!")


# ─────────────────────────────────────────────────────────────────────────────
# Application Setup
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Zep OpenRouter Chat",
    version="0.3.0",
    description="Chat application with Zep memory, OpenRouter LLM, and PostgreSQL persistence",
    lifespan=lifespan,
)

# CORS middleware (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
async def read_index():
    """Serve the main frontend page."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    from db import check_db_health, is_initialized
    
    db_health = await check_db_health()
    
    return {
        "status": "healthy" if db_health.get("healthy") else "degraded",
        "database": {
            "connected": db_health.get("healthy", False),
            "initialized": is_initialized(),
            "host": db_health.get("host", "unknown"),
        },
        "version": "0.3.0",
    }


# Include API routes
app.include_router(api_router)


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
