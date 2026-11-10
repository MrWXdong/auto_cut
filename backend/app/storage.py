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
    tenant_id TEXT NOT NULL DEFAULT 'demo',
    workflow TEXT NOT NULL,
    status TEXT NOT NULL,
    input_path TEXT NOT NULL,
    params TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    duration_ms INTEGER,
    error TEXT,
    result_json TEXT,
    work_dir TEXT NOT NULL DEFAULT ''
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

CREATE TABLE IF NOT EXISTS job_artifacts (
    job_id TEXT NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    object_key TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (job_id, relative_path)
);

CREATE INDEX IF NOT EXISTS idx_job_artifacts_job
    ON job_artifacts (job_id);

CREATE TABLE IF NOT EXISTS worker_heartbeats (
    worker_id TEXT PRIMARY KEY,
    host TEXT NOT NULL,
    pid INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    current_job_id TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    last_seen TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_worker_heartbeats_seen
    ON worker_heartbeats (last_seen);
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
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(jobs)")
            }
            if "tenant_id" not in columns:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'demo'"
                )
            if "work_dir" not in columns:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN work_dir TEXT NOT NULL DEFAULT ''"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_tenant_status "
                "ON jobs (tenant_id, status, created_at)"
            )
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
                INSERT INTO jobs (
                    id, tenant_id, workflow, status, input_path, params, created_at, work_dir
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.tenant_id,
                    job.workflow,
                    job.status.value,
                    job.input_path,
                    json.dumps(job.params, ensure_ascii=False),
                    created_at,
                    job.work_dir,
                ),
            )
            connection.commit()
        saved = self.get(job.id)
        if saved is None:
            raise RuntimeError(f"failed to create job: {job.id}")
        return saved

    def get(self, job_id: str, tenant_id: str | None = None) -> Job | None:
        query = "SELECT * FROM jobs WHERE id = ?"
        args: list[Any] = [job_id]
        if tenant_id:
            query += " AND tenant_id = ?"
            args.append(tenant_id)
        with closing(self._connect()) as connection:
            row = connection.execute(query, args).fetchone()
        return self._to_job(row) if row is not None else None

    def list(
        self,
        limit: int = 50,
        status: str | None = None,
        tenant_id: str | None = None,
    ) -> list[Job]:
        query = "SELECT * FROM jobs"
        args: list[Any] = []
        clauses: list[str] = []
        if tenant_id:
            clauses.append("tenant_id = ?")
            args.append(tenant_id)
        if status:
            clauses.append("status = ?")
            args.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with closing(self._connect()) as connection:
            rows = connection.execute(query, args).fetchall()
        return [self._to_job(row) for row in rows]

    def claim_next(self, tenant_id: str | None = None) -> Job | None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            query = "SELECT * FROM jobs WHERE status = ?"
            args: list[Any] = [JobStatus.QUEUED.value]
            if tenant_id:
                query += " AND tenant_id = ?"
                args.append(tenant_id)
            query += " ORDER BY created_at LIMIT 1"
            row = connection.execute(
                query,
                args,
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

    def update_result(
        self,
        job_id: str,
        tenant_id: str,
        result: dict[str, Any],
    ) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET result_json = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (json.dumps(result, ensure_ascii=False), job_id, tenant_id),
            )
            connection.commit()
        return cursor.rowcount == 1

    def heartbeat(
        self,
        worker_id: str,
        host: str,
        pid: int,
        *,
        status: str = "idle",
        current_job_id: str = "",
    ) -> None:
        now = utcnow()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO worker_heartbeats (
                    worker_id, host, pid, status, current_job_id, started_at, last_seen
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    host = excluded.host,
                    pid = excluded.pid,
                    status = excluded.status,
                    current_job_id = excluded.current_job_id,
                    last_seen = excluded.last_seen
                """,
                (worker_id, host, pid, status, current_job_id, now, now),
            )
            connection.commit()

    def remove_worker(self, worker_id: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "DELETE FROM worker_heartbeats WHERE worker_id = ?",
                (worker_id,),
            )
            connection.commit()

    def list_workers(self, stale_seconds: int = 15) -> dict[str, Any]:
        now = datetime.now(UTC)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM worker_heartbeats ORDER BY last_seen DESC"
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            try:
                last_seen = datetime.fromisoformat(row["last_seen"])
            except ValueError:
                last_seen = now
            age = max(0, int((now - last_seen).total_seconds()))
            item = dict(row)
            item["online"] = age <= stale_seconds
            item["age_seconds"] = age
            items.append(item)
        online = [item for item in items if item["online"]]
        return {
            "online": len(online),
            "stale_seconds": stale_seconds,
            "items": items,
            "last_seen": items[0]["last_seen"] if items else None,
        }

    def cancel(self, job_id: str, tenant_id: str | None = None) -> bool:
        tenant_clause = " AND tenant_id = ?" if tenant_id else ""
        args: list[Any] = [
            JobStatus.CANCELED.value,
            utcnow(),
            job_id,
            JobStatus.QUEUED.value,
        ]
        if tenant_id:
            args.append(tenant_id)
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                f"""
                UPDATE jobs
                SET status = ?, finished_at = ?
                WHERE id = ? AND status = ?{tenant_clause}
                """,
                args,
            )
            connection.commit()
            return cursor.rowcount == 1

    def requeue(self, job_id: str, tenant_id: str | None = None) -> bool:
        tenant_clause = " AND tenant_id = ?" if tenant_id else ""
        args: list[Any] = [
            JobStatus.QUEUED.value,
            job_id,
            JobStatus.FAILED.value,
            JobStatus.CANCELED.value,
        ]
        if tenant_id:
            args.append(tenant_id)
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                f"""
                UPDATE jobs
                SET status = ?, started_at = NULL, finished_at = NULL,
                    duration_ms = NULL, error = NULL, result_json = NULL
                WHERE id = ? AND status IN (?, ?){tenant_clause}
                """,
                args,
            )
            connection.commit()
            return cursor.rowcount == 1

    def delete(self, job_id: str, tenant_id: str | None = None) -> bool:
        tenant_clause = " AND tenant_id = ?" if tenant_id else ""
        args: list[Any] = [job_id, JobStatus.RUNNING.value]
        if tenant_id:
            args.append(tenant_id)
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                f"DELETE FROM jobs WHERE id = ? AND status != ?{tenant_clause}",
                args,
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

    def replace_artifacts(self, job_id: str, items: list[dict[str, Any]]) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM job_artifacts WHERE job_id = ?", (job_id,))
            for item in items:
                connection.execute(
                    """
                    INSERT INTO job_artifacts
                        (job_id, relative_path, object_key, size_bytes, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        item["relative_path"],
                        item["object_key"],
                        int(item["size_bytes"]),
                        utcnow(),
                    ),
                )
            connection.commit()

    def list_artifacts(self, job_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM job_artifacts
                WHERE job_id = ?
                ORDER BY relative_path
                """,
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def storage_bytes(self, tenant_id: str | None = None) -> int:
        with closing(self._connect()) as connection:
            if tenant_id:
                row = connection.execute(
                    """
                    SELECT COALESCE(SUM(a.size_bytes), 0) AS total
                    FROM job_artifacts a
                    JOIN jobs j ON j.id = a.job_id
                    WHERE j.tenant_id = ?
                    """,
                    (tenant_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT COALESCE(SUM(size_bytes), 0) AS total FROM job_artifacts"
                ).fetchone()
        return int(row["total"]) if row is not None else 0

    def get_artifact(self, job_id: str, relative_path: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT * FROM job_artifacts
                WHERE job_id = ? AND relative_path = ?
                """,
                (job_id, relative_path),
            ).fetchone()
        return dict(row) if row is not None else None

    def delete_artifact(self, job_id: str, relative_path: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                DELETE FROM job_artifacts
                WHERE job_id = ? AND relative_path = ?
                """,
                (job_id, relative_path),
            )
            connection.commit()
        return cursor.rowcount == 1

    @staticmethod
    def _to_job(row: sqlite3.Row) -> Job:
        raw_result = row["result_json"]
        return Job(
            id=row["id"],
            tenant_id=row["tenant_id"] or "demo",
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
            work_dir=row["work_dir"] or "",
        )
