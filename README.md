# zep-openrouter-agent

Lightweight AI chat with **Zep Knowledge Graph** and **OpenRouter's multi-model AI** for context-aware conversations.

![zep-openrouter-agent Screenshot](assets/hyprshot.png)

## Technical Stack

- **Backend**: FastAPI, Python 3.10+
- **Memory/RAG**: Zep Cloud (handles embeddings + graph-based memory)
- **AI Models**: OpenRouter API (100+ models)

## Features

**Knowledge Graph**

- Persistent graph-based memory via Zep
- User preferences, traits, conversation history
- Semantic search and retrieval (handled by Zep's cloud embeddings)

**AI Integration**

- 100+ models via OpenRouter
- Free models: Llama, Gemini, Mistral, Phi-3, Qwen
- Configurable temperature, max_tokens

## Installation

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
ZEP_API_KEY=         # Get from https://www.getzep.com/
```

## Resources

- [UV Documentation](https://docs.astral.sh/uv/)
- [OpenRouter API](https://openrouter.ai/docs)
- [Zep Documentation](https://help.getzep.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
