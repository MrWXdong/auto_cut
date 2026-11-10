from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_platform_store, get_studio_store, require_platform
from app.auth.security import issue_token
from app.config import get_settings
from app.platform.store import PLANS, PlatformStore
from app.studio.store import StudioStore

router = APIRouter(tags=["platform"])


class PlatformLoginRequest(BaseModel):
    email: str
    password: str


class TenantCreate(BaseModel):
    name: str
    plan: str = "trial"
    owner_email: str
    owner_password: str = Field(min_length=4)
    owner_name: str = "Owner"


class TenantUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    plan: str | None = None
    seats: int | None = None
    render_minutes: int | None = None
    storage_gb: int | None = None
    concurrency: int | None = None


class ActivationCodeCreate(BaseModel):
    plan: str = "basic"
    count: int = 1
    duration_days: int = 30


class ScriptStyleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    prompt: str = Field(default="", max_length=1000)
    sort_order: int | None = None
    enabled: bool = True


class ScriptStyleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    prompt: str | None = Field(default=None, max_length=1000)
    sort_order: int | None = None
    enabled: bool | None = None


@router.post("/api/v1/platform/auth/login")
async def platform_login(
    payload: PlatformLoginRequest,
    store: PlatformStore = Depends(get_platform_store),
) -> dict[str, object]:
    admin = store.verify_platform_admin(payload.email, payload.password)
    if admin is None:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    token = issue_token(
        {
            "scope": "platform",
            "sub": admin["id"],
            "email": admin["email"],
            "name": admin["name"],
        },
        get_settings().auth_secret,
    )
    return {"access_token": token, "token_type": "bearer", "admin": admin}


@router.get("/api/v1/platform/plans")
async def list_plans(
    _: dict[str, object] = Depends(require_platform),
) -> dict[str, list[dict[str, object]]]:
    return {
        "items": [{"id": key, **value} for key, value in PLANS.items()]
    }


@router.get("/api/v1/platform/overview")
async def platform_overview(
    store: PlatformStore = Depends(get_platform_store),
    studio: StudioStore = Depends(get_studio_store),
    _: dict[str, object] = Depends(require_platform),
) -> dict[str, object]:
    tenants = store.list_tenants()
    jobs = studio.list_jobs(limit=500)
    return {
        "tenants": len(tenants),
        "active_tenants": sum(1 for tenant in tenants if tenant["status"] == "active"),
        "users": sum(int(tenant["user_count"]) for tenant in tenants),
        "jobs": len(jobs),
        "feedback": studio.feedback_summary(),
    }


@router.get("/api/v1/platform/tenants")
async def list_tenants(
    store: PlatformStore = Depends(get_platform_store),
    studio: StudioStore = Depends(get_studio_store),
    _: dict[str, object] = Depends(require_platform),
) -> dict[str, list[dict[str, object]]]:
    items = []
    for tenant in store.list_tenants():
        enriched = dict(tenant)
        enriched["usage"] = studio.usage(str(tenant["id"]))
        items.append(enriched)
    return {"items": items}


@router.post("/api/v1/platform/tenants", status_code=201)
async def create_tenant(
    payload: TenantCreate,
    store: PlatformStore = Depends(get_platform_store),
    _: dict[str, object] = Depends(require_platform),
) -> dict[str, object]:
    try:
        return store.create_tenant(
            payload.name,
            payload.plan,
            payload.owner_email,
            payload.owner_password,
            payload.owner_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/api/v1/platform/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    payload: TenantUpdate,
    store: PlatformStore = Depends(get_platform_store),
    _: dict[str, object] = Depends(require_platform),
) -> dict[str, object]:
    tenant = store.update_tenant(tenant_id, payload.model_dump(exclude_none=True))
    if tenant is None:
        raise HTTPException(status_code=404, detail="tenant not found")
    return tenant


@router.get("/api/v1/platform/tenants/{tenant_id}/users")
async def list_tenant_users(
    tenant_id: str,
    store: PlatformStore = Depends(get_platform_store),
    _: dict[str, object] = Depends(require_platform),
) -> dict[str, list[dict[str, object]]]:
    if store.get_tenant(tenant_id) is None:
        raise HTTPException(status_code=404, detail="tenant not found")
    return {"items": store.list_tenant_users(tenant_id)}


@router.post("/api/v1/platform/activation-codes", status_code=201)
async def create_activation_codes(
    payload: ActivationCodeCreate,
    store: PlatformStore = Depends(get_platform_store),
    _: dict[str, object] = Depends(require_platform),
) -> dict[str, object]:
    try:
        items = store.create_activation_codes(
            payload.plan,
            payload.count,
            payload.duration_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"items": items}


@router.get("/api/v1/platform/activation-codes")
async def list_activation_codes(
    store: PlatformStore = Depends(get_platform_store),
    _: dict[str, object] = Depends(require_platform),
) -> dict[str, list[dict[str, object]]]:
    return {"items": store.list_activation_codes()}


@router.get("/api/v1/platform/orders")
async def list_orders(
    store: PlatformStore = Depends(get_platform_store),
    _: dict[str, object] = Depends(require_platform),
) -> dict[str, list[dict[str, object]]]:
    return {"items": store.list_orders()}


@router.get("/api/v1/platform/script-styles")
async def list_platform_script_styles(
    store: PlatformStore = Depends(get_platform_store),
    _: dict[str, object] = Depends(require_platform),
) -> dict[str, list[dict[str, object]]]:
    return {"items": store.list_script_styles()}


@router.post("/api/v1/platform/script-styles", status_code=201)
async def create_platform_script_style(
    payload: ScriptStyleCreate,
    store: PlatformStore = Depends(get_platform_store),
    _: dict[str, object] = Depends(require_platform),
) -> dict[str, object]:
    try:
        return store.create_script_style(
            payload.name,
            payload.prompt,
            payload.sort_order,
            payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/api/v1/platform/script-styles/{style_id}")
async def update_platform_script_style(
    style_id: str,
    payload: ScriptStyleUpdate,
    store: PlatformStore = Depends(get_platform_store),
    _: dict[str, object] = Depends(require_platform),
) -> dict[str, object]:
    try:
        style = store.update_script_style(
            style_id,
            payload.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if style is None:
        raise HTTPException(status_code=404, detail="script style not found")
    return style


@router.delete("/api/v1/platform/script-styles/{style_id}")
async def delete_platform_script_style(
    style_id: str,
    store: PlatformStore = Depends(get_platform_store),
    _: dict[str, object] = Depends(require_platform),
) -> dict[str, str]:
    if not store.delete_script_style(style_id):
        raise HTTPException(status_code=404, detail="script style not found")
    return {"status": "deleted"}
