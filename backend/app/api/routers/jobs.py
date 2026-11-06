from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_service
from app.config import get_settings
from app.domain import Job
from app.service import JobService, WorkflowNotFoundError

router = APIRouter(tags=["jobs"])


def serialize_job(job: Job) -> dict[str, Any]:
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
    }


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


@router.post("/api/v1/jobs", status_code=202)
async def create_job(
    workflow: str = Form(...),
    file: UploadFile = File(...),
    params: str | None = Form(default=None),
    service: JobService = Depends(get_service),
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

    try:
        job = service.create_job(
            workflow=workflow,
            input_path=target,
            params=parsed,
            job_id=job_id,
        )
    except WorkflowNotFoundError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return serialize_job(job)


@router.get("/api/v1/jobs")
async def list_jobs(
    limit: int = 50,
    status: str | None = None,
    service: JobService = Depends(get_service),
) -> dict[str, list[dict[str, Any]]]:
    jobs = service.store.list(limit=max(1, min(limit, 200)), status=status)
    return {"items": [serialize_job(job) for job in jobs]}


@router.get("/api/v1/jobs/{job_id}")
async def get_job(
    job_id: str,
    service: JobService = Depends(get_service),
) -> dict[str, Any]:
    job = service.store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job": serialize_job(job), "events": service.store.events(job_id)}


@router.post("/api/v1/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    service: JobService = Depends(get_service),
) -> dict[str, str]:
    if not service.store.cancel(job_id):
        raise HTTPException(status_code=409, detail="only queued jobs can be canceled")
    return {"status": "canceled"}


@router.post("/api/v1/jobs/{job_id}/retry", status_code=202)
async def retry_job(
    job_id: str,
    service: JobService = Depends(get_service),
) -> dict[str, Any]:
    if not service.store.requeue(job_id):
        raise HTTPException(status_code=409, detail="only failed or canceled jobs can be retried")
    job = service.store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return serialize_job(job)


@router.get("/api/v1/jobs/{job_id}/artifacts")
async def list_artifacts(
    job_id: str,
    service: JobService = Depends(get_service),
) -> dict[str, list[dict[str, Any]]]:
    job = service.store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"items": collect_artifacts(job.result, service.work_dir(job_id))}


@router.get("/api/v1/jobs/{job_id}/files/{relative_path:path}")
async def download_file(
    job_id: str,
    relative_path: str,
    service: JobService = Depends(get_service),
) -> FileResponse:
    job = service.store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    work_dir = service.work_dir(job_id)
    candidate = (work_dir / relative_path).resolve()
    if not candidate.is_relative_to(work_dir):
        raise HTTPException(status_code=400, detail="invalid path")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(candidate)
