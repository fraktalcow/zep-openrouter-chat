"""
FastAPI server for Zep + OpenRouter chat application.
Session data persisted to Zep Cloud, RAG using Pinecone.
"""

from pathlib import Path
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import get_settings
from openrouter_service import OpenRouterService
from routes import api_router
from routes.chat import init_services as init_chat_services
from routes.graph import init_services as init_graph_services
from routes.memory import init_services as init_memory_services
from routes.models import init_services as init_models_services
from routes.schema import init_services as init_schema_services, load_schema
from routes.session import init_services as init_session_services
from zep_service import ZepService

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


# Initialize services using validated config
settings = get_settings()
zep_service = ZepService(settings.ZEP_API_KEY)
openrouter_service = OpenRouterService(settings.OPENROUTER_API_KEY)

# Initialize route services (sessions now use SQLite - no in-memory dict needed)
init_chat_services(zep_service, openrouter_service)
init_session_services(zep_service)
init_schema_services(zep_service)
init_models_services(openrouter_service)
init_graph_services(zep_service)
init_memory_services(zep_service)

# Register API routes
app.include_router(api_router)


@app.on_event("startup")
async def startup_event():
    schema = load_schema()
    await zep_service.ensure_ontology(schema["entities"], schema["edges"])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
