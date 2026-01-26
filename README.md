# Zep OpenRouter Chat

Chat application with **Zep memory**, **OpenRouter LLM**, and **PostgreSQL persistence**.

## Quick Start

```bash
# 1. Start database
docker compose up -d

# 2. Set up environment
cp backend/.env.example backend/.env
# Edit backend/.env with your API keys

# 3. Run
uv run run.py
```

Open http://localhost:8000

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Vanilla JS)                 │
│  - Chat interface                                            │
│  - Knowledge graph visualization (vis.js)                    │
│  - Session management                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│                                                              │
│  Routes:                     Services:                       │
│  ├─ /chat       ────────────► OpenRouter (LLM)              │
│  ├─ /session    ────────────► Zep Cloud (Memory/Graph)      │
│  ├─ /graph      ────────────► PostgreSQL (Persistence)      │
│  └─ /stats                                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      PostgreSQL                              │
│                                                              │
│  Tables (auto-created by SQLAlchemy):                        │
│  ├─ users           - User identity                          │
│  ├─ sessions        - Chat sessions                          │
│  ├─ messages        - Message history with LLM params        │
│  ├─ llm_interactions - Token/cost tracking                   │
│  └─ graph_cache     - Zep graph node cache                   │
└─────────────────────────────────────────────────────────────┘
```

## Database Commands

```bash
docker compose up -d      # Start PostgreSQL (detached)
docker compose down       # Stop and remove containers
docker compose logs -f    # Stream logs

```

## Data Flow

**On Chat Message:**

1. User message → Backend → Zep (add to memory)
2. Parallel retrieval: Zep context
3. Build prompt with context → OpenRouter LLM → Stream response
4. Background: Persist message + log LLM interaction to PostgreSQL
5. Background: Add assistant response to Zep

**What's Stored:**
| Store | Data | Purpose |
|-------|------|---------|
| PostgreSQL | Messages, sessions, LLM metrics | Fast local queries, analytics |
| Zep Cloud | Memory, facts, knowledge graph | AI context, entity extraction |

## Project Structure

```
├── docker-compose.yml    # PostgreSQL container
├── run.py                # Application entry point
├── backend/
│   ├── server.py         # FastAPI app + lifespan
│   ├── config.py         # Settings with validation
│   ├── routes/           # API endpoints
│   │   ├── chat.py       # Streaming chat with persistence
│   │   ├── session.py    # CRUD + history
│   │   ├── graph.py      # Knowledge graph
│   │   └── stats.py      # Analytics
│   ├── db/
│   │   ├── models.py     # SQLAlchemy ORM models
│   │   ├── connection.py # Async engine + sessions
│   │   └── repositories/ # Data access layer
│   └── *_service.py      # External API integrations
└── frontend/
    ├── index.html
    ├── style.css
    └── js/               # Modular ES6
```

## Requirements

- Python 3.10+
- Docker
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## License

MIT
# Updated git config
