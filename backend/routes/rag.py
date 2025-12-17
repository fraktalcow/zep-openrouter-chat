"""
RAG API Routes

Simple RAG endpoints using OpenRouter embeddings.
All logic handled by backend - frontend just calls these.
"""

from typing import Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openrouter_service import OpenRouterService
from config import get_embedding_model, set_embedding_model

router = APIRouter(prefix="/rag", tags=["rag"])

# Service instance (injected at startup)
_service: Optional[OpenRouterService] = None


def init_services(openrouter_service: OpenRouterService):
    global _service
    _service = openrouter_service


# Request Models

class IngestRequest(BaseModel):
    text: str = Field(..., description="Document text to ingest")
    metadata: Optional[Dict] = Field(None, description="Optional metadata")


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    top_k: int = Field(5, ge=1, le=20)


class SetModelRequest(BaseModel):
    model_id: str = Field(..., description="Embedding model ID")


# Routes

@router.get("/models")
async def get_embedding_models():
    """Get available embedding models from OpenRouter."""
    if not _service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    models = await _service.fetch_embedding_models()
    return {
        "models": models,
        "current": get_embedding_model(),
    }


@router.post("/models")
async def set_embedding_model_endpoint(request: SetModelRequest):
    """Set the embedding model to use."""
    set_embedding_model(request.model_id)
    return {"status": "success", "model": request.model_id}


@router.post("/ingest")
async def ingest(request: IngestRequest):
    """Ingest a document into the RAG store."""
    if not _service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        result = await _service.add_documents(
            documents=[{"text": request.text, "metadata": request.metadata or {}}],
            embedding_model=get_embedding_model(),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search(request: SearchRequest):
    """Search for relevant documents."""
    if not _service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        results = await _service.search(
            query=request.query,
            top_k=request.top_k,
            embedding_model=get_embedding_model(),
        )
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear():
    """Clear all documents from RAG store."""
    if not _service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return _service.clear_documents()


@router.get("/stats")
async def stats():
    """Get RAG store stats."""
    if not _service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return {
        "document_count": _service.get_document_count(),
        "embedding_model": get_embedding_model(),
    }
