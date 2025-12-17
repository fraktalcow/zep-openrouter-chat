"""Session management routes with SQLite persistence."""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import db
from zep_service import ZepService

router = APIRouter()


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


# Injected by server.py
zep_service: ZepService = None


def init_services(zep: ZepService):
    """Initialize with Zep service only - sessions now use SQLite."""
    global zep_service
    zep_service = zep


@router.get("/list")
async def list_sessions():
    """List all saved sessions for the sidebar."""
    sessions = db.list_sessions()
    return {"sessions": sessions}


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get a specific session by ID."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    deleted = db.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


@router.post("")
async def create_session(request: SessionRequest):
    """Create a new session with SQLite persistence."""
    user_id = request.user_id or f"user_{uuid.uuid4().hex[:8]}"
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    metadata = {
        "preferences": request.preferences,
        "traits": request.traits,
        "business_data": request.business_data,
    }

    # Create in Zep
    await zep_service.create_session(
        user_id,
        session_id,
        first_name=request.first_name,
        last_name=request.last_name,
        metadata=metadata,
    )

    # Persist to SQLite
    db.save_session(
        session_id=session_id,
        user_id=user_id,
        first_name=request.first_name,
        last_name=request.last_name,
        traits=request.traits or "",
        preferences=request.preferences or "",
        business_data=request.business_data or "",
    )

    return {
        "session_id": session_id,
        "user_id": user_id,
        "first_name": request.first_name,
        "last_name": request.last_name,
        "preferences": request.preferences,
        "traits": request.traits,
        "business_data": request.business_data,
    }
