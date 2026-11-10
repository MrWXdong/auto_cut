from __future__ import annotations

import json
import re
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from app.nodes.subtitle import write_clip_subtitles
from app.storage_names import (
    AUDIO_DIR,
    AUDIO_FILE,
    CHECKPOINT_FILE,
    CLIPS_DIR,
    EXPORTS_DIR,
    FULL_SUBTITLE_TXT,
    SUBTITLES_DIR,
    SYSTEM_DIR,
    TRANSCRIPT_FILE,
)

INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
DEV_FILE_PATTERNS = (
    "chat_smoke.py",
    "kb_smoke.py",
    "quality_smoke.py",
    "studio_smoke.py",
    "*-smoke*.db",
    "asr-probe*.wav",
    "audio-probe.wav",
    "ai-edit-test.mp4",
    "ffmpeg-test-input.mp4",
)


def safe_storage_component(value: str, fallback: str = "素材", limit: int = 40) -> str:
    name = INVALID_CHARS.sub("_", str(value or "")).strip(" .")
    return name[:limit] or fallback


def job_folder_name(job_id: str, created_at: str, source_name: str) -> str:
    try:
        stamp = datetime.fromisoformat(created_at).astimezone().strftime("%Y%m%d-%H%M")
    except (TypeError, ValueError):
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
    stem = Path(str(source_name or "素材")).stem
    return f"{stamp}_{safe_storage_component(stem)}_{job_id}"


def job_work_relpath(job_id: str, created_at: str, source_name: str) -> str:
    return f"jobs/{job_folder_name(job_id, created_at, source_name)}"


def _replace_paths(value: Any, old_pre: str, new_pre: str) -> Any:
    if isinstance(value, str):
        return value.replace(old_pre, new_pre)
    if isinstance(value, dict):
        return {key: _replace_paths(item, old_pre, new_pre) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_paths(item, old_pre, new_pre) for item in value]
    return value


def _unique_target(path: Path) -> Path:
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = path.with_name(f"{path.name}-{index}")
        if not candidate.exists():
            return candidate
        index += 1


def _merge_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    if not target.exists():
        shutil.move(str(source), str(target))
        return
    target.mkdir(parents=True, exist_ok=True)
    for child in list(source.iterdir()):
        destination = target / child.name
        if child.is_dir():
            _merge_tree(child, destination)
        else:
            if destination.exists():
                destination = _unique_target(destination)
            shutil.move(str(child), str(destination))
    if source.is_dir() and not any(source.iterdir()):
        source.rmdir()


def _apply_mappings(value: Any, mappings: list[tuple[str, str]]) -> Any:
    for old, new in mappings:
        value = _replace_paths(value, old, new)
    return value


def _write_plain_subtitles(job_dir: Path, result: dict[str, Any] | None) -> None:
    if result is None:
        return
    transcript = result.get("transcript") or {}
    segments = transcript.get("segments") or []
    clips = (
        (result.get("select") or {}).get("segments")
        or (result.get("split") or {}).get("segments")
        or []
    )
    subtitle_dir = job_dir / SUBTITLES_DIR
    subtitle_dir.mkdir(parents=True, exist_ok=True)
    records = write_clip_subtitles(job_dir, clips, segments)
    for legacy in subtitle_dir.glob("*.srt"):
        legacy.unlink(missing_ok=True)
    exports_dir = job_dir / EXPORTS_DIR
    if exports_dir.is_dir():
        for legacy in exports_dir.glob("*.srt"):
            legacy.unlink(missing_ok=True)
    result["clip_subtitles"] = records
    full = next((item for item in records if item["kind"] == "full"), None)
    if full is not None:
        transcript["text_path"] = full["path"]
    transcript.pop("srt_path", None)
    result["transcript"] = transcript
    manual_exports = result.get("manual_exports") or []
    if manual_exports:
        result["manual_exports"] = [
            item
            for item in manual_exports
            if not str(
                item.get("relative_path") or item.get("path") or ""
            ).lower().endswith(".srt")
        ]


def _normalize_job_tree(
    job_dir: Path,
    result: dict[str, Any] | None,
) -> list[tuple[str, str]]:
    if not job_dir.is_dir():
        return []
    mappings: list[tuple[str, str]] = []
    system_dir = job_dir / SYSTEM_DIR
    system_dir.mkdir(parents=True, exist_ok=True)

    old_audio = job_dir / "audio"
    old_audio_file = old_audio / "audio.wav"
    new_audio_file = job_dir / AUDIO_DIR / AUDIO_FILE
    if old_audio_file.is_file():
        new_audio_file.parent.mkdir(parents=True, exist_ok=True)
        if new_audio_file.exists():
            new_audio_file = _unique_target(new_audio_file)
        shutil.move(str(old_audio_file), str(new_audio_file))
        mappings.append((str(old_audio_file), str(new_audio_file)))
    if old_audio.is_dir():
        _merge_tree(old_audio, job_dir / AUDIO_DIR)
        mappings.append((str(old_audio), str(job_dir / AUDIO_DIR)))

    old_asr = job_dir / "asr"
    old_transcript = old_asr / "transcript.json"
    new_transcript = system_dir / TRANSCRIPT_FILE
    if old_transcript.is_file():
        if new_transcript.exists():
            new_transcript = _unique_target(new_transcript)
        shutil.move(str(old_transcript), str(new_transcript))
        mappings.append((str(old_transcript), str(new_transcript)))
    if old_asr.is_dir():
        _merge_tree(old_asr, system_dir)
        mappings.append((str(old_asr), str(system_dir)))

    for old_name, new_name in (
        ("clips", CLIPS_DIR),
        ("exports", EXPORTS_DIR),
        ("subtitles", SUBTITLES_DIR),
    ):
        old_dir = job_dir / old_name
        if old_dir.is_dir():
            _merge_tree(old_dir, job_dir / new_name)
            mappings.append((str(old_dir), str(job_dir / new_name)))

    old_checkpoint = job_dir / "checkpoint.json"
    new_checkpoint = system_dir / CHECKPOINT_FILE
    if old_checkpoint.is_file():
        if new_checkpoint.exists():
            new_checkpoint = _unique_target(new_checkpoint)
        shutil.move(str(old_checkpoint), str(new_checkpoint))
        mappings.append((str(old_checkpoint), str(new_checkpoint)))

    if result is not None:
        result = _apply_mappings(result, mappings)
        _write_plain_subtitles(job_dir, result)
    if new_checkpoint.is_file():
        text = new_checkpoint.read_text(encoding="utf-8", errors="replace")
        for old, new in mappings:
            text = text.replace(old, new)
        new_checkpoint.write_text(text, encoding="utf-8")
    return mappings


def _source_name_for_job(
    connection: sqlite3.Connection,
    params: dict[str, Any],
    input_path: str,
) -> str:
    explicit = str(params.get("source_name") or "")
    if explicit:
        return explicit
    asset_id = str(params.get("asset_id") or "")
    tenant_id = str(params.get("tenant_id") or "demo")
    if asset_id:
        try:
            row = connection.execute(
                "SELECT filename FROM assets WHERE id = ? AND tenant_id = ?",
                (asset_id, tenant_id),
            ).fetchone()
        except sqlite3.OperationalError:
            row = None
        if row is not None and row["filename"]:
            return str(row["filename"])
    return Path(input_path).name


def migrate_storage_layout(work_root: Path, database_path: Path) -> list[dict[str, str]]:
    root = Path(work_root).resolve()
    database = Path(database_path).resolve()
    if not database.exists():
        return []
    jobs_root = root / "jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)
    moved: list[dict[str, str]] = []

    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(jobs)")
        }
        if "work_dir" not in columns:
            connection.execute(
                "ALTER TABLE jobs ADD COLUMN work_dir TEXT NOT NULL DEFAULT ''"
            )
        rows = connection.execute(
            """
            SELECT id, tenant_id, created_at, input_path, params, result_json, work_dir
            FROM jobs
            ORDER BY created_at
            """
        ).fetchall()
        tables = {
            item["name"]
            for item in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        for row in rows:
            job_id = str(row["id"])
            params = json.loads(row["params"] or "{}")
            source_name = _source_name_for_job(
                connection,
                {**params, "tenant_id": row["tenant_id"]},
                str(row["input_path"]),
            )
            old = root / job_id
            moved_job = False
            if row["work_dir"]:
                rel = str(row["work_dir"])
                target = root / rel
            else:
                rel = job_work_relpath(job_id, str(row["created_at"]), source_name)
                target = _unique_target(root / rel)
                rel = target.relative_to(root).as_posix()
                if old.is_dir():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(old), str(target))
                    moved_job = True
            result = json.loads(row["result_json"]) if row["result_json"] else None
            root_mappings = (
                [(str(old), str(target))]
                if moved_job
                else []
            )
            if moved_job:
                result = _apply_mappings(result, root_mappings)
            subtree_mappings = _normalize_job_tree(target, result)
            mappings = root_mappings + subtree_mappings
            if result is not None:
                result = _apply_mappings(result, mappings)
                _write_plain_subtitles(target, result)
                if result.get("transcript"):
                    result["transcript"]["text_path"] = str(
                        target / SUBTITLES_DIR / FULL_SUBTITLE_TXT
                    )
                    result["transcript"].pop("srt_path", None)
            params["source_name"] = source_name
            connection.execute(
                """
                UPDATE jobs
                SET work_dir = ?, params = ?, result_json = ?
                WHERE id = ?
                """,
                (
                    rel,
                    json.dumps(params, ensure_ascii=False),
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    job_id,
                ),
            )
            if "clip_segments" in tables:
                segments = connection.execute(
                    "SELECT id, clip_path, export_paths_json FROM clip_segments WHERE job_id = ?",
                    (job_id,),
                ).fetchall()
                for segment in segments:
                    clip_path = str(segment["clip_path"] or "")
                    clip_path = _apply_mappings(clip_path, mappings)
                    exports = json.loads(segment["export_paths_json"] or "[]")
                    exports = _apply_mappings(exports, mappings)
                    connection.execute(
                        """
                        UPDATE clip_segments
                        SET clip_path = ?, export_paths_json = ?
                        WHERE id = ?
                        """,
                        (
                            clip_path,
                            json.dumps(exports, ensure_ascii=False),
                            segment["id"],
                        ),
                    )
            if moved_job or subtree_mappings:
                moved.append({"job_id": job_id, "work_dir": rel})
        connection.commit()

    dev_root = root / "dev"
    for pattern in DEV_FILE_PATTERNS:
        for path in root.glob(pattern):
            if path.is_file():
                dev_root.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(dev_root / path.name))

    (root / "存储目录说明.txt").write_text(
        "\n".join(
            [
                "云流影存储目录说明",
                "",
                "jobs/       每个剪辑任务的工作目录，名称包含时间、素材名和任务 ID",
                "projects/   项目素材和项目级文件",
                "uploads/    上传任务的临时输入文件",
                "previews/   浏览器兼容预览的转码文件",
                "dev/        开发测试脚本和临时探测文件",
                "autocut.db  系统数据库",
                "",
                "任务目录中的 成片/ 是最终成片和重剪文件，字幕/ 是 SRT 和 TXT 字幕。",
            ]
        ),
        encoding="utf-8",
    )
    return moved
