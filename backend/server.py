import uvicorn
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from logger import logger
from routes import api_router

load_dotenv()
app = FastAPI(title="Zep OpenRouter Chat", version="0.2.0")

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = (BASE_DIR / "../frontend").resolve()
ASSETS_DIR = (BASE_DIR / "../assets").resolve()

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

@app.get("/")
async def read_index():
    return FileResponse(FRONTEND_DIR / "index.html")

app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    logger.info("Server starting...")
    
    # Initialize database (create tables if needed)
    db_ready = False
    try:
        from db import init_db
        await init_db()
        db_ready = True
        logger.info("Database initialized.")
    except Exception as e:
        logger.warning(f"Database init skipped (may need PostgreSQL): {e}")
    
    # Sync existing Zep sessions to PostgreSQL
    if db_ready:
        try:
            from sync_service import sync_zep_sessions_to_db
            stats = await sync_zep_sessions_to_db(limit=50)
            if stats["synced"] > 0:
                logger.info(f"Synced {stats['synced']} sessions from Zep to DB")
        except Exception as e:
            logger.warning(f"Session sync skipped: {e}")
    
    logger.info("Server ready.")

@app.on_event("shutdown") 
async def shutdown_event():
    logger.info("Server shutting down...")
    try:
        from db import close_db
        await close_db()
    except Exception:
        pass



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
