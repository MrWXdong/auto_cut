from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_platform_store
from app.auth.security import issue_token
from app.config import get_settings
from app.platform.store import PLANS, PlatformStore

router = APIRouter(tags=["public"])


class SignupRequest(BaseModel):
    plan: str = "trial"
    company_name: str
    owner_email: str
    owner_password: str = Field(min_length=4)
    owner_name: str = "Owner"
    activation_code: str


class CheckoutRequest(BaseModel):
    plan: str
    company_name: str
    owner_email: str
    owner_password: str = Field(min_length=4)
    owner_name: str = "Owner"
    provider: str = "manual"


class PaymentWebhookRequest(BaseModel):
    order_id: str
    external_id: str | None = None
    status: str = "paid"


def _tenant_token(user: dict[str, object]) -> str:
    return issue_token(
        {
            "scope": "tenant",
            "sub": user["id"],
            "tenant_id": user["tenant_id"],
            "role": user["role"],
            "email": user["email"],
            "name": user["name"],
        },
        get_settings().auth_secret,
    )


@router.get("/api/v1/public/plans")
async def public_plans() -> dict[str, list[dict[str, object]]]:
    return {
        "items": [{"id": key, **value} for key, value in PLANS.items()]
    }


@router.post("/api/v1/public/signup", status_code=201)
async def public_signup(
    payload: SignupRequest,
    store: PlatformStore = Depends(get_platform_store),
) -> dict[str, object]:
    try:
        result = store.redeem_activation_code(
            payload.activation_code,
            payload.company_name,
            payload.owner_email,
            payload.owner_password,
            payload.owner_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user = result.get("user")
    if not isinstance(user, dict):
        raise HTTPException(status_code=500, detail="开通失败，请联系平台")
    return {
        "access_token": _tenant_token(user),
        "token_type": "bearer",
        "user": user,
        "tenant": result.get("tenant"),
        "plan": result.get("plan"),
    }


@router.post("/api/v1/public/checkout", status_code=201)
async def public_checkout(
    payload: CheckoutRequest,
    store: PlatformStore = Depends(get_platform_store),
) -> dict[str, object]:
    try:
        order = store.create_order(
            plan=payload.plan,
            company_name=payload.company_name,
            owner_email=payload.owner_email,
            owner_name=payload.owner_name,
            owner_password=payload.owner_password,
            provider=payload.provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "order": order,
        "payment_url": None,
        "message": "支付渠道未配置，请接入微信/支付宝/Stripe 后使用回调开通",
    }


@router.post("/api/v1/public/payments/webhook")
async def payment_webhook(
    payload: PaymentWebhookRequest,
    x_payment_secret: str | None = Header(default=None, alias="X-Payment-Secret"),
    store: PlatformStore = Depends(get_platform_store),
) -> dict[str, object]:
    settings = get_settings()
    if not settings.payment_webhook_secret:
        raise HTTPException(status_code=501, detail="支付回调未配置")
    if not x_payment_secret or not hmac.compare_digest(
        x_payment_secret,
        settings.payment_webhook_secret,
    ):
        raise HTTPException(status_code=401, detail="invalid webhook secret")
    if payload.status != "paid":
        raise HTTPException(status_code=422, detail="unsupported payment status")

    try:
        result = store.mark_order_paid(payload.order_id, payload.external_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result
