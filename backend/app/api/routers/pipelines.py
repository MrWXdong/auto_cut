from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import (
    get_credit_service,
    get_platform_store,
    get_studio_store,
    get_tenant_id,
)
from app.billing.credits import CreditService, InsufficientCredits
from app.billing.pricing import module_cost
from app.billing.quota_guard import ensure_quota
from app.platform.store import PlatformStore
from app.studio.pipelines import PIPELINE_TEMPLATE_BY_ID, PIPELINE_TEMPLATES
from app.studio.store import StudioStore

router = APIRouter(tags=["pipelines"])


class StepInput(BaseModel):
    module: str
    mode: str = ""
    prompt: str = ""


class PipelineCreate(BaseModel):
    name: str = ""
    project_id: str | None = None
    template: str | None = None
    steps: list[StepInput] | None = None


@router.get("/api/v1/pipeline-templates")
async def list_pipeline_templates() -> dict[str, object]:
    return {"items": PIPELINE_TEMPLATES}


@router.get("/api/v1/pipelines")
async def list_pipelines(
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, list[dict[str, object]]]:
    return {"items": store.list_pipelines()}


@router.post("/api/v1/pipelines", status_code=201)
async def create_pipeline(
    payload: PipelineCreate,
    store: StudioStore = Depends(get_studio_store),
    credits: CreditService = Depends(get_credit_service),
    tenant_id: str = Depends(get_tenant_id),
    platform: PlatformStore = Depends(get_platform_store),
) -> dict[str, object]:
    if payload.steps:
        steps = [step.model_dump() for step in payload.steps]
        name = payload.name.strip() or "自定义流水线"
        template = ""
    elif payload.template:
        template_config = PIPELINE_TEMPLATE_BY_ID.get(payload.template)
        if template_config is None:
            raise HTTPException(status_code=404, detail="pipeline template not found")
        steps = list(template_config["steps"])
        name = payload.name.strip() or str(template_config["name"])
        template = payload.template
    else:
        raise HTTPException(status_code=422, detail="template or steps is required")
    ensure_quota(store, platform, tenant_id, "jobs")

    pipeline_id = uuid.uuid4().hex[:12]
    cost = sum(
        module_cost(str(step.get("module") or ""), str(step.get("mode") or ""))
        for step in steps
    )
    try:
        credits.reserve(tenant_id, cost, "pipeline", pipeline_id)
    except InsufficientCredits as exc:
        raise HTTPException(
            status_code=402,
            detail="积分不足，请充值或升级套餐",
        ) from exc

    try:
        pipeline = store.create_pipeline(
            name,
            steps,
            template,
            payload.project_id,
            pipeline_id=pipeline_id,
        )
    except KeyError as exc:
        credits.refund_ref(tenant_id, "pipeline", pipeline_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        credits.refund_ref(tenant_id, "pipeline", pipeline_id)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {**pipeline, "credits_cost": cost}


@router.get("/api/v1/pipelines/{pipeline_id}")
async def get_pipeline(
    pipeline_id: str,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    pipeline = store.get_pipeline(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="pipeline not found")
    return pipeline


@router.post("/api/v1/pipelines/{pipeline_id}/cancel")
async def cancel_pipeline(
    pipeline_id: str,
    store: StudioStore = Depends(get_studio_store),
    credits: CreditService = Depends(get_credit_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, str]:
    if not store.cancel_pipeline(pipeline_id):
        raise HTTPException(status_code=409, detail="only queued pipelines can be canceled")
    credits.refund_ref(tenant_id, "pipeline", pipeline_id)
    return {"status": "canceled"}


@router.delete("/api/v1/pipelines/{pipeline_id}")
async def delete_pipeline(
    pipeline_id: str,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, str]:
    if not store.delete_pipeline(pipeline_id):
        raise HTTPException(status_code=404, detail="pipeline not found")
    return {"status": "deleted"}
