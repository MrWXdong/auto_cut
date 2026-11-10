from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_calendar_service, get_tenant_id
from app.studio.calendar import CalendarService

router = APIRouter(tags=["calendar"])

class CalendarGenerateRequest(BaseModel):
    direction: str = Field(min_length=1, max_length=80)
    start_date: str = Field(default_factory=lambda: date.today().isoformat())
    days: int = Field(default=7, ge=1, le=90)
    per_day: int = Field(default=1, ge=1, le=5)
    platforms: list[str] = Field(default_factory=lambda: ["抖音"])
    project_id: str | None = None


class CalendarUpdate(BaseModel):
    plan_date: str | None = None
    title: str | None = Field(default=None, max_length=180)
    angle: str | None = Field(default=None, max_length=300)
    hook: str | None = Field(default=None, max_length=240)
    format: str | None = Field(default=None, max_length=40)
    platform: str | None = Field(default=None, max_length=40)
    status: str | None = None
    notes: str | None = Field(default=None, max_length=1000)


@router.get("/api/v1/content-calendar")
async def list_calendar(
    start_date: str | None = None,
    end_date: str | None = None,
    status: str | None = None,
    project_id: str | None = None,
    service: CalendarService = Depends(get_calendar_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, list[dict[str, object]]]:
    return {
        "items": service.list_items(
            tenant_id,
            start_date=start_date,
            end_date=end_date,
            status=status,
            project_id=project_id,
        )
    }


@router.post("/api/v1/content-calendar/generate", status_code=201)
async def generate_calendar(
    payload: CalendarGenerateRequest,
    service: CalendarService = Depends(get_calendar_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    try:
        start = date.fromisoformat(payload.start_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="start_date must be YYYY-MM-DD") from exc
    items = await service.generate(
        payload.direction,
        payload.start_date,
        payload.days,
        payload.per_day,
        payload.platforms,
        payload.project_id,
        tenant_id,
    )
    end = (start + timedelta(days=payload.days - 1)).isoformat()
    return {
        "items": items,
        "start_date": payload.start_date,
        "end_date": end,
        "count": len(items),
    }


@router.patch("/api/v1/content-calendar/{item_id}")
async def update_calendar_item(
    item_id: str,
    payload: CalendarUpdate,
    service: CalendarService = Depends(get_calendar_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    item = service.update_item(
        item_id,
        payload.model_dump(exclude_none=True),
        tenant_id,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="calendar item not found")
    return item


@router.delete("/api/v1/content-calendar/{item_id}")
async def delete_calendar_item(
    item_id: str,
    service: CalendarService = Depends(get_calendar_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, str]:
    if not service.delete_item(item_id, tenant_id):
        raise HTTPException(status_code=404, detail="calendar item not found")
    return {"status": "deleted"}
