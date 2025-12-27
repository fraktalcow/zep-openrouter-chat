# zep-openrouter-agent

Lightweight AI chat with **Zep Knowledge Graph** and **OpenRouter AI** for context-aware conversations.

![zep-openrouter-agent Screenshot](assets/hyprshot.png)

## Features

**Zep Memory** - Persistent graph-based memory via Zep Cloud

- User preferences, traits, conversation history
- Semantic search and retrieval

**AI Models** - 100+ models via OpenRouter

- Free models: Llama, Gemini, Mistral, Phi-3, Qwen
- Configurable temperature, max_tokens

## Stack

- **Backend**: FastAPI, Python 3.10+
- **Memory**: Zep Cloud
- **AI**: OpenRouter API

## Installation

```bash
# Clone
git clone <repo-url>
cd zep-openrouter-agent

# Install dependencies
uv sync

# Configure
cp backend/.env.example backend/.env
# Edit backend/.env with API keys

# Run
uv run run.py
```

## Configuration

**backend/.env**

```bash
OPENROUTER_API_KEY=  # https://openrouter.ai/keys
ZEP_API_KEY=         # https://www.getzep.com/
```

## API Endpoints

| Endpoint          | Description               |
| ----------------- | ------------------------- |
| `POST /chat`      | Chat with AI (SSE stream) |
| `POST /session`   | Create session            |
| `GET /models/all` | List AI models            |

## Resources

- [OpenRouter API](https://openrouter.ai/docs)
- [Zep Documentation](https://help.getzep.com/)
