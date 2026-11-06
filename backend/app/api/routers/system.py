from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings

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
    return {
        "name": "AutoCut",
        "version": "0.1.0",
        "demo_mode": get_settings().demo_mode,
        "features": {
            "auth": "shell",
            "chat_router": "ready",
            "prompt_skill": "ready",
            "video_skill": "shell",
            "rag": "shell",
            "model_gateway": "partial",
            "billing": "shell",
            "workflow_canvas": "planned",
        },
    }
