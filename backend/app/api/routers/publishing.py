from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_publish_service, get_studio_store, get_tenant_id
from app.studio.publishing import PublishService
from app.studio.store import StudioStore

router = APIRouter(tags=["publishing"])

class AccountCreate(BaseModel):
    platform: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    handle: str = Field(default="", max_length=120)
    status: str = "active"
    followers: int = 0
    notes: str = Field(default="", max_length=500)


class AccountUpdate(BaseModel):
    platform: str | None = None
    name: str | None = None
    handle: str | None = None
    status: str | None = None
    followers: int | None = None
    notes: str | None = None


class PublishJobCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    scheduled_at: str
    account_id: str | None = None
    platform: str | None = None
    project_id: str | None = None
    asset_id: str | None = None
    notes: str = Field(default="", max_length=1000)


class PublishJobUpdate(BaseModel):
    title: str | None = None
    scheduled_at: str | None = None
    notes: str | None = None


class PublishResult(BaseModel):
    result_url: str = Field(default="", max_length=1000)


@router.get("/api/v1/publish/accounts")
async def list_publish_accounts(
    service: PublishService = Depends(get_publish_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, list[dict[str, object]]]:
    return {"items": service.list_accounts(tenant_id)}


@router.post("/api/v1/publish/accounts", status_code=201)
async def create_publish_account(
    payload: AccountCreate,
    service: PublishService = Depends(get_publish_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    try:
        return service.create_account(payload.model_dump(), tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/api/v1/publish/accounts/{account_id}")
async def update_publish_account(
    account_id: str,
    payload: AccountUpdate,
    service: PublishService = Depends(get_publish_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    account = service.update_account(
        account_id,
        payload.model_dump(exclude_none=True),
        tenant_id,
    )
    if account is None:
        raise HTTPException(status_code=404, detail="publish account not found")
    return account


@router.delete("/api/v1/publish/accounts/{account_id}")
async def delete_publish_account(
    account_id: str,
    service: PublishService = Depends(get_publish_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, str]:
    if not service.delete_account(account_id, tenant_id):
        raise HTTPException(status_code=404, detail="publish account not found")
    return {"status": "deleted"}


@router.get("/api/v1/publish/jobs")
async def list_publish_jobs(
    limit: int = 200,
    service: PublishService = Depends(get_publish_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, list[dict[str, object]]]:
    return {"items": service.list_jobs(tenant_id, limit)}


@router.post("/api/v1/publish/jobs", status_code=201)
async def create_publish_job(
    payload: PublishJobCreate,
    service: PublishService = Depends(get_publish_service),
    studio: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    values = payload.model_dump()
    if payload.project_id and studio.get_project(payload.project_id, tenant_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    if payload.asset_id and studio.get_asset(payload.asset_id, tenant_id) is None:
        raise HTTPException(status_code=404, detail="asset not found")
    if not payload.account_id and not payload.platform:
        raise HTTPException(status_code=422, detail="请选择发布账号或填写平台")
    try:
        return service.create_job(values, tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/api/v1/publish/jobs/{job_id}")
async def update_publish_job(
    job_id: str,
    payload: PublishJobUpdate,
    service: PublishService = Depends(get_publish_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    job = service.update_job(
        job_id,
        payload.model_dump(exclude_none=True),
        tenant_id,
    )
    if job is None:
        raise HTTPException(status_code=404, detail="publish job not found")
    return job


@router.post("/api/v1/publish/jobs/{job_id}/run")
async def run_publish_job(
    job_id: str,
    service: PublishService = Depends(get_publish_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    job = service.get_job(job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="publish job not found")
    if job["status"] == "published":
        return job
    updated = service.update_job(
        job_id,
        {
            "status": "manual_required",
            "error": "平台开放接口尚未授权，请手动发布后标记完成",
        },
        tenant_id,
    )
    return updated or job


@router.post("/api/v1/publish/jobs/{job_id}/published")
async def mark_publish_job_published(
    job_id: str,
    payload: PublishResult,
    service: PublishService = Depends(get_publish_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    job = service.mark_published(job_id, payload.result_url, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="publish job not found")
    return job


@router.post("/api/v1/publish/jobs/{job_id}/cancel")
async def cancel_publish_job(
    job_id: str,
    service: PublishService = Depends(get_publish_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    try:
        job = service.cancel_job(job_id, tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="publish job not found")
    return job


@router.delete("/api/v1/publish/jobs/{job_id}")
async def delete_publish_job(
    job_id: str,
    service: PublishService = Depends(get_publish_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, str]:
    if not service.delete_job(job_id, tenant_id):
        raise HTTPException(status_code=404, detail="publish job not found")
    return {"status": "deleted"}
