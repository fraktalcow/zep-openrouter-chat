"""
GraphRAG Service

Integrates GraphRAG with Zep knowledge graph for enhanced retrieval.
Provides document ingestion and chat capabilities.
"""

import logging
from typing import Any, Dict, List, Optional

from graphrag_config import GraphRAGConfig, get_config, EmbeddingDevice
from graphrag_core import GraphRAG
from zep_service import ZepService


logger = logging.getLogger(__name__)


class GraphRAGService:
    """Service layer for GraphRAG operations"""
    
    def __init__(
        self,
        zep_service: Optional[ZepService] = None,
        config: Optional[GraphRAGConfig] = None,
        config_profile: str = "default",
    ):
        """
        Initialize GraphRAG service
        
        Args:
            zep_service: Optional Zep service for knowledge graph integration
            config: GraphRAG configuration (overrides config_profile)
            config_profile: Configuration profile name (default, fast, accurate, balanced)
        """
        self.zep_service = zep_service
        self.config = config or get_config(config_profile)
        self.graphrag = GraphRAG(self.config)
        
        logger.info(f"GraphRAG service initialized with profile: {config_profile}")
    
    async def ingest_document(
        self,
        text: str,
        metadata: Optional[Dict] = None,
        doc_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict:
        """
        Ingest a document into GraphRAG
        
        Args:
            text: Document text
            metadata: Optional metadata
            doc_id: Optional document ID
            user_id: Optional user ID for Zep integration
            
        Returns:
            Ingestion result
        """
        # Ingest into GraphRAG
        result = await self.graphrag.ingest_document(text, metadata, doc_id)
        
        # Optionally add to Zep knowledge graph
        if self.zep_service and user_id:
            try:
                # Add document as a fact to Zep
                await self.zep_service.add_fact(
                    user_id=user_id,
                    fact=f"Document: {text[:200]}...",  # Truncate for fact
                    metadata={
                        "type": "document",
                        "document_id": result["document_id"],
                        **(metadata or {}),
                    },
                )
                result["zep_integrated"] = True
            except Exception as e:
                logger.error(f"Failed to integrate with Zep: {e}")
                result["zep_integrated"] = False
        
        return result
    
    async def ingest_documents(
        self,
        documents: List[Dict],
        user_id: Optional[str] = None,
    ) -> Dict:
        """
        Ingest multiple documents
        
        Args:
            documents: List of documents with 'text', 'metadata', and optional 'id'
            user_id: Optional user ID for Zep integration
            
        Returns:
            Batch ingestion result
        """
        results = []
        
        for doc in documents:
            result = await self.ingest_document(
                text=doc.get("text", ""),
                metadata=doc.get("metadata", {}),
                doc_id=doc.get("id"),
                user_id=user_id,
            )
            results.append(result)
        
        return {
            "documents_ingested": len(results),
            "total_chunks": sum(r["chunks_created"] for r in results),
            "results": results,
        }
    
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Search for relevant chunks
        
        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters
            
        Returns:
            List of relevant chunks with scores
        """
        results = self.graphrag.search(query, top_k)
        
        # Apply metadata filters if provided
        if filters:
            results = self._apply_filters(results, filters)
        
        return results
    
    async def chat(
        self,
        query: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        top_k: Optional[int] = None,
        include_zep_context: bool = True,
    ) -> Dict:
        """
        Chat with GraphRAG and optionally Zep context
        
        Args:
            query: User query
            user_id: User ID for Zep integration
            session_id: Session ID for Zep integration
            top_k: Number of chunks to retrieve
            include_zep_context: Whether to include Zep knowledge graph context
            
        Returns:
            Chat response with context
        """
        # Search GraphRAG
        graphrag_results = self.search(query, top_k)
        
        # Get Zep context if enabled
        zep_context = []
        if include_zep_context and self.zep_service and user_id:
            try:
                zep_facts = await self.zep_service.search_facts(user_id, query)
                zep_context = [
                    {
                        "fact": fact.get("fact", ""),
                        "score": fact.get("score", 0.0),
                        "source": "zep",
                    }
                    for fact in zep_facts
                ]
            except Exception as e:
                logger.error(f"Failed to get Zep context: {e}")
        
        # Combine contexts
        context = {
            "graphrag_chunks": graphrag_results,
            "zep_facts": zep_context,
            "query": query,
        }
        
        return {
            "context": context,
            "num_graphrag_results": len(graphrag_results),
            "num_zep_facts": len(zep_context),
        }
    
    def update_config(self, config_updates: Dict) -> Dict:
        """
        Update GraphRAG configuration
        
        Args:
            config_updates: Dictionary of config updates
            
        Returns:
            Updated configuration
        """
        for key, value in config_updates.items():
            if key == "embedding_device":
                # Validate device
                allowed_devices = [d.value for d in EmbeddingDevice]
                if value not in allowed_devices:
                    raise ValueError(f"Invalid embedding_device: {value}. Must be one of {allowed_devices}")

            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        # Reinitialize GraphRAG with new config
        self.graphrag = GraphRAG(self.config)
        
        return self.config.to_dict()
    
    def get_config(self) -> Dict:
        """Get current configuration"""
        return self.config.to_dict()
    
    def get_stats(self) -> Dict:
        """Get GraphRAG statistics"""
        return self.graphrag.get_stats()
    
    def clear(self):
        """Clear all indexed data"""
        self.graphrag.clear()
    
    def _apply_filters(self, results: List[Dict], filters: Dict) -> List[Dict]:
        """Apply metadata filters to results"""
        filtered = []
        
        for result in results:
            metadata = result.get("metadata", {})
            match = True
            
            for key, value in filters.items():
                if metadata.get(key) != value:
                    match = False
                    break
            
            if match:
                filtered.append(result)
        
        return filtered


# Global instance (can be initialized in server.py)
_graphrag_service: Optional[GraphRAGService] = None


def get_graphrag_service() -> Optional[GraphRAGService]:
    """Get global GraphRAG service instance"""
    return _graphrag_service


def init_graphrag_service(
    zep_service: Optional[ZepService] = None,
    config: Optional[GraphRAGConfig] = None,
    config_profile: str = "default",
) -> GraphRAGService:
    """Initialize global GraphRAG service"""
    global _graphrag_service
    _graphrag_service = GraphRAGService(zep_service, config, config_profile)
    return _graphrag_service
