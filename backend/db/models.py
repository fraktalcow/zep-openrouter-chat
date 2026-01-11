"""
SQLAlchemy models for persistent session storage.

These tables complement Zep by providing:
- Fast local retrieval with proper ordering
- LLM usage tracking (tokens, cost)
- Graph data caching
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    String, Text, Integer, Float, DateTime, ForeignKey, Index, Boolean, 
    CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# User Model
# ─────────────────────────────────────────────────────────────────────────────

class User(Base):
    """
    User model - mirrors Zep user for local caching.
    
    Stores user identity and preferences. Acts as the root
    for all user-related data (sessions, graph cache, etc.)
    """
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False, default="User")
    last_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    
    # Relationships
    sessions: Mapped[List["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    graph_cache: Mapped[List["GraphCache"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<User {self.id}: {self.first_name} {self.last_name}>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "metadata": self.metadata_,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Session Model
# ─────────────────────────────────────────────────────────────────────────────

class Session(Base):
    """
    Chat session model - mirrors Zep session with additional local metadata.
    
    Each session belongs to a user and contains ordered messages.
    The zep_session_id links to the corresponding Zep session for
    memory and graph features.
    """
    __tablename__ = "sessions"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    zep_session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[List["Message"]] = relationship(
        back_populates="session", 
        cascade="all, delete-orphan", 
        order_by="Message.sequence_order",
        lazy="selectin"
    )
    llm_interactions: Mapped[List["LLMInteraction"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="dynamic"
    )
    
    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_created_at", created_at.desc()),
        Index("ix_sessions_user_created", "user_id", created_at.desc()),
        Index("ix_sessions_zep_id", "zep_session_id"),
    )
    
    def __repr__(self) -> str:
        return f"<Session {self.id} (user={self.user_id})>"
    
    def to_dict(self, include_messages: bool = False) -> dict:
        """Convert to dictionary for API responses."""
        result = {
            "session_id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "is_archived": self.is_archived,
            "first_name": self.metadata_.get("first_name", "User"),
            "last_name": self.metadata_.get("last_name", ""),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_messages:
            result["messages"] = [m.to_dict() for m in self.messages]
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Message Model
# ─────────────────────────────────────────────────────────────────────────────

class Message(Base):
    """
    Chat message with LLM parameters and ordering.
    
    Messages are ordered within a session by sequence_order.
    Stores both human and AI messages with associated metadata.
    """
    __tablename__ = "messages"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    llm_params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    usage: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    
    # Relationships
    session: Mapped["Session"] = relationship(back_populates="messages")
    llm_interaction: Mapped[Optional["LLMInteraction"]] = relationship(
        back_populates="message", uselist=False
    )
    
    __table_args__ = (
        Index("ix_messages_session_id", "session_id"),
        Index("ix_messages_session_order", "session_id", "sequence_order"),
        Index("ix_messages_created_at", created_at.desc()),
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_role_valid"),
        UniqueConstraint("session_id", "sequence_order", name="uq_session_sequence"),
    )
    
    def __repr__(self) -> str:
        content_preview = self.content[:30] + "..." if len(self.content) > 30 else self.content
        return f"<Message {self.id[:8]} ({self.role}): {content_preview}>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "llm_params": self.llm_params,
            "usage": self.usage,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Graph Cache Model
# ─────────────────────────────────────────────────────────────────────────────

class GraphCache(Base):
    """
    Cached graph nodes from Zep for faster visualization.
    
    Zep builds a knowledge graph from conversations.
    This cache allows fast local rendering without
    re-fetching from Zep on every page load.
    """
    __tablename__ = "graph_cache"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    node_uuid: Mapped[str] = mapped_column(String(64), nullable=False)
    node_name: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    edges: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="graph_cache")
    
    __table_args__ = (
        Index("ix_graph_cache_user_id", "user_id"),
        Index("ix_graph_cache_node_uuid", "node_uuid", unique=True),
        Index("ix_graph_cache_synced_at", synced_at.desc()),
    )
    
    def __repr__(self) -> str:
        return f"<GraphCache {self.node_uuid[:8]}: {self.node_name}>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "uuid": self.node_uuid,
            "name": self.node_name,
            "summary": self.summary,
            "type": self.node_type,
            "edges": self.edges,
        }


# ─────────────────────────────────────────────────────────────────────────────
# LLM Interaction Model
# ─────────────────────────────────────────────────────────────────────────────

class LLMInteraction(Base):
    """
    LLM interaction logs for token/cost tracking.
    
    Tracks every LLM call for analytics and billing.
    Linked to sessions and optionally to specific messages.
    """
    __tablename__ = "llm_interactions"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    model_name: Mapped[str] = mapped_column(String(256), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="openrouter")
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    
    # Relationships
    session: Mapped["Session"] = relationship(back_populates="llm_interactions")
    message: Mapped[Optional["Message"]] = relationship(back_populates="llm_interaction")
    
    __table_args__ = (
        Index("ix_llm_interactions_session_id", "session_id"),
        Index("ix_llm_interactions_created_at", created_at.desc()),
        Index("ix_llm_interactions_model", "model_name"),
    )
    
    def __repr__(self) -> str:
        return f"<LLMInteraction {self.id[:8]}: {self.model_name} tokens={self.total_tokens}>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "model_name": self.model_name,
            "provider": self.provider,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }



