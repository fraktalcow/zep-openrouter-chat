"""Analytics and stats routes."""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from db.repositories import (
    SessionRepository,
    LLMInteractionRepository,
    UserRepository,
)
from logger import logger

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Response Models
# ─────────────────────────────────────────────────────────────────────────────

class SystemStatsResponse(BaseModel):
    """Overall system statistics."""
    user_count: int
    session_count: int
    message_count: int
    total_tokens: int
    total_cost: float
    

class UserStatsResponse(BaseModel):
    """Statistics for a specific user."""
    user_id: str
    session_count: int
    interaction_count: int
    total_tokens: int
    total_cost: float


class ModelUsageResponse(BaseModel):
    """Model usage statistics."""
    model_name: str
    call_count: int
    total_tokens: int
    total_cost: float
    avg_duration: float


class DailyStatsResponse(BaseModel):
    """Daily usage statistics."""
    date: str
    call_count: int
    total_tokens: int
    total_cost: float


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/system", response_model=SystemStatsResponse)
async def get_system_stats(db: AsyncSession = Depends(get_db)):
    """Get overall system statistics."""
    try:
        session_repo = SessionRepository(db)
        user_repo = UserRepository(db)
        llm_repo = LLMInteractionRepository(db)
        user_count = await user_repo.count()
        session_count = await session_repo.count(include_archived=True)
        
        # Get total messages via raw query for efficiency
        from sqlalchemy import text
        msg_result = await db.execute(text("SELECT COUNT(*) FROM messages"))
        message_count = msg_result.scalar() or 0
        
        # Get LLM totals
        model_usage = await llm_repo.get_model_usage(limit=100)
        total_tokens = sum(m["total_tokens"] for m in model_usage)
        total_cost = sum(m["total_cost"] for m in model_usage)
        
        return SystemStatsResponse(
            user_count=user_count,
            session_count=session_count,
            message_count=message_count,
            total_tokens=total_tokens,
            total_cost=total_cost,
        )
        
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")


@router.get("/user/{user_id}", response_model=UserStatsResponse)
async def get_user_stats(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get statistics for a specific user."""
    try:
        session_repo = SessionRepository(db)
        llm_repo = LLMInteractionRepository(db)
        
        session_count = await session_repo.count(user_id=user_id, include_archived=True)
        
        if session_count == 0:
            raise HTTPException(status_code=404, detail="User not found or has no sessions")
        
        llm_stats = await llm_repo.get_user_stats(user_id)
        
        return UserStatsResponse(
            user_id=user_id,
            session_count=session_count,
            interaction_count=llm_stats["interaction_count"],
            total_tokens=llm_stats["total_tokens"],
            total_cost=llm_stats["total_cost"],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")


@router.get("/models", response_model=list[ModelUsageResponse])
async def get_model_usage(
    days: int = 30,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Get model usage statistics for the past N days."""
    try:
        llm_repo = LLMInteractionRepository(db)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        usage = await llm_repo.get_model_usage(since=since, limit=limit)
        
        return [
            ModelUsageResponse(**m) for m in usage
        ]
        
    except Exception as e:
        logger.error(f"Failed to get model usage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")


@router.get("/daily", response_model=list[DailyStatsResponse])
async def get_daily_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """Get daily usage statistics for the past N days."""
    try:
        llm_repo = LLMInteractionRepository(db)
        stats = await llm_repo.get_daily_stats(days=days)
        
        return [
            DailyStatsResponse(**s) for s in stats
        ]
        
    except Exception as e:
        logger.error(f"Failed to get daily stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")
