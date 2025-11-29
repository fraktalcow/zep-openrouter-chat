import os
import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from gemini_service import GeminiService
from graph_config import CUSTOM_ENTITIES, CUSTOM_EDGES, DEFAULT_CONTEXT_TEMPLATE
from zep_service import ZepService

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = (BASE_DIR / "../frontend").resolve()
ASSETS_DIR = (BASE_DIR / "../assets").resolve()

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/")
async def read_index():
    return FileResponse(FRONTEND_DIR / "index.html")


ZEP_API_KEY = os.getenv("ZEP_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not ZEP_API_KEY or not GEMINI_API_KEY:
    raise RuntimeError("ZEP_API_KEY and GEMINI_API_KEY must be set in backend/.env")

zep_service = ZepService(ZEP_API_KEY)
gemini_service = GeminiService(GEMINI_API_KEY)

SessionMeta = Dict[str, Any]
SESSIONS: Dict[str, SessionMeta] = {}


class SessionRequest(BaseModel):
    user_id: Optional[str] = None
    first_name: str = "User"
    last_name: str = "Guest"
    preferences: Optional[str] = Field(
        default="Enjoys structured, actionable answers.",
        description="High level user preferences.",
    )
    traits: Optional[str] = Field(
        default="Curious, detail oriented.",
        description="Optional personality traits.",
    )
    business_data: Optional[str] = Field(
        default="Building a Zep + Gemini agentic chat experience.",
        description="Business or domain specific signals.",
    )


class ChatRequest(BaseModel):
    session_id: str
    message: str
    use_memory: bool = True
    use_retrieval: bool = True
    use_gemini: bool = True
    model_name: str = "gemini-1.5-flash"
    context_message_limit: int = Field(default=6, ge=2, le=20)


class SchemaRequest(BaseModel):
    entities: list[Dict[str, str]]
    edges: list[Dict[str, str]]


def load_schema():
    schema_path = BASE_DIR / "schema.json"
    if schema_path.exists():
        with open(schema_path, "r") as f:
            return json.load(f)
    return {"entities": CUSTOM_ENTITIES, "edges": CUSTOM_EDGES}


@app.on_event("startup")
async def startup_event():
    schema = load_schema()
    await zep_service.ensure_ontology(schema["entities"], schema["edges"])


@app.get("/schema")
async def get_schema():
    return load_schema()


@app.post("/schema")
async def update_schema(request: SchemaRequest):
    schema_path = BASE_DIR / "schema.json"
    schema = {"entities": request.entities, "edges": request.edges}
    with open(schema_path, "w") as f:
        json.dump(schema, f, indent=2)
    
    await zep_service.ensure_ontology(request.entities, request.edges)
    return {"status": "success", "message": "Schema updated and ontology ensured."}


@app.post("/session")
async def create_session(request: SessionRequest):
    user_id = request.user_id or f"user_{uuid.uuid4().hex[:8]}"
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    metadata = {
        "preferences": request.preferences,
        "traits": request.traits,
        "business_data": request.business_data,
    }

    await zep_service.create_session(
        user_id,
        session_id,
        first_name=request.first_name,
        last_name=request.last_name,
        metadata=metadata,
    )

    SESSIONS[session_id] = {
        "user_id": user_id,
        "first_name": request.first_name,
        "last_name": request.last_name,
        **metadata,
    }

    return {
        "session_id": session_id,
        "user_id": user_id,
        "preferences": request.preferences,
        "traits": request.traits,
        "business_data": request.business_data,
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    session_meta = SESSIONS.get(request.session_id)
    if not session_meta:
        raise HTTPException(status_code=404, detail="Unknown session. Create one first.")

    await zep_service.add_memory(request.session_id, "user", request.message)

    context_sections = await zep_service.build_context_block(
        session_id=request.session_id,
        user_id=session_meta.get("user_id"),
        query=request.message,
        include_memory=request.use_memory,
        include_graph=request.use_retrieval,
        max_messages=request.context_message_limit,
    )

    prompt = DEFAULT_CONTEXT_TEMPLATE.format(
        session_id=request.session_id,
        user_name=f"{session_meta['first_name']} {session_meta['last_name']}",
        preferences=session_meta.get("preferences") or "Not provided",
        traits=session_meta.get("traits") or "Not provided",
        business_data=session_meta.get("business_data") or "Not provided",
        memory_section=context_sections["memory_section"],
        graph_section=context_sections["graph_section"],
        query=request.message,
    )

    if request.use_gemini:
        response_text = await gemini_service.generate_response(prompt, model_name=request.model_name)
    else:
        response_text = "Gemini API is disabled. Context block generated."

    await zep_service.add_memory(request.session_id, "assistant", response_text)

    return {
        "response": response_text,
        "context_block": {
            "rendered": prompt,
            "sections": context_sections,
            "template": DEFAULT_CONTEXT_TEMPLATE,
            "use_memory": request.use_memory,
            "use_retrieval": request.use_retrieval,
        },
    }


@app.get("/graph/{user_id}")
async def get_graph_data(user_id: str, limit: int = 100):
    """
    Retrieve knowledge graph data for visualization.
    Returns nodes and edges for the user's knowledge graph.
    """
    try:
        graph_data = await zep_service.get_graph_data(user_id, limit)
        return graph_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching graph: {str(e)}")


@app.get("/memory/{session_id}")
async def get_memory_context(session_id: str):
    """Get the memory context for a session."""
    try:
        memory = await zep_service.get_memory(session_id)
        return {
            "session_id": session_id,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in (memory.messages or [])
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching memory: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
