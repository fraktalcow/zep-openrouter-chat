"""
RAG API Routes using Pinecone

Handles document ingestion and semantic search via Pinecone's 
integrated embedding and retrieval services.
"""

from typing import Dict, Optional, List, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pinecone_service import get_pinecone_service, PineconeService

router = APIRouter(prefix="/rag", tags=["rag"])

# Models
class IngestRequest(BaseModel):
    text: str = Field(..., description="Document text to ingest")
    metadata: Optional[Dict] = Field(None, description="Optional metadata")
    namespace: Optional[str] = Field(None, description="Pinecone namespace")

class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    top_k: int = Field(5, ge=1, le=20)
    namespace: Optional[str] = Field(None, description="Pinecone namespace")
    rerank: bool = Field(False, description="Whether to rerank results")

# Routes
@router.post("/ingest")
async def ingest(request: IngestRequest):
    """Ingest a document into Pinecone."""
    try:
        service = get_pinecone_service()
        result = service.add_documents(
            documents=[{"text": request.text, "metadata": request.metadata or {}}],
            namespace=request.namespace
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search")
async def search(request: SearchRequest):
    """Search for relevant documents using Pinecone."""
    try:
        service = get_pinecone_service()
        results = service.search(
            query=request.query,
            top_k=request.top_k,
            namespace=request.namespace,
            rerank=request.rerank
        )
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear")
async def clear(namespace: Optional[str] = None):
    """Clear all documents from a namespace."""
    try:
        service = get_pinecone_service()
        return service.delete_namespace(namespace)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def stats():
    """Get Pinecone index stats."""
    try:
        service = get_pinecone_service()
        return service.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
