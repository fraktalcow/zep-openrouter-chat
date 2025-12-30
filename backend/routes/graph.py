"""Graph visualization routes with PostgreSQL caching."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from zep_service import get_zep_service
from db import get_db
from db.repositories import GraphRepository
from logger import logger

router = APIRouter()


async def _cache_graph(user_id: str, nodes: list, edges: list):
    """Background task to cache graph data."""
    try:
        from db import get_db_context
        async with get_db_context() as db:
            graph_repo = GraphRepository(db)
            await graph_repo.cache_nodes(user_id, nodes, edges)
    except Exception as e:
        logger.warning(f"Failed to cache graph: {e}")


@router.get("/{user_id}")
async def get_graph_data(
    user_id: str, 
    limit: int = 100, 
    refresh: bool = False,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve knowledge graph data for visualization.
    Uses PostgreSQL cache by default, fetches from Zep if cache is stale or refresh=True.
    """
    graph_repo = GraphRepository(db)
    
    # Try cache first (unless refresh requested)
    if not refresh:
        cached = await graph_repo.get_cached(user_id)
        if cached:
            logger.info(f"[Graph] Returning cached data for {user_id}")
            return cached
    
    # Fetch from Zep
    try:
        graph_data = await get_zep_service().get_graph_data(user_id, limit)
        
        # Cache in background
        if background_tasks and graph_data.get("nodes"):
            background_tasks.add_task(
                _cache_graph, 
                user_id, 
                graph_data.get("nodes", []), 
                graph_data.get("edges", [])
            )
        
        return graph_data
        
    except Exception as e:
        logger.error(f"Error fetching graph from Zep: {e}")
        
        # Try returning stale cache as fallback
        cached = await graph_repo.get_cached(user_id, max_age_hours=168)  # 1 week
        if cached:
            cached["stale"] = True
            return cached
        
        raise HTTPException(status_code=500, detail=f"Error fetching graph: {str(e)}")


@router.delete("/{user_id}/cache")
async def invalidate_graph_cache(user_id: str, db: AsyncSession = Depends(get_db)):
    """Invalidate the graph cache for a user."""
    graph_repo = GraphRepository(db)
    count = await graph_repo.invalidate(user_id)
    return {"invalidated": count, "user_id": user_id}
