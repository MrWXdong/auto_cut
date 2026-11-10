from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.storage_config import resolve_storage_root
from app.studio.modules import MODULE_BY_ID

BRAND_FIELDS = {
    "brand_name",
    "slogan",
    "primary_color",
    "secondary_color",
    "font_family",
    "watermark_text",
    "voice_tone",
    "intro_text",
    "outro_text",
    "logo_filename",
    "logo_storage_key",
}

BRAND_DEFAULTS: dict[str, Any] = {
    "brand_name": "",
    "slogan": "",
    "primary_color": "#0f766e",
    "secondary_color": "#2563eb",
    "font_family": "Microsoft YaHei",
    "watermark_text": "",
    "voice_tone": "",
    "intro_text": "",
    "outro_text": "",
    "logo_filename": "",
    "logo_storage_key": "",
}

STYLE_FIELDS = {
    "name",
    "description",
    "prompt",
    "negative_prompt",
    "model_ref",
    "palette",
    "shot_rhythm",
    "subtitle_style",
    "lora_name",
    "lora_trigger",
    "lora_base_model",
    "lora_status",
    "lora_job_id",
}

STYLE_DEFAULTS: dict[str, Any] = {
    "name": "",
    "description": "",
    "prompt": "",
    "negative_prompt": "",
    "model_ref": "",
    "palette": ["#0f766e", "#2563eb"],
    "shot_rhythm": "中速",
    "subtitle_style": "白字黑边",
    "lora_name": "",
    "lora_trigger": "",
    "lora_base_model": "",
    "lora_status": "none",
    "lora_job_id": "",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    aspect_ratio TEXT NOT NULL DEFAULT '9:16',
    style_id TEXT NOT NULL DEFAULT '',
    custom_style TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    kind TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    meta_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scripts (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    project_id TEXT,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS module_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    project_id TEXT,
    module TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT '',
    prompt TEXT NOT NULL DEFAULT '',
    params_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued',
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'demo',
    action TEXT NOT NULL,
    target TEXT NOT NULL DEFAULT '',
    meta_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipelines (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    project_id TEXT,
    name TEXT NOT NULL,
    template TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'queued',
    steps_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    tenant_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, key)
);

CREATE TABLE IF NOT EXISTS style_profiles (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    prompt TEXT NOT NULL DEFAULT '',
    negative_prompt TEXT NOT NULL DEFAULT '',
    model_ref TEXT NOT NULL DEFAULT '',
    palette_json TEXT NOT NULL DEFAULT '[]',
    shot_rhythm TEXT NOT NULL DEFAULT '',
    subtitle_style TEXT NOT NULL DEFAULT '',
    lora_name TEXT NOT NULL DEFAULT '',
    lora_trigger TEXT NOT NULL DEFAULT '',
    lora_base_model TEXT NOT NULL DEFAULT '',
    lora_status TEXT NOT NULL DEFAULT 'none',
    lora_job_id TEXT NOT NULL DEFAULT '',
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    meta_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quality_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    project_id TEXT,
    asset_id TEXT,
    job_id TEXT,
    rating INTEGER NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (conversation_id, id);
CREATE INDEX IF NOT EXISTS idx_feedback_tenant ON quality_feedback (tenant_id, id);

CREATE INDEX IF NOT EXISTS idx_projects_tenant ON projects (tenant_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_assets_project ON assets (project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_scripts_project ON scripts (project_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_jobs_module ON module_jobs (module, created_at);
CREATE INDEX IF NOT EXISTS idx_pipelines_tenant ON pipelines (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_styles_tenant ON style_profiles (tenant_id, is_default, updated_at);
"""


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _asset_kind(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}:
        return "image"
    if suffix in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
        return "video"
    if suffix in {".mp3", ".wav", ".m4a", ".flac", ".aac"}:
        return "audio"
    return "file"


class StudioStore:
    def __init__(self, database_path: Path, work_root: Path) -> None:
        self._path = Path(database_path)
        self._work_root = Path(work_root)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._work_root.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)
            project_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(projects)").fetchall()
            }
            if "style_id" not in project_columns:
                connection.execute(
                    "ALTER TABLE projects ADD COLUMN style_id TEXT NOT NULL DEFAULT ''"
                )
            if "custom_style" not in project_columns:
                connection.execute(
                    "ALTER TABLE projects ADD COLUMN custom_style TEXT NOT NULL DEFAULT ''"
                )
            connection.commit()

    @property
    def work_root(self) -> Path:
        return resolve_storage_root(self._work_root, self._path)

    @property
    def database_path(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.isolation_level = None
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    # projects
    def create_project(
        self,
        name: str,
        aspect_ratio: str = "9:16",
        tenant_id: str = "demo",
        style_id: str = "",
        custom_style: str = "",
    ) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValueError("project name is required")
        project_id = uuid.uuid4().hex[:8]
        now = utcnow()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO projects (
                    id, tenant_id, name, aspect_ratio, style_id, custom_style,
                    status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    project_id,
                    tenant_id,
                    name,
                    aspect_ratio,
                    style_id,
                    custom_style.strip(),
                    now,
                    now,
                ),
            )
            connection.commit()
        self.audit("project.create", project_id)
        return self.get_project(project_id, tenant_id) or {}

    def get_project(self, project_id: str, tenant_id: str = "demo") -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT p.*,
                    (
                        SELECT s.name FROM style_profiles s
                        WHERE s.id = p.style_id AND s.tenant_id = p.tenant_id
                    ) AS style_name
                FROM projects p
                WHERE p.id = ? AND p.tenant_id = ?
                """,
                (project_id, tenant_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_projects(self, tenant_id: str = "demo") -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT p.*,
                    (SELECT COUNT(*) FROM assets a WHERE a.project_id = p.id) AS asset_count,
                    (SELECT COUNT(*) FROM scripts s WHERE s.project_id = p.id) AS script_count,
                    (
                        SELECT s.name FROM style_profiles s
                        WHERE s.id = p.style_id AND s.tenant_id = p.tenant_id
                    ) AS style_name
                FROM projects p
                WHERE p.tenant_id = ?
                ORDER BY p.updated_at DESC
                """,
                (tenant_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_project(
        self,
        project_id: str,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        fields: list[str] = []
        args: list[Any] = []
        for key in ("name", "aspect_ratio", "style_id", "custom_style", "status"):
            if values.get(key) is not None:
                fields.append(f"{key} = ?")
                args.append(values[key])
        if not fields:
            return self.get_project(project_id, tenant_id)
        fields.append("updated_at = ?")
        args.append(utcnow())
        args.extend([project_id, tenant_id])
        with closing(self._connect()) as connection:
            connection.execute(
                f"UPDATE projects SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?",
                args,
            )
            connection.commit()
        self.audit("project.update", project_id)
        return self.get_project(project_id, tenant_id)

    def delete_project(self, project_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            storage_keys = [
                str(row["storage_key"])
                for row in connection.execute(
                    "SELECT storage_key FROM assets WHERE project_id = ? AND tenant_id = ?",
                    (project_id, tenant_id),
                ).fetchall()
            ]
            cursor = connection.execute(
                "DELETE FROM projects WHERE id = ? AND tenant_id = ?",
                (project_id, tenant_id),
            )
            connection.commit()
        if cursor.rowcount == 1:
            root = self.work_root.resolve()
            for storage_key in storage_keys:
                path = (root / storage_key).resolve()
                if path.is_relative_to(root):
                    path.unlink(missing_ok=True)
            self.audit("project.delete", project_id)
            return True
        return False

    # assets
    def add_asset(
        self,
        project_id: str,
        filename: str,
        storage_key: str,
        size_bytes: int,
        meta: dict[str, Any] | None = None,
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        if self.get_project(project_id, tenant_id) is None:
            raise KeyError("project not found")
        asset_id = uuid.uuid4().hex[:10]
        kind = _asset_kind(filename)
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO assets (
                    id, tenant_id, project_id, filename, kind, storage_key,
                    size_bytes, meta_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    tenant_id,
                    project_id,
                    filename,
                    kind,
                    storage_key,
                    size_bytes,
                    json.dumps(meta or {}, ensure_ascii=False),
                    utcnow(),
                ),
            )
            connection.commit()
        self.audit("asset.create", asset_id)
        return self.get_asset(asset_id, tenant_id) or {}

    def get_asset(self, asset_id: str, tenant_id: str = "demo") -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM assets WHERE id = ? AND tenant_id = ?",
                (asset_id, tenant_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_assets(self, project_id: str, tenant_id: str = "demo") -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM assets
                WHERE project_id = ? AND tenant_id = ?
                ORDER BY created_at DESC
                """,
                (project_id, tenant_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_asset(self, asset_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM assets WHERE id = ? AND tenant_id = ?",
                (asset_id, tenant_id),
            )
            connection.commit()
        if cursor.rowcount == 1:
            self.audit("asset.delete", asset_id)
            return True
        return False

    # scripts
    def create_script(
        self,
        title: str,
        body: str,
        project_id: str | None = None,
        tags: list[str] | None = None,
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        title = title.strip()
        body = body.strip()
        if not title or not body:
            raise ValueError("script title and body are required")
        script_id = uuid.uuid4().hex[:10]
        now = utcnow()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO scripts
                    (id, tenant_id, project_id, title, body, tags_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    script_id,
                    tenant_id,
                    project_id,
                    title,
                    body,
                    json.dumps(tags or [], ensure_ascii=False),
                    now,
                    now,
                ),
            )
            connection.commit()
        self.audit("script.create", script_id)
        return self.get_script(script_id, tenant_id) or {}

    def get_script(self, script_id: str, tenant_id: str = "demo") -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM scripts WHERE id = ? AND tenant_id = ?",
                (script_id, tenant_id),
            ).fetchone()
        if row is None:
            return None
        script = dict(row)
        script["tags"] = json.loads(script.pop("tags_json") or "[]")
        return script

    def list_scripts(
        self,
        project_id: str | None = None,
        tenant_id: str = "demo",
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM scripts WHERE tenant_id = ?"
        args: list[Any] = [tenant_id]
        if project_id:
            query += " AND project_id = ?"
            args.append(project_id)
        query += " ORDER BY updated_at DESC"
        with closing(self._connect()) as connection:
            rows = connection.execute(query, args).fetchall()
        items = []
        for row in rows:
            script = dict(row)
            script["tags"] = json.loads(script.pop("tags_json") or "[]")
            items.append(script)
        return items

    def update_script(
        self,
        script_id: str,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        fields: list[str] = []
        args: list[Any] = []
        for key in ("title", "body"):
            if values.get(key) is not None:
                fields.append(f"{key} = ?")
                args.append(values[key])
        if values.get("tags") is not None:
            fields.append("tags_json = ?")
            args.append(json.dumps(values["tags"], ensure_ascii=False))
        if not fields:
            return self.get_script(script_id, tenant_id)
        fields.append("updated_at = ?")
        args.append(utcnow())
        args.extend([script_id, tenant_id])
        with closing(self._connect()) as connection:
            connection.execute(
                f"UPDATE scripts SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?",
                args,
            )
            connection.commit()
        self.audit("script.update", script_id)
        return self.get_script(script_id, tenant_id)

    def delete_script(self, script_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM scripts WHERE id = ? AND tenant_id = ?",
                (script_id, tenant_id),
            )
            connection.commit()
        if cursor.rowcount == 1:
            self.audit("script.delete", script_id)
            return True
        return False

    # module jobs
    def create_job(
        self,
        module: str,
        mode: str,
        prompt: str,
        params: dict[str, Any] | None = None,
        project_id: str | None = None,
        tenant_id: str = "demo",
        job_id: str | None = None,
    ) -> dict[str, Any]:
        if module not in MODULE_BY_ID:
            raise KeyError("module not found")
        if project_id and self.get_project(project_id, tenant_id) is None:
            raise KeyError("project not found")
        job_id = job_id or uuid.uuid4().hex[:12]
        now = utcnow()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO module_jobs
                    (id, tenant_id, project_id, module, mode, prompt, params_json,
                     status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)
                """,
                (
                    job_id,
                    tenant_id,
                    project_id,
                    module,
                    mode,
                    prompt,
                    json.dumps(params or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            connection.commit()
        self.audit("module.job.create", job_id)
        return self.get_job(job_id, tenant_id) or {}

    def get_job(self, job_id: str, tenant_id: str = "demo") -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM module_jobs WHERE id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            ).fetchone()
        return self._job_dict(row) if row is not None else None

    def list_jobs(
        self,
        module: str | None = None,
        project_id: str | None = None,
        limit: int = 50,
        tenant_id: str = "demo",
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM module_jobs WHERE tenant_id = ?"
        args: list[Any] = [tenant_id]
        if module:
            query += " AND module = ?"
            args.append(module)
        if project_id:
            query += " AND project_id = ?"
            args.append(project_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with closing(self._connect()) as connection:
            rows = connection.execute(query, args).fetchall()
        return [self._job_dict(row) for row in rows]

    def cancel_job(self, job_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE module_jobs
                SET status = 'canceled', updated_at = ?
                WHERE id = ? AND tenant_id = ? AND status = 'queued'
                """,
                (utcnow(), job_id, tenant_id),
            )
            connection.commit()
        if cursor.rowcount == 1:
            self.audit("module.job.cancel", job_id)
            return True
        return False

    def delete_job(self, job_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                DELETE FROM module_jobs
                WHERE id = ? AND tenant_id = ? AND status != 'running'
                """,
                (job_id, tenant_id),
            )
            connection.commit()
        if cursor.rowcount == 1:
            self.audit("module.job.delete", job_id)
            return True
        return False

    def claim_next_job(self, tenant_id: str = "demo") -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM module_jobs
                WHERE tenant_id = ? AND status = 'queued'
                ORDER BY created_at LIMIT 1
                """,
                (tenant_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            connection.execute(
                "UPDATE module_jobs SET status = 'running', updated_at = ? WHERE id = ?",
                (utcnow(), row["id"]),
            )
            connection.commit()
        job = self._job_dict(row)
        job["status"] = "running"
        return job

    def update_job(
        self,
        job_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        tenant_id: str = "demo",
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE module_jobs
                SET status = ?, result_json = ?, error = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (
                    status,
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    error,
                    utcnow(),
                    job_id,
                    tenant_id,
                ),
            )
            connection.commit()

    # pipelines
    def create_pipeline(
        self,
        name: str,
        steps: list[dict[str, Any]],
        template: str = "",
        project_id: str | None = None,
        tenant_id: str = "demo",
        pipeline_id: str | None = None,
    ) -> dict[str, Any]:
        if not steps:
            raise ValueError("pipeline must contain at least one step")
        if project_id and self.get_project(project_id, tenant_id) is None:
            raise KeyError("project not found")

        prepared: list[dict[str, Any]] = []
        for step in steps:
            module = str(step.get("module") or "")
            if module not in MODULE_BY_ID:
                raise ValueError(f"unknown module: {module}")
            prepared.append(
                {
                    "id": uuid.uuid4().hex[:8],
                    "module": module,
                    "mode": str(step.get("mode") or ""),
                    "prompt": str(step.get("prompt") or ""),
                    "status": "queued",
                    "result": None,
                }
            )

        pipeline_id = pipeline_id or uuid.uuid4().hex[:12]
        now = utcnow()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO pipelines (
                    id, tenant_id, project_id, name, template, status,
                    steps_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?)
                """,
                (
                    pipeline_id,
                    tenant_id,
                    project_id,
                    name,
                    template,
                    json.dumps(prepared, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            connection.commit()
        self.audit("pipeline.create", pipeline_id)
        return self.get_pipeline(pipeline_id, tenant_id) or {}

    def get_pipeline(
        self,
        pipeline_id: str,
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM pipelines WHERE id = ? AND tenant_id = ?",
                (pipeline_id, tenant_id),
            ).fetchone()
        return self._pipeline_dict(row) if row is not None else None

    def list_pipelines(
        self,
        tenant_id: str = "demo",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM pipelines
                WHERE tenant_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (tenant_id, limit),
            ).fetchall()
        return [self._pipeline_dict(row) for row in rows]

    def cancel_pipeline(self, pipeline_id: str, tenant_id: str = "demo") -> bool:
        pipeline = self.get_pipeline(pipeline_id, tenant_id)
        if pipeline is None or pipeline["status"] != "queued":
            return False
        steps = [{**step, "status": "canceled"} for step in pipeline["steps"]]
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE pipelines
                SET status = 'canceled', steps_json = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (json.dumps(steps, ensure_ascii=False), utcnow(), pipeline_id, tenant_id),
            )
            connection.commit()
        self.audit("pipeline.cancel", pipeline_id)
        return True

    def delete_pipeline(self, pipeline_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM pipelines WHERE id = ? AND tenant_id = ?",
                (pipeline_id, tenant_id),
            )
            connection.commit()
        if cursor.rowcount == 1:
            self.audit("pipeline.delete", pipeline_id)
            return True
        return False

    def claim_next_pipeline(self, tenant_id: str = "demo") -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM pipelines
                WHERE tenant_id = ? AND status = 'queued'
                ORDER BY created_at LIMIT 1
                """,
                (tenant_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            connection.execute(
                "UPDATE pipelines SET status = 'running', updated_at = ? WHERE id = ?",
                (utcnow(), row["id"]),
            )
            connection.commit()
        pipeline = self._pipeline_dict(row)
        pipeline["status"] = "running"
        return pipeline

    def update_pipeline(
        self,
        pipeline_id: str,
        status: str,
        steps: list[dict[str, Any]],
        tenant_id: str = "demo",
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE pipelines
                SET status = ?, steps_json = ?, updated_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (
                    status,
                    json.dumps(steps, ensure_ascii=False),
                    utcnow(),
                    pipeline_id,
                    tenant_id,
                ),
            )
            connection.commit()

    def usage(self, tenant_id: str = "demo") -> dict[str, int]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM projects WHERE tenant_id = ?) AS projects,
                    (SELECT COUNT(*) FROM assets WHERE tenant_id = ?) AS assets,
                    (SELECT COUNT(*) FROM scripts WHERE tenant_id = ?) AS scripts,
                    (SELECT COUNT(*) FROM module_jobs WHERE tenant_id = ?) AS jobs,
                    (SELECT COALESCE(SUM(size_bytes), 0) FROM assets
                     WHERE tenant_id = ?) AS asset_bytes
                """,
                (tenant_id, tenant_id, tenant_id, tenant_id, tenant_id),
            ).fetchone()
            usage = dict(row) if row is not None else {}
            workflow_jobs = 0
            has_jobs = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'jobs'"
            ).fetchone()
            if has_jobs is not None:
                job_row = connection.execute(
                    "SELECT COUNT(*) AS total FROM jobs WHERE tenant_id = ?",
                    (tenant_id,),
                ).fetchone()
                workflow_jobs = int(job_row["total"]) if job_row is not None else 0
        usage["workflow_jobs"] = workflow_jobs
        usage["jobs_total"] = int(usage.get("jobs", 0)) + workflow_jobs
        return usage

    def audit(
        self,
        action: str,
        target: str = "",
        meta: dict[str, Any] | None = None,
        tenant_id: str = "demo",
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO audit_logs (tenant_id, actor, action, target, meta_json, created_at)
                VALUES (?, 'demo', ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    action,
                    target,
                    json.dumps(meta or {}, ensure_ascii=False),
                    utcnow(),
                ),
            )
            connection.commit()

    def list_logs(self, limit: int = 100, tenant_id: str = "demo") -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM audit_logs
                WHERE tenant_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (tenant_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_preference(self, key: str, tenant_id: str = "demo") -> dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT value_json FROM preferences WHERE tenant_id = ? AND key = ?",
                (tenant_id, key),
            ).fetchone()
        return json.loads(row["value_json"]) if row is not None else {}

    def set_preference(
        self,
        key: str,
        value: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO preferences (tenant_id, key, value_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (tenant_id, key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (
                    tenant_id,
                    key,
                    json.dumps(value, ensure_ascii=False),
                    utcnow(),
                ),
            )
            connection.commit()
        self.audit("preference.update", key)
        return value

    # brand kit
    def get_brand_kit(self, tenant_id: str = "demo") -> dict[str, Any]:
        stored = self.get_preference("brand_kit", tenant_id)
        values = {
            key: value
            for key, value in stored.items()
            if key in BRAND_FIELDS
        }
        return {**BRAND_DEFAULTS, **values, "configured": bool(stored)}

    def brand_configured(self, tenant_id: str = "demo") -> bool:
        return bool(self.get_preference("brand_kit", tenant_id))

    def set_brand_kit(
        self,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        current = {
            key: value
            for key, value in self.get_brand_kit(tenant_id).items()
            if key in BRAND_FIELDS
        }
        for key, value in values.items():
            if key in BRAND_FIELDS and value is not None:
                current[key] = str(value)
        self.set_preference("brand_kit", current, tenant_id)
        self.audit("brand.update", "brand_kit", tenant_id=tenant_id)
        return {**current, "configured": True}

    # style profiles
    @staticmethod
    def _style_dict(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["palette"] = json.loads(item.pop("palette_json") or "[]")
        item["is_default"] = bool(item["is_default"])
        return item

    def create_style(
        self,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        name = str(values.get("name") or "").strip()
        if not name:
            raise ValueError("style name is required")

        style_id = uuid.uuid4().hex[:10]
        now = utcnow()
        palette = values.get("palette") or STYLE_DEFAULTS["palette"]
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO style_profiles (
                    id, tenant_id, name, description, prompt, negative_prompt,
                    model_ref, palette_json, shot_rhythm, subtitle_style,
                    lora_name, lora_trigger, lora_base_model, lora_status,
                    lora_job_id, is_default, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    style_id,
                    tenant_id,
                    name,
                    str(values.get("description") or ""),
                    str(values.get("prompt") or ""),
                    str(values.get("negative_prompt") or ""),
                    str(values.get("model_ref") or ""),
                    json.dumps(palette, ensure_ascii=False),
                    str(values.get("shot_rhythm") or STYLE_DEFAULTS["shot_rhythm"]),
                    str(values.get("subtitle_style") or STYLE_DEFAULTS["subtitle_style"]),
                    str(values.get("lora_name") or ""),
                    str(values.get("lora_trigger") or ""),
                    str(values.get("lora_base_model") or ""),
                    str(values.get("lora_status") or "none"),
                    str(values.get("lora_job_id") or ""),
                    now,
                    now,
                ),
            )
            connection.commit()
        self.audit("style.create", style_id, tenant_id=tenant_id)
        return self.get_style(style_id, tenant_id) or {}

    def get_style(self, style_id: str, tenant_id: str = "demo") -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM style_profiles WHERE id = ? AND tenant_id = ?",
                (style_id, tenant_id),
            ).fetchone()
        return self._style_dict(row) if row is not None else None

    def list_styles(self, tenant_id: str = "demo") -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM style_profiles
                WHERE tenant_id = ?
                ORDER BY is_default DESC, updated_at DESC
                """,
                (tenant_id,),
            ).fetchall()
        return [self._style_dict(row) for row in rows]

    def update_style(
        self,
        style_id: str,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        fields: list[str] = []
        args: list[Any] = []
        for key in STYLE_FIELDS:
            if key not in values or values[key] is None:
                continue
            if key == "palette":
                fields.append("palette_json = ?")
                args.append(json.dumps(values[key], ensure_ascii=False))
            else:
                fields.append(f"{key} = ?")
                args.append(str(values[key]))
        if not fields:
            return self.get_style(style_id, tenant_id)
        fields.append("updated_at = ?")
        args.append(utcnow())
        args.extend([style_id, tenant_id])
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                f"UPDATE style_profiles SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?",
                args,
            )
            connection.commit()
        if cursor.rowcount != 1:
            return None
        self.audit("style.update", style_id, tenant_id=tenant_id)
        return self.get_style(style_id, tenant_id)

    def delete_style(self, style_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM style_profiles WHERE id = ? AND tenant_id = ?",
                (style_id, tenant_id),
            )
            connection.commit()
        if cursor.rowcount == 1:
            self.audit("style.delete", style_id, tenant_id=tenant_id)
            return True
        return False

    def set_default_style(
        self,
        style_id: str,
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        now = utcnow()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            target = connection.execute(
                "SELECT id FROM style_profiles WHERE id = ? AND tenant_id = ?",
                (style_id, tenant_id),
            ).fetchone()
            if target is None:
                connection.rollback()
                return None
            connection.execute(
                "UPDATE style_profiles SET is_default = 0, updated_at = ? WHERE tenant_id = ?",
                (now, tenant_id),
            )
            connection.execute(
                """
                UPDATE style_profiles
                SET is_default = 1, updated_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (now, style_id, tenant_id),
            )
            connection.commit()
        self.audit("style.default", style_id, tenant_id=tenant_id)
        return self.get_style(style_id, tenant_id)

    def get_default_style(self, tenant_id: str = "demo") -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT * FROM style_profiles
                WHERE tenant_id = ? AND is_default = 1
                LIMIT 1
                """,
                (tenant_id,),
            ).fetchone()
        return self._style_dict(row) if row is not None else None

    def effective_style(
        self,
        project_id: str | None,
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        if project_id:
            project = self.get_project(project_id, tenant_id)
            custom_style = str(project.get("custom_style") or "").strip() if project else ""
            if custom_style:
                base = self.get_default_style(tenant_id) or {}
                return {
                    **STYLE_DEFAULTS,
                    **base,
                    "id": "",
                    "name": "自定义风格",
                    "prompt": custom_style,
                    "is_default": False,
                    "custom": True,
                }
            style_id = str(project.get("style_id") or "") if project else ""
            if style_id:
                style = self.get_style(style_id, tenant_id)
                if style is not None:
                    return style
        return self.get_default_style(tenant_id)

    # conversations
    def create_conversation(self, title: str = "新对话", tenant_id: str = "demo") -> dict[str, Any]:
        conversation_id = uuid.uuid4().hex[:12]
        now = utcnow()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO conversations (id, tenant_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, tenant_id, title.strip() or "新对话", now, now),
            )
            connection.commit()
        return self.get_conversation(conversation_id, tenant_id) or {}

    def get_conversation(
        self,
        conversation_id: str,
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM conversations WHERE id = ? AND tenant_id = ?",
                (conversation_id, tenant_id),
            ).fetchone()
            if row is None:
                return None
            messages = connection.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id",
                (conversation_id,),
            ).fetchall()
        conversation = dict(row)
        conversation["messages"] = [
            {
                **{key: value for key, value in dict(message).items() if key != "meta_json"},
                "meta": json.loads(message["meta_json"] or "{}"),
            }
            for message in messages
        ]
        return conversation

    def list_conversations(
        self,
        tenant_id: str = "demo",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT c.*,
                    (SELECT COUNT(*) FROM messages m
                     WHERE m.conversation_id = c.id) AS message_count,
                    (SELECT content FROM messages m WHERE m.conversation_id = c.id
                     ORDER BY id DESC LIMIT 1) AS last_message
                FROM conversations c
                WHERE c.tenant_id = ?
                ORDER BY c.updated_at DESC LIMIT ?
                """,
                (tenant_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        meta: dict[str, Any] | None = None,
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        now = utcnow()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO messages (conversation_id, role, content, meta_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    role,
                    content,
                    json.dumps(meta or {}, ensure_ascii=False),
                    now,
                ),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ? AND tenant_id = ?",
                (now, conversation_id, tenant_id),
            )
            connection.commit()
        return {"role": role, "content": content, "meta": meta or {}, "created_at": now}

    def delete_conversation(self, conversation_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM conversations WHERE id = ? AND tenant_id = ?",
                (conversation_id, tenant_id),
            )
            connection.commit()
        return cursor.rowcount == 1

    # quality feedback
    def add_feedback(
        self,
        rating: int,
        *,
        project_id: str | None = None,
        asset_id: str | None = None,
        job_id: str | None = None,
        tags: list[str] | None = None,
        comment: str = "",
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO quality_feedback (
                    tenant_id, project_id, asset_id, job_id, rating,
                    tags_json, comment, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id,
                    project_id,
                    asset_id,
                    job_id,
                    rating,
                    json.dumps(tags or [], ensure_ascii=False),
                    comment.strip(),
                    utcnow(),
                ),
            )
            connection.commit()
            feedback_id = cursor.lastrowid
        return {
            "id": feedback_id,
            "rating": rating,
            "tags": tags or [],
            "comment": comment.strip(),
        }

    def list_feedback(
        self,
        project_id: str | None = None,
        limit: int = 100,
        tenant_id: str = "demo",
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM quality_feedback WHERE tenant_id = ?"
        args: list[Any] = [tenant_id]
        if project_id:
            query += " AND project_id = ?"
            args.append(project_id)
        query += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with closing(self._connect()) as connection:
            rows = connection.execute(query, args).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["tags"] = json.loads(item.pop("tags_json") or "[]")
            items.append(item)
        return items

    def feedback_summary(self, tenant_id: str = "demo") -> dict[str, Any]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT rating, tags_json FROM quality_feedback WHERE tenant_id = ?",
                (tenant_id,),
            ).fetchall()
        if not rows:
            return {"total": 0, "average": 0, "negative": 0, "top_tags": []}

        ratings = [int(row["rating"]) for row in rows]
        tag_counts: dict[str, int] = {}
        for row in rows:
            for tag in json.loads(row["tags_json"] or "[]"):
                tag_counts[str(tag)] = tag_counts.get(str(tag), 0) + 1
        top_tags = sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:5]
        return {
            "total": len(ratings),
            "average": round(sum(ratings) / len(ratings), 2),
            "negative": sum(1 for rating in ratings if rating <= 2),
            "top_tags": [{"tag": tag, "count": count} for tag, count in top_tags],
        }

    @staticmethod
    def _job_dict(row: sqlite3.Row) -> dict[str, Any]:
        job = dict(row)
        job["params"] = json.loads(job.pop("params_json") or "{}")
        raw_result = job.pop("result_json")
        job["result"] = json.loads(raw_result) if raw_result else None
        return job

    @staticmethod
    def _pipeline_dict(row: sqlite3.Row) -> dict[str, Any]:
        pipeline = dict(row)
        pipeline["steps"] = json.loads(pipeline.pop("steps_json") or "[]")
        return pipeline
