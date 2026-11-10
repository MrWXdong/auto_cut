from __future__ import annotations

import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.deps import (
    get_credit_service,
    get_platform_store,
    get_service,
    get_studio_store,
    get_tenant_id,
)
from app.api.routers.jobs import serialize_job
from app.billing.credits import CreditService, InsufficientCredits
from app.billing.pricing import workflow_cost
from app.billing.quota_guard import ensure_quota
from app.config import get_settings
from app.platform.store import PlatformStore
from app.service import JobService, WorkflowNotFoundError
from app.studio.edit import choose_workflow, edit_capabilities
from app.studio.importer import YtDlpUnavailableError, import_asset, preview_asset
from app.studio.media_preview import (
    ensure_video_preview,
    is_browser_video_codec,
    preview_path,
    probe_video_codec,
)
from app.studio.store import StudioStore

router = APIRouter(tags=["projects"])
MAX_ASSET_BYTES = 500 * 1024 * 1024
GIB = 1024 * 1024 * 1024


def _storage_limit(platform: PlatformStore, tenant_id: str) -> int:
    tenant = platform.get_tenant(tenant_id)
    if tenant is None:
        return 0
    return max(0, int(tenant["storage_gb"])) * GIB


def _storage_used(studio: StudioStore, service: JobService, tenant_id: str) -> int:
    return int(studio.usage(tenant_id).get("asset_bytes", 0)) + service.store.storage_bytes(
        tenant_id
    )


class ProjectCreate(BaseModel):
    name: str
    aspect_ratio: str = "9:16"
    style_id: str = ""
    custom_style: str = Field(default="", max_length=1000)


class ProjectUpdate(BaseModel):
    name: str | None = None
    aspect_ratio: str | None = None
    style_id: str | None = None
    custom_style: str | None = Field(default=None, max_length=1000)
    status: str | None = None


class EditJobRequest(BaseModel):
    asset_id: str
    workflow: str = "quick_cut"
    params: dict[str, object] = Field(default_factory=dict)


class AutoEditRequest(BaseModel):
    asset_id: str
    count: int = 3
    max_clips: int | None = None
    min_seconds: float | None = Field(default=None, ge=0, le=600)
    max_seconds: float | None = Field(default=None, ge=0, le=86400)
    aspects: list[str] = Field(default_factory=lambda: ["9:16"])
    model_ref: str = ""
    asr_provider: str = ""
    asr_model: str = ""
    brief: str = Field(default="", max_length=1000)


class ImportAssetRequest(BaseModel):
    url: str


def _validate_style(store: StudioStore, style_id: str | None) -> None:
    if style_id and store.get_style(style_id) is None:
        raise HTTPException(status_code=422, detail="style not found")


