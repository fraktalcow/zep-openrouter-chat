"""
Database layer using SQLite.
Handles persistence for sessions and RAG documents.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

# Database location
DB_PATH = Path(__file__).parent / "app.db"


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database tables."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                first_name TEXT DEFAULT 'User',
                last_name TEXT DEFAULT '',
                traits TEXT DEFAULT '',
                preferences TEXT DEFAULT '',
                business_data TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS rag_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                embedding TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
        """)


# ==================== SESSION OPERATIONS ====================

def save_session(
    session_id: str,
    user_id: str,
    first_name: str = "User",
    last_name: str = "",
    traits: str = "",
    preferences: str = "",
    business_data: str = "",
) -> Dict[str, Any]:
    """Save or update a session."""
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO sessions 
            (session_id, user_id, first_name, last_name, traits, preferences, business_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session_id, user_id, first_name, last_name, traits, preferences, business_data))
    
    return {
        "session_id": session_id,
        "user_id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "traits": traits,
        "preferences": preferences,
        "business_data": business_data,
    }


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get a session by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    
    if row:
        return dict(row)
    return None


def delete_session(session_id: str) -> bool:
    """Delete a session."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM sessions WHERE session_id = ?", (session_id,)
        )
    return cursor.rowcount > 0


def list_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    """List all sessions, most recent first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


# ==================== RAG DOCUMENT OPERATIONS ====================

def add_documents(
    documents: List[Dict[str, Any]], 
    embeddings: List[List[float]]
) -> int:
    """Add documents with embeddings. Returns total count."""
    with get_connection() as conn:
        for doc, emb in zip(documents, embeddings):
            conn.execute(
                "INSERT INTO rag_documents (text, metadata, embedding) VALUES (?, ?, ?)",
                (doc["text"], json.dumps(doc.get("metadata", {})), json.dumps(emb))
            )
        count = conn.execute("SELECT COUNT(*) FROM rag_documents").fetchone()[0]
    return count


def get_all_documents() -> tuple[List[Dict[str, Any]], List[List[float]]]:
    """Get all documents and embeddings."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT text, metadata, embedding FROM rag_documents"
        ).fetchall()
    
    documents = [{"text": r["text"], "metadata": json.loads(r["metadata"])} for r in rows]
    embeddings = [json.loads(r["embedding"]) for r in rows]
    return documents, embeddings


def get_document_count() -> int:
    """Get total document count."""
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM rag_documents").fetchone()[0]


def clear_documents() -> int:
    """Clear all documents. Returns count cleared."""
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM rag_documents").fetchone()[0]
        conn.execute("DELETE FROM rag_documents")
    return count


# Initialize database on module import
init_db()
