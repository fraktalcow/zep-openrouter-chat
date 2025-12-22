"""
Pinecone Vector Database Service.
Handles document storage, embedding, and semantic search.
"""

from typing import List, Dict, Any, Optional
from pinecone import Pinecone

from config import get_settings
from logger import logger


class PineconeService:
    """Vector database service using Pinecone with integrated embeddings."""
    
    def __init__(self):
        self.settings = get_settings()
        self.pc = Pinecone(api_key=self.settings.PINECONE_API_KEY)
        self.index_name = self.settings.PINECONE_INDEX
        self.namespace = self.settings.RAG_NAMESPACE
        self.top_k = self.settings.RAG_TOP_K
        self.index = None
        
    def _ensure_resources(self):
        """Lazy initialization of cloud resources."""
        if self.index:
            return

        # Create index if it doesn't exist
        if not self.pc.has_index(self.index_name):
            try:
                self.pc.create_index_for_model(
                    name=self.index_name,
                    cloud=self.settings.PINECONE_CLOUD,
                    region=self.settings.PINECONE_REGION,
                    embed={
                        "model": self.settings.DEFAULT_EMBEDDING_MODEL,
                        "field_map": {"text": "chunk_text"}
                    }
                )
            except Exception as e:
                # Handle race condition or permission errors safely
                logger.warning(f"Index creation warning: {e}")
                
        self.index = self.pc.Index(self.index_name)

    
    
    def add_documents(
        self, 
        documents: List[Dict[str, Any]],
        namespace: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add documents to the index.
        
        Args:
            documents: List of {"text": str, "metadata": dict}
            namespace: Optional namespace override
            
        Returns:
            Status with count
        """
        self._ensure_resources()
        ns = namespace or self.namespace
        
        # Prepare records for Pinecone
        records = []
        for i, doc in enumerate(documents):
            record = {
                "_id": f"doc_{i}_{hash(doc['text']) % 100000}",
                "chunk_text": doc["text"],
                **doc.get("metadata", {})
            }
            records.append(record)
        
        # Upsert to Pinecone
        self.index.upsert_records(namespace=ns, records=records)
        
        return {"added": len(documents), "namespace": ns}
    
    def search(
        self, 
        query: str, 
        top_k: Optional[int] = None,
        namespace: Optional[str] = None,
        rerank: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Semantic search with optional reranking.
        
        Args:
            query: Search query text
            top_k: Number of results
            namespace: Optional namespace override
            rerank: Whether to rerank results
            
        Returns:
            List of matching documents with scores
        """
        self._ensure_resources()
        ns = namespace or self.namespace
        k = top_k or self.top_k
        
        search_params = {
            "namespace": ns,
            "query": {
                "top_k": k,
                "inputs": {"text": query}
            }
        }
        
        # Add reranking if requested
        if rerank:
            search_params["rerank"] = {
                "model": "bge-reranker-v2-m3",
                "top_n": k,
                "rank_fields": ["chunk_text"]
            }
        
        results = self.index.search(**search_params)
        
        # Format results
        hits = []

        for hit in results.get("result", {}).get("hits", []):
            hits.append({
                "id": hit.get("_id"),
                "score": hit.get("_score", 0),
                "text": hit.get("fields", {}).get("chunk_text", ""),
                "metadata": {k: v for k, v in hit.get("fields", {}).items() if k != "chunk_text"}
            })
        
        return hits
    
    def delete_namespace(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Delete all documents in a namespace."""
        self._ensure_resources()
        ns = namespace or self.namespace
        self.index.delete(namespace=ns, delete_all=True)
        return {"deleted_namespace": ns}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        self._ensure_resources()
        stats = self.index.describe_index_stats()
        return {
            "total_vectors": stats.get("total_vector_count", 0),
            "namespaces": stats.get("namespaces", {}),
            "index_name": self.index_name
        }


# Singleton instance
_pinecone_service: Optional[PineconeService] = None


def get_pinecone_service() -> PineconeService:
    """Get or create Pinecone service instance."""
    global _pinecone_service
    if _pinecone_service is None:
        _pinecone_service = PineconeService()
    return _pinecone_service

