from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import get_trend_service
from app.studio.trends import TrendFetchError, TrendService

router = APIRouter(tags=["trends"])


class CustomTrendSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    url: str = Field(min_length=8, max_length=1000)


@router.get("/api/v1/trends/sources")
async def list_trend_sources(
    service: TrendService = Depends(get_trend_service),
) -> dict[str, list[dict[str, object]]]:
    return {"items": service.list_sources()}


@router.post("/api/v1/trends/custom-sources", status_code=201)
async def create_custom_trend_source(
    payload: CustomTrendSourceCreate,
    service: TrendService = Depends(get_trend_service),
) -> dict[str, object]:
    try:
        return service.add_custom_source(payload.name, payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/api/v1/trends/custom-sources/{source_id}")
async def delete_custom_trend_source(
    source_id: str,
    service: TrendService = Depends(get_trend_service),
) -> dict[str, str]:
    if not service.delete_custom_source(source_id):
        raise HTTPException(status_code=404, detail="custom trend source not found")
    return {"status": "deleted"}


@router.get("/api/v1/trends/related")
async def related_trends(
    direction: str = Query(min_length=1, max_length=50),
    limit: int = Query(default=50, ge=1, le=200),
    use_ai: bool = Query(default=True),
    service: TrendService = Depends(get_trend_service),
) -> dict[str, object]:
    try:
        return await service.related(direction, limit=limit, use_ai=use_ai)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/v1/trends")
async def list_trends(
    source: str = Query(default="weibo"),
    limit: int = Query(default=30, ge=1, le=200),
    refresh: bool = Query(default=False),
    service: TrendService = Depends(get_trend_service),
) -> dict[str, object]:
    try:
        return await service.fetch(source, limit=limit, force=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TrendFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"热点平台暂时不可用：{exc}",
        ) from exc
