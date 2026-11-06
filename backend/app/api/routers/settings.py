from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.gateway.catalog import MODEL_CATALOG

router = APIRouter(tags=["settings"])


@router.get("/api/v1/settings/models")
async def list_models() -> dict[str, object]:
    return {"items": MODEL_CATALOG}


@router.put("/api/v1/settings/models")
async def update_models() -> dict[str, object]:
    raise HTTPException(status_code=501, detail="model settings are a shell")
