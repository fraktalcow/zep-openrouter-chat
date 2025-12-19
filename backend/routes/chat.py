import asyncio
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
from textwrap import dedent

from openrouter_service import OpenRouterService
from zep_service import ZepService
from pinecone_service import get_pinecone_service

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

    # RAG Context
    {rag_section}

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
    use_rag: bool = False
    use_ai: bool = True
    model_name: str = "meta-llama/llama-3.2-3b-instruct:free"
    context_message_limit: int = Field(default=6, ge=2, le=20)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=100000)


# Injected by server.py
zep_service: ZepService = None
openrouter_service: OpenRouterService = None


def init_services(zep: ZepService, openrouter: OpenRouterService):
    """Initialize with services."""
    global zep_service, openrouter_service
    zep_service = zep
    openrouter_service = openrouter


async def _stream_chat_response(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Internal generator for streaming chat responses.
    Yields SSE-formatted data chunks.
    """
    context_sections = {"memory_section": "", "graph_section": "", "rag_section": ""}
    rag_chunks = []
    session_meta = None
    
    # Only get session if Zep services are enabled
    if request.use_memory or request.use_retrieval:
        try:
            session_meta = await asyncio.wait_for(zep_service.get_session(request.session_id), timeout=5.0)
            if not session_meta:
                print(f"[Chat] Session {request.session_id} not found in Zep. Proceeding without memory.")
        except Exception as e:
            print(f"[Chat] Session retrieval failed: {e}. Proceeding without memory.")
            session_meta = None
            
        if session_meta:
            yield f"data: {json.dumps({'type': 'step', 'id': 'retrieval', 'message': 'Retrieving context & memory...'})}\n\n"

    # --- Parallel Retrieval ---
    loop = asyncio.get_running_loop()
    tasks = {}

    # 1. Zep Context Task (only if session exists)
    if session_meta:
        tasks['zep'] = zep_service.build_context_block(
            session_id=request.session_id,
            user_id=session_meta.get("user_id"),
            query=request.message,
            include_memory=request.use_memory,
            include_graph=request.use_retrieval,
            max_messages=request.context_message_limit,
        )
    
    # 2. RAG Task (Run sync Pinecone in executor)
    if request.use_rag:
        pinecone = get_pinecone_service()
        tasks['rag'] = loop.run_in_executor(
            None, 
            lambda: pinecone.search(query=request.message, top_k=3, rerank=True)
        )
    
    # Await all tasks
    print(f"[Chat] Starting retrieval tasks: {list(tasks.keys())}")
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks.values(), return_exceptions=True),
            timeout=10.0
        )
        print("[Chat] Retrieval tasks complete")
    except asyncio.TimeoutError:
        print("[Chat] Retrieval timed out")
        results = [TimeoutError("Retrieval timed out")] * len(tasks)
    
    results_map = dict(zip(tasks.keys(), results))

    # Process Zep Results
    if 'zep' in results_map:
        res = results_map['zep']
        if isinstance(res, Exception):
            print(f"Zep Error: {res}")
            context_sections["memory_section"] = "Error retrieving memory."
        else:
            context_sections["memory_section"] = res.get("memory_section", "")
            context_sections["graph_section"] = res.get("graph_section", "")
            
    # Process RAG Results
    if 'rag' in results_map:
        res = results_map['rag']
        if isinstance(res, Exception):
             print(f"RAG Error: {res}")
             yield f"data: {json.dumps({'type': 'error', 'error': f'RAG Error: {str(res)}'})}\n\n"
        elif res:
            rag_texts = []
            for r in res:
                score = r.get("score", 0)
                if score > 0.4:  # Threshold
                    rag_texts.append(f"- {r['text']}")
                    rag_chunks.append({
                        "text": r["text"],
                        "score": score,
                        "metadata": r.get("metadata")
                    })
            if rag_texts:
                context_sections["rag_section"] = "\n".join(rag_texts)
                yield f"data: {json.dumps({'type': 'rag_sources', 'chunks': rag_chunks})}\n\n"
            else:
                 yield f"data: {json.dumps({'type': 'step', 'id': 'rag_empty', 'message': 'No relevant RAG chunks.'})}\n\n"


    # Build prompt - simple if no session, full context if session exists
    if session_meta:
        prompt = DEFAULT_CONTEXT_TEMPLATE.format(
            session_id=request.session_id,
            user_name=f"{session_meta['first_name']} {session_meta['last_name']}",
            preferences=session_meta.get("preferences") or "Not provided",
            traits=session_meta.get("traits") or "Not provided",
            business_data=session_meta.get("business_data") or "Not provided",
            memory_section=context_sections["memory_section"],
            graph_section=context_sections["graph_section"],
            rag_section=context_sections["rag_section"],
            query=request.message,
        )
    else:
        # Simple prompt without session context
        prompt = request.message
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[Chat] Prompt ready, length={len(prompt)}, use_ai={request.use_ai}, model={request.model_name}")
    
    # Send context debug info
    yield f"data: {json.dumps({'type': 'context', 'context_block': {'sections': context_sections}})}\n\n"

    # 3. LLM Generation -> Answer
    if request.use_ai:
        yield f"data: {json.dumps({'type': 'step', 'id': 'llm', 'message': 'Generating answer...'})}\n\n"
        logger.info(f"[Chat] Starting LLM stream with model: {request.model_name}")
        
        full_response = ""
        try:
            async for chunk in openrouter_service.generate_response_stream(
                prompt,
                model_name=request.model_name,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            ):
                print(f"[Chat] Yielding chunk: {len(chunk)} chars")
                full_response += chunk
                yield f"data: {json.dumps({'type': 'content', 'chunk': chunk})}\n\n"
            
            logger.info(f"[Chat] LLM complete, response_len={len(full_response)}")
            
            # Save response to memory (only if session exists)
            if session_meta and (request.use_memory or request.use_retrieval):
                 background_tasks.add_task(zep_service.add_memory, request.session_id, "assistant", full_response)
            
            yield f"data: {json.dumps({'type': 'done', 'response': full_response})}\n\n"
            
        except Exception as e:
            logger.error(f"[Chat] LLM error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    else:
        response_text = "AI API is disabled. Context block generated."
        yield f"data: {json.dumps({'type': 'content', 'chunk': response_text})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'response': response_text})}\n\n"


@router.post("")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """Chat endpoint with streaming SSE response."""
    
    # Add user message to memory in background
    if request.use_memory or request.use_retrieval:
        background_tasks.add_task(zep_service.add_memory, request.session_id, "user", request.message)

    return StreamingResponse(
        _stream_chat_response(request, background_tasks),
        media_type="text/event-stream",
        background=background_tasks,
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

