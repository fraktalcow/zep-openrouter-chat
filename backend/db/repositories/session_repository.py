"""
Session repository - CRUD operations for sessions and users.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import User, Session
from logger import logger


class SessionRepository:
    """Repository for session and user operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ─────────────────────────────────────────────────────────────────────────
    # User Operations
    # ─────────────────────────────────────────────────────────────────────────
    
    async def ensure_user(
        self,
        user_id: str,
        first_name: str = "User",
        last_name: str = "",
        metadata: Optional[dict] = None,
    ) -> User:
        """Create user if not exists, otherwise return existing."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if user is None:
            user = User(
                id=user_id,
                first_name=first_name,
                last_name=last_name,
                metadata_=metadata or {},
            )
            self.db.add(user)
            await self.db.flush()
            logger.info(f"[DB] User created: {user_id}")
        
        return user
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Session Operations
    # ─────────────────────────────────────────────────────────────────────────
    
    async def create(
        self,
        session_id: str,
        user_id: str,
        *,
        zep_session_id: Optional[str] = None,
        title: Optional[str] = None,
        first_name: str = "User",
        last_name: str = "",
        metadata: Optional[dict] = None,
    ) -> Session:
        """Create a new session, ensuring user exists first."""
        # Ensure user exists
        await self.ensure_user(user_id, first_name, last_name)
        
        session = Session(
            id=session_id,
            user_id=user_id,
            zep_session_id=zep_session_id or session_id,
            title=title,
            metadata_=metadata or {"first_name": first_name, "last_name": last_name},
        )
        self.db.add(session)
        await self.db.flush()
        logger.info(f"[DB] Session created: {session_id} for user {user_id}")
        return session
    
    async def get_by_id(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        result = await self.db.execute(
            select(Session).where(Session.id == session_id)
        )
        return result.scalar_one_or_none()
    
    async def get_with_messages(self, session_id: str) -> Optional[Session]:
        """Get session with messages preloaded."""
        result = await self.db.execute(
            select(Session)
            .where(Session.id == session_id)
            .options(selectinload(Session.messages))
        )
        return result.scalar_one_or_none()
    
    async def list_all(
        self,
        limit: int = 20,
        offset: int = 0,
        user_id: Optional[str] = None,
    ) -> list[Session]:
        """List sessions ordered by created_at desc."""
        query = select(Session).order_by(Session.created_at.desc())
        
        if user_id:
            query = query.where(Session.user_id == user_id)
        
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def count(self, user_id: Optional[str] = None) -> int:
        """Count total sessions."""
        query = select(func.count(Session.id))
        if user_id:
            query = query.where(Session.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def delete(self, session_id: str) -> bool:
        """Delete a session by ID."""
        session = await self.get_by_id(session_id)
        if session:
            await self.db.delete(session)
            await self.db.flush()
            logger.info(f"[DB] Session deleted: {session_id}")
            return True
        return False
    
    async def update_title(self, session_id: str, title: str) -> Optional[Session]:
        """Update session title."""
        session = await self.get_by_id(session_id)
        if session:
            session.title = title
            session.updated_at = datetime.utcnow()
            await self.db.flush()
            return session
        return None
    
    async def exists(self, session_id: str) -> bool:
        """Check if session exists."""
        result = await self.db.execute(
            select(func.count(Session.id)).where(Session.id == session_id)
        )
        return (result.scalar() or 0) > 0
