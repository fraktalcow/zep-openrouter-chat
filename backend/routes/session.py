"""Minimal session management routes using Zep."""

import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from zep_service import get_zep_service

router = APIRouter()


class SessionRequest(BaseModel):
    first_name: str = "User"
    last_name: str = ""
    user_id: str | None = None


@router.get("/list")
async def list_sessions():
    """List all saved sessions from Zep."""
    sessions = await get_zep_service().list_sessions()
    return {"sessions": sessions}


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get a specific session by ID from Zep."""
    session = await get_zep_service().get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a session from Zep."""
    deleted = await get_zep_service().delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


@router.post("")
async def create_session(request: SessionRequest):
    """Create a new session (thread) in Zep."""
    # Reuse user_id if provided, otherwise generate a persistent-like one (or random)
    # Ideally frontend should cache user_id. 
    user_id = request.user_id or f"user_{uuid.uuid4().hex[:8]}"
    
    # Generate new thread_id
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    try:
        await get_zep_service().create_session(
            user_id,
            session_id,
            first_name=request.first_name,
            last_name=request.last_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create session: {e}")

    return {
        "session_id": session_id,
        "user_id": user_id,
        "first_name": request.first_name,
        "last_name": request.last_name,
    }
