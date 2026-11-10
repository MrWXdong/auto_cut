from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class Job:
    id: str
    workflow: str
    input_path: str
    tenant_id: str = "demo"
    status: JobStatus = JobStatus.QUEUED
    params: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    duration_ms: int | None = None
    result: dict[str, Any] | None = None
    work_dir: str = ""
