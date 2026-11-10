from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, Header, HTTPException, Query

from app.auth.security import verify_token
from app.auth.service import AuthService
from app.auth.store import AuthStore
from app.billing.credits import CreditService
from app.bootstrap import build_registry
from app.clips.store import ClipSegmentStore
from app.config import get_settings
from app.gateway.factory import build_chat_model
from app.object_storage import build_object_storage
from app.platform.store import PlatformStore
from app.rag.store import RagStore
from app.rag.tenant_store import TenantRagStore
from app.service import JobService
from app.storage import JobStore
from app.studio.calendar import CalendarService, CalendarStore
from app.studio.compliance import ComplianceService, ComplianceStore
from app.studio.publishing import PublishService, PublishStore
from app.studio.store import StudioStore
from app.studio.tenant_store import TenantStudioStore
from app.studio.trends import TrendService, TrendStore


@lru_cache
def get_service() -> JobService:
    settings = get_settings()
    store = JobStore(settings.database_path)
    return JobService(
        store,
        settings.work_root,
        build_registry(),
        settings.max_concurrency,
        database_path=settings.database_path,
        object_storage=build_object_storage(settings),
    )


@lru_cache
def _base_rag_store() -> RagStore:
    return RagStore(get_settings().database_path)


def get_rag_store(
    authorization: str | None = Header(default=None),
) -> RagStore:
    base = _base_rag_store()
    settings = get_settings()
    if not authorization:
        if settings.demo_mode:
            return base
        raise HTTPException(status_code=401, detail="missing authorization")
    token = get_token(authorization)
    if token.get("scope") == "platform":
        return base
    tenant_id = str(token.get("tenant_id") or "")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="tenant_id is missing")
    return TenantRagStore(base, tenant_id)


@lru_cache
def get_auth_service() -> AuthService:
    settings = get_settings()
    return AuthService(AuthStore(settings.database_path), settings)


@lru_cache
def _base_studio_store() -> StudioStore:
    settings = get_settings()
    return StudioStore(settings.database_path, settings.work_root)


def get_tenant_id(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> str:
    settings = get_settings()
    credential = authorization or (f"Bearer {token}" if token else None)
    if not credential:
        if settings.demo_mode:
            return "demo"
        raise HTTPException(status_code=401, detail="missing authorization")
    payload = get_token(credential)
    if payload.get("scope") == "platform":
        raise HTTPException(status_code=403, detail="tenant account required")
    tenant_id = str(payload.get("tenant_id") or "")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="tenant_id is missing")
    return tenant_id


def get_studio_store(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> StudioStore:
    base = _base_studio_store()
    settings = get_settings()
    credential = authorization or (f"Bearer {token}" if token else None)
    if not credential:
        if settings.demo_mode:
            return base
        raise HTTPException(status_code=401, detail="missing authorization")
    payload = get_token(credential)
    if payload.get("scope") == "platform":
        return base
    tenant_id = str(payload.get("tenant_id") or "")
    if not tenant_id:
        raise HTTPException(status_code=403, detail="tenant_id is missing")
    return TenantStudioStore(base, tenant_id)


@lru_cache
def get_platform_store() -> PlatformStore:
    settings = get_settings()
    store = PlatformStore(settings.database_path)
    store.seed(settings)
    return store


@lru_cache
def get_credit_service() -> CreditService:
    return CreditService(get_settings().database_path)


@lru_cache
def get_clip_store() -> ClipSegmentStore:
    return ClipSegmentStore(get_settings().database_path)


@lru_cache
def get_trend_service() -> TrendService:
    settings = get_settings()
    return TrendService(
        ttl_seconds=settings.trend_ttl_seconds,
        store=TrendStore(settings.database_path),
        retention_days=settings.trend_retention_days,
        chat_model=build_chat_model(),
    )


@lru_cache
def get_calendar_service() -> CalendarService:
    settings = get_settings()
    return CalendarService(
        CalendarStore(settings.database_path),
        chat_model=build_chat_model(),
        trend_store=TrendStore(settings.database_path),
    )


@lru_cache
def get_compliance_service() -> ComplianceService:
    settings = get_settings()
    return ComplianceService(ComplianceStore(settings.database_path))


@lru_cache
def get_publish_service() -> PublishService:
    settings = get_settings()
    return PublishService(PublishStore(settings.database_path))


def get_token(authorization: str | None = Header(default=None)) -> dict[str, object]:
    settings = get_settings()
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if token == "demo-token" and settings.demo_mode:
        return {
            "scope": "tenant",
            "tenant_id": "demo",
            "role": "owner",
            "sub": "demo",
            "email": "demo@local",
            "name": "Demo Owner",
        }
    payload = verify_token(token, settings.auth_secret) if token else None
    if payload is None:
        raise HTTPException(status_code=401, detail="invalid or missing token")
    return payload


def require_tenant(token: dict[str, object] = Depends(get_token)) -> dict[str, object]:
    if token.get("scope") != "tenant":
        raise HTTPException(status_code=403, detail="tenant account required")
    return token


def require_platform(token: dict[str, object] = Depends(get_token)) -> dict[str, object]:
    if token.get("scope") != "platform":
        raise HTTPException(status_code=403, detail="platform admin required")
    return token
