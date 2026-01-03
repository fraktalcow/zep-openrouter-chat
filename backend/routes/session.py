"""Session management routes with PostgreSQL + Zep dual-write."""

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from zep_service import get_zep_service
from db import get_db
from db.repositories import SessionRepository, MessageRepository
from logger import logger

router = APIRouter()


class SessionRequest(BaseModel):
    first_name: str = "User"
    last_name: str = ""
    user_id: Optional[str] = None
    new_user: bool = False  # Explicit flag to force a fresh user context

class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: Optional[str] = None
    llm_params: Optional[Dict[str, Any]] = None
    usage: Optional[Dict[str, Any]] = None

class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    first_name: str
    last_name: str
    title: Optional[str] = None
    created_at: Optional[str] = None
    messages: List[MessageResponse] = []

class SessionListResponse(BaseModel):
    sessions: List[Dict[str, Any]]


@router.post("")
async def create_session(request: SessionRequest, db: AsyncSession = Depends(get_db)):
    """Create a new session in both PostgreSQL and Zep."""
    
    # Logic:
    # 1. If new_user is True, ALWAYS generate a new user_id.
    # 2. If user_id is provided and new_user is False, use provided user_id.
    # 3. If no user_id and new_user is False, generate a new one.
    
    if request.new_user:
        user_id = f"user_{uuid.uuid4().hex[:8]}"
    else:
        user_id = request.user_id or f"user_{uuid.uuid4().hex[:8]}"
    
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    # 1. Create in Zep (for memory/graph features)
    try:
        await get_zep_service().create_session(
            user_id,
            session_id,
            first_name=request.first_name,
            last_name=request.last_name,
        )
    except Exception as e:
        logger.error(f"Zep session creation failed: {e}")
        # Continue anyway - PostgreSQL is primary storage
    
    # 2. Store in PostgreSQL (for fast retrieval/ordering)
    try:
        session_repo = SessionRepository(db)
        await session_repo.create(
            session_id=session_id,
            user_id=user_id,
            zep_session_id=session_id,
            first_name=request.first_name,
            last_name=request.last_name,
        )
    except Exception as e:
        logger.error(f"PostgreSQL session creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {e}")

    return {
        "session_id": session_id,
        "user_id": user_id,
        "first_name": request.first_name,
        "last_name": request.last_name,
    }


@router.get("/list", response_model=SessionListResponse)
async def list_sessions(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """List recent sessions from PostgreSQL (faster, better ordering)."""
    try:
        session_repo = SessionRepository(db)
        sessions = await session_repo.list_all(limit=limit)
        
        # Format response
        result = []
        for s in sessions:
            meta = s.metadata_ or {}
            result.append({
                "session_id": s.id,
                "user_id": s.user_id,
                "first_name": meta.get("first_name", "User"),
                "last_name": meta.get("last_name", ""),
                "title": s.title,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            })
        
        return {"sessions": result}
        return {"sessions": result}
    except Exception as e:
        logger.error(f"PostgreSQL list failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {e}")


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get session details and message history."""
    try:
        session_repo = SessionRepository(db)
        message_repo = MessageRepository(db)
        
        # Try PostgreSQL first
        session = await session_repo.get_by_id(session_id)
        
        if not session:
            logger.warning(f"Session {session_id} not found in DB")
            raise HTTPException(status_code=404, detail="Session not found")
        
        messages = await message_repo.get_history(session_id)
        meta = session.metadata_ or {}
        
        # Explicitly create lists of dicts
        msg_list = []
        for m in messages:
            msg_list.append({
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "llm_params": m.llm_params,
                "usage": m.usage,
            })

        return {
            "session_id": session.id,
            "user_id": session.user_id,
            "first_name": meta.get("first_name", "User"),
            "last_name": meta.get("last_name", ""),
            "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "messages": msg_list,
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get session: {e}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get session: {e}")


@router.delete("/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a session from both PostgreSQL and Zep."""
    try:
        # Delete from PostgreSQL
        session_repo = SessionRepository(db)
        db_deleted = await session_repo.delete(session_id)
        
        # Delete from Zep
        zep_deleted = await get_zep_service().delete_session(session_id)
        
        if not db_deleted and not zep_deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {"status": "success", "deleted_from_db": db_deleted, "deleted_from_zep": zep_deleted}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {e}")


@router.get("/{session_id}/stats")
async def get_session_stats(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get LLM usage stats for a session."""
    from db.repositories import LLMInteractionRepository
    
    try:
        llm_repo = LLMInteractionRepository(db)
        stats = await llm_repo.get_session_stats(session_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")


@router.post("/sync")
async def sync_sessions():
    """Manually sync all Zep sessions to PostgreSQL."""
    try:
        from sync_service import sync_zep_sessions_to_db
        stats = await sync_zep_sessions_to_db(limit=100)
        return {"status": "success", **stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")


@router.post("/{session_id}/sync-messages")
async def sync_session_messages(session_id: str):
    """Sync messages for a specific session from Zep to PostgreSQL."""
    try:
        from sync_service import sync_zep_messages_to_db
        synced = await sync_zep_messages_to_db(session_id)
        return {"status": "success", "synced": synced, "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")


@router.post("/{session_id}/sync-graph")
async def sync_session_graph(session_id: str, db: AsyncSession = Depends(get_db)):
    """Sync graph data for the user of this session."""
    try:
        session_repo = SessionRepository(db)
        session = await session_repo.get_by_id(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        from sync_service import sync_graph_for_user
        graph = await sync_graph_for_user(session.user_id)
        
        return {
            "status": "success",
            "user_id": session.user_id,
            "nodes": len(graph.get("nodes", [])) if graph else 0,
            "edges": len(graph.get("edges", [])) if graph else 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")
