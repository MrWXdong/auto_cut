from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import get_clip_store, get_service, get_tenant_id
from app.clips.render import render_clip
from app.clips.store import ClipSegmentStore
from app.nodes.media import ASPECT_SIZES
from app.nodes.subtitle import (
    build_clip_timed_text,
    build_timed_text,
    format_short_timestamp,
)
from app.service import JobService
from app.storage_names import EXPORTS_DIR, FULL_SUBTITLE_TXT, SUBTITLES_DIR

router = APIRouter(tags=["clips"])


class SegmentUpdate(BaseModel):
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)
    title: str | None = Field(default=None, max_length=200)
    kind: Literal["highlight", "normal", "silence", "blank"] | None = None
    locked: bool | None = None


class SegmentMergeRequest(BaseModel):
    ids: list[str] = Field(min_length=2, max_length=50)


class SegmentReorderRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=200)


class SegmentRenderRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=50)
    aspects: list[str] = Field(default_factory=list, max_length=6)


def _relative_path(value: str, work_dir: Path) -> str:
    if not value:
        return ""
    try:
        return Path(value).resolve().relative_to(work_dir.resolve()).as_posix()
    except (OSError, ValueError):
        return ""


def _serialize(segment: dict[str, Any], service: JobService) -> dict[str, Any]:
    work_dir = service.work_dir(str(segment.get("job_id") or ""))
    data = dict(segment)
    data["clip_relative"] = _relative_path(str(data.get("clip_path") or ""), work_dir)
    data["exports"] = [
        {
            **item,
            "relative_path": _relative_path(str(item.get("path") or ""), work_dir),
        }
        for item in data.get("exports") or []
    ]
    return data


def _edited_name(segment: dict[str, Any], aspect: str) -> str:
    raw = str(segment.get("source_name") or "素材")
    stem = Path(raw).stem
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .")[:60] or "素材"
    duration = float(segment.get("duration") or 0)
    seconds = f"{duration:.1f}".rstrip("0").rstrip(".")
    width, height = ASPECT_SIZES[aspect]
    sequence = int(segment.get("seq") or 0) + 1
    return f"{stem}_切片{sequence:02d}_{seconds}s_{width}x{height}_重剪.mp4"


def _txt_response(content: str, filename: str) -> Response:
    return Response(
        content="\ufeff" + content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(filename)}"
            )
        },
    )


def _record_subtitle_export(
    *,
    service: JobService,
    job: Any,
    tenant_id: str,
    output: Path,
    name: str,
    segment_id: str = "",
) -> None:
    result = dict(job.result or {})
    manual_exports = list(result.get("manual_exports") or [])
    relative_path = output.relative_to(service.work_dir(str(job.id))).as_posix()
    manual_exports = [
        item
        for item in manual_exports
        if str(item.get("relative_path") or "") != relative_path
    ]
    manual_exports.append(
        {
            "segment_id": segment_id,
            "name": name,
            "path": str(output),
            "relative_path": relative_path,
            "kind": "subtitle",
        }
    )
    result["manual_exports"] = manual_exports
    service.store.update_result(str(job.id), tenant_id, result)


def _transcript_segments(job: Any) -> list[dict[str, Any]]:
    return list(
        (job.result or {}).get("transcript", {}).get("segments") or []
    )


def _has_clip_adjustments(
    job: Any,
    current: list[dict[str, Any]],
) -> bool:
    result = job.result or {}
    original = (
        result.get("select", {}).get("segments")
        or result.get("split", {}).get("segments")
        or []
    )
    if not original:
        return False
    if len(current) != len(original):
        return True
    for index, (source, segment) in enumerate(zip(original, current, strict=False)):
        if abs(float(segment["start"]) - float(source.get("start") or 0)) > 0.01:
            return True
        if abs(float(segment["end"]) - float(source.get("end") or 0)) > 0.01:
            return True
        expected_title = str(source.get("title") or f"片段 {index + 1}").strip()
        if str(segment.get("title") or "").strip() != expected_title:
            return True
        if segment.get("locked"):
            return True
    return False


