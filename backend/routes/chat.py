from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from graph_config import DEFAULT_CONTEXT_TEMPLATE
from openrouter_service import OpenRouterService
from zep_service import ZepService

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    message: str
    use_memory: bool = True
    use_retrieval: bool = True
    use_ai: bool = True
    model_name: str = "meta-llama/llama-3.2-3b-instruct:free"
    context_message_limit: int = Field(default=6, ge=2, le=20)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=100000)


# Injected by server.py
zep_service: ZepService = None
openrouter_service: OpenRouterService = None
SESSIONS: dict = None


def init_services(zep: ZepService, openrouter: OpenRouterService, sessions: dict):
    global zep_service, openrouter_service, SESSIONS
    zep_service = zep
    openrouter_service = openrouter
    SESSIONS = sessions


@router.post("")
async def chat(request: ChatRequest):
    # Zep-based flow
    session_meta = SESSIONS.get(request.session_id)
    if not session_meta:
        raise HTTPException(status_code=404, detail="Unknown session. Create one first.")

    if request.use_memory or request.use_retrieval:
        await zep_service.add_memory(request.session_id, "user", request.message)

    context_sections = {"memory_section": "", "graph_section": ""}
    prompt = request.message

    if request.use_memory or request.use_retrieval:
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

    if request.use_ai:
        response_text = await openrouter_service.generate_response(
            prompt,
            model_name=request.model_name,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
    else:
        response_text = "AI API is disabled. Context block generated."

    if request.use_memory or request.use_retrieval:
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




