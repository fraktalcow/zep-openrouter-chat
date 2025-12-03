import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

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


# These will be injected by server.py
zep_service: ZepService = None
SESSIONS: Dict[str, Dict[str, Any]] = None


def init_services(zep: ZepService, sessions: Dict[str, Dict[str, Any]]):
    global zep_service, SESSIONS
    zep_service = zep
    SESSIONS = sessions


@router.post("")
async def create_session(request: SessionRequest):
    user_id = request.user_id or f"user_{uuid.uuid4().hex[:8]}"
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    metadata = {
        "preferences": request.preferences,
        "traits": request.traits,
        "business_data": request.business_data,
    }

    await zep_service.create_session(
        user_id,
        session_id,
        first_name=request.first_name,
        last_name=request.last_name,
        metadata=metadata,
    )

    SESSIONS[session_id] = {
        "user_id": user_id,
        "first_name": request.first_name,
        "last_name": request.last_name,
        **metadata,
    }

    return {
        "session_id": session_id,
        "user_id": user_id,
        "preferences": request.preferences,
        "traits": request.traits,
        "business_data": request.business_data,
    }

