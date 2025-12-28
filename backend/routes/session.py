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
    new_user: bool = False  # Explicit flag to force a fresh user context

# ... (existing list path logic unchanged) ...

@router.post("")
async def create_session(request: SessionRequest):
    """Create a new session (thread) in Zep."""
    
    # Logic:
    # 1. If new_user is True, ALWAYS generate a new user_id.
    # 2. If user_id is provided and new_user is False, use provided user_id.
    # 3. If no user_id and new_user is False, generate a new one (default behavior).
    
    if request.new_user:
        user_id = f"user_{uuid.uuid4().hex[:8]}"
    else:
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
