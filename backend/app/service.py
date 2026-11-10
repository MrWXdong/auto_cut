from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Any

from app.clips.store import ClipSegmentStore
from app.core.workflow.context import RunContext
from app.core.workflow.executor import WorkflowExecutor
from app.core.workflow.graph import WorkflowSpec
from app.core.workflow.registry import NodeRegistry
from app.domain import Job
from app.nodes.subtitle import write_clip_subtitles
from app.object_storage import ObjectStorage
from app.storage import JobStore, utcnow
from app.storage_config import resolve_storage_root
from app.storage_layout import job_work_relpath
from app.storage_names import (
    CHECKPOINT_FILE,
    SYSTEM_DIR,
)

WORKFLOW_DIR = Path(__file__).resolve().parent / "workflows"


class WorkflowNotFoundError(LookupError):
    pass


class JobService:
    def __init__(
        self,
        store: JobStore,
        work_root: Path,
        registry: NodeRegistry,
        max_concurrency: int = 2,
        database_path: Path | None = None,
        object_storage: ObjectStorage | None = None,
    ) -> None:
        self._store = store
        self._work_root = Path(work_root)
        self._registry = registry
        self._max_concurrency = max_concurrency
        self._database_path = Path(database_path) if database_path else None
        self._object_storage = object_storage
        self._clip_store = (
            ClipSegmentStore(self._database_path)
            if self._database_path is not None
            else None
        )

    @property
    def store(self) -> JobStore:
        return self._store

    @property
    def work_root(self) -> Path:
        if self._database_path is not None:
            return resolve_storage_root(self._work_root, self._database_path)
        return self._work_root

    def load_workflow(self, name: str) -> WorkflowSpec:
        path = WORKFLOW_DIR / f"{name}.yaml"
        if not path.exists():
            raise WorkflowNotFoundError(f"workflow not found: {name}")
        return WorkflowSpec.from_yaml(path)

    def create_job(
        self,
        *,
        workflow: str,
        input_path: Path,
        params: dict[str, Any] | None = None,
        job_id: str | None = None,
        tenant_id: str = "demo",
    ) -> Job:
        self.load_workflow(workflow)
        created_at = utcnow()
        params = dict(params or {})
        resolved_input = Path(input_path).resolve()
        source_name = str(params.get("source_name") or resolved_input.name)
        actual_id = job_id or uuid.uuid4().hex[:12]
        job = Job(
            id=actual_id,
            tenant_id=tenant_id,
            workflow=workflow,
            input_path=str(resolved_input),
            params=params,
            created_at=created_at,
            work_dir=job_work_relpath(
                actual_id,
                created_at,
                source_name,
            ),
        )
        return self._store.create(job)

    def work_dir(self, job_id: str) -> Path:
        job = self._store.get(job_id)
        if job is not None and job.work_dir:
            return (self.work_root / job.work_dir).resolve()
        return (self._work_root / job_id).resolve()

    @property
    def object_storage(self) -> ObjectStorage | None:
        return self._object_storage

    async def upload_artifacts(
        self,
        job_id: str,
        work_dir: Path,
        tenant_id: str = "demo",
    ) -> list[dict[str, Any]]:
        if self._object_storage is None or not work_dir.is_dir():
            return []
        records: list[dict[str, Any]] = []
        for path in sorted(work_dir.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(work_dir).as_posix()
            object_key = f"tenants/{tenant_id}/jobs/{job_id}/{relative}"
            await self._object_storage.put_file(path, object_key)
            records.append(
                {
                    "relative_path": relative,
                    "object_key": object_key,
                    "size_bytes": path.stat().st_size,
                }
            )
        self._store.replace_artifacts(job_id, records)
        return records

    async def delete_job(
        self,
        job_id: str,
        tenant_id: str | None = None,
    ) -> bool:
        job = self._store.get(job_id, tenant_id)
        if job is None:
            return False
        if job.status.value == "running":
            raise ValueError("运行中的任务不能删除")
        root = self.work_root.resolve()
        artifacts = self._store.list_artifacts(job_id)
        if self._object_storage is not None:
            for artifact in artifacts:
                try:
                    await self._object_storage.delete_key(str(artifact["object_key"]))
                except Exception:
                    pass
        targets = [
            self.work_dir(job_id),
            (root / "uploads" / job_id).resolve(),
        ]
        if not self._store.delete(job_id, job.tenant_id):
            current = self._store.get(job_id)
            if current is not None and current.status.value == "running":
                raise ValueError("运行中的任务不能删除")
            return False
        if self._clip_store is not None:
            self._clip_store.delete_for_job(job_id, job.tenant_id)
        for target in targets:
            if target.is_relative_to(root) and target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
        return True

    async def run_job(self, job: Job) -> None:
        try:
            workflow = self.load_workflow(job.workflow)
            work_dir = self.work_dir(job.id)
            work_dir.mkdir(parents=True, exist_ok=True)
            params: dict[str, Any] = {"input_path": job.input_path, **job.params}

            async def on_event(event) -> None:
                self._store.add_event(job.id, event)

            context = RunContext(
                job_id=job.id,
                work_dir=work_dir,
                params=params,
                on_event=on_event,
            )
            executor = WorkflowExecutor(self._registry, self._max_concurrency)
            result = await executor.run(workflow, context)
        except Exception as exc:
            self._store.mark_failed(job.id, f"{type(exc).__name__}: {exc}", 0)
            return

        if result.succeeded:
            try:
                self._write_clip_subtitles(work_dir, result.outputs)
            except Exception:
                pass
            if self._object_storage is not None:
                try:
                    uploaded = await self.upload_artifacts(
                        job.id,
                        work_dir,
                        tenant_id=job.tenant_id,
                    )
                    if uploaded:
                        shutil.rmtree(work_dir, ignore_errors=True)
                except Exception as exc:
                    result.outputs["storage_warning"] = (
                        f"cloud upload failed, artifacts kept locally: {exc}"
                    )
            self._store.mark_succeeded(job.id, result.outputs, result.duration_ms)
            try:
                self._persist_clip_segments(job, result.outputs)
            except Exception:
                pass
        else:
            self._store.mark_failed(
                job.id,
                result.error or "workflow failed",
                result.duration_ms,
            )

    def _write_clip_subtitles(
        self,
        work_dir: Path,
        outputs: dict[str, Any],
    ) -> None:
        clips = (
            (outputs.get("select") or {}).get("segments")
            or (outputs.get("split") or {}).get("segments")
            or []
        )
        segments = (outputs.get("transcript") or {}).get("segments") or []
        if not clips:
            return
        records = write_clip_subtitles(work_dir, clips, segments)
        if not records:
            return
        outputs["clip_subtitles"] = records
        full = next((item for item in records if item["kind"] == "full"), None)
        if full is not None:
            outputs.setdefault("transcript", {})["text_path"] = full["path"]

    def retry_job(self, job_id: str, tenant_id: str | None = None) -> bool:
        if not self._store.requeue(job_id, tenant_id):
            return False
        checkpoint = self.work_dir(job_id) / SYSTEM_DIR / CHECKPOINT_FILE
        checkpoint.unlink(missing_ok=True)
        if self._clip_store is not None and tenant_id:
            self._clip_store.delete_for_job(job_id, tenant_id)
        return True

    def ensure_clip_segments(self, job: Job) -> None:
        if self._clip_store is None or not job.result:
            return
        if self._clip_store.list_for_job(job.id, job.tenant_id):
            return
        try:
            self._persist_clip_segments(job, job.result)
        except Exception:
            pass

    def reset_clip_segments(self, job: Job) -> None:
        if self._clip_store is None or not job.result:
            return
        self._persist_clip_segments(job, job.result)

    def _persist_clip_segments(self, job: Job, outputs: dict[str, Any]) -> None:
        if self._clip_store is None:
            return
        selected = outputs.get("select", {}).get("segments") or []
        if not selected:
            selected = outputs.get("split", {}).get("segments") or []
        clips = outputs.get("cut", {}).get("clips") or []
        exports = outputs.get("export", {}).get("outputs") or []
        transcript_segments = outputs.get("transcript", {}).get("segments") or []
        if not selected or not clips:
            return

        source_duration = float(outputs.get("probe", {}).get("duration") or 0)
        source_name = str(
            job.params.get("source_name") or Path(job.input_path).name
        )
        clips_by_range = {
            (
                round(float(item.get("start") or 0), 3),
                round(float(item.get("end") or 0), 3),
            ): item
            for item in clips
        }
        records: list[dict[str, Any]] = []
        for index, segment in enumerate(selected):
            start = float(segment.get("start") or 0)
            end = float(segment.get("end") or 0)
            if end - start < 0.05:
                continue
            clip = clips_by_range.get(
                (round(start, 3), round(end, 3)),
                clips[index] if index < len(clips) else {},
            )
            clip_path = str(clip.get("path") or "")
            clip_exports = [
                {
                    "path": str(item.get("path") or ""),
                    "aspect": str(item.get("aspect") or ""),
                    "width": int(item.get("width") or 0),
                    "height": int(item.get("height") or 0),
                }
                for item in exports
                if str(item.get("source") or "") == clip_path
            ]
            transcript = " ".join(
                str(item.get("text") or "").strip()
                for item in transcript_segments
                if float(item.get("end") or 0) > start
                and float(item.get("start") or 0) < end
                and str(item.get("text") or "").strip()
            )
            score = float(segment.get("score") or 0)
            records.append(
                {
                    "seq": len(records),
                    "project_id": str(job.params.get("project_id") or ""),
                    "asset_id": str(job.params.get("asset_id") or ""),
                    "source_name": source_name,
                    "source_duration": source_duration,
                    "start": start,
                    "end": end,
                    "duration": end - start,
                    "title": str(segment.get("title") or f"片段 {index + 1}"),
                    "transcript": transcript,
                    "reason": str(segment.get("reason") or ""),
                    "score": score,
                    "kind": "highlight" if score >= 0.7 else "normal",
                    "clip_path": clip_path,
                    "exports": clip_exports,
                }
            )
        self._clip_store.replace_for_job(
            job_id=job.id,
            tenant_id=job.tenant_id,
            records=records,
        )
