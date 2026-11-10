from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

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
from app.studio.modules import MODULE_BY_ID, MODULES
from app.studio.store import StudioStore

router = APIRouter(tags=["modules"])


class JobCreate(BaseModel):
    mode: str = ""
    prompt: str = ""
    params: dict[str, object] = Field(default_factory=dict)
    project_id: str | None = None


@router.get("/api/v1/modules")
async def list_modules(
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, list[dict[str, object]]]:
    items = []
    for module in MODULES:
        enriched = dict(module)
        enriched["job_count"] = len(store.list_jobs(module=str(module["id"]), limit=500))
        items.append(enriched)
    return {"items": items}


@router.post("/api/v1/modules/{module_id}/jobs", status_code=201)
async def create_module_job(
    module_id: str,
    payload: JobCreate,
    store: StudioStore = Depends(get_studio_store),
    credits: CreditService = Depends(get_credit_service),
    tenant_id: str = Depends(get_tenant_id),
    platform: PlatformStore = Depends(get_platform_store),
) -> dict[str, object]:
    module = MODULE_BY_ID.get(module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="module not found")
    modes = [str(mode) for mode in module["modes"]]
    if payload.mode and payload.mode not in modes:
        raise HTTPException(status_code=422, detail="unsupported mode")
    ensure_quota(store, platform, tenant_id, "jobs")

    mode = payload.mode or modes[0]
    quality = str(payload.params.get("quality") or "standard")
    cost = module_cost(module_id, mode, quality)
    job_id = uuid.uuid4().hex[:12]
    try:
        credits.reserve(tenant_id, cost, "module_job", job_id)
    except InsufficientCredits as exc:
        raise HTTPException(
            status_code=402,
            detail="积分不足，请充值或升级套餐",
        ) from exc

    try:
        job = store.create_job(
            module_id,
            mode,
            payload.prompt,
            payload.params,
            payload.project_id,
            job_id=job_id,
        )
    except KeyError as exc:
        credits.refund_ref(tenant_id, "module_job", job_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {**job, "credits_cost": cost}


@router.get("/api/v1/modules/{module_id}/jobs")
async def list_module_jobs(
    module_id: str,
    project_id: str | None = None,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, list[dict[str, object]]]:
    if module_id not in MODULE_BY_ID:
        raise HTTPException(status_code=404, detail="module not found")
    return {"items": store.list_jobs(module=module_id, project_id=project_id)}


@router.get("/api/v1/module-jobs")
async def list_all_jobs(
    project_id: str | None = None,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, list[dict[str, object]]]:
    return {"items": store.list_jobs(project_id=project_id)}


@router.get("/api/v1/module-jobs/{job_id}")
async def get_job(
    job_id: str,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@router.post("/api/v1/module-jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    store: StudioStore = Depends(get_studio_store),
    credits: CreditService = Depends(get_credit_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, str]:
    if not store.cancel_job(job_id):
        raise HTTPException(status_code=409, detail="only queued jobs can be canceled")
    credits.refund_ref(tenant_id, "module_job", job_id)
    return {"status": "canceled"}


@router.delete("/api/v1/module-jobs/{job_id}")
async def delete_job(
    job_id: str,
    store: StudioStore = Depends(get_studio_store),
    credits: CreditService = Depends(get_credit_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, str]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job["status"] == "running":
        raise HTTPException(status_code=409, detail="运行中的任务不能删除")
    if job["status"] == "queued":
        if not store.cancel_job(job_id):
            raise HTTPException(status_code=409, detail="任务状态已变化，请刷新")
        credits.refund_ref(tenant_id, "module_job", job_id)
    if not store.delete_job(job_id):
        raise HTTPException(status_code=409, detail="任务删除失败，请刷新")
    return {"status": "deleted"}
