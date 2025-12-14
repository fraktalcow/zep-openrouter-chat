from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
from textwrap import dedent

from openrouter_service import OpenRouterService
from zep_service import ZepService
from routes.rag import get_embedding_model

router = APIRouter()


DEFAULT_CONTEXT_TEMPLATE = dedent(
    """
    You are an expert agent who reasons over temporal knowledge graphs.
    Stay concise, personal, and cite the user's preferences when helpful.

    # Session
    - Session ID: {session_id}
    - User: {user_name}

    # User Signals
    • Preferences: {preferences}
    • Traits: {traits}
    • Business Data: {business_data}

    # Conversation Memory
    {memory_section}

    # Knowledge Graph Retrieval
    {graph_section}

    # Latest Query
    {query}

    Compose a thoughtful assistant reply grounded in the context above.
    """
).strip()


class ChatRequest(BaseModel):
    session_id: str
    message: str
    use_memory: bool = True
    use_retrieval: bool = True
    use_rag: bool = False  # Use OpenRouter embeddings RAG
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

    context_sections = {"memory_section": "", "graph_section": "", "rag_section": ""}
    prompt = request.message

    # Build Zep context block
    if request.use_memory or request.use_retrieval:
        zep_context = await zep_service.build_context_block(
            session_id=request.session_id,
            user_id=session_meta.get("user_id"),
            query=request.message,
            include_memory=request.use_memory,
            include_graph=request.use_retrieval,
            max_messages=request.context_message_limit,
        )
        context_sections["memory_section"] = zep_context.get("memory_section", "")
        context_sections["graph_section"] = zep_context.get("graph_section", "")

    # Add RAG context if enabled
    if request.use_rag and openrouter_service.get_document_count() > 0:
        try:
            rag_results = await openrouter_service.search(
                query=request.message,
                top_k=3,
                embedding_model=get_embedding_model(),
            )
            if rag_results:
                rag_texts = []
                for r in rag_results:
                    score = r.get("score", 0)
                    if score > 0.5:  # Only include relevant results
                        rag_texts.append(f"- {r['text'][:500]}...")
                if rag_texts:
                    context_sections["rag_section"] = "\n".join(rag_texts)
        except Exception as e:
            print(f"RAG search error: {e}")

    # Build full prompt with context
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
    
    # Append RAG section if present
    if context_sections["rag_section"]:
        prompt += f"\n\n# RAG Retrieved Documents\n{context_sections['rag_section']}"

    # Send context block info first
    yield f"data: {json.dumps({'type': 'context', 'context_block': {'sections': context_sections, 'use_memory': request.use_memory, 'use_retrieval': request.use_retrieval, 'use_rag': request.use_rag}})}\n\n"

    # Generate AI response if enabled
    if request.use_ai:
        try:
            full_response = await openrouter_service.generate_response(
                prompt,
                model_name=request.model_name,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )

            yield f"data: {json.dumps({'type': 'content', 'chunk': full_response})}\n\n"
            
            # Save response to memory
            if request.use_memory or request.use_retrieval:
                await zep_service.add_memory(request.session_id, "assistant", full_response)
            
            yield f"data: {json.dumps({'type': 'done', 'response': full_response})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    else:
        response_text = "AI API is disabled. Context block generated."
        yield f"data: {json.dumps({'type': 'content', 'chunk': response_text})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'response': response_text})}\n\n"


@router.post("")
async def chat(request: ChatRequest):
    """Chat endpoint with streaming SSE response."""
    return StreamingResponse(
        _stream_chat_response(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
