"""
Graph repository - caching Zep graph data in PostgreSQL.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import GraphCache
from logger import logger


class GraphRepository:
    """Repository for caching Zep graph data."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def cache_nodes(self, user_id: str, nodes: list[dict], edges: list[dict]) -> int:
        """Cache graph nodes and edges for a user. Returns count cached."""
        # Clear old cache for this user
        await self.db.execute(
            delete(GraphCache).where(GraphCache.user_id == user_id)
        )
        
        count = 0
        for node in nodes:
            node_uuid = node.get("uuid") or node.get("node_uuid")
            if not node_uuid:
                continue
            
            # Find edges connected to this node
            connected_edges = [
                e for e in edges 
                if e.get("source") == node_uuid or e.get("target") == node_uuid
            ]
            
            cache_entry = GraphCache(
                user_id=user_id,
                node_uuid=node_uuid,
                node_name=node.get("name", ""),
                summary=node.get("summary"),
                node_type=node.get("type", "unknown"),
                edges=connected_edges if connected_edges else None,
            )
            self.db.add(cache_entry)
            count += 1
        
        await self.db.flush()
        logger.info(f"[DB] Cached {count} graph nodes for user {user_id}")
        return count
    
    async def get_cached(self, user_id: str, max_age_hours: int = 24) -> Optional[dict]:
        """Get cached graph data if fresh enough."""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        result = await self.db.execute(
            select(GraphCache)
            .where(GraphCache.user_id == user_id)
            .where(GraphCache.synced_at >= cutoff)
        )
        cached = list(result.scalars().all())
        
        if not cached:
            return None
        
        nodes = []
        edges = []
        seen_edges = set()
        
        for c in cached:
            nodes.append({
                "uuid": c.node_uuid,
                "name": c.node_name,
                "summary": c.summary,
                "type": c.node_type,
            })
            if c.edges:
                for e in c.edges:
                    edge_id = e.get("uuid")
                    if edge_id and edge_id not in seen_edges:
                        edges.append(e)
                        seen_edges.add(edge_id)
        
        return {"nodes": nodes, "edges": edges, "user_id": user_id, "cached": True}
    
    async def invalidate(self, user_id: str) -> int:
        """Invalidate cache for a user. Returns count deleted."""
        result = await self.db.execute(
            delete(GraphCache).where(GraphCache.user_id == user_id)
        )
        await self.db.flush()
        return result.rowcount
