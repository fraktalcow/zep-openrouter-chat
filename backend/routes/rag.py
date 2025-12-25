"""
RAG API Routes using Pinecone

Handles document ingestion via file uploads and semantic search.
Supports PDF, TXT, MD, and DOCX file formats.
"""

import io
from typing import Dict, Optional, List, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from pinecone_service import get_pinecone_service
from logger import logger

# Document parsers
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None

router = APIRouter(prefix="/rag", tags=["rag"])


# Models
class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    top_k: int = Field(5, ge=1, le=20)
    namespace: Optional[str] = Field(None, description="Pinecone namespace")
    rerank: bool = Field(False, description="Whether to rerank results")


# Document parsing utilities
def parse_pdf(file_content: bytes) -> str:
    """Extract text from PDF file."""
    if PdfReader is None:
        raise ValueError("PDF support not available. Install pypdf.")
    
    pdf = PdfReader(io.BytesIO(file_content))
    text_parts = []
    for page in pdf.pages:
        text = page.extract_text()
        if text.strip():
            text_parts.append(text)
    
    return "\n\n".join(text_parts)


def parse_docx(file_content: bytes) -> str:
    """Extract text from DOCX file."""
    if Document is None:
        raise ValueError("DOCX support not available. Install python-docx.")
    
    doc = Document(io.BytesIO(file_content))
    text_parts = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            text_parts.append(paragraph.text)
    
    return "\n\n".join(text_parts)


def parse_text(file_content: bytes) -> str:
    """Parse plain text file (TXT, MD)."""
    return file_content.decode('utf-8', errors='ignore')


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # Try to break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            
            if break_point > chunk_size // 2:
                chunk = chunk[:break_point + 1]
                end = start + break_point + 1
        
        chunks.append(chunk.strip())
        start = end - overlap
    
    return [c for c in chunks if c]


# Routes
@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    namespace: Optional[str] = Form(None),
    chunk_size: int = Form(1000),
    session_id: Optional[str] = Form(None)
):
    """
    Upload and ingest a document into Pinecone.
    Supports PDF, TXT, MD, and DOCX files.
    """
    try:
        # Read file content
        content = await file.read()
        filename = file.filename or "unknown"
        file_ext = filename.lower().split('.')[-1]
        
        logger.info(f"[RAG] Uploading file: {filename} ({len(content)} bytes)")
        
        # Parse based on file type
        if file_ext == 'pdf':
            text = parse_pdf(content)
        elif file_ext == 'docx':
            text = parse_docx(content)
        elif file_ext in ['txt', 'md', 'markdown']:
            text = parse_text(content)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        if not text.strip():
            raise ValueError("No text content found in file")
        
        # Chunk the text
        chunks = chunk_text(text, chunk_size=chunk_size)
        logger.info(f"[RAG] Split into {len(chunks)} chunks")
        
        # Prepare documents with metadata
        documents = []
        for i, chunk in enumerate(chunks):
            doc = {
                "text": chunk,
                "metadata": {
                    "filename": filename,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "file_type": file_ext,
                }
            }
            if session_id:
                doc["metadata"]["session_id"] = session_id
            documents.append(doc)
        
        # Add to Pinecone
        service = get_pinecone_service()
        result = service.add_documents(documents=documents, namespace=namespace)
        
        return {
            **result,
            "filename": filename,
            "chunks": len(chunks),
            "total_chars": len(text)
        }
        
    except Exception as e:
        logger.error(f"[RAG] Upload failed: {e}")
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
        logger.error(f"[RAG] Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear(namespace: Optional[str] = None):
    """Clear all documents from a namespace."""
    try:
        service = get_pinecone_service()
        return service.delete_namespace(namespace)
    except Exception as e:
        logger.error(f"[RAG] Clear failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def stats():
    """Get Pinecone index stats."""
    try:
        service = get_pinecone_service()
        return service.get_stats()
    except Exception as e:
        logger.error(f"[RAG] Stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
