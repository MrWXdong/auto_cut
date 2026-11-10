from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

PUBLISH_SCHEMA = """
CREATE TABLE IF NOT EXISTS publish_accounts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    name TEXT NOT NULL,
    handle TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    followers INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publish_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    project_id TEXT,
    asset_id TEXT,
    account_id TEXT,
    account_name TEXT NOT NULL DEFAULT '',
    platform TEXT NOT NULL,
    title TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    result_url TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_publish_accounts_tenant
    ON publish_accounts (tenant_id, created_at);

CREATE INDEX IF NOT EXISTS idx_publish_jobs_schedule
    ON publish_jobs (tenant_id, status, scheduled_at);
"""

ACCOUNT_FIELDS = {"platform", "name", "handle", "status", "followers", "notes"}
JOB_FIELDS = {
    "project_id",
    "asset_id",
    "account_id",
    "account_name",
    "platform",
    "title",
    "scheduled_at",
    "status",
    "result_url",
    "error",
    "notes",
}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class PublishStore:
    def __init__(self, database_path: Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(PUBLISH_SCHEMA)
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def list_accounts(self, tenant_id: str = "demo") -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM publish_accounts WHERE tenant_id = ? ORDER BY created_at",
                (tenant_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_account(self, account_id: str, tenant_id: str = "demo") -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM publish_accounts WHERE id = ? AND tenant_id = ?",
                (account_id, tenant_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def create_account(
        self,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        name = str(values.get("name") or "").strip()
        platform = str(values.get("platform") or "").strip()
        if not name or not platform:
            raise ValueError("平台和账号名称不能为空")
        account_id = uuid.uuid4().hex[:12]
        now = _now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO publish_accounts (
                    id, tenant_id, platform, name, handle, status,
                    followers, notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    tenant_id,
                    platform,
                    name,
                    str(values.get("handle") or ""),
                    str(values.get("status") or "active"),
                    int(values.get("followers") or 0),
                    str(values.get("notes") or ""),
                    now,
                    now,
                ),
            )
            connection.commit()
        return self.get_account(account_id, tenant_id) or {}

    def update_account(
        self,
        account_id: str,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        fields: list[str] = []
        args: list[Any] = []
        for key in ACCOUNT_FIELDS:
            if key in values and values[key] is not None:
                fields.append(f"{key} = ?")
                args.append(values[key])
        if not fields:
            return self.get_account(account_id, tenant_id)
        fields.append("updated_at = ?")
        args.append(_now())
        args.extend([account_id, tenant_id])
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                f"UPDATE publish_accounts SET {', '.join(fields)} "
                "WHERE id = ? AND tenant_id = ?",
                args,
            )
            connection.commit()
        return self.get_account(account_id, tenant_id) if cursor.rowcount == 1 else None

    def delete_account(self, account_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM publish_accounts WHERE id = ? AND tenant_id = ?",
                (account_id, tenant_id),
            )
            connection.commit()
        return cursor.rowcount == 1

    def list_jobs(self, tenant_id: str = "demo", limit: int = 200) -> list[dict[str, Any]]:
        now = _now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE publish_jobs
                SET status = 'due', updated_at = ?
                WHERE tenant_id = ? AND status = 'scheduled' AND scheduled_at <= ?
                """,
                (now, tenant_id, now),
            )
            connection.commit()
            rows = connection.execute(
                """
                SELECT * FROM publish_jobs
                WHERE tenant_id = ?
                ORDER BY scheduled_at DESC LIMIT ?
                """,
                (tenant_id, max(1, min(limit, 500))),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_job(self, job_id: str, tenant_id: str = "demo") -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM publish_jobs WHERE id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def create_job(
        self,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        title = str(values.get("title") or "").strip()
        platform = str(values.get("platform") or "").strip()
        scheduled_at = str(values.get("scheduled_at") or "").strip()
        if not title or not platform or not scheduled_at:
            raise ValueError("标题、平台和发布时间不能为空")
        try:
            scheduled = datetime.fromisoformat(scheduled_at)
        except ValueError as exc:
            raise ValueError("发布时间格式无效") from exc
        now_dt = datetime.now().astimezone()
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=now_dt.tzinfo)
        status = "due" if scheduled <= now_dt else "scheduled"
        job_id = uuid.uuid4().hex[:12]
        now = _now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO publish_jobs (
                    id, tenant_id, project_id, asset_id, account_id,
                    account_name, platform, title, scheduled_at, status,
                    result_url, error, notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', '', ?, ?, ?)
                """,
                (
                    job_id,
                    tenant_id,
                    values.get("project_id"),
                    values.get("asset_id"),
                    values.get("account_id"),
                    str(values.get("account_name") or ""),
                    platform,
                    title,
                    scheduled.isoformat(timespec="seconds"),
                    status,
                    str(values.get("notes") or ""),
                    now,
                    now,
                ),
            )
            connection.commit()
        return self.get_job(job_id, tenant_id) or {}

    def update_job(
        self,
        job_id: str,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        fields: list[str] = []
        args: list[Any] = []
        for key in JOB_FIELDS:
            if key in values and values[key] is not None:
                fields.append(f"{key} = ?")
                args.append(values[key])
        if not fields:
            return self.get_job(job_id, tenant_id)
        fields.append("updated_at = ?")
        args.append(_now())
        args.extend([job_id, tenant_id])
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                f"UPDATE publish_jobs SET {', '.join(fields)} "
                "WHERE id = ? AND tenant_id = ?",
                args,
            )
            connection.commit()
        return self.get_job(job_id, tenant_id) if cursor.rowcount == 1 else None

    def delete_job(self, job_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM publish_jobs WHERE id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            )
            connection.commit()
        return cursor.rowcount == 1


class PublishService:
    def __init__(self, store: PublishStore) -> None:
        self._store = store

    def list_accounts(self, tenant_id: str = "demo") -> list[dict[str, Any]]:
        return self._store.list_accounts(tenant_id)

    def create_account(
        self,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        return self._store.create_account(values, tenant_id)

    def update_account(
        self,
        account_id: str,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        return self._store.update_account(account_id, values, tenant_id)

    def delete_account(self, account_id: str, tenant_id: str = "demo") -> bool:
        return self._store.delete_account(account_id, tenant_id)

    def list_jobs(self, tenant_id: str = "demo", limit: int = 200) -> list[dict[str, Any]]:
        return self._store.list_jobs(tenant_id, limit)

    def get_job(self, job_id: str, tenant_id: str = "demo") -> dict[str, Any] | None:
        return self._store.get_job(job_id, tenant_id)

    def update_job(
        self,
        job_id: str,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        return self._store.update_job(job_id, values, tenant_id)

    def create_job(
        self,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        account_id = str(values.get("account_id") or "")
        if account_id:
            account = self._store.get_account(account_id, tenant_id)
            if account is None:
                raise ValueError("发布账号不存在")
            values["account_name"] = account["name"]
            values["platform"] = account["platform"]
        return self._store.create_job(values, tenant_id)

    def mark_published(
        self,
        job_id: str,
        result_url: str = "",
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        return self._store.update_job(
            job_id,
            {
                "status": "published",
                "result_url": result_url,
                "error": "",
            },
            tenant_id,
        )

    def cancel_job(self, job_id: str, tenant_id: str = "demo") -> dict[str, Any] | None:
        job = self._store.get_job(job_id, tenant_id)
        if job is None:
            return None
        if job["status"] == "published":
            raise ValueError("已发布任务不能取消")
        return self._store.update_job(job_id, {"status": "canceled"}, tenant_id)

    def delete_job(self, job_id: str, tenant_id: str = "demo") -> bool:
        return self._store.delete_job(job_id, tenant_id)
