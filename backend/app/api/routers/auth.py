from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(tags=["auth"])

DEMO_USER = {
    "id": "demo",
    "email": "demo@local",
    "name": "Demo Owner",
    "role": "owner",
    "plan": "trial",
}


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/api/v1/auth/login")
async def login(payload: LoginRequest) -> dict[str, object]:
    if not get_settings().demo_mode:
        raise HTTPException(status_code=501, detail="auth is not implemented")
    return {"access_token": "demo-token", "token_type": "bearer", "user": DEMO_USER}


@router.post("/api/v1/auth/register")
async def register(payload: LoginRequest) -> dict[str, object]:
    if not get_settings().demo_mode:
        raise HTTPException(status_code=501, detail="auth is not implemented")
    return {"access_token": "demo-token", "token_type": "bearer", "user": DEMO_USER}


@router.post("/api/v1/auth/logout")
async def logout() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/auth/me")
async def me() -> dict[str, object]:
    if not get_settings().demo_mode:
        raise HTTPException(status_code=501, detail="auth is not implemented")
    return DEMO_USER