@router.get("/api/v1/jobs/{job_id}/segments")
async def list_segments(
    job_id: str,
    service: JobService = Depends(get_service),
    store: ClipSegmentStore = Depends(get_clip_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    job = service.store.get(job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    service.ensure_clip_segments(job)
    items = store.list_for_job(job_id, tenant_id)
    return {
        "items": [_serialize(item, service) for item in items],
        "has_adjustments": _has_clip_adjustments(job, items),
    }


@router.patch("/api/v1/segments/{segment_id}")
async def update_segment(
    segment_id: str,
    payload: SegmentUpdate,
    service: JobService = Depends(get_service),
    store: ClipSegmentStore = Depends(get_clip_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    current = store.get(segment_id, tenant_id)
    if current is None or current.get("status") != "active":
        raise HTTPException(status_code=404, detail="segment not found")
    values = payload.model_dump(exclude_none=True)
    changing_range = (
        ("start" in values and float(values["start"]) != float(current["start"]))
        or ("end" in values and float(values["end"]) != float(current["end"]))
    )
    if current["locked"] and changing_range:
        raise HTTPException(status_code=409, detail="locked segment cannot be trimmed")

    start = float(values.get("start", current["start"]))
    end = float(values.get("end", current["end"]))
    duration_limit = float(current.get("source_duration") or 0)
    if end <= start:
        raise HTTPException(status_code=422, detail="end must be greater than start")
    if start < 0 or (duration_limit > 0 and end > duration_limit + 0.05):
        raise HTTPException(status_code=422, detail="segment range exceeds source video")

    values["start"] = round(start, 3)
    values["end"] = round(end, 3)
    values["duration"] = round(end - start, 3)
    if isinstance(values.get("title"), str):
        values["title"] = values["title"].strip()
    if values.get("locked") is not None:
        values["locked"] = 1 if values["locked"] else 0
    updated = store.update(segment_id, tenant_id, values)
    if updated is None:
        raise HTTPException(status_code=404, detail="segment not found")
    return _serialize(updated, service)


@router.delete("/api/v1/segments/{segment_id}")
async def delete_segment(
    segment_id: str,
    store: ClipSegmentStore = Depends(get_clip_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, str]:
    current = store.get(segment_id, tenant_id)
    if current is None or current.get("status") != "active":
        raise HTTPException(status_code=404, detail="segment not found")
    if current["locked"]:
        raise HTTPException(status_code=409, detail="locked segment cannot be deleted")
    if not store.delete(segment_id, tenant_id):
        raise HTTPException(status_code=404, detail="segment not found")
    return {"status": "deleted"}


@router.post("/api/v1/jobs/{job_id}/segments/merge")
async def merge_segments(
    job_id: str,
    payload: SegmentMergeRequest,
    service: JobService = Depends(get_service),
    store: ClipSegmentStore = Depends(get_clip_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    if service.store.get(job_id, tenant_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    try:
        merged = store.merge(
            job_id=job_id,
            tenant_id=tenant_id,
            segment_ids=list(dict.fromkeys(payload.ids)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _serialize(merged, service)


@router.post("/api/v1/jobs/{job_id}/segments/{segment_id}/unmerge")
async def unmerge_segment(
    job_id: str,
    segment_id: str,
    service: JobService = Depends(get_service),
    store: ClipSegmentStore = Depends(get_clip_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    if service.store.get(job_id, tenant_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    try:
        restored = store.unmerge(
            job_id=job_id,
            tenant_id=tenant_id,
            segment_id=segment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"items": [_serialize(item, service) for item in restored]}


@router.post("/api/v1/jobs/{job_id}/segments/reorder")
async def reorder_segments(
    job_id: str,
    payload: SegmentReorderRequest,
    service: JobService = Depends(get_service),
    store: ClipSegmentStore = Depends(get_clip_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    if service.store.get(job_id, tenant_id) is None:
        raise HTTPException(status_code=404, detail="job not found")
    try:
        store.reorder(job_id, tenant_id, payload.ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "items": [
            _serialize(item, service)
            for item in store.list_for_job(job_id, tenant_id)
        ]
    }


@router.post("/api/v1/jobs/{job_id}/segments/reset")
async def reset_segments(
    job_id: str,
    service: JobService = Depends(get_service),
    store: ClipSegmentStore = Depends(get_clip_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    job = service.store.get(job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if not job.result:
        raise HTTPException(status_code=409, detail="job has no original result")
    service.reset_clip_segments(job)
    return {
        "items": [
            _serialize(item, service)
            for item in store.list_for_job(job_id, tenant_id)
        ]
    }


@router.post("/api/v1/jobs/{job_id}/segments/render")
async def render_segments(
    job_id: str,
    payload: SegmentRenderRequest,
    service: JobService = Depends(get_service),
    store: ClipSegmentStore = Depends(get_clip_store),
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, object]:
    job = service.store.get(job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if service.store.list_artifacts(job_id):
        raise HTTPException(
            status_code=409,
            detail="对象存储模式暂不支持时间轴重剪导出",
        )

    service.ensure_clip_segments(job)
    segments = {
        str(item["id"]): item
        for item in store.list_for_job(job_id, tenant_id)
    }
    selected = []
    for segment_id in dict.fromkeys(payload.ids):
        segment = segments.get(segment_id)
        if segment is None:
            raise HTTPException(status_code=404, detail="segment not found")
        selected.append(segment)

    aspects = payload.aspects or list(job.params.get("aspects") or []) or ["9:16"]
    invalid_aspects = [item for item in aspects if item not in ASPECT_SIZES]
    if invalid_aspects:
        raise HTTPException(status_code=422, detail="unsupported aspect ratio")

    source = Path(job.input_path)
    if not source.is_file():
        raise HTTPException(status_code=404, detail="source video not found")
    output_dir = service.work_dir(job_id) / EXPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, Any]] = []
    for segment in selected:
        for aspect in aspects:
            output = output_dir / _edited_name(segment, aspect)
            index = 2
            stem = output.stem
            while output.exists():
                output = output_dir / f"{stem}-{index}.mp4"
                index += 1
            try:
                await render_clip(
                    source,
                    float(segment["start"]),
                    float(segment["end"]),
                    aspect,
                    output,
                )
            except Exception as exc:
                output.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"片段导出失败：{type(exc).__name__}: {exc}",
                ) from exc
            width, height = ASPECT_SIZES[aspect]
            outputs.append(
                {
                    "segment_id": segment["id"],
                    "name": output.name,
                    "path": str(output),
                    "relative_path": output.relative_to(
                        service.work_dir(job_id)
                    ).as_posix(),
                    "aspect": aspect,
                    "width": width,
                    "height": height,
                }
            )

    result = dict(job.result or {})
    manual_exports = list(result.get("manual_exports") or [])
    manual_exports.extend(outputs)
    result["manual_exports"] = manual_exports
    service.store.update_result(job_id, tenant_id, result)
    return {"outputs": outputs}


@router.get("/api/v1/jobs/{job_id}/subtitles.txt")
async def export_job_subtitles(
    job_id: str,
    service: JobService = Depends(get_service),
    tenant_id: str = Depends(get_tenant_id),
) -> Response:
    job = service.store.get(job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    segments = _transcript_segments(job)
    if not segments:
        raise HTTPException(status_code=404, detail="transcript not found")
    clips = (job.result or {}).get("select", {}).get("segments") or []
    content = build_clip_timed_text(clips, segments) if clips else build_timed_text(segments)
    if not content:
        raise HTTPException(status_code=404, detail="transcript not found")
    download_name = f"{Path(str(job.params.get('source_name') or '字幕')).stem}_完整字幕.txt"
    name = FULL_SUBTITLE_TXT
    output_dir = service.work_dir(job_id) / SUBTITLES_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / name
    output.write_text("\ufeff" + content, encoding="utf-8")
    _record_subtitle_export(
        service=service,
        job=job,
        tenant_id=tenant_id,
        output=output,
        name=name,
    )
    return _txt_response(content, download_name)


@router.get("/api/v1/jobs/{job_id}/segments/{segment_id}/subtitles.txt")
async def export_segment_subtitles(
    job_id: str,
    segment_id: str,
    service: JobService = Depends(get_service),
    store: ClipSegmentStore = Depends(get_clip_store),
    tenant_id: str = Depends(get_tenant_id),
) -> Response:
    job = service.store.get(job_id, tenant_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    service.ensure_clip_segments(job)
    segment = store.get(segment_id, tenant_id)
    if segment is None or segment.get("job_id") != job_id:
        raise HTTPException(status_code=404, detail="segment not found")

    start = float(segment["start"])
    end = float(segment["end"])
    content = build_clip_timed_text([segment], _transcript_segments(job))
    if not content:
        text = str(segment.get("transcript") or segment.get("title") or "").strip()
        if text:
            content = (
                f"[{format_short_timestamp(start)} --> "
                f"{format_short_timestamp(end)}] {text}"
            )
    if not content:
        raise HTTPException(status_code=404, detail="transcript not found")
    sequence = int(segment.get("seq") or 0) + 1
    name = f"切片{sequence:02d}_字幕.txt"
    output_dir = service.work_dir(job_id) / SUBTITLES_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / name
    output.write_text("\ufeff" + content, encoding="utf-8")
    _record_subtitle_export(
        service=service,
        job=job,
        tenant_id=tenant_id,
        output=output,
        name=name,
        segment_id=segment_id,
    )
    return _txt_response(content, name)
