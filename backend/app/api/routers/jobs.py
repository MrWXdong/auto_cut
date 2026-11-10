from __future__ import annotations

import hashlib
import json
import re
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from starlette.background import BackgroundTask

from app.api.deps import (
    get_credit_service,
    get_platform_store,
    get_service,
    get_studio_store,
    get_tenant_id,
)
from app.billing.credits import CreditService, InsufficientCredits
from app.billing.pricing import workflow_cost
from app.billing.quota_guard import ensure_quota
from app.config import get_settings
from app.core.commands import run_command
from app.domain import Job
from app.platform.store import PlatformStore
from app.service import JobService, WorkflowNotFoundError
from app.storage_names import EXPORTS_DIR
from app.studio.store import StudioStore

router = APIRouter(tags=["jobs"])


def serialize_job(job: Job, source_name: str = "") -> dict[str, Any]:
    result = job.result or {}
    segments = (
        result.get("select", {}).get("segments")
        or result.get("split", {}).get("segments")
        or result.get("cut", {}).get("clips")
        or []
    )
    return {
        "id": job.id,
        "workflow": job.workflow,
        "status": job.status.value,
        "input_path": job.input_path,
        "params": job.params,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "duration_ms": job.duration_ms,
        "error": job.error,
        "result": job.result,
        "source_name": (
            str(job.params.get("source_name") or source_name)
            or Path(job.input_path).name
        ),
        "segment_count": len(segments),
    }


def _job_source_name(
    job: Job,
    studio: StudioStore,
    tenant_id: str,
) -> str:
    explicit = str(job.params.get("source_name") or "")
    if explicit:
        return explicit
    asset_id = str(job.params.get("asset_id") or "")
    if asset_id:
        asset = studio.get_asset(asset_id, tenant_id)
        if asset is not None:
            return str(asset.get("filename") or "")
    return Path(job.input_path).name


def collect_artifacts(
    result: dict[str, Any] | None,
    work_dir: Path,
) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    base = work_dir.resolve()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, str):
            path = Path(value)
            if not path.is_absolute():
                return
            try:
                resolved = path.resolve()
                relative = resolved.relative_to(base)
            except (OSError, ValueError):
                return
            if not resolved.is_file():
                return
            key = relative.as_posix()
            found[key] = {
                "name": resolved.name,
                "path": key,
                "size_bytes": resolved.stat().st_size,
            }

    visit(result)
    return sorted(found.values(), key=lambda item: str(item["path"]))


def _zip_download_name(job: Job) -> str:
    raw = str(job.params.get("source_name") or "成片")
    stem = Path(raw).stem
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .") or "成片"
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return f"{stem[:60]}_成片_{stamp}.zip"


def _unique_archive_name(name: str, used: set[str]) -> str:
    candidate = name
    stem = Path(name).stem
    suffix = Path(name).suffix
    index = 2
    while candidate in used:
        candidate = f"{stem}-{index}{suffix}"
        index += 1
    used.add(candidate)
    return candidate


