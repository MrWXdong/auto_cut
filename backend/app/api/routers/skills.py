from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.skills import PromptSkill

router = APIRouter(tags=["skills"])


class PromptRequest(BaseModel):
    product: str
    platform: str = "抖音"
    style: str = "口播"


@router.post("/api/v1/skills/prompt")
async def generate_prompt(payload: PromptRequest) -> dict[str, object]:
    return await PromptSkill().run({}, payload.model_dump())


@router.post("/api/v1/skills/video")
async def generate_video() -> dict[str, object]:
    raise HTTPException(status_code=501, detail="video skill is a shell")


@router.post("/api/v1/skills/subtitle")
async def generate_subtitle() -> dict[str, object]:
    raise HTTPException(status_code=501, detail="subtitle skill is a shell")
