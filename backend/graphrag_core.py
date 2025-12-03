"""
GraphRAG Core Module

Implements the core GraphRAG functionality including:
- Document ingestion and chunking
- Embedding generation
- Vector and BM25 search
- Hybrid search with configurable algorithms
- Entity and relationship extraction
- Graph-based retrieval
"""

import asyncio
import hashlib
import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

from graphrag_config import GraphRAGConfig, SearchAlgorithm, ChunkingStrategy


logger = logging.getLogger(__name__)


class DocumentChunker:
    """Handles document chunking with multiple strategies"""
    
    def __init__(self, config: GraphRAGConfig):
        self.config = config
    
    def chunk_document(self, text: str, metadata: Optional[Dict] = None) -> List[Dict]:
        """Chunk document based on configured strategy"""
        strategy = self.config.chunking_strategy
        
        if strategy == ChunkingStrategy.FIXED_SIZE:
            chunks = self._chunk_fixed_size(text)
        elif strategy == ChunkingStrategy.SEMANTIC:
            chunks = self._chunk_semantic(text)
        elif strategy == ChunkingStrategy.SENTENCE:
            chunks = self._chunk_by_sentence(text)
        elif strategy == ChunkingStrategy.PARAGRAPH:
            chunks = self._chunk_by_paragraph(text)
        else:
            chunks = self._chunk_fixed_size(text)
        
        # Add metadata to chunks
        result = []
        for i, chunk_text in enumerate(chunks):
            chunk_data = {
                "text": chunk_text,
                "chunk_id": self._generate_chunk_id(chunk_text),
                "chunk_index": i,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat(),
            }
            result.append(chunk_data)
        
        return result
    
    def _chunk_fixed_size(self, text: str) -> List[str]:
        """Fixed-size chunking with overlap"""
        chunks = []
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap
        
        words = text.split()
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if len(chunk) >= self.config.min_chunk_size:
                chunks.append(chunk)
        
        return chunks
    
    def _chunk_semantic(self, text: str) -> List[str]:
        """Semantic chunking based on topic coherence"""
        # Split by paragraphs first
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para.split())
            
            if current_size + para_size > self.config.chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    def _chunk_by_sentence(self, text: str) -> List[str]:
        """Chunk by sentences"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence.split())
            
            if current_size + sentence_size > self.config.chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_size = sentence_size
            else:
                current_chunk.append(sentence)
                current_size += sentence_size
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    def _chunk_by_paragraph(self, text: str) -> List[str]:
        """Chunk by paragraphs"""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return [p for p in paragraphs if len(p.split()) >= self.config.min_chunk_size]
    
    def _generate_chunk_id(self, text: str) -> str:
        """Generate unique ID for chunk"""
        return hashlib.sha256(text.encode()).hexdigest()[:16]


class EmbeddingGenerator:
    """Generates embeddings using sentence transformers"""
    
    def __init__(self, config: GraphRAGConfig):
        self.config = config
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load embedding model"""
        logger.info(f"Loading embedding model: {self.config.embedding_model}")
        self.model = SentenceTransformer(
            self.config.embedding_model,
            device=self.config.embedding_device
        )
    
    def encode(self, texts: List[str], batch_size: Optional[int] = None) -> np.ndarray:
        """Generate embeddings for texts"""
        batch_size = batch_size or self.config.embedding_batch_size
        
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=self.config.normalize_embeddings,
            show_progress_bar=self.config.verbose,
        )
        
        return embeddings
    
    def encode_single(self, text: str) -> np.ndarray:
        """Generate embedding for single text"""
        return self.encode([text])[0]


