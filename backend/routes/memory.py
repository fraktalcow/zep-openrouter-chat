"""Memory context route - fetches Zep context for a session."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from zep_service import get_zep_service
from db import get_db
from db.repositories import MessageRepository
from logger import logger

router = APIRouter()


@router.get("/{session_id}")
async def get_memory_context(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get the memory context for a session from both PostgreSQL and Zep."""
    try:
        # Get context from Zep (user summary + facts)
        zep_context = await get_zep_service().get_context(session_id)
        
        # Get recent messages from PostgreSQL for history
        message_repo = MessageRepository(db)
        messages = await message_repo.get_recent(session_id, limit=10)
        
        return {
            "session_id": session_id,
            "zep_context": zep_context,
            "messages": [
                {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat() if m.created_at else None}
                for m in messages
            ],
        }
    except Exception as e:
        logger.error(f"Error fetching memory: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching memory: {str(e)}")
