"""
Sync service - syncs existing Zep data to PostgreSQL.
Runs on startup to ensure database is up-to-date.
"""

from typing import Optional
from logger import logger


async def sync_zep_sessions_to_db(limit: int = 100) -> dict:
    """
    Sync existing Zep sessions to PostgreSQL.
    Called on startup to populate DB with historical data.
    """
    from zep_service import get_zep_service
    from db import get_db_context
    from db.repositories import SessionRepository
    
    stats = {"synced": 0, "skipped": 0, "errors": 0}
    
    try:
        zep = get_zep_service()
        zep_sessions = await zep.list_sessions(limit=limit)
        
        if not zep_sessions:
            logger.info("[Sync] No Zep sessions to sync")
            return stats
        
        async with get_db_context() as db:
            session_repo = SessionRepository(db)
            
            for zep_session in zep_sessions:
                session_id = zep_session.get("session_id")
                if not session_id:
                    continue
                
                # Check if already in DB
                exists = await session_repo.exists(session_id)
                if exists:
                    stats["skipped"] += 1
                    continue
                
                # Create in DB
                try:
                    user_id = zep_session.get("user_id", "unknown_user")
                    await session_repo.create(
                        session_id=session_id,
                        user_id=user_id,
                        zep_session_id=session_id,
                        first_name=zep_session.get("first_name", "User"),
                        last_name=zep_session.get("last_name", ""),
                    )
                    stats["synced"] += 1
                except Exception as e:
                    logger.warning(f"[Sync] Failed to sync session {session_id}: {e}")
                    stats["errors"] += 1
        
        logger.info(f"[Sync] Complete: synced={stats['synced']}, skipped={stats['skipped']}, errors={stats['errors']}")
        
    except Exception as e:
        logger.error(f"[Sync] Failed: {e}")
        stats["errors"] += 1
    
    return stats


async def sync_zep_messages_to_db(session_id: str) -> int:
    """
    Sync messages from a Zep session to PostgreSQL.
    Called when accessing a session that has messages in Zep but not in DB.
    """
    from zep_service import get_zep_service
    from db import get_db_context
    from db.repositories import MessageRepository
    
    try:
        zep = get_zep_service()
        messages = await zep.get_session_messages(session_id)
        
        if not messages:
            return 0
        
        async with get_db_context() as db:
            message_repo = MessageRepository(db)
            
            # Check if messages already in DB
            existing_count = await message_repo.count(session_id)
            if existing_count >= len(messages):
                return 0  # Already synced
            
            # Add messages that aren't in DB
            synced = 0
            for msg in messages[existing_count:]:
                await message_repo.add(
                    session_id=session_id,
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                )
                synced += 1
            
            logger.info(f"[Sync] Synced {synced} messages for session {session_id}")
            return synced
            
    except Exception as e:
        logger.warning(f"[Sync] Failed to sync messages for {session_id}: {e}")
        return 0


async def sync_graph_for_user(user_id: str) -> Optional[dict]:
    """
    Sync and cache graph data for a user.
    """
    from zep_service import get_zep_service
    from db import get_db_context
    from db.repositories import GraphRepository
    
    try:
        zep = get_zep_service()
        graph_data = await zep.get_graph_data(user_id, limit=100)
        
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        
        if nodes:
            async with get_db_context() as db:
                graph_repo = GraphRepository(db)
                await graph_repo.cache_nodes(user_id, nodes, edges)
        
        return graph_data
        
    except Exception as e:
        logger.warning(f"[Sync] Failed to sync graph for {user_id}: {e}")
        return None
