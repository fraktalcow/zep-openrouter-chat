from fastapi import APIRouter, HTTPException

from zep_service import ZepService

router = APIRouter()


# This will be injected by server.py
zep_service: ZepService = None



def init_services(zep: ZepService):
    global zep_service
    zep_service = zep


@router.get("/{user_id}")
async def get_graph_data(user_id: str, limit: int = 100, source: str = "zep"):
    """
    Retrieve knowledge graph data for visualization.
    Returns nodes and edges from either Zep or local GraphRAG.
    
    Query params:
        source: "zep" (default) or "local" to choose graph source
    """
    try:
        graph_data = await zep_service.get_graph_data(user_id, limit)
        return graph_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching graph: {str(e)}")

