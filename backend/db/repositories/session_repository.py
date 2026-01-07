"""
Session repository - CRUD operations for sessions.
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import User, Session
from logger import logger


class SessionRepository:
    """Repository for session operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ─────────────────────────────────────────────────────────────────────────
    # User Helper (for convenience, use UserRepository for full user ops)
    # ─────────────────────────────────────────────────────────────────────────
    
    async def _ensure_user(
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
        await self._ensure_user(user_id, first_name, last_name)
        
        # Build metadata
        session_metadata = metadata or {}
        session_metadata.setdefault("first_name", first_name)
        session_metadata.setdefault("last_name", last_name)
        
        session = Session(
            id=session_id,
            user_id=user_id,
            zep_session_id=zep_session_id or session_id,
            title=title,
            metadata_=session_metadata,
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
    
    async def get_with_user(self, session_id: str) -> Optional[Session]:
        """Get session with user preloaded."""
        result = await self.db.execute(
            select(Session)
            .where(Session.id == session_id)
            .options(selectinload(Session.user))
        )
        return result.scalar_one_or_none()
    
    async def list_all(
        self,
        limit: int = 20,
        offset: int = 0,
        user_id: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[Session]:
        """List sessions ordered by created_at desc."""
        query = select(Session).order_by(Session.created_at.desc())
        
        if user_id:
            query = query.where(Session.user_id == user_id)
        
        if not include_archived:
            query = query.where(Session.is_archived == False)
        
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def list_recent(
        self,
        limit: int = 10,
        user_id: Optional[str] = None,
    ) -> List[Session]:
        """Get most recent active sessions."""
        return await self.list_all(
            limit=limit,
            user_id=user_id,
            include_archived=False,
        )
    
    async def count(
        self,
        user_id: Optional[str] = None,
        include_archived: bool = False,
    ) -> int:
        """Count total sessions."""
        query = select(func.count(Session.id))
        
        if user_id:
            query = query.where(Session.user_id == user_id)
        
        if not include_archived:
            query = query.where(Session.is_archived == False)
        
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def delete(self, session_id: str) -> bool:
        """Delete a session by ID (cascades to messages, interactions)."""
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
            session.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            logger.info(f"[DB] Session title updated: {session_id}")
            return session
        return None
    
    async def archive(self, session_id: str) -> Optional[Session]:
        """Archive a session (soft delete)."""
        session = await self.get_by_id(session_id)
        if session:
            session.is_archived = True
            session.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            logger.info(f"[DB] Session archived: {session_id}")
            return session
        return None
    
    async def unarchive(self, session_id: str) -> Optional[Session]:
        """Unarchive a session."""
        session = await self.get_by_id(session_id)
        if session:
            session.is_archived = False
            session.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            logger.info(f"[DB] Session unarchived: {session_id}")
            return session
        return None
    
    async def update_metadata(
        self,
        session_id: str,
        metadata: dict,
        merge: bool = True,
    ) -> Optional[Session]:
        """Update session metadata."""
        session = await self.get_by_id(session_id)
        if session:
            if merge:
                current = session.metadata_ or {}
                current.update(metadata)
                session.metadata_ = current
            else:
                session.metadata_ = metadata
            session.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            return session
        return None
    
    async def exists(self, session_id: str) -> bool:
        """Check if session exists."""
        result = await self.db.execute(
            select(func.count(Session.id)).where(Session.id == session_id)
        )
        return (result.scalar() or 0) > 0
    
    async def get_user_id(self, session_id: str) -> Optional[str]:
        """Get user ID for a session (lightweight query)."""
        result = await self.db.execute(
            select(Session.user_id).where(Session.id == session_id)
        )
        row = result.one_or_none()
        return row[0] if row else None
