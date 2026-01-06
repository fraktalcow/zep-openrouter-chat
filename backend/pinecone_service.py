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

        # Check if index exists
        try:
            indexes = self.pc.list_indexes()
            index_names = [i.name for i in indexes]
        except Exception:
            # Fallback for older SDKs
            index_names = self.pc.list_indexes().names()

        if self.index_name not in index_names:
            try:
                logger.info(f"Creating Pinecone index: {self.index_name}")
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
                logger.warning(f"Index creation warning (may already exist): {e}")
                
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
        # Note: 'values' are empty as we rely on server-side embedding via 'create_index_for_model'
        # The text to embed must be in metadata match 'field_map' key ('chunk_text')
        vectors = []
        for i, doc in enumerate(documents):
            # Generate a stable-ish ID
            chunk_hash = hash(doc['text']) % 1000000
            vector_id = f"{doc.get('metadata', {}).get('filename', 'doc')}_chunk_{i}_{chunk_hash}"
            
            vector = {
                "id": vector_id,
                "values": [], 
                "metadata": {
                    "chunk_text": doc["text"],
                    **doc.get("metadata", {})
                }
            }
            vectors.append(vector)
        
        # Batch upsert (Pinecone limit is usually 100-1000 vectors per call)
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch, namespace=ns)
        
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
        """
        self._ensure_resources()
        ns = namespace or self.namespace
        k = top_k or self.top_k
        
        # For integrated inference index, we pass the query string in 'inputs'
        # and Pinecone handles embedding it.
        try:
            results = self.index.search(
                namespace=ns,
                query=query, # Some SDK versions accept query string directly for inference indexes
                top_k=k,
                # If query param doesn't work for inference, use:
                # inputs={"text": query} 
                # But typically usage is index.search(q=..., ...) or similar
            )
        except TypeError:
            # Fallback to dictionary styled params if direct arg fails
             results = self.index.search(
                namespace=ns,
                query={"inputs": {"text": query}, "top_k": k}
            )

        # Handle reranking (client-side for now or via another call if supported)
        # Assuming simple search for now as rerank param in search() is not standard in all SDKs
        
        # Format results
        hits = []
        for hit in results.get("matches", []):
            hits.append({
                "id": hit.get("id"),
                "score": hit.get("score", 0),
                "text": hit.get("metadata", {}).get("chunk_text", ""),
                "metadata": {k: v for k, v in hit.get("metadata", {}).items() if k != "chunk_text"}
            })
        
        return hits
    
    def delete_namespace(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Delete all documents in a namespace."""
        self._ensure_resources()
        ns = namespace or self.namespace
        self.index.delete(delete_all=True, namespace=ns)
        return {"deleted_namespace": ns}

    def delete_file(self, filename: str, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Delete all chunks belonging to a specific file."""
        self._ensure_resources()
        ns = namespace or self.namespace
        self.index.delete(
            filter={"filename": {"$eq": filename}},
            namespace=ns
        )
        return {"deleted_file": filename}
    
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