class BM25Retriever:
    """BM25-based text retrieval"""
    
    def __init__(self, config: GraphRAGConfig):
        self.config = config
        self.bm25 = None
        self.documents = []
        self.tokenized_docs = []
    
    def index_documents(self, documents: List[Dict]):
        """Index documents for BM25 search"""
        self.documents = documents
        self.tokenized_docs = [self._tokenize(doc["text"]) for doc in documents]
        
        # Only initialize BM25 if we have documents
        if self.tokenized_docs:
            self.bm25 = BM25Okapi(self.tokenized_docs)
        else:
            self.bm25 = None

    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict, float]]:
        """Search using BM25"""
        if not self.bm25:
            return []
        
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top k results
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = [(self.documents[i], scores[i]) for i in top_indices]
        
        return results
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization"""
        return text.lower().split()


class VectorRetriever:
    """Vector similarity-based retrieval"""
    
    def __init__(self, config: GraphRAGConfig, embedding_generator: EmbeddingGenerator):
        self.config = config
        self.embedding_generator = embedding_generator
        self.documents = []
        self.embeddings = None
    
    def index_documents(self, documents: List[Dict]):
        """Index documents with embeddings"""
        self.documents = documents
        texts = [doc["text"] for doc in documents]
        self.embeddings = self.embedding_generator.encode(texts)
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict, float]]:
        """Search using vector similarity"""
        if self.embeddings is None or len(self.documents) == 0:
            return []
        
        query_embedding = self.embedding_generator.encode_single(query)
        
        # Compute cosine similarity
        similarities = np.dot(self.embeddings, query_embedding)
        
        # Get top k results
        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = [(self.documents[i], similarities[i]) for i in top_indices]
        
        # Filter by threshold
        results = [(doc, score) for doc, score in results 
                   if score >= self.config.similarity_threshold]
        
        return results


class HybridRetriever:
    """Hybrid retrieval combining BM25 and vector search"""
    
    def __init__(
        self,
        config: GraphRAGConfig,
        bm25_retriever: BM25Retriever,
        vector_retriever: VectorRetriever,
    ):
        self.config = config
        self.bm25_retriever = bm25_retriever
        self.vector_retriever = vector_retriever
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict, float]]:
        """Hybrid search combining BM25 and vector similarity"""
        alpha = self.config.hybrid_alpha
        
        # Get results from both retrievers
        bm25_results = {}
        vector_results = {}
        
        if self.config.enable_bm25:
            bm25_results = {
                doc["chunk_id"]: score 
                for doc, score in self.bm25_retriever.search(query, top_k * 2)
            }
        
        if self.config.enable_vector_search:
            vector_results = {
                doc["chunk_id"]: score 
                for doc, score in self.vector_retriever.search(query, top_k * 2)
            }
        
        # Normalize scores
        bm25_scores = self._normalize_scores(bm25_results)
        vector_scores = self._normalize_scores(vector_results)
        
        # Combine scores
        all_chunk_ids = set(bm25_scores.keys()) | set(vector_scores.keys())
        combined_scores = {}
        
        for chunk_id in all_chunk_ids:
            bm25_score = bm25_scores.get(chunk_id, 0.0)
            vector_score = vector_scores.get(chunk_id, 0.0)
            combined_scores[chunk_id] = (1 - alpha) * bm25_score + alpha * vector_score
        
        # Sort by combined score
        sorted_ids = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Get documents
        doc_map = {doc["chunk_id"]: doc for doc in self.vector_retriever.documents}
        results = [
            (doc_map[chunk_id], score) 
            for chunk_id, score in sorted_ids[:top_k]
            if chunk_id in doc_map
        ]
        
        return results
    
    def _normalize_scores(self, scores: Dict[str, float]) -> Dict[str, float]:
        """Normalize scores to [0, 1]"""
        if not scores:
            return {}
        
        values = list(scores.values())
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            return {k: 1.0 for k in scores.keys()}
        
        return {
            k: (v - min_val) / (max_val - min_val)
            for k, v in scores.items()
        }


class GraphRAG:
    """Main GraphRAG system"""
    
    def __init__(self, config: Optional[GraphRAGConfig] = None):
        self.config = config or GraphRAGConfig()
        
        # Initialize components
        self.chunker = DocumentChunker(self.config)
        self.embedding_generator = EmbeddingGenerator(self.config)
        self.bm25_retriever = BM25Retriever(self.config)
        self.vector_retriever = VectorRetriever(self.config, self.embedding_generator)
        self.hybrid_retriever = HybridRetriever(
            self.config, self.bm25_retriever, self.vector_retriever
        )
        
        # Storage
        self.documents = []
        self.chunks = []
        
        # Metrics
        self.metrics = {
            "documents_ingested": 0,
            "chunks_created": 0,
            "queries_processed": 0,
        }
    
    async def ingest_document(
        self,
        text: str,
        metadata: Optional[Dict] = None,
        doc_id: Optional[str] = None,
    ) -> Dict:
        """Ingest a document into the GraphRAG system"""
        logger.info(f"Ingesting document: {doc_id or 'unnamed'}")
        
        # Generate document ID
        if not doc_id:
            doc_id = hashlib.sha256(text.encode()).hexdigest()[:16]
        
        # Chunk document
        chunks = self.chunker.chunk_document(text, metadata)
        
        # Add document ID to chunks
        for chunk in chunks:
            chunk["document_id"] = doc_id
        
        # Store chunks
        self.chunks.extend(chunks)
        
        # Index for retrieval
        self._reindex()
        
        # Update metrics
        self.metrics["documents_ingested"] += 1
        self.metrics["chunks_created"] += len(chunks)
        
        return {
            "document_id": doc_id,
            "chunks_created": len(chunks),
            "status": "success",
        }
    
    async def ingest_documents(self, documents: List[Dict]) -> Dict:
        """Ingest multiple documents"""
        results = []
        
        for doc in documents:
            result = await self.ingest_document(
                text=doc.get("text", ""),
                metadata=doc.get("metadata", {}),
                doc_id=doc.get("id"),
            )
            results.append(result)
        
        return {
            "documents_ingested": len(results),
            "total_chunks": sum(r["chunks_created"] for r in results),
            "results": results,
        }
    
    def search(self, query: str, top_k: Optional[int] = None) -> List[Dict]:
        """Search for relevant chunks"""
        top_k = top_k or self.config.top_k
        
        # Select search algorithm
        algorithm = self.config.search_algorithm
        
        if algorithm == SearchAlgorithm.BM25:
            results = self.bm25_retriever.search(query, top_k)
        elif algorithm == SearchAlgorithm.VECTOR_SIMILARITY:
            results = self.vector_retriever.search(query, top_k)
        elif algorithm == SearchAlgorithm.HYBRID:
            results = self.hybrid_retriever.search(query, top_k)
        else:
            results = self.hybrid_retriever.search(query, top_k)
        
        # Update metrics
        self.metrics["queries_processed"] += 1
        
        # Format results
        formatted_results = []
        for doc, score in results:
            formatted_results.append({
                "chunk_id": doc["chunk_id"],
                "text": doc["text"],
                "score": float(score),
                "metadata": doc.get("metadata", {}),
                "document_id": doc.get("document_id"),
            })
        
        return formatted_results
    
    def _reindex(self):
        """Reindex all chunks"""
        if self.config.enable_bm25:
            self.bm25_retriever.index_documents(self.chunks)
        
        if self.config.enable_vector_search:
            self.vector_retriever.index_documents(self.chunks)
    
    def get_stats(self) -> Dict:
        """Get system statistics"""
        return {
            "config": self.config.to_dict(),
            "metrics": self.metrics,
            "total_chunks": len(self.chunks),
            "embedding_model": self.config.embedding_model,
            "search_algorithm": self.config.search_algorithm,
        }
    
    def clear(self):
        """Clear all indexed data"""
        self.chunks = []
        self.documents = []
        self.bm25_retriever.documents = []
        self.bm25_retriever.tokenized_docs = []
        self.bm25_retriever.bm25 = None
        self.vector_retriever.documents = []
        self.vector_retriever.embeddings = None
        
        logger.info("GraphRAG cleared")
