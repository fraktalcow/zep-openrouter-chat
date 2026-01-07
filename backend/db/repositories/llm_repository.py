"""
LLM Interaction repository - tracking LLM usage and costs.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import LLMInteraction, Session
from logger import logger


class LLMInteractionRepository:
    """Repository for LLM interaction logging and analytics."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def log(
        self,
        session_id: str,
        model_name: str,
        *,
        message_id: Optional[str] = None,
        provider: str = "openrouter",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        cost: Optional[float] = None,
        duration_seconds: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> LLMInteraction:
        """Log an LLM interaction."""
        interaction = LLMInteraction(
            session_id=session_id,
            message_id=message_id,
            model_name=model_name,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            duration_seconds=duration_seconds,
            error_message=error_message,
        )
        self.db.add(interaction)
        await self.db.flush()
        
        if error_message:
            logger.warning(f"[DB] LLM error logged: {model_name} - {error_message[:50]}")
        else:
            logger.debug(f"[DB] LLM interaction logged: {model_name}, tokens={total_tokens}")
        
        return interaction
    
    async def log_error(
        self,
        session_id: str,
        model_name: str,
        error_message: str,
        *,
        duration_seconds: Optional[float] = None,
    ) -> LLMInteraction:
        """Log a failed LLM interaction."""
        return await self.log(
            session_id=session_id,
            model_name=model_name,
            error_message=error_message,
            duration_seconds=duration_seconds,
        )
    
    async def get_by_id(self, interaction_id: str) -> Optional[LLMInteraction]:
        """Get an interaction by ID."""
        result = await self.db.execute(
            select(LLMInteraction).where(LLMInteraction.id == interaction_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_session(
        self,
        session_id: str,
        limit: int = 50,
        include_errors: bool = True,
    ) -> List[LLMInteraction]:
        """Get LLM interactions for a session."""
        query = (
            select(LLMInteraction)
            .where(LLMInteraction.session_id == session_id)
            .order_by(LLMInteraction.created_at.desc())
            .limit(limit)
        )
        
        if not include_errors:
            query = query.where(LLMInteraction.error_message.is_(None))
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_session_stats(self, session_id: str) -> Dict[str, Any]:
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
            .where(LLMInteraction.error_message.is_(None))  # Only successful calls
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
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get aggregated stats for a user across all sessions."""
        result = await self.db.execute(
            select(
                func.count(LLMInteraction.id).label("interaction_count"),
                func.sum(LLMInteraction.total_tokens).label("total_tokens"),
                func.sum(LLMInteraction.cost).label("total_cost"),
                func.count(func.distinct(LLMInteraction.session_id)).label("session_count"),
            )
            .join(Session, LLMInteraction.session_id == Session.id)
            .where(Session.user_id == user_id)
            .where(LLMInteraction.error_message.is_(None))
        )
        row = result.one()
        return {
            "interaction_count": row.interaction_count or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost": float(row.total_cost or 0),
            "session_count": row.session_count or 0,
        }
    
    async def get_model_usage(
        self,
        since: Optional[datetime] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get model usage statistics, grouped by model."""
        query = select(
            LLMInteraction.model_name,
            func.count(LLMInteraction.id).label("call_count"),
            func.sum(LLMInteraction.total_tokens).label("total_tokens"),
            func.sum(LLMInteraction.cost).label("total_cost"),
            func.avg(LLMInteraction.duration_seconds).label("avg_duration"),
        ).where(LLMInteraction.error_message.is_(None))
        
        if since:
            query = query.where(LLMInteraction.created_at >= since)
        
        query = (
            query
            .group_by(LLMInteraction.model_name)
            .order_by(func.count(LLMInteraction.id).desc())
            .limit(limit)
        )
        
        result = await self.db.execute(query)
        return [
            {
                "model_name": row.model_name,
                "call_count": row.call_count,
                "total_tokens": row.total_tokens or 0,
                "total_cost": float(row.total_cost or 0),
                "avg_duration": float(row.avg_duration or 0),
            }
            for row in result.all()
        ]
    
    async def get_recent(
        self,
        limit: int = 20,
        since: Optional[datetime] = None,
    ) -> List[LLMInteraction]:
        """Get recent LLM interactions globally."""
        query = (
            select(LLMInteraction)
            .order_by(LLMInteraction.created_at.desc())
        )
        
        if since:
            query = query.where(LLMInteraction.created_at >= since)
        
        result = await self.db.execute(query.limit(limit))
        return list(result.scalars().all())
    
    async def get_daily_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily usage statistics for the past N days."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        result = await self.db.execute(
            select(
                func.date(LLMInteraction.created_at).label("date"),
                func.count(LLMInteraction.id).label("call_count"),
                func.sum(LLMInteraction.total_tokens).label("total_tokens"),
                func.sum(LLMInteraction.cost).label("total_cost"),
            )
            .where(LLMInteraction.created_at >= since)
            .where(LLMInteraction.error_message.is_(None))
            .group_by(func.date(LLMInteraction.created_at))
            .order_by(func.date(LLMInteraction.created_at).desc())
        )
        
        return [
            {
                "date": str(row.date),
                "call_count": row.call_count,
                "total_tokens": row.total_tokens or 0,
                "total_cost": float(row.total_cost or 0),
            }
            for row in result.all()
        ]
