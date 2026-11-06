from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from app.core.workflow.context import RunContext
from app.core.workflow.executor import WorkflowExecutor
from app.core.workflow.graph import WorkflowSpec
from app.core.workflow.registry import NodeRegistry
from app.domain import Job
from app.storage import JobStore, utcnow

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
    ) -> None:
        self._store = store
        self._work_root = Path(work_root)
        self._registry = registry
        self._max_concurrency = max_concurrency

    @property
    def store(self) -> JobStore:
        return self._store

    @property
    def work_root(self) -> Path:
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
    ) -> Job:
        self.load_workflow(workflow)
        job = Job(
            id=job_id or uuid.uuid4().hex[:12],
            workflow=workflow,
            input_path=str(Path(input_path).resolve()),
            params=dict(params or {}),
            created_at=utcnow(),
        )
        return self._store.create(job)

    def work_dir(self, job_id: str) -> Path:
        return (self._work_root / job_id).resolve()

    async def run_job(self, job: Job) -> None:
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
        try:
            result = await executor.run(workflow, context)
        except Exception as exc:
            self._store.mark_failed(job.id, f"{type(exc).__name__}: {exc}", 0)
            return

        if result.succeeded:
            self._store.mark_succeeded(job.id, result.outputs, result.duration_ms)
        else:
            self._store.mark_failed(
                job.id,
                result.error or "workflow failed",
                result.duration_ms,
            )
