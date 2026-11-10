from __future__ import annotations

import asyncio
import os
import shutil
import string
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_studio_store
from app.config import get_settings
from app.gateway.catalog import MODEL_CATALOG
from app.gateway.routing import auto_model_refs
from app.storage_config import migrate_storage, write_storage_root
from app.studio.store import StudioStore

router = APIRouter(tags=["settings"])


class DefaultsUpdate(BaseModel):
    models: dict[str, str] = {}


class WorkspacePreferencesUpdate(BaseModel):
    default_platform: str | None = Field(default=None, max_length=40)
    default_aspect: str | None = Field(default=None, max_length=10)
    default_quality: str | None = Field(default=None, max_length=20)
    default_subtitle_style: str | None = Field(default=None, max_length=80)
    default_voice: str | None = Field(default=None, max_length=80)
    auto_subtitle: bool | None = None
    auto_cover: bool | None = None
    auto_bgm: bool | None = None
    quality_gate: bool | None = None
    keep_original_audio: bool | None = None
    notify_success: bool | None = None
    notify_failure: bool | None = None
    notify_low_credits: bool | None = None


class StorageRootUpdate(BaseModel):
    root: str = Field(min_length=1, max_length=500)


class StoragePickRequest(BaseModel):
    initial: str = Field(default="", max_length=500)


DEFAULT_PREFERENCES: dict[str, object] = {
    "default_platform": "抖音",
    "default_aspect": "9:16",
    "default_quality": "standard",
    "default_subtitle_style": "白字黑边",
    "default_voice": "专业、可信、简洁",
    "auto_subtitle": True,
    "auto_cover": True,
    "auto_bgm": False,
    "quality_gate": True,
    "keep_original_audio": True,
    "notify_success": True,
    "notify_failure": True,
    "notify_low_credits": True,
}

ALLOWED_PLATFORMS = {"抖音", "小红书", "视频号", "淘宝", "通用"}
ALLOWED_ASPECTS = {"9:16", "16:9", "1:1", "4:5"}
ALLOWED_QUALITY = {"draft", "standard", "high"}


def _preferences(store: StudioStore) -> dict[str, object]:
    stored = store.get_preference("workspace")
    return {**DEFAULT_PREFERENCES, **stored}


@router.get("/api/v1/settings/models")
async def list_models() -> dict[str, object]:
    settings = get_settings()
    items = []
    for item in MODEL_CATALOG:
        provider = str(item["provider"])
        provider_key = settings.provider_api_key(provider) or os.getenv(
            f"AUTOCUT_{provider.upper()}_API_KEY",
            "",
        )
        base_url = str(item.get("base_url") or "").rstrip("/")
        llm_base = settings.llm_base_url.rstrip("/")
        if not provider_key and base_url and (
            llm_base.startswith(base_url) or base_url.startswith(llm_base)
        ):
            provider_key = settings.llm_api_key
        entry = dict(item)
        entry["configured"] = bool(provider_key)
        entry["status"] = "ready" if provider_key else "needs_key"
        items.append(entry)
    return {"items": items, "auto": auto_model_refs()}


@router.put("/api/v1/settings/models")
async def update_models() -> dict[str, object]:
    raise HTTPException(status_code=501, detail="model settings are a shell")


