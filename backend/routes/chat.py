import asyncio
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
from textwrap import dedent

from openrouter_service import get_openrouter_service
from zep_service import get_zep_service
from pinecone_service import get_pinecone_service
from logger import logger

router = APIRouter()


CONTEXT_TEMPLATE = dedent("""
You are a helpful assistant with access to conversation history and knowledge graph facts.

# Conversation Memory
{memory_section}

# Knowledge Graph
{graph_section}

# RAG Context
{rag_section}

# User Query
{query}

Respond naturally and helpfully.
""").strip()


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


async def _stream_chat_response(request: ChatRequest, background_tasks: BackgroundTasks):
    """Stream chat response with context from Zep memory and graph."""
    context_sections = {"memory_section": "", "graph_section": "", "rag_section": ""}
    rag_chunks = []
    session_meta = None
    
    zep_service = get_zep_service()
    openrouter_service = get_openrouter_service()
    
    # Get session if Zep services enabled
    if request.use_memory or request.use_retrieval:
        try:
            session_meta = await asyncio.wait_for(
                zep_service.get_session(request.session_id), timeout=5.0
            )
            if not session_meta:
                logger.warning(f"[Chat] Session {request.session_id} not found")
        except Exception as e:
            logger.warning(f"[Chat] Session retrieval failed: {e}")
            session_meta = None
            
        if session_meta:
            yield f"data: {json.dumps({'type': 'step', 'id': 'retrieval', 'message': 'Retrieving context...'})}\n\n"

    # Parallel retrieval
    tasks = {}
    
    if session_meta:
        # Add user message AND retrieve context in one go
        tasks['zep'] = zep_service.add_memory(
            session_id=request.session_id,
            role="user",
            content=request.message,
            return_context=True
        )
    
    if request.use_rag:
        pinecone = get_pinecone_service()
        loop = asyncio.get_running_loop()
        tasks['rag'] = loop.run_in_executor(
            None, lambda: pinecone.search(query=request.message, top_k=3, rerank=True)
        )
    
    if tasks:
        logger.info(f"[Chat] Retrieval tasks: {list(tasks.keys())}")
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks.values(), return_exceptions=True), timeout=10.0
            )
        except asyncio.TimeoutError:
            logger.warning("[Chat] Retrieval timed out")
            results = [TimeoutError()] * len(tasks)
        
        results_map = dict(zip(tasks.keys(), results))

        # Process Zep Context (Summary + Facts)
        if 'zep' in results_map:
            res = results_map['zep']
            if isinstance(res, Exception):
                logger.error(f"Zep Error: {res}")
            elif res:
                # The 'res' here is the context string returned by add_messages(return_context=True)
                # It contains <USER_SUMMARY> and <FACTS> sections.
                # We can put it directly into memory_section for now, or assume it covers graph too.
                context_sections["memory_section"] = res
                # graph_section is likely included in the Facts part of the response, so we might leave it empty
                # or we can parse it if we really want to split it.

                
        # Process RAG
        if 'rag' in results_map:
            res = results_map['rag']
            if isinstance(res, Exception):
                logger.error(f"RAG Error: {res}")
            elif res:
                rag_texts = []
                for r in res:
                    if r.get("score", 0) > 0.4:
                        rag_texts.append(f"- {r['text']}")
                        rag_chunks.append({"text": r["text"], "score": r["score"]})
                if rag_texts:
                    context_sections["rag_section"] = "\n".join(rag_texts)
                    yield f"data: {json.dumps({'type': 'rag_sources', 'chunks': rag_chunks})}\n\n"

    # Build prompt - only include non-empty sections
    sections = []
    if context_sections["memory_section"]:
        sections.append(f"# Conversation Memory\n{context_sections['memory_section']}")
    if context_sections["graph_section"]:
        sections.append(f"# Knowledge Graph\n{context_sections['graph_section']}")
    if context_sections["rag_section"]:
        sections.append(f"# RAG Context\n{context_sections['rag_section']}")
    
    if sections:
        prompt = "\n\n".join(sections) + f"\n\n# User Query\n{request.message}\n\nRespond naturally."
    else:
        prompt = request.message
    
    logger.info(f"[Chat] Prompt length={len(prompt)}, model={request.model_name}")
    yield f"data: {json.dumps({'type': 'context', 'context_block': {'sections': context_sections}})}\n\n"

    # LLM Generation
    if request.use_ai:
        yield f"data: {json.dumps({'type': 'step', 'id': 'llm', 'message': 'Generating...'})}\n\n"
        
        full_response = ""
        try:
            async for chunk in openrouter_service.generate_response_stream(
                prompt,
                model_name=request.model_name,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'content', 'chunk': chunk})}\n\n"
            
            logger.info(f"[Chat] LLM complete, len={len(full_response)}")
            
            if session_meta and (request.use_memory or request.use_retrieval):
                background_tasks.add_task(zep_service.add_memory, request.session_id, "assistant", full_response)
            
            yield f"data: {json.dumps({'type': 'done', 'response': full_response})}\n\n"
            
        except Exception as e:
            logger.error(f"[Chat] LLM error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    else:
        response_text = "AI is disabled. Context block generated."
        yield f"data: {json.dumps({'type': 'content', 'chunk': response_text})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'response': response_text})}\n\n"


@router.post("")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """Chat endpoint with streaming SSE response."""
    """Chat endpoint with streaming SSE response."""
    # Note: User memory is now added INSIDE _stream_chat_response to get context immediately.


    return StreamingResponse(
        _stream_chat_response(request, background_tasks),
        media_type="text/event-stream",
        background=background_tasks,
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
