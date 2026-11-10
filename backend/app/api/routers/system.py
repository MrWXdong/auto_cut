from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_service, get_tenant_id
from app.config import get_settings
from app.service import JobService

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.environment,
        "app": settings.app_name,
    }


@router.get("/api/v1/meta")
async def meta() -> dict[str, object]:
    settings = get_settings()
    return {
        "name": "云流影",
        "version": "0.1.0",
        "demo_mode": settings.demo_mode,
        "features": {
            "auth": "demo",
            "chat_router": "ready",
            "prompt_skill": "ready",
            "video_skill": "ready",
            "rag": "ready",
            "model_gateway": "ready" if settings.llm_api_key else "needs_key",
            "billing": "demo",
            "workflow_canvas": "ready",
        },
    }


@router.get("/api/v1/system/workers")
async def workers(
    service: JobService = Depends(get_service),
    _tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    return service.store.list_workers()
