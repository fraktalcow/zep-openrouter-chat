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
- **Database**: PostgreSQL 16

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

# Start PostgreSQL
docker-compose up -d

# Wait for database to be ready (health check included)
docker-compose ps

# Run
uv run python run.py
```

## Configuration

**backend/.env**

```bash
# =============================================================================
# API Keys (Required)
# =============================================================================
OPENROUTER_API_KEY=sk-or-vX-your-key-here  # https://openrouter.ai/keys
ZEP_API_KEY=z_your-zep-key-here            # https://www.getzep.com/
PINECONE_API_KEY=your-pinecone-key-here    # https://www.pinecone.io/

# =============================================================================
# Database Configuration
# =============================================================================
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/zep_chat

# Individual components (used by docker-compose)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=zep_chat
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Database pool settings (optional)
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
DATABASE_ECHO=false  # Set to true for SQL query logging
```

## Database Schema

The application uses PostgreSQL for persistent storage. Tables are created automatically on startup.

### Tables

| Table              | Description                             |
| ------------------ | --------------------------------------- |
| `users`            | User profiles (mirrors Zep users)       |
| `sessions`         | Chat sessions with metadata             |
| `messages`         | Chat messages with ordering             |
| `graph_cache`      | Cached Zep knowledge graph nodes        |
| `llm_interactions` | LLM usage logs (tokens, cost, duration) |
| `rag_documents`    | Uploaded RAG document tracking          |

### Views

| View                | Description                  |
| ------------------- | ---------------------------- |
| `session_summaries` | Sessions with message counts |
| `user_statistics`   | User-level aggregated stats  |

### Key Features

- **Timezone-aware timestamps** - All timestamps use UTC
- **Automatic updated_at triggers** - Tracks modifications
- **Cascade deletes** - Deleting a user removes all related data
- **Optimized indexes** - Fast queries on common patterns
- **JSONB fields** - Flexible metadata storage

## API Endpoints

### Chat & Sessions

| Endpoint                  | Method | Description               |
| ------------------------- | ------ | ------------------------- |
| `/chat`                   | POST   | Chat with AI (SSE stream) |
| `/session`                | POST   | Create session            |
| `/session/list`           | GET    | List sessions             |
| `/session/{id}`           | GET    | Get session with messages |
| `/session/{id}`           | DELETE | Delete session            |
| `/session/{id}/title`     | PATCH  | Update session title      |
| `/session/{id}/archive`   | POST   | Archive session           |
| `/session/{id}/unarchive` | POST   | Unarchive session         |
| `/session/{id}/stats`     | GET    | LLM usage stats           |

### Sync & Data

| Endpoint                      | Method | Description                 |
| ----------------------------- | ------ | --------------------------- |
| `/session/sync`               | POST   | Sync all Zep sessions to DB |
| `/session/{id}/sync-messages` | POST   | Sync messages from Zep      |
| `/session/{id}/sync-graph`    | POST   | Sync graph for user         |

### Memory & Graph

| Endpoint               | Method | Description         |
| ---------------------- | ------ | ------------------- |
| `/graph/{user_id}`     | GET    | Get knowledge graph |
| `/memory/{session_id}` | GET    | Get memory context  |

### RAG

| Endpoint      | Method | Description             |
| ------------- | ------ | ----------------------- |
| `/rag/upload` | POST   | Upload document for RAG |
| `/rag/search` | POST   | Search documents        |

### Analytics

| Endpoint                | Method | Description            |
| ----------------------- | ------ | ---------------------- |
| `/stats/system`         | GET    | System-wide statistics |
| `/stats/user/{user_id}` | GET    | User statistics        |
| `/stats/models`         | GET    | Model usage breakdown  |
| `/stats/daily`          | GET    | Daily usage stats      |

### System

| Endpoint      | Method | Description                 |
| ------------- | ------ | --------------------------- |
| `/health`     | GET    | Health check with DB status |
| `/models/all` | GET    | List AI models              |

## Data Flow

```
Startup:
  → PostgreSQL connection with health check
  → DB tables created/verified (SQLAlchemy)
  → Zep sessions synced to PostgreSQL

User Flow:
  POST /session → Creates in PostgreSQL + Zep
  POST /chat    → User query saved to DB
               → Zep context retrieved
               → LLM generates response (streamed)
               → Response + metrics saved to DB
               → Zep builds knowledge graph
  GET /graph    → Returns cached graph (or fetches from Zep)
```

**Auto-Sync:**

- On startup: All Zep sessions → PostgreSQL
- On access: If messages missing → syncs from Zep
- On access: If session only in Zep → syncs to PostgreSQL

## Development

```bash
# Reset database (warning: deletes all data)
docker-compose down -v
docker-compose up -d

# View database directly
docker exec zep-chat-postgres psql -U postgres -d zep_chat

# Check tables
docker exec zep-chat-postgres psql -U postgres -d zep_chat -c "\dt"

# View session summaries
docker exec zep-chat-postgres psql -U postgres -d zep_chat -c "SELECT * FROM session_summaries LIMIT 10;"
```

## Resources

- [OpenRouter API](https://openrouter.ai/docs)
- [Zep Documentation](https://help.getzep.com/)
- [Pinecone Docs](https://docs.pinecone.io/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
