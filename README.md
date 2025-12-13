# zep-openrouter-agent

Lightweight AI chat with **Zep Knowledge Graph** and **OpenRouter AI** for context-aware conversations.

![zep-openrouter-agent Screenshot](assets/hyprshot.png)

## Features

**Zep Memory** - Persistent graph-based memory via Zep Cloud

- User preferences, traits, conversation history
- Semantic search and retrieval

**RAG (OpenRouter)** - Document ingestion using OpenRouter embeddings

- Multiple embedding models available (text-embedding-3-small, etc.)
- In-memory vector store with cosine similarity search
- Toggleable in UI

**AI Models** - 100+ models via OpenRouter

- Free models: Llama, Gemini, Mistral, Phi-3, Qwen
- Configurable temperature, max_tokens

## Stack

- **Backend**: FastAPI, Python 3.10+
- **Memory**: Zep Cloud
- **Embeddings**: OpenRouter API
- **AI**: OpenRouter API

## Installation

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone & install
git clone <repo-url>
cd zep-openrouter-agent
uv sync

# Configure
cp backend/.env.example backend/.env
# Edit backend/.env with API keys

# Run
uv run python backend/server.py
```

## Configuration

**backend/.env**

```bash
OPENROUTER_API_KEY=  # https://openrouter.ai/keys
ZEP_API_KEY=         # https://www.getzep.com/
```

## API Endpoints

| Endpoint           | Description               |
| ------------------ | ------------------------- |
| `POST /chat`       | Chat with AI (SSE stream) |
| `POST /session`    | Create session            |
| `GET /models/all`  | List AI models            |
| `GET /rag/models`  | List embedding models     |
| `POST /rag/models` | Set embedding model       |
| `POST /rag/ingest` | Ingest document           |
| `POST /rag/search` | Search RAG store          |
| `GET /rag/stats`   | RAG statistics            |

## Resources

- [OpenRouter API](https://openrouter.ai/docs)
- [OpenRouter Embeddings](https://openrouter.ai/docs/api/reference/embeddings)
- [Zep Documentation](https://help.getzep.com/)
