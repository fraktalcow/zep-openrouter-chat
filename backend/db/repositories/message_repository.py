"""
Message repository - CRUD operations for chat messages.
"""

from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Message
from logger import logger


class MessageRepository:
    """Repository for message operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def _get_next_sequence(self, session_id: str) -> int:
        """Get the next sequence order for a session."""
        result = await self.db.execute(
            select(func.max(Message.sequence_order))
            .where(Message.session_id == session_id)
        )
        max_order = result.scalar()
        return (max_order or 0) + 1
    
    async def add(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        llm_params: Optional[dict] = None,
        usage: Optional[dict] = None,
    ) -> Message:
        """Add a new message to a session."""
        sequence = await self._get_next_sequence(session_id)
        
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            llm_params=llm_params,
            usage=usage,
            sequence_order=sequence,
        )
        self.db.add(message)
        await self.db.flush()
        logger.debug(f"[DB] Message added: {role} in {session_id}, seq={sequence}")
        return message
    
    async def get_by_id(self, message_id: str) -> Optional[Message]:
        """Get a message by ID."""
        result = await self.db.execute(
            select(Message).where(Message.id == message_id)
        )
        return result.scalar_one_or_none()
    
    async def get_history(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        """Get message history for a session, ordered by sequence."""
        result = await self.db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.sequence_order.asc(), Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    async def get_recent(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[Message]:
        """Get most recent messages for a session (for context)."""
        # Get last N messages, but return in chronological order
        subquery = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.sequence_order.desc())
            .limit(limit)
            .subquery()
        )
        result = await self.db.execute(
            select(Message)
            .from_statement(
                select(Message)
                .where(Message.id.in_(select(subquery.c.id)))
                .order_by(Message.sequence_order.asc())
            )
        )
        return list(result.scalars().all())
    
    async def count(self, session_id: str) -> int:
        """Count messages in a session."""
        result = await self.db.execute(
            select(func.count(Message.id))
            .where(Message.session_id == session_id)
        )
        return result.scalar() or 0
    
    async def delete_by_session(self, session_id: str) -> int:
        """Delete all messages in a session. Returns count deleted."""
        from sqlalchemy import delete
        result = await self.db.execute(
            delete(Message).where(Message.session_id == session_id)
        )
        await self.db.flush()
        return result.rowcount
    
    async def update_usage(
        self,
        message_id: str,
        usage: dict,
    ) -> Optional[Message]:
        """Update usage data for a message."""
        message = await self.get_by_id(message_id)
        if message:
            message.usage = usage
            await self.db.flush()
            return message
        return None