@router.post("/api/v1/projects", status_code=201)
async def create_project(
    payload: ProjectCreate,
    store: StudioStore = Depends(get_studio_store),
    platform: PlatformStore = Depends(get_platform_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    ensure_quota(store, platform, tenant_id, "projects")
    custom_style = payload.custom_style.strip()
    style_id = "" if custom_style else payload.style_id
    _validate_style(store, style_id)
    try:
        return store.create_project(
            payload.name,
            payload.aspect_ratio,
            style_id=style_id,
            custom_style=custom_style,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/v1/projects")
async def list_projects(
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, list[dict[str, object]]]:
    return {"items": store.list_projects()}


@router.get("/api/v1/projects/{project_id}")
async def get_project(
    project_id: str,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.patch("/api/v1/projects/{project_id}")
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    values = payload.model_dump(exclude_none=True)
    if "custom_style" in values:
        values["custom_style"] = str(values["custom_style"]).strip()
        if values["custom_style"]:
            values["style_id"] = ""
    _validate_style(store, values.get("style_id"))
    project = store.update_project(project_id, values)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.delete("/api/v1/projects/{project_id}")
async def delete_project(
    project_id: str,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, str]:
    if not store.delete_project(project_id):
        raise HTTPException(status_code=404, detail="project not found")
    return {"status": "deleted"}


@router.post("/api/v1/projects/{project_id}/assets", status_code=201)
async def upload_asset(
    project_id: str,
    file: UploadFile = File(...),
    store: StudioStore = Depends(get_studio_store),
    service: JobService = Depends(get_service),
    platform: PlatformStore = Depends(get_platform_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    ensure_quota(store, platform, tenant_id, "assets")

    filename = file.filename or "asset.bin"
    suffix = Path(filename).suffix
    token = uuid.uuid4().hex[:10]
    storage_key = f"projects/{project_id}/assets/{token}{suffix}"
    root = store.work_root.resolve()
    target = (root / storage_key).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(status_code=400, detail="invalid storage path")
    target.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    used_bytes = _storage_used(store, service, tenant_id)
    limit_bytes = _storage_limit(platform, tenant_id)
    try:
        with target.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_ASSET_BYTES:
                    raise HTTPException(status_code=413, detail="asset too large")
                if limit_bytes > 0 and used_bytes + written > limit_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail="存储空间不足，请删除素材或升级套餐",
                    )
                handle.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    try:
        return store.add_asset(
            project_id,
            filename,
            storage_key,
            written,
            {"content_type": file.content_type or ""},
        )
    except KeyError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/v1/projects/{project_id}/assets")
async def list_assets(
    project_id: str,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, list[dict[str, object]]]:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return {"items": store.list_assets(project_id)}


@router.get("/api/v1/projects/{project_id}/assets/{asset_id}/file")
async def asset_file(
    project_id: str,
    asset_id: str,
    store: StudioStore = Depends(get_studio_store),
) -> FileResponse:
    asset = store.get_asset(asset_id)
    if asset is None or asset["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="asset not found")
    root = store.work_root.resolve()
    path = (root / asset["storage_key"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="asset file not found")
    return FileResponse(path, filename=asset["filename"])


@router.get("/api/v1/projects/{project_id}/assets/{asset_id}/preview-status")
async def asset_preview_status(
    project_id: str,
    asset_id: str,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    asset = store.get_asset(asset_id)
    if asset is None or asset["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="asset not found")
    if asset["kind"] != "video":
        return {
            "status": "ready",
            "url": f"/api/v1/projects/{project_id}/assets/{asset_id}/file",
        }
    root = store.work_root.resolve()
    source = (root / asset["storage_key"]).resolve()
    if not source.is_relative_to(root) or not source.is_file():
        raise HTTPException(status_code=404, detail="asset file not found")
    cached = preview_path(store, asset_id)
    if cached.is_file() and cached.stat().st_size > 0:
        return {
            "status": "ready",
            "url": f"/api/v1/projects/{project_id}/assets/{asset_id}/preview-file",
        }
    codec = await probe_video_codec(source)
    if is_browser_video_codec(codec):
        return {
            "status": "ready",
            "url": f"/api/v1/projects/{project_id}/assets/{asset_id}/file",
            "codec": codec,
        }
    status = await ensure_video_preview(store, asset_id, source)
    return {
        "status": status,
        "url": f"/api/v1/projects/{project_id}/assets/{asset_id}/preview-file",
        "codec": codec,
        "message": "正在生成浏览器兼容预览，首次可能需要一点时间",
    }


@router.get("/api/v1/projects/{project_id}/assets/{asset_id}/preview-file")
async def asset_preview_file(
    project_id: str,
    asset_id: str,
    store: StudioStore = Depends(get_studio_store),
) -> FileResponse:
    asset = store.get_asset(asset_id)
    if asset is None or asset["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="asset not found")
    path = preview_path(store, asset_id)
    if not path.is_relative_to(store.work_root.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="preview not ready")
    return FileResponse(path, media_type="video/mp4")


@router.delete("/api/v1/projects/{project_id}/assets/{asset_id}")
async def delete_asset(
    project_id: str,
    asset_id: str,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, str]:
    asset = store.get_asset(asset_id)
    if asset is None or asset["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="asset not found")
    path = (store.work_root / asset["storage_key"]).resolve()
    store.delete_asset(asset_id)
    path.unlink(missing_ok=True)
    return {"status": "deleted"}


@router.post("/api/v1/projects/{project_id}/assets/import", status_code=201)
async def import_asset_from_url(
    project_id: str,
    payload: ImportAssetRequest,
    studio: StudioStore = Depends(get_studio_store),
    service: JobService = Depends(get_service),
    platform: PlatformStore = Depends(get_platform_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    ensure_quota(studio, platform, tenant_id, "assets")
    try:
        asset = await import_asset(studio, project_id, payload.url)
        used_bytes = _storage_used(studio, service, tenant_id)
        limit_bytes = _storage_limit(platform, tenant_id)
        if limit_bytes > 0 and used_bytes > limit_bytes:
            path = (studio.work_root / str(asset["storage_key"])).resolve()
            studio.delete_asset(str(asset["id"]))
            if path.is_relative_to(studio.work_root.resolve()):
                path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=413,
                detail="存储空间不足，请删除素材或升级套餐",
            )
        return asset
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except YtDlpUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"下载失败：{exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/v1/projects/{project_id}/assets/import/preview")
async def preview_asset_from_url(
    project_id: str,
    payload: ImportAssetRequest,
    studio: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    try:
        return await preview_asset(studio, project_id, payload.url)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except YtDlpUnavailableError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"解析失败：{exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/api/v1/projects/{project_id}/edit-jobs", status_code=202)
async def create_edit_job(
    project_id: str,
    payload: EditJobRequest,
    studio: StudioStore = Depends(get_studio_store),
    service: JobService = Depends(get_service),
    tenant_id: str = Depends(get_tenant_id),
    credits: CreditService = Depends(get_credit_service),
    platform: PlatformStore = Depends(get_platform_store),
) -> dict[str, object]:
    asset = studio.get_asset(payload.asset_id)
    if asset is None or asset["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="asset not found")
    if asset["kind"] != "video":
        raise HTTPException(status_code=422, detail="请选择视频素材")
    ensure_quota(studio, platform, tenant_id, "jobs")

    root = studio.work_root.resolve()
    path = (root / asset["storage_key"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="asset file not found")

    params = {
        "project_id": project_id,
        "asset_id": asset["id"],
        "source_name": asset["filename"],
        **payload.params,
    }
    params.setdefault("count", 3)
    params.setdefault("aspects", ["9:16"])
    cost = workflow_cost(payload.workflow, params)
    job_id = uuid.uuid4().hex[:12]
    try:
        credits.reserve(tenant_id, cost, "workflow_job", job_id)
    except InsufficientCredits as exc:
        raise HTTPException(
            status_code=402,
            detail="积分不足，请充值或升级套餐",
        ) from exc
    try:
        job = service.create_job(
            workflow=payload.workflow,
            input_path=path,
            params=params,
            tenant_id=tenant_id,
            job_id=job_id,
        )
    except WorkflowNotFoundError as exc:
        credits.refund_ref(tenant_id, "workflow_job", job_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    studio.audit("edit.job.create", job.id, {"workflow": payload.workflow})
    return {**serialize_job(job), "credits_cost": cost}


@router.get("/api/v1/edit/capabilities")
async def get_edit_capabilities() -> dict[str, object]:
    return edit_capabilities(get_settings())


@router.post("/api/v1/projects/{project_id}/auto-edit", status_code=202)
async def auto_edit(
    project_id: str,
    payload: AutoEditRequest,
    studio: StudioStore = Depends(get_studio_store),
    service: JobService = Depends(get_service),
    tenant_id: str = Depends(get_tenant_id),
    credits: CreditService = Depends(get_credit_service),
    platform: PlatformStore = Depends(get_platform_store),
) -> dict[str, object]:
    asset = studio.get_asset(payload.asset_id)
    if asset is None or asset["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="asset not found")
    if asset["kind"] != "video":
        raise HTTPException(status_code=422, detail="请选择视频素材")
    ensure_quota(studio, platform, tenant_id, "jobs")

    root = studio.work_root.resolve()
    path = (root / asset["storage_key"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="asset file not found")

    workflow, mode = choose_workflow(get_settings())
    if workflow == "clip":
        requested_clips = payload.max_clips if payload.max_clips is not None else payload.count
        min_seconds = (
            payload.min_seconds
            if payload.min_seconds is not None and payload.min_seconds > 0
            else 1.0
        )
        max_seconds = (
            payload.max_seconds
            if payload.max_seconds is not None and payload.max_seconds > 0
            else 0.0
        )
        if max_seconds > 0 and min_seconds > max_seconds:
            raise HTTPException(status_code=422, detail="最短单段不能大于最长单段")
        params = {
            "project_id": project_id,
            "asset_id": asset["id"],
            "source_name": asset["filename"],
            "mode": mode,
            "max_clips": max(1, min(requested_clips, 20)),
            "min_seconds": min_seconds,
            "max_seconds": max_seconds,
            "aspects": payload.aspects or ["9:16"],
            "model_ref": payload.model_ref,
            "asr_provider": payload.asr_provider,
            "asr_model": payload.asr_model,
            "brief": payload.brief.strip(),
        }
    else:
        params = {
            "project_id": project_id,
            "asset_id": asset["id"],
            "source_name": asset["filename"],
            "mode": mode,
            "count": max(1, min(payload.count, 20)),
            "aspects": payload.aspects or ["9:16"],
            "model_ref": payload.model_ref,
            "asr_provider": payload.asr_provider,
            "asr_model": payload.asr_model,
            "brief": payload.brief.strip(),
        }

    cost = workflow_cost(workflow, params)
    job_id = uuid.uuid4().hex[:12]
    try:
        credits.reserve(tenant_id, cost, "workflow_job", job_id)
    except InsufficientCredits as exc:
        raise HTTPException(
            status_code=402,
            detail="积分不足，请充值或升级套餐",
        ) from exc
    try:
        job = service.create_job(
            workflow=workflow,
            input_path=path,
            params=params,
            tenant_id=tenant_id,
            job_id=job_id,
        )
    except WorkflowNotFoundError as exc:
        credits.refund_ref(tenant_id, "workflow_job", job_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    studio.audit("edit.auto.create", job.id, {"workflow": workflow, "mode": mode})
    return {**serialize_job(job), "credits_cost": cost}
