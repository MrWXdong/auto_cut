from __future__ import annotations

from app.bootstrap import build_registry
from app.domain import Job
from app.service import JobService
from app.storage import JobStore
from app.storage_layout import migrate_storage_layout


def test_new_jobs_use_readable_job_directories(tmp_path) -> None:
    database = tmp_path / "autocut.db"
    service = JobService(
        JobStore(database),
        tmp_path / "work",
        build_registry(),
        database_path=database,
    )
    job = service.create_job(
        workflow="clip",
        input_path=tmp_path / "陈泽.mp4",
        params={"source_name": "陈泽.mp4"},
        job_id="abc123456789",
        tenant_id="demo",
    )
    assert job.work_dir.startswith("jobs/")
    assert "陈泽" in job.work_dir
    assert "abc123456789" in job.work_dir
    assert service.work_dir(job.id) == (tmp_path / "work" / job.work_dir).resolve()


def test_legacy_job_directory_is_migrated_and_paths_are_rewritten(tmp_path) -> None:
    work_root = tmp_path / "work"
    database = tmp_path / "autocut.db"
    store = JobStore(database)
    job = Job(
        id="oldjob123456",
        workflow="clip",
        input_path=str(tmp_path / "陈泽.mp4"),
        tenant_id="demo",
        created_at="2026-11-09T01:01:59+00:00",
        params={"source_name": "陈泽.mp4"},
    )
    store.create(job)
    old_dir = work_root / job.id
    export = old_dir / "exports" / "old.mp4"
    export.parent.mkdir(parents=True)
    export.write_bytes(b"video")
    store.mark_succeeded(job.id, {"export": {"outputs": [{"path": str(export)}]}}, 10)

    moved = migrate_storage_layout(work_root, database)
    assert moved and moved[0]["job_id"] == job.id
    assert not old_dir.exists()
    saved = store.get(job.id)
    assert saved is not None
    assert saved.work_dir.startswith("jobs/")
    new_dir = work_root / saved.work_dir
    assert (new_dir / "成片" / "old.mp4").is_file()
    assert saved.result["export"]["outputs"][0]["path"] == str(
        new_dir / "成片" / "old.mp4"
    )
    assert saved.params["source_name"] == "陈泽.mp4"


def test_migration_writes_single_timed_text_subtitle(tmp_path) -> None:
    work_root = tmp_path / "work"
    database = tmp_path / "autocut.db"
    store = JobStore(database)
    job = Job(
        id="subtitle123456",
        workflow="clip",
        input_path=str(tmp_path / "口播.mp4"),
        tenant_id="demo",
        created_at="2026-11-09T02:02:03+00:00",
        params={"source_name": "口播.mp4"},
    )
    store.create(job)
    legacy_dir = work_root / job.id / "字幕"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "完整字幕.srt").write_text("legacy", encoding="utf-8")
    store.mark_succeeded(
        job.id,
        {
            "transcript": {
                "segments": [
                    {"start": 0, "end": 1.5, "text": "第一句字幕"},
                    {"start": 1.5, "end": 3.2, "text": "第二句字幕"},
                ]
            },
            "select": {
                "segments": [
                    {"start": 0, "end": 1.5, "title": "第一段"},
                    {"start": 1.5, "end": 3.2, "title": "第二段"},
                ]
            },
        },
        10,
    )

    migrate_storage_layout(work_root, database)

    saved = store.get(job.id)
    assert saved is not None
    subtitle_dir = work_root / saved.work_dir / "字幕"
    text_path = subtitle_dir / "完整字幕.txt"
    srt_path = subtitle_dir / "完整字幕.srt"
    assert text_path.is_file()
    assert not srt_path.exists()
    assert text_path.read_text(encoding="utf-8-sig").splitlines() == [
        "[00:00 --> 00:02] 第一句字幕",
        "[00:02 --> 00:03] 第二句字幕",
    ]
    clip_one = subtitle_dir / "切片01_字幕.txt"
    clip_two = subtitle_dir / "切片02_字幕.txt"
    assert clip_one.read_text(encoding="utf-8-sig").splitlines() == [
        "[00:00 --> 00:02] 第一句字幕",
    ]
    assert clip_two.read_text(encoding="utf-8-sig").splitlines() == [
        "[00:02 --> 00:03] 第二句字幕",
    ]
    assert len(saved.result["clip_subtitles"]) == 3
    assert saved.result["transcript"]["text_path"] == str(text_path)
    assert "srt_path" not in saved.result["transcript"]
