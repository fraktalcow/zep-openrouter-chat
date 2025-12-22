import json
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from zep_service import get_zep_service

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_SCHEMA = {
    "entities": [
        {"name": "Project", "description": "A software project or initiative"},
        {"name": "Technology", "description": "A language, framework, tool, or API"},
        {"name": "Preference", "description": "A persistent user preference or trait"},
    ],
    "edges": [
        {"name": "USES", "description": "Project makes use of a technology"},
        {"name": "DEVELOPED_BY", "description": "Project created or owned by a person"},
        {"name": "LIKES", "description": "User preference or affinity"},
    ]
}


class SchemaRequest(BaseModel):
    entities: List[Dict[str, str]]
    edges: List[Dict[str, str]]


def load_schema():
    schema_path = BASE_DIR / "schema.json"
    if not schema_path.exists():
        with open(schema_path, "w") as f:
            json.dump(DEFAULT_SCHEMA, f, indent=2)
    
    with open(schema_path, "r") as f:
        return json.load(f)


@router.get("")
async def get_schema():
    return load_schema()


@router.post("")
async def update_schema(request: SchemaRequest):
    schema_path = BASE_DIR / "schema.json"
    schema = {"entities": request.entities, "edges": request.edges}
    with open(schema_path, "w") as f:
        json.dump(schema, f, indent=2)
    
    await get_zep_service().ensure_ontology(request.entities, request.edges)
    return {"status": "success", "message": "Schema updated and ontology ensured."}

