from fastapi import APIRouter, HTTPException

from openrouter_service import OpenRouterService

router = APIRouter()


# This will be injected by server.py
openrouter_service: OpenRouterService = None


def init_services(openrouter: OpenRouterService):
    global openrouter_service
    openrouter_service = openrouter


@router.get("/search")
async def search_models(query: str = "", free_only: bool = False, limit: int = 50):
    """
    Search for models by name/description with autocomplete-style filtering.
    
    Query params:
        query: Search string (case-insensitive, searches in id, name, description)
        free_only: If true, only return free models
        limit: Maximum number of results (default 50)
    
    Example: /models/search?query=llama&free_only=true&limit=10
    """
    try:
        models = await openrouter_service.search_models(
            query=query,
            free_only=free_only,
            limit=limit
        )
        return {
            "models": models,
            "count": len(models),
            "query": query,
            "free_only": free_only
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching models: {str(e)}")


@router.get("/all")
async def get_all_models(force_refresh: bool = False):
    """
    Get all available models from OpenRouter.
    Results are cached for 1 hour unless force_refresh=true.
    
    Query params:
        force_refresh: Force refresh the cache
    """
    try:
        models = await openrouter_service.fetch_all_models(force_refresh=force_refresh)
        return {
            "models": models,
            "count": len(models)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching models: {str(e)}")

