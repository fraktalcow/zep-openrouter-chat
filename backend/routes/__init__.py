from fastapi import APIRouter

from .chat import router as chat_router
from .session import router as session_router
from .schema import router as schema_router
from .models import router as models_router
from .graph import router as graph_router
from .memory import router as memory_router
from .rag import router as rag_router

api_router = APIRouter()

api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(session_router, prefix="/session", tags=["session"])
api_router.include_router(schema_router, prefix="/schema", tags=["schema"])
api_router.include_router(models_router, prefix="/models", tags=["models"])
api_router.include_router(graph_router, prefix="/graph", tags=["graph"])
api_router.include_router(memory_router, prefix="/memory", tags=["memory"])
api_router.include_router(rag_router, tags=["rag"])
