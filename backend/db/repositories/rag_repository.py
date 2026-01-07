"""
RAG Document repository - tracking uploaded documents.
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import RAGDocument
from logger import logger


class RAGDocumentRepository:
    """Repository for RAG document tracking."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self,
        user_id: str,
        filename: str,
        file_type: str,
        chunk_count: int,
        file_size_bytes: Optional[int] = None,
        pinecone_namespace: str = "default",
        metadata: Optional[dict] = None,
    ) -> RAGDocument:
        """Record a new uploaded document."""
        doc = RAGDocument(
            user_id=user_id,
            filename=filename,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            chunk_count=chunk_count,
            pinecone_namespace=pinecone_namespace,
            metadata_=metadata or {},
        )
        self.db.add(doc)
        await self.db.flush()
        logger.info(f"[DB] RAG document recorded: {filename} ({chunk_count} chunks)")
        return doc
    
    async def get_by_id(self, doc_id: str) -> Optional[RAGDocument]:
        """Get document by ID."""
        result = await self.db.execute(
            select(RAGDocument).where(RAGDocument.id == doc_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_filename(
        self,
        user_id: str,
        filename: str,
    ) -> Optional[RAGDocument]:
        """Get document by filename for a user."""
        result = await self.db.execute(
            select(RAGDocument)
            .where(RAGDocument.user_id == user_id)
            .where(RAGDocument.filename == filename)
        )
        return result.scalar_one_or_none()
    
    async def list_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RAGDocument]:
        """List documents for a user ordered by upload date."""
        result = await self.db.execute(
            select(RAGDocument)
            .where(RAGDocument.user_id == user_id)
            .order_by(RAGDocument.uploaded_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    async def list_by_namespace(
        self,
        namespace: str,
        limit: int = 50,
    ) -> List[RAGDocument]:
        """List documents in a Pinecone namespace."""
        result = await self.db.execute(
            select(RAGDocument)
            .where(RAGDocument.pinecone_namespace == namespace)
            .order_by(RAGDocument.uploaded_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def delete(self, doc_id: str) -> bool:
        """Delete a document record."""
        doc = await self.get_by_id(doc_id)
        if doc:
            await self.db.delete(doc)
            await self.db.flush()
            logger.info(f"[DB] RAG document deleted: {doc.filename}")
            return True
        return False
    
    async def delete_by_filename(
        self,
        user_id: str,
        filename: str,
    ) -> bool:
        """Delete document by filename for a user."""
        doc = await self.get_by_filename(user_id, filename)
        if doc:
            await self.db.delete(doc)
            await self.db.flush()
            logger.info(f"[DB] RAG document deleted: {filename}")
            return True
        return False
    
    async def count_by_user(self, user_id: str) -> int:
        """Count documents for a user."""
        result = await self.db.execute(
            select(func.count(RAGDocument.id))
            .where(RAGDocument.user_id == user_id)
        )
        return result.scalar() or 0
    
    async def total_chunks_by_user(self, user_id: str) -> int:
        """Get total chunk count for a user."""
        result = await self.db.execute(
            select(func.sum(RAGDocument.chunk_count))
            .where(RAGDocument.user_id == user_id)
        )
        return result.scalar() or 0
    
    async def get_stats(self, user_id: Optional[str] = None) -> dict:
        """Get document statistics, optionally filtered by user."""
        query = select(
            func.count(RAGDocument.id).label("document_count"),
            func.sum(RAGDocument.chunk_count).label("total_chunks"),
            func.sum(RAGDocument.file_size_bytes).label("total_bytes"),
        )
        
        if user_id:
            query = query.where(RAGDocument.user_id == user_id)
        
        result = await self.db.execute(query)
        row = result.one()
        
        return {
            "document_count": row.document_count or 0,
            "total_chunks": row.total_chunks or 0,
            "total_bytes": row.total_bytes or 0,
        }
