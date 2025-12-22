from fastapi import APIRouter, HTTPException

from zep_service import get_zep_service

router = APIRouter()


@router.get("/{user_id}")
async def get_graph_data(user_id: str, limit: int = 100):
    """
    Retrieve knowledge graph data for visualization from Zep.
    """
    try:
        graph_data = await get_zep_service().get_graph_data(user_id, limit)
        return graph_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching graph: {str(e)}")

