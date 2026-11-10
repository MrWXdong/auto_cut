from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_credit_service, get_platform_store, get_tenant_id
from app.billing.credits import CreditService
from app.config import get_settings
from app.platform.store import PLANS, PlatformStore

router = APIRouter(tags=["billing"])


class RedeemRequest(BaseModel):
    code: str


class PlanUpgradeRequest(BaseModel):
    plan: str


@router.get("/api/v1/billing/plan")
async def get_plan(
    store: PlatformStore = Depends(get_platform_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    tenant = store.get_tenant(tenant_id)
    plan_id = str(tenant["plan"]) if tenant else "trial"
    plan = PLANS.get(plan_id, PLANS["trial"])
    return {
        "code": plan_id,
        "name": plan["name"],
        "price_cents": plan["price_cents"],
        "price_monthly_cents": plan["price_monthly_cents"],
        "price_yearly_cents": plan["price_yearly_cents"],
        "credits": plan["credits"],
        "period": "month",
        "limits": {
            "credits": plan["credits"],
            "render_minutes": plan["render_minutes"],
            "storage_gb": plan["storage_gb"],
            "concurrency": plan["concurrency"],
            "seats": plan["seats"],
        },
    }


@router.get("/api/v1/billing/usage")
async def get_usage(
    credits: CreditService = Depends(get_credit_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    balance = credits.balance(tenant_id)
    return {
        "period": "2026-11",
        "items": [
            {"kind": "credits", "used": balance, "limit": balance, "unit": "点"},
        ],
    }


@router.post("/api/v1/billing/redeem")
async def redeem(payload: RedeemRequest) -> dict[str, object]:
    raise HTTPException(status_code=501, detail="redeem is a shell")


@router.get("/api/v1/billing/credits")
async def get_credits(
    store: PlatformStore = Depends(get_platform_store),
    credits: CreditService = Depends(get_credit_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    tenant = store.get_tenant(tenant_id)
    return {
        "tenant_id": tenant_id,
        "balance": credits.balance(tenant_id),
        "plan": tenant,
        "ledger": credits.ledger(tenant_id, limit=30),
    }


@router.post("/api/v1/billing/upgrade")
async def upgrade_plan(
    payload: PlanUpgradeRequest,
    store: PlatformStore = Depends(get_platform_store),
    credits: CreditService = Depends(get_credit_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    if not get_settings().demo_mode:
        raise HTTPException(
            status_code=501,
            detail="在线升级支付接入中，请联系平台开通",
        )
    if payload.plan not in PLANS:
        raise HTTPException(status_code=422, detail="unknown plan")
    tenant = store.get_tenant(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="tenant not found")
    if tenant["plan"] == payload.plan:
        raise HTTPException(status_code=409, detail="已经是当前套餐")

    old_plan = PLANS.get(str(tenant["plan"]), PLANS["trial"])
    new_plan = PLANS[payload.plan]
    if new_plan["credits"] < old_plan["credits"]:
        raise HTTPException(status_code=422, detail="暂不支持降级")

    granted = max(0, new_plan["credits"] - old_plan["credits"])
    updated = store.update_tenant(
        tenant_id,
        {
            "plan": payload.plan,
            "credits": new_plan["credits"],
            "seats": new_plan["seats"],
            "render_minutes": new_plan["render_minutes"],
            "storage_gb": new_plan["storage_gb"],
            "concurrency": new_plan["concurrency"],
        },
    )
    if granted:
        credits.grant(tenant_id, granted, f"upgrade {tenant['plan']} -> {payload.plan}")
    return {
        "tenant": updated,
        "plan": payload.plan,
        "granted": granted,
        "balance": credits.balance(tenant_id),
    }
