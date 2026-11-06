from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.workflow.events import NodeEvent
from app.domain import Job, JobStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    workflow TEXT NOT NULL,
    status TEXT NOT NULL,
    input_path TEXT NOT NULL,
    params TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    duration_ms INTEGER,
    error TEXT,
    result_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_created
    ON jobs (status, created_at);

CREATE TABLE IF NOT EXISTS job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,
    node_type TEXT NOT NULL,
    status TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    duration_ms INTEGER,
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_events_job
    ON job_events (job_id, id);
"""


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class JobStore:
    """SQLite-backed job store.

    This is intentionally small: one process writes, one worker consumes.
    Swap it for PostgreSQL when the system needs multiple workers.
    """

    def __init__(self, database_path: Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.isolation_level = None
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def create(self, job: Job) -> Job:
        created_at = job.created_at or utcnow()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO jobs (id, workflow, status, input_path, params, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.workflow,
                    job.status.value,
                    job.input_path,
                    json.dumps(job.params, ensure_ascii=False),
                    created_at,
                ),
            )
            connection.commit()
        saved = self.get(job.id)
        if saved is None:
            raise RuntimeError(f"failed to create job: {job.id}")
        return saved

    def get(self, job_id: str) -> Job | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        return self._to_job(row) if row is not None else None

    def list(self, limit: int = 50, status: str | None = None) -> list[Job]:
        query = "SELECT * FROM jobs"
        args: list[Any] = []
        if status:
            query += " WHERE status = ?"
            args.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with closing(self._connect()) as connection:
            rows = connection.execute(query, args).fetchall()
        return [self._to_job(row) for row in rows]

    def claim_next(self) -> Job | None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at LIMIT 1",
                (JobStatus.QUEUED.value,),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            started_at = utcnow()
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, started_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    JobStatus.RUNNING.value,
                    started_at,
                    row["id"],
                    JobStatus.QUEUED.value,
                ),
            )
            connection.commit()
        job = self._to_job(row)
        job.status = JobStatus.RUNNING
        job.started_at = started_at
        return job

    def mark_succeeded(self, job_id: str, result: dict[str, Any], duration_ms: int) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, finished_at = ?, duration_ms = ?, result_json = ?, error = NULL
                WHERE id = ?
                """,
                (
                    JobStatus.SUCCEEDED.value,
                    utcnow(),
                    duration_ms,
                    json.dumps(result, ensure_ascii=False),
                    job_id,
                ),
            )
            connection.commit()

    def mark_failed(self, job_id: str, error: str, duration_ms: int) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, finished_at = ?, duration_ms = ?, error = ?
                WHERE id = ?
                """,
                (
                    JobStatus.FAILED.value,
                    utcnow(),
                    duration_ms,
                    error,
                    job_id,
                ),
            )
            connection.commit()

    def cancel(self, job_id: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, finished_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    JobStatus.CANCELED.value,
                    utcnow(),
                    job_id,
                    JobStatus.QUEUED.value,
                ),
            )
            connection.commit()
            return cursor.rowcount == 1

    def requeue(self, job_id: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, started_at = NULL, finished_at = NULL,
                    duration_ms = NULL, error = NULL, result_json = NULL
                WHERE id = ? AND status IN (?, ?)
                """,
                (
                    JobStatus.QUEUED.value,
                    job_id,
                    JobStatus.FAILED.value,
                    JobStatus.CANCELED.value,
                ),
            )
            connection.commit()
            return cursor.rowcount == 1

    def add_event(self, job_id: str, event: NodeEvent) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO job_events
                    (job_id, node_id, node_type, status, attempt, duration_ms, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    event.node_id,
                    event.node_type,
                    event.status,
                    event.attempt,
                    event.duration_ms,
                    event.error,
                    utcnow(),
                ),
            )
            connection.commit()

    def events(self, job_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM job_events WHERE job_id = ? ORDER BY id",
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _to_job(row: sqlite3.Row) -> Job:
        raw_result = row["result_json"]
        return Job(
            id=row["id"],
            workflow=row["workflow"],
            input_path=row["input_path"],
            status=JobStatus(row["status"]),
            params=json.loads(row["params"] or "{}"),
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            error=row["error"],
            duration_ms=row["duration_ms"],
            result=json.loads(raw_result) if raw_result else None,
        )