@router.post("/api/v1/jobs", status_code=202)
async def create_job(
    workflow: str = Form(...),
    file: UploadFile = File(...),
    params: str | None = Form(default=None),
    service: JobService = Depends(get_service),
    tenant_id: str = Depends(get_tenant_id),
    credits: CreditService = Depends(get_credit_service),
    studio: StudioStore = Depends(get_studio_store),
    platform: PlatformStore = Depends(get_platform_store),
) -> dict[str, Any]:
    settings = get_settings()
    job_id = uuid.uuid4().hex[:12]
    upload_dir = (service.work_root / "uploads" / job_id).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "input.mp4").suffix or ".mp4"
    target = upload_dir / f"input{suffix}"

    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    try:
        with target.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(status_code=413, detail="upload too large")
                handle.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    try:
        parsed = json.loads(params) if params else {}
    except json.JSONDecodeError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"invalid params json: {exc}") from exc
    if not isinstance(parsed, dict):
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="params must be a JSON object")
    parsed.setdefault("source_name", file.filename or "素材")

    ensure_quota(studio, platform, tenant_id, "jobs")
    cost = workflow_cost(workflow, parsed)
    try:
        credits.reserve(tenant_id, cost, "workflow_job", job_id)
    except InsufficientCredits as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=402,
            detail="积分不足，请充值或升级套餐",
        ) from exc

    try:
        job = service.create_job(
            workflow=workflow,
            input_path=target,
            params=parsed,
            job_id=job_id,
            tenant_id=tenant_id,
        )
    except WorkflowNotFoundError as exc:
        target.unlink(missing_ok=True)
        credits.refund_ref(tenant_id, "workflow_job", job_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {**serialize_job(job), "credits_cost": cost}


@router.get("/api/v1/jobs")
async def list_jobs(
    limit: int = 50,
    status: str | None = None,
    service: JobService = Depends(get_service),
    studio: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, list[dict[str, Any]]]:
    jobs = service.store.list(
        limit=max(1, min(limit, 200)),
        status=status,
        tenant_id=tenant_id,
    )
    return {
        "items": [
            serialize_job(job, _job_source_name(job, studio, tenant_id))
            for job in jobs
        ]
    }


@router.get("/api/v1/jobs/{job_id}")
async def get_job(
    job_id: str,
    service: JobService = Depends(get_service),
    studio: StudioStore = Depends(get_studio_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    job = service.store.get(job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job": serialize_job(job, _job_source_name(job, studio, tenant_id)),
        "events": service.store.events(job_id),
    }


@router.post("/api/v1/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    service: JobService = Depends(get_service),
    tenant_id: str = Depends(get_tenant_id),
    credits: CreditService = Depends(get_credit_service),
) -> dict[str, str]:
    if not service.store.cancel(job_id, tenant_id):
        raise HTTPException(status_code=409, detail="only queued jobs can be canceled")
    credits.refund_ref(tenant_id, "workflow_job", job_id)
    return {"status": "canceled"}


@router.post("/api/v1/jobs/{job_id}/retry", status_code=202)
async def retry_job(
    job_id: str,
    service: JobService = Depends(get_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    if not service.retry_job(job_id, tenant_id):
        raise HTTPException(status_code=409, detail="only failed or canceled jobs can be retried")
    job = service.store.get(job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return serialize_job(job)


@router.delete("/api/v1/jobs/{job_id}")
async def delete_job(
    job_id: str,
    service: JobService = Depends(get_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, str]:
    try:
        deleted = await service.delete_job(job_id, tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="job not found")
    return {"status": "deleted"}


@router.get("/api/v1/jobs/{job_id}/artifacts")
async def list_artifacts(
    job_id: str,
    service: JobService = Depends(get_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, list[dict[str, Any]]]:
    job = service.store.get(job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    cloud_items = service.store.list_artifacts(job_id)
    if cloud_items and service.object_storage is not None:
        return {
            "items": [
                {
                    "name": Path(str(item["relative_path"])).name,
                    "path": item["relative_path"],
                    "size_bytes": item["size_bytes"],
                    "storage": "cloud",
                }
                for item in cloud_items
            ]
        }
    return {"items": collect_artifacts(job.result, service.work_dir(job_id))}


@router.get("/api/v1/jobs/{job_id}/artifacts/export")
async def export_artifacts(
    job_id: str,
    path: list[str] = Query(default=[]),
    service: JobService = Depends(get_service),
    tenant_id: str = Depends(get_tenant_id),
) -> FileResponse:
    job = service.store.get(job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if service.store.list_artifacts(job_id):
        raise HTTPException(
            status_code=409,
            detail="当前任务使用对象存储，请先接入云端打包下载",
        )

    work_dir = service.work_dir(job_id)
    available = {
        item["path"]: item
        for item in collect_artifacts(job.result, work_dir)
    }
    selected = list(dict.fromkeys(path))
    if not selected:
        selected = [
            item_path
            for item_path in available
            if item_path.startswith(f"{EXPORTS_DIR}/")
        ] or list(available)
    invalid = [item_path for item_path in selected if item_path not in available]
    if invalid:
        raise HTTPException(status_code=400, detail="invalid artifact path")
    if not selected:
        raise HTTPException(status_code=404, detail="no artifacts to export")

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    temp_path = Path(temp.name)
    temp.close()
    used_names: set[str] = set()
    written = 0
    try:
        with zipfile.ZipFile(
            temp_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=True,
        ) as archive:
            for item_path in selected:
                source = (work_dir / item_path).resolve()
                if not source.is_relative_to(work_dir) or not source.is_file():
                    continue
                archive.write(
                    source,
                    _unique_archive_name(source.name, used_names),
                )
                written += 1
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    if not written:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="artifact files not found")
    return FileResponse(
        temp_path,
        media_type="application/zip",
        filename=_zip_download_name(job),
        background=BackgroundTask(temp_path.unlink, missing_ok=True),
    )


@router.get("/api/v1/jobs/{job_id}/files/{relative_path:path}")
async def download_file(
    job_id: str,
    relative_path: str,
    service: JobService = Depends(get_service),
    tenant_id: str = Depends(get_tenant_id),
) -> FileResponse:
    job = service.store.get(job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    cloud = service.store.get_artifact(job_id, relative_path)
    if cloud is not None and service.object_storage is not None:
        return RedirectResponse(service.object_storage.presigned_url(str(cloud["object_key"])))
    work_dir = service.work_dir(job_id)
    candidate = (work_dir / relative_path).resolve()
    if not candidate.is_relative_to(work_dir):
        raise HTTPException(status_code=400, detail="invalid path")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(candidate)


@router.get("/api/v1/jobs/{job_id}/thumbnail")
async def artifact_thumbnail(
    job_id: str,
    path: str,
    service: JobService = Depends(get_service),
    tenant_id: str = Depends(get_tenant_id),
) -> FileResponse:
    if service.store.get(job_id, tenant_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    work_dir = service.work_dir(job_id)
    candidate = (work_dir / path).resolve()
    if not candidate.is_relative_to(work_dir):
        raise HTTPException(status_code=400, detail="invalid path")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    if candidate.suffix.lower() not in {".mp4", ".webm", ".mov", ".mkv"}:
        raise HTTPException(status_code=404, detail="thumbnail not available")

    key = hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]
    output = work_dir / "previews" / f"{key}.jpg"
    if (
        output.is_file()
        and output.stat().st_mtime >= candidate.stat().st_mtime
    ):
        return FileResponse(output, media_type="image/jpeg")

    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        await run_command(
            [
                get_settings().ffmpeg_bin,
                "-y",
                "-i",
                str(candidate),
                "-vf",
                "thumbnail=100,scale=-2:480",
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(output),
            ],
            timeout=120,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail="thumbnail not available",
        ) from exc
    if not output.is_file():
        raise HTTPException(status_code=404, detail="thumbnail not available")
    return FileResponse(output, media_type="image/jpeg")


@router.delete("/api/v1/jobs/{job_id}/files/{relative_path:path}")
async def delete_artifact(
    job_id: str,
    relative_path: str,
    service: JobService = Depends(get_service),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, str]:
    if service.store.get(job_id, tenant_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    cloud = service.store.get_artifact(job_id, relative_path)
    if cloud is not None:
        if service.object_storage is not None:
            await service.object_storage.delete_key(str(cloud["object_key"]))
        service.store.delete_artifact(job_id, relative_path)
        return {"status": "deleted"}
    work_dir = service.work_dir(job_id)
    candidate = (work_dir / relative_path).resolve()
    if not candidate.is_relative_to(work_dir):
        raise HTTPException(status_code=400, detail="invalid path")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    candidate.unlink()
    return {"status": "deleted"}
