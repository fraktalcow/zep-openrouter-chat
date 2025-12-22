from fastapi import APIRouter, HTTPException

from zep_service import get_zep_service

router = APIRouter()


@router.get("/{session_id}")
async def get_memory_context(session_id: str):
    """Get the memory context for a session."""
    try:
        memory = await get_zep_service().get_memory(session_id)
        return {
            "session_id": session_id,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in (memory.messages or [])
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching memory: {str(e)}")

