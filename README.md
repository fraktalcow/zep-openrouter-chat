# zep-openrouter-agent

AI chat system combining **Zep's Knowledge Graph**, **Local GraphRAG**, and **OpenRouter's multi-model AI** for context-aware conversations with document retrieval.

![zep-openrouter-agent Screenshot](assets/hyprshot.png)

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
cd zep-openrouter-agent

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
- `langchain-core>=0.3.0`
- `langgraph>=0.2.0`

## Development

**Run server**

```bash
uv run python backend/server.py
# or
python backend/server.py
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
