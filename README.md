# Zep + OpenRouter Chat

AI chat with **Zep Knowledge Graph**, **OpenRouter AI**, **Pinecone RAG**, and **PostgreSQL** storage.

![Screenshot](assets/hyprshot.png)

## Features

- **Zep Memory** - Graph-based conversation memory with context extraction
- **AI Models** - 100+ models via OpenRouter (Llama, Gemini, Mistral, etc.)
- **RAG** - Document retrieval with Pinecone vector search
- **PostgreSQL** - Persistent session/message storage with LLM usage tracking

## Stack

- **Backend**: FastAPI, Python 3.10+, SQLAlchemy async
- **Memory**: Zep Cloud
- **AI**: OpenRouter API
- **Vectors**: Pinecone
- **Database**: PostgreSQL

## Setup

```bash
# Clone
git clone <repo-url>
cd zep-openrouter-chat

# Install
uv sync

# Configure
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

# Start PostgreSQL (optional but recommended)
docker-compose up -d

# Run
uv run python run.py
```

## Configuration

**backend/.env**

```bash
OPENROUTER_API_KEY=  # https://openrouter.ai/keys
ZEP_API_KEY=         # https://www.getzep.com/
PINECONE_API_KEY=    # https://www.pinecone.io/

# PostgreSQL (local Docker or cloud)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/zep_chat
```

## API Endpoints

| Endpoint                      | Method | Description                 |
| ----------------------------- | ------ | --------------------------- |
| `/chat`                       | POST   | Chat with AI (SSE stream)   |
| `/session`                    | POST   | Create session              |
| `/session/list`               | GET    | List sessions               |
| `/session/sync`               | POST   | Sync all Zep sessions to DB |
| `/session/{id}`               | GET    | Get session with messages   |
| `/session/{id}`               | DELETE | Delete session              |
| `/session/{id}/stats`         | GET    | LLM usage stats             |
| `/session/{id}/sync-messages` | POST   | Sync messages from Zep      |
| `/session/{id}/sync-graph`    | POST   | Sync graph for user         |
| `/graph/{user_id}`            | GET    | Get knowledge graph         |
| `/memory/{session_id}`        | GET    | Get memory context          |
| `/rag/upload`                 | POST   | Upload document for RAG     |
| `/rag/search`                 | POST   | Search documents            |
| `/models/all`                 | GET    | List AI models              |

## Data Flow

```
Startup:
  → DB tables created
  → Zep sessions synced to PostgreSQL

User Flow:
  POST /session → Creates in PostgreSQL + Zep
  POST /chat    → User query saved to DB
               → Zep context retrieved
               → LLM generates response
               → Response + metrics saved to DB
               → Zep builds knowledge graph
  GET /graph    → Returns cached graph (or fetches from Zep)
```

**Auto-Sync:**

- On startup: All Zep sessions → PostgreSQL
- On access: If messages missing → syncs from Zep
- On access: If session only in Zep → syncs to PostgreSQL

## Resources

- [OpenRouter API](https://openrouter.ai/docs)
- [Zep Documentation](https://help.getzep.com/)
- [Pinecone Docs](https://docs.pinecone.io/)
