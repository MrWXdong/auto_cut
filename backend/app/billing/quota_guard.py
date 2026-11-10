from __future__ import annotations

from fastapi import HTTPException

from app.platform.store import PLANS, PlatformStore
from app.studio.store import StudioStore

KIND_LABELS = {
    "projects": "项目",
    "assets": "素材",
    "scripts": "文案",
    "jobs": "任务",
}


def ensure_quota(
    studio: StudioStore,
    platform: PlatformStore,
    tenant_id: str,
    kind: str,
) -> None:
    tenant = platform.get_tenant(tenant_id)
    if tenant is None:
        return
    plan = PLANS.get(str(tenant["plan"]), PLANS["trial"])
    limit = int(plan.get(kind, 0))
    if limit <= 0:
        return
    usage = studio.usage(tenant_id)
    used = int(usage.get("jobs_total" if kind == "jobs" else kind, 0))
    if used < limit:
        return
    label = KIND_LABELS.get(kind, kind)
    raise HTTPException(
        status_code=402,
        detail=f"{label}数量已达套餐上限（{used}/{limit}），请升级套餐或清理已有内容",
    )
