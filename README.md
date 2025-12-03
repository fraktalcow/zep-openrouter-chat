# Zep Knowledge Graph + GraphRAG Chat

AI chat system combining **Zep's Knowledge Graph**, **Local GraphRAG**, and **OpenRouter's multi-model AI** for context-aware conversations with document retrieval.

![OpenAgent Screenshot](assets/hyprshot.png)

## Technical Stack

- **Backend**: FastAPI, Python 3.10+
- **Knowledge Graph**: Zep Cloud (graph-based memory)
- **GraphRAG**: Local document retrieval with BM25 + vector search
- **Embeddings**: sentence-transformers (MiniLM, MPNet, BGE)
- **AI Models**: OpenRouter API (100+ models)
- **Search**: Hybrid (BM25Okapi + cosine similarity)
- **Compute**: CUDA/CPU support for embeddings

## Features

**Knowledge Graph**

- Persistent graph-based memory via Zep
- User preferences, traits, conversation history
- Adaptive graph generation

**GraphRAG**

- Document ingestion with chunking strategies (fixed, semantic, sentence, paragraph)
- Hybrid search (BM25 + vector similarity)
- Configurable algorithms: vector, BM25, hybrid, graph traversal
- GPU-accelerated embeddings
- Reranking support

**AI Integration**

- 100+ models via OpenRouter
- Free models: Llama, Gemini, Mistral, Phi-3, Qwen
- Dynamic model search/autocomplete
- Configurable temperature, max_tokens

## Installation

### Using UV (Recommended)

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone <repo-url>
cd openagent

# Install dependencies
uv sync

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

# Run server
uv run python backend/server.py
```

## Configuration

**backend/.env**

```bash
OPENROUTER_API_KEY=  # Get from https://openrouter.ai/keys
ZEP_API_KEY=           # Get from https://www.getzep.com/

# GraphRAG (optional)
GRAPHRAG_ENABLED=true
GRAPHRAG_PROFILE=balanced  # default | fast | accurate | balanced
```

**GraphRAG Profiles**

- `default`: Balanced config
- `fast`: Vector search only
- `accurate`: All features enabled
- `balanced`: Speed + accuracy

## API Endpoints

### Session

```bash
POST /session
{
  "first_name": "John",
  "last_name": "Doe",
  "preferences": "Concise technical answers",
  "traits": "Software engineer"
}
```

### Chat

```bash
POST /chat
{
  "session_id": "session_123",
  "message": "Explain GraphRAG",
  "use_memory": true,
  "use_retrieval": true,
  "model_name": "meta-llama/llama-3.2-3b-instruct:free",
  "temperature": 0.7,
  "max_tokens": 1024
}
```

### Models

```bash
GET /models/search?query=llama&free_only=true&limit=10
GET /models/all
```

### GraphRAG

```bash
POST /graphrag/ingest
{
  "text": "Document content...",
  "metadata": {"source": "manual"},
  "user_id": "user123"
}

POST /graphrag/search
{
  "query": "Search query",
  "top_k": 5,
  "filters": {"source": "manual"}
}

GET /graphrag/config
POST /graphrag/config
GET /graphrag/stats
```

### Memory & Graph

```bash
GET /memory/{session_id}
GET /graph/{user_id}?limit=100
```

## Dependencies

**Core**

- `fastapi>=0.115.0` - Web framework
- `uvicorn[standard]>=0.32.0` - ASGI server
- `httpx>=0.27.0` - HTTP client
- `python-dotenv>=1.0.0` - Environment variables

**AI & ML**

- `zep-cloud>=2.0.0` - Knowledge graph
- `sentence-transformers>=2.2.0` - Embeddings
- `torch>=2.0.0` - Deep learning
- `rank-bm25>=0.2.2` - BM25 search
- `numpy>=1.24.0` - Numerical computing
- `scikit-learn>=1.3.0` - ML utilities
- `nltk>=3.8.0` - NLP

**LangChain**

- `langchain-core>=0.3.0`
- `langgraph>=0.2.0`

## Architecture

```
backend/
├── server.py                 # FastAPI app
├── openrouter_service.py     # OpenRouter client
├── zep_service.py            # Zep knowledge graph
├── graphrag_core.py          # GraphRAG implementation
├── graphrag_service.py       # GraphRAG service layer
├── graphrag_config.py        # Configuration
├── graph_config.py           # Graph schema
├── routes/
│   ├── chat.py               # Chat endpoint
│   ├── session.py            # Session management
│   ├── models.py             # Model search
│   ├── graphrag.py           # GraphRAG endpoints
│   ├── graph.py              # Graph queries
│   └── memory.py             # Memory queries
└── tools/
    ├── base.py               # Tool interface
    └── weather.py            # Weather tool

frontend/
└── index.html                # Web UI

assets/
└── hyprshot.png              # Screenshot
```

## GraphRAG Configuration

```python
from graphrag_config import GraphRAGConfig

config = GraphRAGConfig(
    # Embedding
    embedding_model="all-MiniLM-L6-v2",
    embedding_device="cuda",  # cuda | cpu | mps

    # Search
    search_algorithm="hybrid",  # vector_similarity | bm25 | hybrid
    enable_bm25=True,
    enable_vector_search=True,
    hybrid_alpha=0.5,  # 0=BM25, 1=vector

    # Chunking
    chunking_strategy="semantic",  # fixed_size | semantic | sentence | paragraph
    chunk_size=512,
    chunk_overlap=50,

    # Retrieval
    top_k=5,
    similarity_threshold=0.7,
    enable_reranking=True,
)
```

## Free Models (OpenRouter)

| Model            | ID                                          | Context |
| ---------------- | ------------------------------------------- | ------- |
| Llama 3.2 3B     | `meta-llama/llama-3.2-3b-instruct:free`     | 131K    |
| Llama 3.1 8B     | `meta-llama/llama-3.1-8b-instruct:free`     | 131K    |
| Gemini Flash 1.5 | `google/gemini-flash-1.5`                   | 1M      |
| Mistral 7B       | `mistralai/mistral-7b-instruct:free`        | 32K     |
| Phi-3 Medium     | `microsoft/phi-3-medium-128k-instruct:free` | 128K    |

## Development

**Run server**

```bash
uv run python backend/server.py
# or
python backend/server.py
```

**Test GraphRAG**

```bash
uv run python test_graphrag.py
```

**Custom entities** - Edit `backend/graph_config.py`:

```python
CUSTOM_ENTITIES = [
    {"name": "person", "description": "Person entity"},
    {"name": "project", "description": "Project entity"},
]
```

## Resources

- [UV Documentation](https://docs.astral.sh/uv/)
- [OpenRouter API](https://openrouter.ai/docs)
- [Zep Documentation](https://help.getzep.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
