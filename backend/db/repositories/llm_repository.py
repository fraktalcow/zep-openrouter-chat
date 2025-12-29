"""
LLM Interaction repository - tracking LLM usage and costs.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import LLMInteraction
from logger import logger


class LLMInteractionRepository:
    """Repository for LLM interaction logging."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log(
        self,
        session_id: str,
        model_name: str,
        *,
        message_id: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        cost: Optional[float] = None,
        duration_seconds: Optional[float] = None,
    ) -> LLMInteraction:
        """Log an LLM interaction."""
        interaction = LLMInteraction(
            session_id=session_id,
            message_id=message_id,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            duration_seconds=duration_seconds,
        )
        self.db.add(interaction)
        await self.db.flush()
        logger.debug(f"[DB] LLM interaction logged: {model_name}, tokens={total_tokens}")
        return interaction
    
    async def get_by_session(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[LLMInteraction]:
        """Get LLM interactions for a session."""
        result = await self.db.execute(
            select(LLMInteraction)
            .where(LLMInteraction.session_id == session_id)
            .order_by(LLMInteraction.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_session_stats(self, session_id: str) -> dict:
        """Get aggregated stats for a session."""
        result = await self.db.execute(
            select(
                func.count(LLMInteraction.id).label("interaction_count"),
                func.sum(LLMInteraction.prompt_tokens).label("total_prompt_tokens"),
                func.sum(LLMInteraction.completion_tokens).label("total_completion_tokens"),
                func.sum(LLMInteraction.total_tokens).label("total_tokens"),
                func.sum(LLMInteraction.cost).label("total_cost"),
                func.avg(LLMInteraction.duration_seconds).label("avg_duration"),
            )
            .where(LLMInteraction.session_id == session_id)
        )
        row = result.one()
        return {
            "interaction_count": row.interaction_count or 0,
            "total_prompt_tokens": row.total_prompt_tokens or 0,
            "total_completion_tokens": row.total_completion_tokens or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost": float(row.total_cost or 0),
            "avg_duration": float(row.avg_duration or 0),
        }
    
    async def get_user_stats(self, user_id: str) -> dict:
        """Get aggregated stats for a user across all sessions."""
        from db.models import Session
        
        result = await self.db.execute(
            select(
                func.count(LLMInteraction.id).label("interaction_count"),
                func.sum(LLMInteraction.total_tokens).label("total_tokens"),
                func.sum(LLMInteraction.cost).label("total_cost"),
            )
            .join(Session, LLMInteraction.session_id == Session.id)
            .where(Session.user_id == user_id)
        )
        row = result.one()
        return {
            "interaction_count": row.interaction_count or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost": float(row.total_cost or 0),
        }
    
    async def get_recent(
        self,
        limit: int = 20,
        since: Optional[datetime] = None,
    ) -> list[LLMInteraction]:
        """Get recent LLM interactions globally."""
        query = select(LLMInteraction).order_by(LLMInteraction.created_at.desc())
        
        if since:
            query = query.where(LLMInteraction.created_at >= since)
        
        result = await self.db.execute(query.limit(limit))
        return list(result.scalars().all())
