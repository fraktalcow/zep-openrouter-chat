"""
GraphRAG API Routes

Provides REST API endpoints for GraphRAG operations:
- Document ingestion
- Search
- Chat with context
- Configuration management
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from graphrag_service import GraphRAGService


router = APIRouter(prefix="/graphrag", tags=["graphrag"])

# Service instance (initialized in server.py)
_service: Optional[GraphRAGService] = None


def init_services(graphrag_service: GraphRAGService):
    """Initialize route services"""
    global _service
    _service = graphrag_service


# Request/Response Models

class DocumentIngestRequest(BaseModel):
    """Request model for document ingestion"""
    text: str = Field(..., description="Document text")
    metadata: Optional[Dict] = Field(None, description="Document metadata")
    doc_id: Optional[str] = Field(None, description="Document ID")
    user_id: Optional[str] = Field(None, description="User ID for Zep integration")


class BatchIngestRequest(BaseModel):
    """Request model for batch document ingestion"""
    documents: List[Dict] = Field(..., description="List of documents")
    user_id: Optional[str] = Field(None, description="User ID for Zep integration")


class SearchRequest(BaseModel):
    """Request model for search"""
    query: str = Field(..., description="Search query")
    top_k: Optional[int] = Field(None, description="Number of results")
    filters: Optional[Dict] = Field(None, description="Metadata filters")


class ChatRequest(BaseModel):
    """Request model for chat"""
    query: str = Field(..., description="User query")
    user_id: Optional[str] = Field(None, description="User ID")
    session_id: Optional[str] = Field(None, description="Session ID")
    top_k: Optional[int] = Field(None, description="Number of chunks to retrieve")
    include_zep_context: bool = Field(True, description="Include Zep context")


class ConfigUpdateRequest(BaseModel):
    """Request model for config updates"""
    config: Dict = Field(..., description="Configuration updates")


# Routes

@router.post("/ingest")
async def ingest_document(request: DocumentIngestRequest):
    """
    Ingest a single document into GraphRAG
    
    **Example:**
    ```json
    {
        "text": "Machine learning is a subset of artificial intelligence...",
        "metadata": {"source": "textbook", "chapter": 1},
        "user_id": "user123"
    }
    ```
    """
    if not _service:
        raise HTTPException(status_code=503, detail="GraphRAG service not initialized")
    
    try:
        result = await _service.ingest_document(
            text=request.text,
            metadata=request.metadata,
            doc_id=request.doc_id,
            user_id=request.user_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/batch")
async def ingest_documents(request: BatchIngestRequest):
    """
    Ingest multiple documents into GraphRAG
    
    **Example:**
    ```json
    {
        "documents": [
            {
                "text": "Document 1 content...",
                "metadata": {"source": "book1"}
            },
            {
                "text": "Document 2 content...",
                "metadata": {"source": "book2"}
            }
        ],
        "user_id": "user123"
    }
    ```
    """
    if not _service:
        raise HTTPException(status_code=503, detail="GraphRAG service not initialized")
    
    try:
        result = await _service.ingest_documents(
            documents=request.documents,
            user_id=request.user_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search(request: SearchRequest):
    """
    Search for relevant chunks
    
    **Example:**
    ```json
    {
        "query": "What is machine learning?",
        "top_k": 5,
        "filters": {"source": "textbook"}
    }
    ```
    """
    if not _service:
        raise HTTPException(status_code=503, detail="GraphRAG service not initialized")
    
    try:
        results = _service.search(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
        )
        return {
            "results": results,
            "count": len(results),
            "query": request.query,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Chat with GraphRAG and Zep context
    
    **Example:**
    ```json
    {
        "query": "Explain neural networks",
        "user_id": "user123",
        "top_k": 5,
        "include_zep_context": true
    }
    ```
    """
    if not _service:
        raise HTTPException(status_code=503, detail="GraphRAG service not initialized")
    
    try:
        result = await _service.chat(
            query=request.query,
            user_id=request.user_id,
            session_id=request.session_id,
            top_k=request.top_k,
            include_zep_context=request.include_zep_context,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_config():
    """Get current GraphRAG configuration"""
    if not _service:
        raise HTTPException(status_code=503, detail="GraphRAG service not initialized")
    
    return _service.get_config()


@router.post("/config")
async def update_config(request: ConfigUpdateRequest):
    """
    Update GraphRAG configuration
    
    **Example:**
    ```json
    {
        "config": {
            "search_algorithm": "hybrid",
            "enable_bm25": true,
            "enable_vector_search": true,
            "hybrid_alpha": 0.7,
            "top_k": 10
        }
    }
    ```
    """
    if not _service:
        raise HTTPException(status_code=503, detail="GraphRAG service not initialized")
    
    try:
        updated_config = _service.update_config(request.config)
        return {
            "status": "success",
            "config": updated_config,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Get GraphRAG statistics and metrics"""
    if not _service:
        raise HTTPException(status_code=503, detail="GraphRAG service not initialized")
    
    return _service.get_stats()


@router.post("/clear")
async def clear():
    """Clear all indexed data"""
    if not _service:
        raise HTTPException(status_code=503, detail="GraphRAG service not initialized")
    
    try:
        _service.clear()
        return {
            "status": "success",
            "message": "All GraphRAG data cleared",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    if not _service:
        return {
            "status": "unavailable",
            "message": "GraphRAG service not initialized",
        }
    
    return {
        "status": "healthy",
        "service": "graphrag",
        "config_profile": _service.config.to_dict().get("search", {}).get("algorithm"),
    }
