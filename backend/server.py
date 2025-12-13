import os
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openrouter_service import OpenRouterService
from routes import api_router
from routes.chat import init_services as init_chat_services
from routes.graph import init_services as init_graph_services
from routes.memory import init_services as init_memory_services
from routes.models import init_services as init_models_services
from routes.schema import init_services as init_schema_services, load_schema
from routes.session import init_services as init_session_services
from routes.rag import init_services as init_rag_services
from zep_service import ZepService

load_dotenv()
app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = (BASE_DIR / "../frontend").resolve()
ASSETS_DIR = (BASE_DIR / "../assets").resolve()

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

@app.get("/")
async def read_index():
    return FileResponse(FRONTEND_DIR / "index.html")

# Initialize services
ZEP_API_KEY = os.getenv("ZEP_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not ZEP_API_KEY or not OPENROUTER_API_KEY:
    raise RuntimeError("ZEP_API_KEY and OPENROUTER_API_KEY must be set in backend/.env")

zep_service = ZepService(ZEP_API_KEY)
openrouter_service = OpenRouterService(OPENROUTER_API_KEY)

# Session storage
SESSIONS: Dict[str, Dict[str, Any]] = {}

# Initialize route services
init_chat_services(zep_service, openrouter_service, SESSIONS)
init_session_services(zep_service, SESSIONS)
init_schema_services(zep_service)
init_models_services(openrouter_service)
init_graph_services(zep_service)
init_memory_services(zep_service)
init_rag_services(openrouter_service)

# Register API routes
app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    schema = load_schema()
    await zep_service.ensure_ontology(schema["entities"], schema["edges"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