@router.get("/api/v1/settings/defaults")
async def get_defaults(
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    return {"models": store.get_preference("models"), "auto": auto_model_refs()}


@router.put("/api/v1/settings/defaults")
async def update_defaults(
    payload: DefaultsUpdate,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    return {
        "models": store.set_preference("models", payload.models),
        "auto": auto_model_refs(),
    }


@router.get("/api/v1/settings/preferences")
async def get_workspace_preferences(
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    return {**_preferences(store), "storage_root": str(store.work_root)}


@router.put("/api/v1/settings/preferences")
async def update_workspace_preferences(
    payload: WorkspacePreferencesUpdate,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    values = payload.model_dump(exclude_none=True)
    if "default_platform" in values and values["default_platform"] not in ALLOWED_PLATFORMS:
        raise HTTPException(status_code=422, detail="unsupported platform")
    if "default_aspect" in values and values["default_aspect"] not in ALLOWED_ASPECTS:
        raise HTTPException(status_code=422, detail="unsupported aspect")
    if "default_quality" in values and values["default_quality"] not in ALLOWED_QUALITY:
        raise HTTPException(status_code=422, detail="unsupported quality")
    merged = {**_preferences(store), **values}
    return store.set_preference("workspace", merged)


@router.put("/api/v1/settings/storage")
async def update_storage_root(
    payload: StorageRootUpdate,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    settings = get_settings()
    if not settings.demo_mode and settings.environment.lower() not in {"dev", "local"}:
        raise HTTPException(
            status_code=403,
            detail="存储目录由平台管理员在部署配置中管理",
        )
    root = Path(payload.root).expanduser()
    if not root.is_absolute():
        raise HTTPException(status_code=422, detail="storage root must be absolute")
    old_root = store.work_root
    try:
        migrate_storage(old_root, root)
        write_storage_root(store.database_path, root)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "storage_root": str(root.resolve()),
        "previous_root": str(old_root),
    }


def _binary_ready(value: str) -> bool:
    if not value:
        return False
    return Path(value).is_file() or shutil.which(value) is not None


def _storage_roots() -> list[dict[str, str]]:
    roots = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            path = Path(f"{letter}:\\")
            if path.exists():
                roots.append({"name": f"{letter}:\\", "path": str(path)})
    else:
        roots.append({"name": "/", "path": "/"})
        home = Path.home()
        roots.append({"name": home.name or "Home", "path": str(home)})
    return roots


@router.get("/api/v1/settings/storage/browse")
async def browse_storage(
    path: str | None = None,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    settings = get_settings()
    if not settings.demo_mode and settings.environment.lower() not in {"dev", "local"}:
        raise HTTPException(
            status_code=403,
            detail="目录浏览仅允许在本地开发环境使用",
        )
    target = Path(path).expanduser() if path else Path(store.work_root)
    try:
        target = target.resolve()
    except OSError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not target.is_absolute() or not target.is_dir():
        raise HTTPException(status_code=422, detail="目录不存在或不可访问")

    items: list[dict[str, str]] = []
    try:
        for child in sorted(target.iterdir(), key=lambda item: item.name.lower()):
            if child.name.startswith(("$", ".")):
                continue
            try:
                if child.is_dir():
                    items.append({"name": child.name, "path": str(child)})
            except OSError:
                continue
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="没有权限访问该目录") from exc

    parent = str(target.parent) if target.parent != target else ""
    return {
        "current": str(target),
        "parent": parent,
        "roots": _storage_roots(),
        "items": items,
    }


@router.post("/api/v1/settings/storage/pick")
async def pick_storage_folder(
    payload: StoragePickRequest,
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    settings = get_settings()
    if not settings.demo_mode and settings.environment.lower() not in {"dev", "local"}:
        raise HTTPException(
            status_code=403,
            detail="系统文件夹选择仅允许在本地开发环境使用",
        )
    if os.name != "nt":
        raise HTTPException(status_code=501, detail="当前系统不支持原生文件夹选择")

    initial = payload.initial.strip() or str(store.work_root)
    script = r"""
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "选择云流影本地存储目录"
$dialog.ShowNewFolderButton = $true
$initial = $env:AUTOCUT_PICKER_INITIAL
if ($initial -and (Test-Path -LiteralPath $initial)) {
    $dialog.SelectedPath = $initial
}
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::Out.Write($dialog.SelectedPath)
}
"""
    environment = {**os.environ, "AUTOCUT_PICKER_INITIAL": initial}

    def _run_picker() -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-STA",
                "-Command",
                script,
            ],
            capture_output=True,
            timeout=300,
            env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    try:
        completed = await asyncio.to_thread(_run_picker)
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=408, detail="文件夹选择超时") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise HTTPException(
            status_code=500,
            detail=f"无法打开系统文件夹选择器：{detail[:300]}",
        )
    selected = completed.stdout.decode("utf-8", errors="replace").strip()
    if not selected:
        return {"canceled": True, "path": ""}
    path = Path(selected).expanduser()
    if not path.is_dir():
        raise HTTPException(status_code=422, detail="选择的目录不存在")
    return {"canceled": False, "path": str(path.resolve())}


@router.get("/api/v1/settings/status")
async def get_runtime_status(
    store: StudioStore = Depends(get_studio_store),
) -> dict[str, object]:
    settings = get_settings()
    image_base = settings.image_base_url or settings.llm_base_url
    doubao_key = settings.provider_api_key("doubao") or os.getenv(
        "AUTOCUT_DOUBAO_API_KEY",
        "",
    )
    if doubao_key:
        image_status = {
            "provider": "doubao",
            "model": settings.doubao_image_model,
            "configured": True,
        }
    else:
        image_status = {
            "provider": "zhipu" if "bigmodel.cn" in image_base else "placeholder",
            "model": settings.image_model,
            "configured": bool(settings.image_api_key or settings.llm_api_key)
            and "bigmodel.cn" in image_base,
        }
    return {
        "demo_mode": settings.demo_mode,
        "llm": {
            "configured": bool(settings.llm_api_key),
            "model": settings.llm_model,
            "base_url": settings.llm_base_url,
        },
        "ffmpeg": {
            "configured": _binary_ready(settings.ffmpeg_bin),
            "path": settings.ffmpeg_bin,
        },
        "asr": {
            "provider": settings.asr_provider,
            "configured": settings.asr_provider == "local"
            or bool(settings.asr_api_key or settings.llm_api_key),
            "model": settings.asr_model or "glm-asr-2512",
        },
        "image": image_status,
        "storage": {
            "root": str(store.work_root),
            "mode": settings.object_storage_backend
            if settings.object_storage_backend == "s3"
            and settings.s3_bucket
            and settings.s3_access_key
            and settings.s3_secret_key
            else "local",
            "bucket": settings.s3_bucket,
            "endpoint": settings.s3_endpoint_url,
        },
    }
