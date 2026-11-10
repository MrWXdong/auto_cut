from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_credit_service, get_studio_store, get_tenant_id
from app.billing.credits import CreditService, InsufficientCredits
from app.billing.pricing import module_cost
from app.studio.store import StudioStore

router = APIRouter(tags=["styles"])

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class StyleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    prompt: str = Field(default="", max_length=2000)
    negative_prompt: str = Field(default="", max_length=1000)
    model_ref: str = Field(default="", max_length=120)
    palette: list[str] = Field(
        default_factory=lambda: ["#0f766e", "#2563eb"],
        max_length=6,
    )
    shot_rhythm: str = Field(default="中速", max_length=40)
    subtitle_style: str = Field(default="白字黑边", max_length=80)
    lora_name: str = Field(default="", max_length=80)
    lora_trigger: str = Field(default="", max_length=120)
    lora_base_model: str = Field(default="", max_length=120)
    lora_status: str = Field(default="none", max_length=40)


class StyleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    prompt: str | None = Field(default=None, max_length=2000)
    negative_prompt: str | None = Field(default=None, max_length=1000)
    model_ref: str | None = Field(default=None, max_length=120)
    palette: list[str] | None = Field(default=None, max_length=6)
    shot_rhythm: str | None = Field(default=None, max_length=40)
    subtitle_style: str | None = Field(default=None, max_length=80)
    lora_name: str | None = Field(default=None, max_length=80)
    lora_trigger: str | None = Field(default=None, max_length=120)
    lora_base_model: str | None = Field(default=None, max_length=120)
    lora_status: str | None = Field(default=None, max_length=40)


class LoraTrainRequest(BaseModel):
    project_id: str


def _validate_palette(palette: list[str] | None) -> None:
    if palette is None:
        return
    if any(not HEX_COLOR.fullmatch(color) for color in palette):
        raise HTTPException(status_code=422, detail="palette colors must be #RRGGBB")


@router.get("/api/v1/styles")
async def list_styles(
    store: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, list[dict[str, object]]]:
    return {"items": store.list_styles(tenant_id)}


@router.post("/api/v1/styles", status_code=201)
async def create_style(
    payload: StyleCreate,
    store: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    values = payload.model_dump()
    _validate_palette(values.get("palette"))
    try:
        return store.create_style(values, tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/v1/styles/{style_id}")
async def get_style(
    style_id: str,
    store: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    style = store.get_style(style_id, tenant_id)
    if style is None:
        raise HTTPException(status_code=404, detail="style not found")
    return style


@router.patch("/api/v1/styles/{style_id}")
async def update_style(
    style_id: str,
    payload: StyleUpdate,
    store: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    values = payload.model_dump(exclude_none=True)
    _validate_palette(values.get("palette"))
    style = store.update_style(style_id, values, tenant_id)
    if style is None:
        raise HTTPException(status_code=404, detail="style not found")
    return style


@router.delete("/api/v1/styles/{style_id}")
async def delete_style(
    style_id: str,
    store: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, str]:
    if not store.delete_style(style_id, tenant_id):
        raise HTTPException(status_code=404, detail="style not found")
    return {"status": "deleted"}


@router.post("/api/v1/styles/{style_id}/default")
async def set_default_style(
    style_id: str,
    store: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    style = store.set_default_style(style_id, tenant_id)
    if style is None:
        raise HTTPException(status_code=404, detail="style not found")
    return style


@router.post("/api/v1/styles/{style_id}/lora/train", status_code=202)
async def train_lora(
    style_id: str,
    payload: LoraTrainRequest,
    store: StudioStore = Depends(get_studio_store),
    credits: CreditService = Depends(get_credit_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    style = store.get_style(style_id, tenant_id)
    if style is None:
        raise HTTPException(status_code=404, detail="style not found")
    if store.get_project(payload.project_id, tenant_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    images = [
        asset
        for asset in store.list_assets(payload.project_id, tenant_id)
        if asset["kind"] == "image"
    ]
    if len(images) < 3:
        raise HTTPException(status_code=422, detail="至少需要 3 张图片素材才能训练 LoRA")

    cost = module_cost("lora", "train", "standard")
    job_id = uuid.uuid4().hex[:12]
    try:
        credits.reserve(tenant_id, cost, "module_job", job_id)
    except InsufficientCredits as exc:
        raise HTTPException(status_code=402, detail="积分不足，请充值或升级套餐") from exc

    try:
        job = store.create_job(
            "lora",
            "train",
            str(style.get("lora_name") or style["name"]),
            {
                "style_id": style_id,
                "lora_name": style.get("lora_name") or "",
                "trigger": style.get("lora_trigger") or "",
                "base_model": style.get("lora_base_model") or "",
                "dataset_assets": [asset["id"] for asset in images],
            },
            payload.project_id,
            tenant_id,
            job_id=job_id,
        )
    except Exception:
        credits.refund_ref(tenant_id, "module_job", job_id)
        raise

    store.update_style(
        style_id,
        {"lora_status": "queued", "lora_job_id": job_id},
        tenant_id,
    )
    return {**job, "credits_cost": cost}
