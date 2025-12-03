"""
GraphRAG Test Script

Demonstrates GraphRAG functionality including:
- Document ingestion
- Search with different algorithms
- Configuration updates
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from graphrag_config import GraphRAGConfig, SearchAlgorithm, ChunkingStrategy
from graphrag_core import GraphRAG


async def main():
    print("=" * 80)
    print("GraphRAG Test Script")
    print("=" * 80)
    
    # Sample documents
    documents = [
        {
            "text": """
            Machine learning is a subset of artificial intelligence that focuses on 
            developing algorithms and statistical models that enable computers to learn 
            from and make predictions or decisions based on data. Unlike traditional 
            programming where explicit instructions are provided, machine learning 
            systems improve their performance through experience.
            """,
            "metadata": {"source": "ml_textbook", "chapter": 1, "topic": "introduction"},
        },
        {
            "text": """
            Neural networks are computing systems inspired by biological neural networks 
            that constitute animal brains. They consist of interconnected nodes (neurons) 
            organized in layers. Deep learning uses neural networks with multiple hidden 
            layers to learn hierarchical representations of data. This approach has 
            revolutionized fields like computer vision and natural language processing.
            """,
            "metadata": {"source": "ml_textbook", "chapter": 2, "topic": "neural_networks"},
        },
        {
            "text": """
            Natural Language Processing (NLP) is a branch of AI that helps computers 
            understand, interpret, and manipulate human language. NLP combines 
            computational linguistics with machine learning and deep learning models. 
            Applications include sentiment analysis, machine translation, chatbots, 
            and text summarization.
            """,
            "metadata": {"source": "nlp_guide", "chapter": 1, "topic": "nlp_basics"},
        },
        {
            "text": """
            Transformers are a type of neural network architecture that has become the 
            foundation of modern NLP. They use self-attention mechanisms to process 
            sequential data in parallel, making them much more efficient than recurrent 
            neural networks. Models like BERT, GPT, and T5 are all based on the 
            transformer architecture.
            """,
            "metadata": {"source": "nlp_guide", "chapter": 3, "topic": "transformers"},
        },
    ]
    
    # Test 1: Vector Search
    print("\n" + "=" * 80)
    print("Test 1: Vector Search")
    print("=" * 80)
    
    config = GraphRAGConfig(
        search_algorithm=SearchAlgorithm.VECTOR_SIMILARITY,
        enable_bm25=False,
        enable_vector_search=True,
        embedding_device="cpu",  # Use CPU for compatibility
        chunking_strategy=ChunkingStrategy.SEMANTIC,
        top_k=3,
    )
    
    graphrag = GraphRAG(config)
    
    # Ingest documents
    print("\nIngesting documents...")
    for doc in documents:
        result = await graphrag.ingest_document(
            text=doc["text"],
            metadata=doc["metadata"],
        )
        print(f"  ✓ Document ingested: {result['chunks_created']} chunks created")
    
    # Search
    query = "What are neural networks?"
    print(f"\nQuery: '{query}'")
    results = graphrag.search(query, top_k=3)
    
    print(f"\nTop {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. Score: {result['score']:.4f}")
        print(f"   Source: {result['metadata'].get('source', 'unknown')}")
        print(f"   Topic: {result['metadata'].get('topic', 'unknown')}")
        print(f"   Text: {result['text'][:150]}...")
    
    # Test 2: BM25 Search
    print("\n" + "=" * 80)
    print("Test 2: BM25 Search")
    print("=" * 80)
    
    config.search_algorithm = SearchAlgorithm.BM25
    config.enable_bm25 = True
    config.enable_vector_search = False
    graphrag = GraphRAG(config)
    
    # Ingest documents
    print("\nIngesting documents...")
    for doc in documents:
        await graphrag.ingest_document(text=doc["text"], metadata=doc["metadata"])
    
    # Search
    query = "transformers attention mechanism"
    print(f"\nQuery: '{query}'")
    results = graphrag.search(query, top_k=3)
    
    print(f"\nTop {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. Score: {result['score']:.4f}")
        print(f"   Source: {result['metadata'].get('source', 'unknown')}")
        print(f"   Topic: {result['metadata'].get('topic', 'unknown')}")
        print(f"   Text: {result['text'][:150]}...")
    
    # Test 3: Hybrid Search
    print("\n" + "=" * 80)
    print("Test 3: Hybrid Search (BM25 + Vector)")
    print("=" * 80)
    
    config.search_algorithm = SearchAlgorithm.HYBRID
    config.enable_bm25 = True
    config.enable_vector_search = True
    config.hybrid_alpha = 0.5  # Equal weight
    graphrag = GraphRAG(config)
    
    # Ingest documents
    print("\nIngesting documents...")
    for doc in documents:
        await graphrag.ingest_document(text=doc["text"], metadata=doc["metadata"])
    
    # Search
    query = "How does NLP work?"
    print(f"\nQuery: '{query}'")
    results = graphrag.search(query, top_k=3)
    
    print(f"\nTop {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. Score: {result['score']:.4f}")
        print(f"   Source: {result['metadata'].get('source', 'unknown')}")
        print(f"   Topic: {result['metadata'].get('topic', 'unknown')}")
        print(f"   Text: {result['text'][:150]}...")
    
    # Test 4: Different Chunking Strategies
    print("\n" + "=" * 80)
    print("Test 4: Different Chunking Strategies")
    print("=" * 80)
    
    strategies = [
        ChunkingStrategy.FIXED_SIZE,
        ChunkingStrategy.SEMANTIC,
        ChunkingStrategy.SENTENCE,
        ChunkingStrategy.PARAGRAPH,
    ]
    
    sample_text = documents[0]["text"]
    
    for strategy in strategies:
        config.chunking_strategy = strategy
        graphrag = GraphRAG(config)
        
        result = await graphrag.ingest_document(text=sample_text)
        print(f"\n{strategy}: {result['chunks_created']} chunks created")
    
    # Statistics
    print("\n" + "=" * 80)
    print("GraphRAG Statistics")
    print("=" * 80)
    
    stats = graphrag.get_stats()
    print(f"\nDocuments ingested: {stats['metrics']['documents_ingested']}")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Queries processed: {stats['metrics']['queries_processed']}")
    print(f"Embedding model: {stats['embedding_model']}")
    print(f"Search algorithm: {stats['search_algorithm']}")
    
    print("\n" + "=" * 80)
    print("All tests completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
