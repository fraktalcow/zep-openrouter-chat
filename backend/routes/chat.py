from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json

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


async def _stream_chat_response(request: ChatRequest):
    """
    Internal generator for streaming chat responses.
    Yields SSE-formatted data chunks.
    """
    session_meta = SESSIONS.get(request.session_id)
    if not session_meta:
        yield f"data: {json.dumps({'error': 'Unknown session. Create one first.'})}\n\n"
        return

    # Add user message to memory
    if request.use_memory or request.use_retrieval:
        await zep_service.add_memory(request.session_id, "user", request.message)

    context_sections = {"memory_section": "", "graph_section": ""}
    prompt = request.message

    # Build context block
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

    # Send context block info first
    yield f"data: {json.dumps({'type': 'context', 'context_block': {'rendered': prompt, 'sections': context_sections, 'template': DEFAULT_CONTEXT_TEMPLATE, 'use_memory': request.use_memory, 'use_retrieval': request.use_retrieval}})}\n\n"

    # Stream AI response if enabled
    if request.use_ai:
        full_response = ""
        try:
            # Non-streaming call (to avoid OpenRouter streaming 429s)
            full_response = await openrouter_service.generate_response(
                prompt,
                model_name=request.model_name,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )

            # Send content chunk as SSE (one big chunk)
            yield f"data: {json.dumps({'type': 'content', 'chunk': full_response})}\n\n"
            
            # Save full response to memory
            if request.use_memory or request.use_retrieval:
                await zep_service.add_memory(request.session_id, "assistant", full_response)
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'done', 'response': full_response})}\n\n"
        except Exception as e:
            error_msg = str(e)
            yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"
    else:
        response_text = "AI API is disabled. Context block generated."
        yield f"data: {json.dumps({'type': 'content', 'chunk': response_text})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'response': response_text})}\n\n"


@router.post("")
async def chat(request: ChatRequest):
    """
    Chat endpoint with streaming support.
    Returns Server-Sent Events (SSE) stream for real-time response.
    """
    return StreamingResponse(
        _stream_chat_response(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )




