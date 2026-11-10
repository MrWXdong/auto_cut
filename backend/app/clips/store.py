from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from itertools import pairwise
from pathlib import Path
from typing import Any

from app.storage import utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS clip_segments (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    project_id TEXT NOT NULL DEFAULT '',
    asset_id TEXT NOT NULL DEFAULT '',
    source_name TEXT NOT NULL DEFAULT '',
    source_duration REAL NOT NULL DEFAULT 0,
    seq INTEGER NOT NULL DEFAULT 0,
    start REAL NOT NULL,
    "end" REAL NOT NULL,
    duration REAL NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    transcript TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    score REAL NOT NULL DEFAULT 0,
    kind TEXT NOT NULL DEFAULT 'normal',
    locked INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    clip_path TEXT NOT NULL DEFAULT '',
    export_paths_json TEXT NOT NULL DEFAULT '[]',
    merged_from_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clip_segments_job
    ON clip_segments (tenant_id, job_id, status, seq);
"""


class ClipSegmentStore:
    def __init__(self, database_path: Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(clip_segments)")
            }
            if "merged_from_json" not in columns:
                connection.execute(
                    "ALTER TABLE clip_segments "
                    "ADD COLUMN merged_from_json TEXT NOT NULL DEFAULT '[]'"
                )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def replace_for_job(
        self,
        *,
        job_id: str,
        tenant_id: str,
        records: list[dict[str, Any]],
    ) -> None:
        now = utcnow()
        with closing(self._connect()) as connection:
            connection.execute(
                "DELETE FROM clip_segments WHERE job_id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            )
            for record in records:
                connection.execute(
                    """
                    INSERT INTO clip_segments (
                        id, tenant_id, job_id, project_id, asset_id, source_name,
                        source_duration, seq, start, "end", duration, title,
                        transcript, reason, score, kind, locked, status,
                        clip_path, export_paths_json, merged_from_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(record.get("id") or uuid.uuid4().hex[:12]),
                        tenant_id,
                        job_id,
                        str(record.get("project_id") or ""),
                        str(record.get("asset_id") or ""),
                        str(record.get("source_name") or ""),
                        float(record.get("source_duration") or 0),
                        int(record.get("seq") or 0),
                        float(record.get("start") or 0),
                        float(record.get("end") or 0),
                        float(record.get("duration") or 0),
                        str(record.get("title") or ""),
                        str(record.get("transcript") or ""),
                        str(record.get("reason") or ""),
                        float(record.get("score") or 0),
                        str(record.get("kind") or "normal"),
                        1 if record.get("locked") else 0,
                        str(record.get("status") or "active"),
                        str(record.get("clip_path") or ""),
                        json.dumps(record.get("exports") or [], ensure_ascii=False),
                        "[]",
                        now,
                        now,
                    ),
                )
            connection.commit()

    def list_for_job(
        self,
        job_id: str,
        tenant_id: str,
        *,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM clip_segments WHERE job_id = ? AND tenant_id = ?"
        if not include_deleted:
            query += " AND status = 'active'"
        query += " ORDER BY seq, start, id"
        with closing(self._connect()) as connection:
            rows = connection.execute(query, (job_id, tenant_id)).fetchall()
        return [self._to_dict(row) for row in rows]

    def get(self, segment_id: str, tenant_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM clip_segments WHERE id = ? AND tenant_id = ?",
                (segment_id, tenant_id),
            ).fetchone()
        return self._to_dict(row) if row is not None else None

    def update(
        self,
        segment_id: str,
        tenant_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        allowed = {"start", "end", "duration", "title", "kind", "locked", "seq"}
        updates = {key: value for key, value in values.items() if key in allowed}
        if not updates:
            return self.get(segment_id, tenant_id)
        updates["updated_at"] = utcnow()
        assignments = ", ".join(f'"{key}" = ?' for key in updates)
        args = [*updates.values(), segment_id, tenant_id]
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                f"UPDATE clip_segments SET {assignments} WHERE id = ? AND tenant_id = ?",
                args,
            )
            connection.commit()
        if cursor.rowcount != 1:
            return None
        return self.get(segment_id, tenant_id)

    def delete(self, segment_id: str, tenant_id: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE clip_segments
                SET status = 'deleted', updated_at = ?
                WHERE id = ? AND tenant_id = ? AND status = 'active'
                """,
                (utcnow(), segment_id, tenant_id),
            )
            connection.commit()
        return cursor.rowcount == 1

    def merge(
        self,
        *,
        job_id: str,
        tenant_id: str,
        segment_ids: list[str],
    ) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            placeholders = ",".join("?" for _ in segment_ids)
            rows = connection.execute(
                f"""
                SELECT * FROM clip_segments
                WHERE job_id = ? AND tenant_id = ? AND status = 'active'
                  AND id IN ({placeholders})
                ORDER BY start, seq
                """,
                (job_id, tenant_id, *segment_ids),
            ).fetchall()
            segments = [self._to_dict(row) for row in rows]
            if len(segments) != len(set(segment_ids)):
                raise ValueError("segment not found")
            if any(int(segment["locked"]) for segment in segments):
                raise ValueError("locked segments cannot be merged")
            for previous, current in pairwise(segments):
                if abs(float(current["start"]) - float(previous["end"])) > 0.5:
                    raise ValueError("only adjacent segments can be merged")

            start = min(float(segment["start"]) for segment in segments)
            end = max(float(segment["end"]) for segment in segments)
            title = " / ".join(
                str(segment["title"]).strip()
                for segment in segments
                if str(segment["title"]).strip()
            )[:80]
            merged_id = uuid.uuid4().hex[:12]
            now = utcnow()
            connection.execute(
                f"""
                UPDATE clip_segments
                SET status = 'merged', updated_at = ?
                WHERE job_id = ? AND tenant_id = ? AND id IN ({placeholders})
                """,
                (now, job_id, tenant_id, *segment_ids),
            )
            connection.execute(
                """
                INSERT INTO clip_segments (
                    id, tenant_id, job_id, project_id, asset_id, source_name,
                    source_duration, seq, start, "end", duration, title,
                    transcript, reason, score, kind, locked, status,
                    clip_path, export_paths_json, merged_from_json, created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    0, 'active', '', '[]', ?, ?, ?
                )
                """,
                (
                    merged_id,
                    tenant_id,
                    job_id,
                    segments[0]["project_id"],
                    segments[0]["asset_id"],
                    segments[0]["source_name"],
                    segments[0]["source_duration"],
                    min(int(segment["seq"]) for segment in segments),
                    start,
                    end,
                    end - start,
                    title or f"合并片段 {len(segments)} 段",
                    " ".join(
                        str(segment["transcript"]).strip()
                        for segment in segments
                        if str(segment["transcript"]).strip()
                    ),
                    "手动合并",
                    max(float(segment["score"]) for segment in segments),
                    (
                        "highlight"
                        if any(segment["kind"] == "highlight" for segment in segments)
                        else "normal"
                    ),
                    json.dumps([segment["id"] for segment in segments], ensure_ascii=False),
                    now,
                    now,
                ),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM clip_segments WHERE id = ?",
                (merged_id,),
            ).fetchone()
        return self._to_dict(row) if row is not None else {}

    def unmerge(
        self,
        *,
        job_id: str,
        tenant_id: str,
        segment_id: str,
    ) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT * FROM clip_segments
                WHERE job_id = ? AND tenant_id = ? AND id = ? AND status = 'active'
                """,
                (job_id, tenant_id, segment_id),
            ).fetchone()
            if row is None:
                raise ValueError("segment not found")
            merged = self._to_dict(row)
            source_ids = [str(item) for item in merged.get("merged_from") or []]
            if source_ids:
                placeholders = ",".join("?" for _ in source_ids)
                source_rows = connection.execute(
                    f"""
                    SELECT * FROM clip_segments
                    WHERE job_id = ? AND tenant_id = ? AND id IN ({placeholders})
                    """,
                    (job_id, tenant_id, *source_ids),
                ).fetchall()
            else:
                source_rows = connection.execute(
                    """
                    SELECT * FROM clip_segments
                    WHERE job_id = ? AND tenant_id = ? AND status = 'merged'
                      AND start >= ? AND "end" <= ?
                    ORDER BY seq, start
                    """,
                    (
                        job_id,
                        tenant_id,
                        float(merged["start"]) - 0.05,
                        float(merged["end"]) + 0.05,
                    ),
                ).fetchall()
            if not source_rows:
                raise ValueError("no merged source segments found")

            now = utcnow()
            restored_ids = [str(item["id"]) for item in source_rows]
            placeholders = ",".join("?" for _ in restored_ids)
            connection.execute(
                f"""
                UPDATE clip_segments
                SET status = 'active', updated_at = ?
                WHERE job_id = ? AND tenant_id = ? AND id IN ({placeholders})
                """,
                (now, job_id, tenant_id, *restored_ids),
            )
            connection.execute(
                """
                UPDATE clip_segments
                SET status = 'unmerged', updated_at = ?
                WHERE job_id = ? AND tenant_id = ? AND id = ?
                """,
                (now, job_id, tenant_id, segment_id),
            )
            connection.commit()
            restored = connection.execute(
                f"""
                SELECT * FROM clip_segments
                WHERE job_id = ? AND tenant_id = ? AND id IN ({placeholders})
                ORDER BY seq, start
                """,
                (job_id, tenant_id, *restored_ids),
            ).fetchall()
        return [self._to_dict(item) for item in restored]

    def reorder(self, job_id: str, tenant_id: str, segment_ids: list[str]) -> None:
        with closing(self._connect()) as connection:
            active = connection.execute(
                """
                SELECT id FROM clip_segments
                WHERE job_id = ? AND tenant_id = ? AND status = 'active'
                """,
                (job_id, tenant_id),
            ).fetchall()
            active_ids = {str(row["id"]) for row in active}
            if set(segment_ids) != active_ids:
                raise ValueError("order must contain every active segment exactly once")
            for seq, segment_id in enumerate(segment_ids):
                connection.execute(
                    """
                    UPDATE clip_segments
                    SET seq = ?, updated_at = ?
                    WHERE id = ? AND tenant_id = ?
                    """,
                    (seq, utcnow(), segment_id, tenant_id),
                )
            connection.commit()

    def delete_for_job(self, job_id: str, tenant_id: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "DELETE FROM clip_segments WHERE job_id = ? AND tenant_id = ?",
                (job_id, tenant_id),
            )
            connection.commit()

    @staticmethod
    def _to_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["locked"] = bool(data.get("locked"))
        data["exports"] = json.loads(data.pop("export_paths_json") or "[]")
        data["merged_from"] = json.loads(data.pop("merged_from_json") or "[]")
        return data
