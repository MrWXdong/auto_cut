from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["knowledge"])

_KNOWLEDGE_BASES: list[dict[str, object]] = []


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str = ""


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.get("/api/v1/knowledge-bases")
async def list_knowledge_bases() -> dict[str, list[dict[str, object]]]:
    return {"items": _KNOWLEDGE_BASES}


@router.post("/api/v1/knowledge-bases", status_code=201)
async def create_knowledge_base(payload: KnowledgeBaseCreate) -> dict[str, object]:
    item = {
        "id": uuid.uuid4().hex[:8],
        "name": payload.name,
        "description": payload.description,
        "document_count": 0,
        "status": "empty",
    }
    _KNOWLEDGE_BASES.append(item)
    return item


@router.post("/api/v1/knowledge-bases/{kb_id}/search")
async def search_knowledge_base(kb_id: str, payload: SearchRequest) -> dict[str, object]:
    return {
        "hits": [],
        "shell": True,
        "message": "retrieval is a shell; pgvector is not connected yet",
    }
