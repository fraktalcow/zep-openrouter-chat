"""Chat routes with message persistence and LLM interaction logging."""

import asyncio
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
from textwrap import dedent

from openrouter_service import get_openrouter_service
from zep_service import get_zep_service
from logger import logger

router = APIRouter()


CONTEXT_TEMPLATE = dedent("""
You are a helpful assistant with access to conversation history and knowledge graph facts.

# Conversation Memory
{memory_section}

# Knowledge Graph
{graph_section}

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


from db import get_db_context
from db.repositories import MessageRepository, LLMInteractionRepository

async def _persist_message(session_id: str, role: str, content: str, llm_params: dict = None, usage: dict = None):
    """Background task to persist message to PostgreSQL."""
    try:
        async with get_db_context() as db:
            message_repo = MessageRepository(db)
            await message_repo.add(
                session_id=session_id,
                role=role,
                content=content,
                llm_params=llm_params,
                usage=usage,
            )
            # logger.debug(f"[Chat] Message persisted for {session_id}")
    except Exception as e:
        logger.error(f"[Chat] CRITICAL: Failed to persist message: {e}", exc_info=True)


async def _log_llm_interaction(
    session_id: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    usage_metrics: dict,
    duration: float,
):
    """Background task to log LLM interaction to PostgreSQL."""
    try:
        async with get_db_context() as db:
            llm_repo = LLMInteractionRepository(db)
            await llm_repo.log(
                session_id=session_id,
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                prompt_tokens=usage_metrics.get("prompt_tokens"),
                completion_tokens=usage_metrics.get("completion_tokens"),
                total_tokens=usage_metrics.get("total_tokens"),
                cost=usage_metrics.get("cost"),
                duration_seconds=duration,
            )
    except Exception as e:
        logger.warning(f"[Chat] Failed to log LLM interaction: {e}")


async def _stream_chat_response(request: ChatRequest, background_tasks: BackgroundTasks):
    """Stream chat response with context from Zep memory and graph."""
    context_sections = {"memory_section": "", "graph_section": ""}
    use_zep = request.use_memory or request.use_retrieval
    
    zep_service = get_zep_service()
    openrouter_service = get_openrouter_service()
    
    # Persist user message to PostgreSQL immediately to ensure Sequence Order covers User -> Assistant
    await _persist_message(
        request.session_id,
        "user",
        request.message,
        {"model": request.model_name, "temperature": request.temperature},
        None,
    )
    
    # Signal that we're retrieving context
    if use_zep:
        yield f"data: {json.dumps({'type': 'step', 'id': 'retrieval', 'message': 'Retrieving Zep context...'})}\n\n"

    # Parallel retrieval
    tasks = {}
    
    if use_zep:
        # Add user message AND retrieve context in one go
        tasks['zep_add'] = zep_service.add_memory(
            session_id=request.session_id,
            role="user",
            content=request.message,
            return_context=True
        )
        # Fallback/Refresh context
        tasks['zep_context'] = zep_service.get_context(session_id=request.session_id)
        
        # Graph search
        if request.use_retrieval:
            tasks['graph'] = zep_service.search_graph(query=request.message)

    # Await all tasks
    results_map = {}
    if tasks:
        task_names = list(tasks.keys())
        task_values = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results_map = dict(zip(task_names, task_values))

    # Process Zep Context
    zep_context = results_map.get('zep_add') or results_map.get('zep_context')
    if isinstance(zep_context, Exception):
        logger.error(f"[Chat] Zep error: {zep_context}")
        zep_context = None

    if zep_context:
        context_sections["memory_section"] = zep_context
        logger.info(f"[Chat] Zep context block set, len={len(zep_context)}")

    # Process Graph
    if 'graph' in results_map:
        graph_res = results_map['graph']
        if isinstance(graph_res, Exception):
            logger.error(f"[Chat] Graph error: {graph_res}")
        elif graph_res:
            graph_lines = []
            for node in graph_res:
                name = node.get("name", "Unknown")
                fct = node.get("fact", "")
                if fct:
                    graph_lines.append(f"- {name}: {fct}")
            
            if graph_lines:
                context_sections["graph_section"] = "Relevant Knowledge Graph Facts:\n" + "\n".join(graph_lines)
                logger.info(f"[Chat] Graph included {len(graph_lines)} facts")

    # Build prompt
    sections = []
    if context_sections.get("memory_section"):
        sections.append(f"# Conversation Memory\n{context_sections['memory_section']}")
    if context_sections.get("graph_section"):
        sections.append(f"# Knowledge Graph\n{context_sections['graph_section']}")
    
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
        usage_metrics = {}
        start_time = asyncio.get_event_loop().time()
        
        try:
            async for chunk in openrouter_service.generate_response_stream(
                prompt,
                model_name=request.model_name,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            ):
                # Check if this is usage data
                if chunk.startswith("__USAGE__"):
                    usage_json = chunk[9:]  # Remove __USAGE__ prefix
                    try:
                        usage_metrics = json.loads(usage_json)
                    except json.JSONDecodeError:
                        logger.warning(f"[Chat] Failed to parse usage data: {usage_json}")
                    continue
                
                full_response += chunk
                yield f"data: {json.dumps({'type': 'content', 'chunk': chunk})}\n\n"
            
            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time
            
            logger.info(f"[Chat] LLM complete, len={len(full_response)}, duration={duration:.2f}s")
            
            # Build metrics object
            metrics = {
                "duration": round(duration, 3),
            }
            
            if usage_metrics:
                metrics["prompt_tokens"] = usage_metrics.get("prompt_tokens", 0)
                metrics["completion_tokens"] = usage_metrics.get("completion_tokens", 0)
                metrics["total_tokens"] = usage_metrics.get("total_tokens", 0)
                if "cost" in usage_metrics:
                     metrics["cost"] = usage_metrics["cost"]
                
                logger.info(f"[Chat] Metrics: {metrics}")
            
            # Persist assistant message and log LLM interaction
            llm_params = {
                "model": request.model_name,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
            }
            
            background_tasks.add_task(
                _persist_message,
                request.session_id,
                "assistant",
                full_response,
                llm_params,
                usage_metrics,
            )
            
            background_tasks.add_task(
                _log_llm_interaction,
                request.session_id,
                request.model_name,
                request.temperature,
                request.max_tokens,
                usage_metrics,
                duration,
            )
            
            # Also add to Zep for memory/graph
            if use_zep:
                background_tasks.add_task(zep_service.add_memory, request.session_id, "assistant", full_response)
            
            yield f"data: {json.dumps({'type': 'done', 'response': full_response, 'metrics': metrics})}\n\n"
            
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
    return StreamingResponse(
        _stream_chat_response(request, background_tasks),
        media_type="text/event-stream",
        background=background_tasks,
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
