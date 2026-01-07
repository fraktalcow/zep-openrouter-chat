"""
User repository - CRUD operations for users.
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User
from logger import logger


class UserRepository:
    """Repository for user operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self,
        user_id: str,
        first_name: str = "User",
        last_name: str = "",
        email: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> User:
        """Create a new user."""
        user = User(
            id=user_id,
            first_name=first_name,
            last_name=last_name,
            email=email,
            metadata_=metadata or {},
        )
        self.db.add(user)
        await self.db.flush()
        logger.info(f"[DB] User created: {user_id}")
        return user
    
    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    
    async def ensure(
        self,
        user_id: str,
        first_name: str = "User",
        last_name: str = "",
        email: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> User:
        """Create user if not exists, otherwise return existing."""
        user = await self.get_by_id(user_id)
        
        if user is None:
            user = await self.create(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                metadata=metadata,
            )
        
        return user
    
    async def update(
        self,
        user_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[User]:
        """Update user fields."""
        user = await self.get_by_id(user_id)
        if not user:
            return None
        
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if email is not None:
            user.email = email
        if metadata is not None:
            user.metadata_ = metadata
        
        user.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        logger.info(f"[DB] User updated: {user_id}")
        return user
    
    async def delete(self, user_id: str) -> bool:
        """Delete a user by ID (cascades to sessions, messages, etc.)."""
        user = await self.get_by_id(user_id)
        if user:
            await self.db.delete(user)
            await self.db.flush()
            logger.info(f"[DB] User deleted: {user_id}")
            return True
        return False
    
    async def list_all(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[User]:
        """List all users ordered by created_at desc."""
        result = await self.db.execute(
            select(User)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    async def count(self) -> int:
        """Count total users."""
        result = await self.db.execute(select(func.count(User.id)))
        return result.scalar() or 0
    
    async def exists(self, user_id: str) -> bool:
        """Check if user exists."""
        result = await self.db.execute(
            select(func.count(User.id)).where(User.id == user_id)
        )
        return (result.scalar() or 0) > 0
