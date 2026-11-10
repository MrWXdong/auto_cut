from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_platform_store,
    get_service,
    get_studio_store,
    get_tenant_id,
)
from app.auth.service import DemoUser
from app.gateway.catalog import MODEL_CATALOG
from app.platform.store import PLANS, PlatformStore
from app.service import JobService
from app.studio.store import StudioStore

router = APIRouter(tags=["admin"])

@router.get("/api/v1/admin/overview")
async def overview(
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    usage = store.usage()
    jobs = store.list_jobs(limit=500)
    status_counts: dict[str, int] = {}
    for job in jobs:
        status = str(job["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "usage": usage,
        "job_status": status_counts,
        "feedback": store.feedback_summary(),
        "recent_logs": store.list_logs(limit=20),
    }


@router.get("/api/v1/admin/logs")
async def logs(
    limit: int = 100,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, list[dict[str, object]]]:
    return {"items": store.list_logs(limit=max(1, min(limit, 500)))}


@router.get("/api/v1/admin/users")
async def users() -> dict[str, list[dict[str, object]]]:
    return {"items": [DemoUser]}


@router.get("/api/v1/admin/models")
async def models() -> dict[str, list[dict[str, object]]]:
    return {"items": MODEL_CATALOG}


@router.get("/api/v1/quotas")
async def quotas(
    store: StudioStore = Depends(get_studio_store),
    service: JobService = Depends(get_service),
    platform: PlatformStore = Depends(get_platform_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    usage = store.usage()
    tenant = platform.get_tenant(tenant_id)
    plan = PLANS.get(str(tenant["plan"]), PLANS["trial"]) if tenant else PLANS["trial"]
    storage_gb = int(tenant["storage_gb"]) if tenant else 0
    storage_used = int(usage.get("asset_bytes", 0)) + service.store.storage_bytes(
        tenant_id
    )
    items = [
        {
            "kind": kind,
            "used": int(usage.get(kind, 0)),
            "limit": int(plan.get(kind, 0)),
            "unit": "个",
        }
        for kind in ("projects", "assets", "scripts")
    ]
    items.append(
        {
            "kind": "jobs",
            "used": int(usage.get("jobs_total", 0)),
            "limit": int(plan.get("jobs", 0)),
            "unit": "个",
        }
    )
    items.append(
        {
            "kind": "storage_bytes",
            "used": storage_used,
            "limit": storage_gb * 1024 * 1024 * 1024,
            "unit": "bytes",
        }
    )
    return {
        "period": "current",
        "items": items,
    }
