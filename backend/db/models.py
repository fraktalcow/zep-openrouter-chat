"""
SQLAlchemy models for persistent session storage.

These tables complement Zep by providing:
- Fast local retrieval with proper ordering
- LLM usage tracking (tokens, cost)
- Graph data caching
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    String, Text, Integer, Float, DateTime, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """User model - mirrors Zep user."""
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(255), default="User")
    last_name: Mapped[str] = mapped_column(String(255), default="")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    graph_cache: Mapped[list["GraphCache"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    """Session model - mirrors Zep thread with additional local metadata."""
    __tablename__ = "sessions"
    
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"))
    zep_session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Message.sequence_order"
    )
    llm_interactions: Mapped[list["LLMInteraction"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    
    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_created_at", "created_at"),
    )


class Message(Base):
    """Chat message with LLM parameters and ordering."""
    __tablename__ = "messages"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(32))  # user, assistant, system
    content: Mapped[str] = mapped_column(Text)
    llm_params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    usage: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    sequence_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session: Mapped["Session"] = relationship(back_populates="messages")
    llm_interaction: Mapped[Optional["LLMInteraction"]] = relationship(
        back_populates="message", uselist=False
    )
    
    __table_args__ = (
        Index("ix_messages_session_id", "session_id"),
        Index("ix_messages_session_order", "session_id", "sequence_order"),
    )


class GraphCache(Base):
    """Cached graph nodes from Zep for faster visualization."""
    __tablename__ = "graph_cache"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE")
    )
    node_uuid: Mapped[str] = mapped_column(String(64))
    node_name: Mapped[str] = mapped_column(String(512))
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    node_type: Mapped[str] = mapped_column(String(64), default="unknown")
    edges: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # Connected edges
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="graph_cache")
    
    __table_args__ = (
        Index("ix_graph_cache_user_id", "user_id"),
        Index("ix_graph_cache_node_uuid", "node_uuid", unique=True),
    )


class LLMInteraction(Base):
    """LLM interaction logs for token/cost tracking."""
    __tablename__ = "llm_interactions"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE")
    )
    message_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    model_name: Mapped[str] = mapped_column(String(256))
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session: Mapped["Session"] = relationship(back_populates="llm_interactions")
    message: Mapped[Optional["Message"]] = relationship(back_populates="llm_interaction")
    
    __table_args__ = (
        Index("ix_llm_interactions_session_id", "session_id"),
        Index("ix_llm_interactions_created_at", "created_at"),
    )
