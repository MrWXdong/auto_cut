from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_auth_service, get_platform_store, get_token
from app.auth.security import issue_token
from app.auth.service import AuthService, DemoUser
from app.config import get_settings
from app.platform.store import PlatformStore

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class SmsSendRequest(BaseModel):
    phone: str


class SmsVerifyRequest(BaseModel):
    phone: str
    code: str


@router.get("/api/v1/auth/methods")
async def auth_methods(
    service: AuthService = Depends(get_auth_service),
) -> dict[str, list[dict[str, object]]]:
    return {"items": service.methods()}


@router.post("/api/v1/auth/login")
async def login(
    payload: LoginRequest,
    store: PlatformStore = Depends(get_platform_store),
) -> dict[str, object]:
    settings = get_settings()
    user = store.verify_tenant_user(payload.email, payload.password)
    if user is not None:
        access_token = issue_token(
            {
                "scope": "tenant",
                "sub": user["id"],
                "tenant_id": user["tenant_id"],
                "role": user["role"],
                "email": user["email"],
                "name": user["name"],
            },
            settings.auth_secret,
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user,
        }
    if settings.demo_mode:
        return {"access_token": "demo-token", "token_type": "bearer", "user": DemoUser}
    raise HTTPException(status_code=401, detail="邮箱或密码错误")


@router.post("/api/v1/auth/register")
async def register(payload: LoginRequest) -> dict[str, object]:
    if not get_settings().demo_mode:
        raise HTTPException(status_code=501, detail="注册待接入")
    return {"access_token": "demo-token", "token_type": "bearer", "user": DemoUser}


@router.post("/api/v1/auth/logout")
async def logout() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/auth/me")
async def me(token: dict[str, object] = Depends(get_token)) -> dict[str, object]:
    return {
        "id": token.get("sub") or "demo",
        "email": token.get("email") or "demo@local",
        "name": token.get("name") or "Demo Owner",
        "role": token.get("role") or "owner",
        "tenant_id": token.get("tenant_id") or "demo",
        "plan": "trial",
    }


@router.post("/api/v1/auth/sms/send")
async def send_sms_code(
    payload: SmsSendRequest,
    service: AuthService = Depends(get_auth_service),
) -> dict[str, object]:
    try:
        return service.send_sms(payload.phone)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@router.post("/api/v1/auth/sms/verify")
async def verify_sms_code(
    payload: SmsVerifyRequest,
    service: AuthService = Depends(get_auth_service),
) -> dict[str, object]:
    try:
        return service.verify_sms(payload.phone, payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/v1/auth/wechat/url")
async def wechat_login_url(
    service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    try:
        return {"url": service.wechat_authorize_url()}
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@router.get("/api/v1/auth/wechat/callback")
async def wechat_callback(code: str = "", state: str = "") -> dict[str, str]:
    raise HTTPException(status_code=501, detail="微信回调授权待接入")
