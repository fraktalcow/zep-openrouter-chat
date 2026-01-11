"""
Database package.

Provides async PostgreSQL connection, session management, and models.
"""

from db.connection import (
    get_db,
    get_db_context,
    init_db,
    close_db,
    check_db_health,
    wait_for_db,
    is_initialized,
    execute_raw_sql,
)
from db.models import (
    Base,
    User,
    Session,
    Message,
    GraphCache,
    LLMInteraction,
)

__all__ = [
    # Connection utilities
    "get_db",
    "get_db_context",
    "init_db",
    "close_db",
    "check_db_health",
    "wait_for_db",
    "is_initialized",
    "execute_raw_sql",
    # Models
    "Base",
    "User",
    "Session",
    "Message",
    "GraphCache",
    "LLMInteraction",
]
