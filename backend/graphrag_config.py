"""
GraphRAG Configuration Module

Defines toggleable features and configuration for the GraphRAG system.
All algorithms and features can be enabled/disabled via configuration.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class EmbeddingModel(str, Enum):
    """Available embedding models"""
    MINILM_L6 = "all-MiniLM-L6-v2"
    MINILM_L12 = "all-MiniLM-L12-v2"
    MPNET_BASE = "all-mpnet-base-v2"
    BGE_SMALL = "BAAI/bge-small-en-v1.5"
    BGE_BASE = "BAAI/bge-base-en-v1.5"


class SearchAlgorithm(str, Enum):
    """Available search algorithms"""
    VECTOR_SIMILARITY = "vector_similarity"
    BM25 = "bm25"
    HYBRID = "hybrid"
    GRAPH_TRAVERSAL = "graph_traversal"


class ChunkingStrategy(str, Enum):
    """Document chunking strategies"""
    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"


class RerankingMethod(str, Enum):
    """Reranking methods for search results"""
    NONE = "none"
    CROSS_ENCODER = "cross_encoder"
    LLM_BASED = "llm_based"
    RECIPROCAL_RANK_FUSION = "rrf"


class EmbeddingDevice(str, Enum):
    """Available embedding devices"""
    CPU = "cpu"
    CUDA = "cuda"


@dataclass
class GraphRAGConfig:
    """Configuration for GraphRAG system with toggleable features"""
    
    # Embedding Configuration
    embedding_model: str = EmbeddingModel.MINILM_L6
    embedding_device: str = EmbeddingDevice.CUDA
    embedding_batch_size: int = 32
    normalize_embeddings: bool = True
    
    # Search Configuration
    search_algorithm: str = SearchAlgorithm.HYBRID
    enable_bm25: bool = True
    enable_vector_search: bool = True
    enable_graph_traversal: bool = True
    hybrid_alpha: float = 0.5  # Weight for vector vs BM25 (0=BM25 only, 1=vector only)
    
    # Chunking Configuration
    chunking_strategy: str = ChunkingStrategy.SEMANTIC
    chunk_size: int = 512
    chunk_overlap: int = 50
    min_chunk_size: int = 100
    max_chunk_size: int = 1000
    
    # Retrieval Configuration
    top_k: int = 5
    similarity_threshold: float = 0.7
    enable_reranking: bool = True
    reranking_method: str = RerankingMethod.RECIPROCAL_RANK_FUSION
    rerank_top_k: int = 20  # Retrieve more, then rerank to top_k
    
    # Graph Construction
    enable_entity_extraction: bool = True
    enable_relationship_extraction: bool = True
    enable_community_detection: bool = True
    min_entity_confidence: float = 0.6
    min_relationship_confidence: float = 0.5
    
    # Advanced Features
    enable_query_expansion: bool = True
    enable_multi_hop_reasoning: bool = True
    max_hops: int = 2
    enable_temporal_awareness: bool = False
    enable_citation_tracking: bool = True
    
    # Performance
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    enable_async_processing: bool = True
    max_workers: int = 4
    
    # Storage
    vector_store_type: str = "faiss"  # faiss, chroma, or qdrant
    graph_store_type: str = "zep"  # zep or networkx
    persist_embeddings: bool = True
    embeddings_path: str = "./data/embeddings"
    
    # Document Processing
    enable_ocr: bool = False
    enable_table_extraction: bool = False
    enable_image_captioning: bool = False
    supported_formats: List[str] = field(default_factory=lambda: [
        "txt", "pdf", "docx", "md", "html", "json"
    ])
    
    # Debugging
    verbose: bool = False
    log_level: str = "INFO"
    enable_metrics: bool = True
    
    def to_dict(self) -> dict:
        """Convert config to dictionary"""
        return {
            "embedding": {
                "model": self.embedding_model,
                "device": self.embedding_device,
                "batch_size": self.embedding_batch_size,
                "normalize": self.normalize_embeddings,
            },
            "search": {
                "algorithm": self.search_algorithm,
                "bm25_enabled": self.enable_bm25,
                "vector_enabled": self.enable_vector_search,
                "graph_enabled": self.enable_graph_traversal,
                "hybrid_alpha": self.hybrid_alpha,
            },
            "chunking": {
                "strategy": self.chunking_strategy,
                "size": self.chunk_size,
                "overlap": self.chunk_overlap,
                "min_size": self.min_chunk_size,
                "max_size": self.max_chunk_size,
            },
            "retrieval": {
                "top_k": self.top_k,
                "threshold": self.similarity_threshold,
                "reranking_enabled": self.enable_reranking,
                "reranking_method": self.reranking_method,
                "rerank_top_k": self.rerank_top_k,
            },
            "graph": {
                "entity_extraction": self.enable_entity_extraction,
                "relationship_extraction": self.enable_relationship_extraction,
                "community_detection": self.enable_community_detection,
                "min_entity_confidence": self.min_entity_confidence,
                "min_relationship_confidence": self.min_relationship_confidence,
            },
            "advanced": {
                "query_expansion": self.enable_query_expansion,
                "multi_hop_reasoning": self.enable_multi_hop_reasoning,
                "max_hops": self.max_hops,
                "temporal_awareness": self.enable_temporal_awareness,
                "citation_tracking": self.enable_citation_tracking,
            },
            "performance": {
                "caching": self.enable_caching,
                "cache_ttl": self.cache_ttl_seconds,
                "async_processing": self.enable_async_processing,
                "max_workers": self.max_workers,
            },
        }


# Default configurations for different use cases
CONFIGS = {
    "default": GraphRAGConfig(),
    
    "fast": GraphRAGConfig(
        search_algorithm=SearchAlgorithm.VECTOR_SIMILARITY,
        enable_bm25=False,
        enable_graph_traversal=False,
        enable_reranking=False,
        enable_entity_extraction=False,
        enable_relationship_extraction=False,
        enable_query_expansion=False,
        enable_multi_hop_reasoning=False,
    ),
    
    "accurate": GraphRAGConfig(
        search_algorithm=SearchAlgorithm.HYBRID,
        enable_bm25=True,
        enable_vector_search=True,
        enable_graph_traversal=True,
        enable_reranking=True,
        reranking_method=RerankingMethod.CROSS_ENCODER,
        enable_entity_extraction=True,
        enable_relationship_extraction=True,
        enable_query_expansion=True,
        enable_multi_hop_reasoning=True,
        rerank_top_k=50,
        top_k=10,
    ),
    
    "balanced": GraphRAGConfig(
        search_algorithm=SearchAlgorithm.HYBRID,
        enable_bm25=True,
        enable_vector_search=True,
        enable_reranking=True,
        reranking_method=RerankingMethod.RECIPROCAL_RANK_FUSION,
        enable_entity_extraction=True,
        enable_relationship_extraction=True,
        top_k=5,
    ),
}


def get_config(profile: str = "default") -> GraphRAGConfig:
    """Get configuration by profile name"""
    return CONFIGS.get(profile, CONFIGS["default"])
