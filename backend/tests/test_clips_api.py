from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clip_store, get_service
from app.api.main import app
from app.bootstrap import build_registry
from app.clips.store import ClipSegmentStore
from app.domain import Job
from app.service import JobService
from app.storage import JobStore


@pytest.fixture
def clip_client(tmp_path):
    database_path = tmp_path / "autocut.db"
    job_store = JobStore(database_path)
    service = JobService(
        job_store,
        tmp_path / "work",
        build_registry(),
        database_path=database_path,
    )
    clip_store = ClipSegmentStore(database_path)
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_clip_store] = lambda: clip_store
    with TestClient(app) as client:
        yield client, service, clip_store
    app.dependency_overrides.clear()


def seed_segments(
    service: JobService,
    clip_store: ClipSegmentStore,
    tmp_path: Path,
) -> str:
    job = service.create_job(
        workflow="clip",
        input_path=tmp_path / "source.mp4",
        params={
            "project_id": "project-1",
            "asset_id": "asset-1",
            "source_name": "陈泽.mp4",
        },
        job_id="job-1",
        tenant_id="demo",
    )
    clip_store.replace_for_job(
        job_id=job.id,
        tenant_id="demo",
        records=[
            {
                "seq": 0,
                "project_id": "project-1",
                "asset_id": "asset-1",
                "source_name": "陈泽.mp4",
                "source_duration": 30,
                "start": 0,
                "end": 10,
                "duration": 10,
                "title": "开场",
                "reason": "高光",
                "score": 0.9,
                "kind": "highlight",
                "clip_path": str(tmp_path / "work" / job.id / "clips" / "a.mp4"),
            },
            {
                "seq": 1,
                "project_id": "project-1",
                "asset_id": "asset-1",
                "source_name": "陈泽.mp4",
                "source_duration": 30,
                "start": 10,
                "end": 20,
                "duration": 10,
                "title": "中段",
                "reason": "普通",
                "score": 0.5,
                "kind": "normal",
                "clip_path": str(tmp_path / "work" / job.id / "clips" / "b.mp4"),
            },
        ],
    )
    return job.id


def test_list_and_trim_segment(clip_client, tmp_path) -> None:
    client, service, clip_store = clip_client
    job_id = seed_segments(service, clip_store, tmp_path)
    service.store.mark_succeeded(
        job_id,
        {
            "probe": {"duration": 30},
            "select": {
                "segments": [
                    {"start": 0, "end": 10, "title": "开场"},
                    {"start": 10, "end": 20, "title": "中段"},
                ]
            },
            "cut": {
                "clips": [
                    {"path": str(service.work_dir(job_id) / "clips" / "a.mp4")},
                    {"path": str(service.work_dir(job_id) / "clips" / "b.mp4")},
                ]
            },
        },
        10,
    )
    items = client.get(f"/api/v1/jobs/{job_id}/segments").json()["items"]
    assert [item["title"] for item in items] == ["开场", "中段"]
    assert items[0]["kind"] == "highlight"
    assert (
        client.get(f"/api/v1/jobs/{job_id}/segments").json()["has_adjustments"]
        is False
    )

    updated = client.patch(
        f"/api/v1/segments/{items[0]['id']}",
        json={"start": 2, "end": 8, "title": "新开场"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["duration"] == 6
    assert updated.json()["title"] == "新开场"
    assert (
        client.get(f"/api/v1/jobs/{job_id}/segments").json()["has_adjustments"]
        is True
    )


def test_locked_segment_cannot_be_trimmed_or_deleted(clip_client, tmp_path) -> None:
    client, service, clip_store = clip_client
    job_id = seed_segments(service, clip_store, tmp_path)
    segment = client.get(f"/api/v1/jobs/{job_id}/segments").json()["items"][0]

    locked = client.patch(
        f"/api/v1/segments/{segment['id']}",
        json={"locked": True},
    )
    assert locked.status_code == 200
    assert locked.json()["locked"] is True
    assert (
        client.patch(
            f"/api/v1/segments/{segment['id']}",
            json={"title": "锁定标题"},
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/segments/{segment['id']}").status_code == 409
    assert (
        client.patch(
            f"/api/v1/segments/{segment['id']}",
            json={"start": 1},
        ).status_code
        == 409
    )


def test_merge_adjacent_and_reorder(clip_client, tmp_path) -> None:
    client, service, clip_store = clip_client
    job_id = seed_segments(service, clip_store, tmp_path)
    items = client.get(f"/api/v1/jobs/{job_id}/segments").json()["items"]
    merged = client.post(
        f"/api/v1/jobs/{job_id}/segments/merge",
        json={"ids": [items[0]["id"], items[1]["id"]]},
    )
    assert merged.status_code == 200, merged.text
    assert merged.json()["merged_from"] == [items[0]["id"], items[1]["id"]]
    assert merged.json()["start"] == 0
    assert merged.json()["end"] == 20
    remaining = client.get(f"/api/v1/jobs/{job_id}/segments").json()["items"]
    assert len(remaining) == 1
    unmerged = client.post(
        f"/api/v1/jobs/{job_id}/segments/{remaining[0]['id']}/unmerge"
    )
    assert unmerged.status_code == 200, unmerged.text
    assert [item["title"] for item in unmerged.json()["items"]] == ["开场", "中段"]

    # Rebuilding two active rows exercises the reorder endpoint.
    clip_store.replace_for_job(
        job_id=job_id,
        tenant_id="demo",
        records=[
            {
                "seq": 0,
                "source_duration": 30,
                "start": 0,
                "end": 5,
                "duration": 5,
                "title": "A",
            },
            {
                "seq": 1,
                "source_duration": 30,
                "start": 5,
                "end": 10,
                "duration": 5,
                "title": "B",
            },
        ],
    )
    items = client.get(f"/api/v1/jobs/{job_id}/segments").json()["items"]
    ordered = client.post(
        f"/api/v1/jobs/{job_id}/segments/reorder",
        json={"ids": [items[1]["id"], items[0]["id"]]},
    )
    assert ordered.status_code == 200, ordered.text
    assert [item["title"] for item in ordered.json()["items"]] == ["B", "A"]


def test_unmerge_recovers_legacy_merge_without_history(clip_client, tmp_path) -> None:
    client, service, clip_store = clip_client
    job_id = seed_segments(service, clip_store, tmp_path)
    items = client.get(f"/api/v1/jobs/{job_id}/segments").json()["items"]
    merged = client.post(
        f"/api/v1/jobs/{job_id}/segments/merge",
        json={"ids": [items[0]["id"], items[1]["id"]]},
    ).json()
    with sqlite3.connect(tmp_path / "autocut.db") as connection:
        connection.execute(
            "UPDATE clip_segments SET merged_from_json = '[]' WHERE id = ?",
            (merged["id"],),
        )
        connection.commit()
    restored = client.post(
        f"/api/v1/jobs/{job_id}/segments/{merged['id']}/unmerge"
    )
    assert restored.status_code == 200, restored.text
    assert [item["title"] for item in restored.json()["items"]] == ["开场", "中段"]


def test_render_selected_segment_after_trim(
    clip_client,
    tmp_path,
    monkeypatch,
) -> None:
    client, service, clip_store = clip_client
    job_id = seed_segments(service, clip_store, tmp_path)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    items = client.get(f"/api/v1/jobs/{job_id}/segments").json()["items"]
    trimmed = client.patch(
        f"/api/v1/segments/{items[0]['id']}",
        json={"start": 2, "end": 8},
    )
    assert trimmed.status_code == 200

    async def fake_render(_source, _start, _end, _aspect, output) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"rendered")

    monkeypatch.setattr("app.api.routers.clips.render_clip", fake_render)
    response = client.post(
        f"/api/v1/jobs/{job_id}/segments/render",
        json={"ids": [items[0]["id"]], "aspects": ["9:16"]},
    )
    assert response.status_code == 200, response.text
    output = response.json()["outputs"][0]
    assert "切片01_6s_1080x1920_重剪.mp4" in output["name"]
    assert (service.work_dir(job_id) / output["relative_path"]).is_file()
    artifacts = client.get(f"/api/v1/jobs/{job_id}/artifacts").json()["items"]
    assert any(item["path"] == output["relative_path"] for item in artifacts)
    saved = service.store.get(job_id, "demo")
    assert saved is not None
    assert saved.result["manual_exports"][0]["relative_path"] == output["relative_path"]


def test_timed_text_export_for_full_video_and_srt_for_segment(
    clip_client,
    tmp_path,
) -> None:
    client, service, clip_store = clip_client
    job_id = seed_segments(service, clip_store, tmp_path)
    service.store.mark_succeeded(
        job_id,
        {
            "transcript": {
                "segments": [
                    {"start": 0, "end": 12.729, "text": "第一句"},
                    {"start": 12.729, "end": 15.233, "text": "第二句"},
                ]
            },
            "select": {
                "segments": [
                    {"start": 0, "end": 15.233, "title": "完整片段"},
                ]
            },
        },
        10,
    )
    full = client.get(f"/api/v1/jobs/{job_id}/subtitles.txt")
    assert full.status_code == 200
    assert "第一句" in full.text
    assert "[00:00 --> 00:15] 第一句 第二句" in full.text
    full_path = service.work_dir(job_id) / "字幕" / "完整字幕.txt"
    assert full_path.is_file()
    assert not (service.work_dir(job_id) / "字幕" / "完整字幕.srt").exists()

    segment = client.get(f"/api/v1/jobs/{job_id}/segments").json()["items"][0]
    client.patch(
        f"/api/v1/segments/{segment['id']}",
        json={"start": 2, "end": 8},
    )
    part = client.get(
        f"/api/v1/jobs/{job_id}/segments/{segment['id']}/subtitles.txt"
    )
    assert part.status_code == 200
    assert "第一句" in part.text
    assert "[00:02 --> 00:08] 第一句" in part.text
    assert (service.work_dir(job_id) / "字幕" / "切片01_字幕.txt").is_file()
    saved = service.store.get(job_id, "demo")
    assert saved is not None
    subtitle_exports = [
        item
        for item in saved.result.get("manual_exports", [])
        if item.get("kind") == "subtitle"
    ]
    assert len(subtitle_exports) == 2


def test_render_multiple_selected_segments(
    clip_client,
    tmp_path,
    monkeypatch,
) -> None:
    client, service, clip_store = clip_client
    job_id = seed_segments(service, clip_store, tmp_path)
    (tmp_path / "source.mp4").write_bytes(b"source")
    items = client.get(f"/api/v1/jobs/{job_id}/segments").json()["items"]

    async def fake_render(_source, _start, _end, _aspect, output) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"rendered")

    monkeypatch.setattr("app.api.routers.clips.render_clip", fake_render)
    response = client.post(
        f"/api/v1/jobs/{job_id}/segments/render",
        json={"ids": [item["id"] for item in items], "aspects": ["9:16"]},
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["outputs"]) == 2
    saved = service.store.get(job_id, "demo")
    assert saved is not None
    assert len(saved.result["manual_exports"]) == 2


def test_reset_segments_restores_original_ai_split(clip_client, tmp_path) -> None:
    client, service, clip_store = clip_client
    job_id = seed_segments(service, clip_store, tmp_path)
    work_dir = service.work_dir(job_id)
    clip_a = work_dir / "clips" / "a.mp4"
    clip_b = work_dir / "clips" / "b.mp4"
    service.store.mark_succeeded(
        job_id,
        {
            "probe": {"duration": 30},
            "select": {
                "segments": [
                    {"start": 0, "end": 10, "title": "开场", "reason": "高光", "score": 0.9},
                    {"start": 10, "end": 20, "title": "中段", "reason": "普通", "score": 0.5},
                ]
            },
            "cut": {"clips": [{"path": str(clip_a)}, {"path": str(clip_b)}]},
        },
        10,
    )
    items = client.get(f"/api/v1/jobs/{job_id}/segments").json()["items"]
    client.patch(
        f"/api/v1/segments/{items[0]['id']}",
        json={"start": 2, "end": 8, "title": "改过"},
    )
    client.delete(f"/api/v1/segments/{items[1]['id']}")

    reset = client.post(f"/api/v1/jobs/{job_id}/segments/reset")
    assert reset.status_code == 200, reset.text
    restored = reset.json()["items"]
    assert [item["title"] for item in restored] == ["开场", "中段"]
    assert restored[0]["start"] == 0
    assert restored[0]["end"] == 10
    assert (
        client.get(f"/api/v1/jobs/{job_id}/segments").json()["has_adjustments"]
        is False
    )


def test_workflow_outputs_are_persisted_as_editable_segments(clip_client, tmp_path) -> None:
    _client, service, clip_store = clip_client
    job = Job(
        id="job-output",
        workflow="clip",
        input_path=str(tmp_path / "source.mp4"),
        tenant_id="demo",
        params={
            "project_id": "project-1",
            "asset_id": "asset-1",
            "source_name": "陈泽.mp4",
        },
    )
    clip_a = str(service.work_dir(job.id) / "clips" / "a.mp4")
    clip_b = str(service.work_dir(job.id) / "clips" / "b.mp4")
    service._persist_clip_segments(
        job,
        {
            "probe": {"duration": 30},
            "transcript": {
                "segments": [
                    {"start": 0, "end": 10, "text": "第一句话"},
                    {"start": 10, "end": 20, "text": "第二句话"},
                ]
            },
            "select": {
                "segments": [
                    {"start": 0, "end": 10, "title": "开场", "reason": "高光", "score": 0.9},
                    {"start": 10, "end": 20, "title": "中段", "reason": "普通", "score": 0.4},
                ]
            },
            "cut": {"clips": [{"path": clip_a}, {"path": clip_b}]},
            "export": {
                "outputs": [
                    {"path": clip_a + ".out.mp4", "source": clip_a, "aspect": "9:16"},
                    {"path": clip_b + ".out.mp4", "source": clip_b, "aspect": "9:16"},
                ]
            },
        },
    )
    items = clip_store.list_for_job(job.id, "demo")
    assert len(items) == 2
    assert items[0]["transcript"] == "第一句话"
    assert items[0]["kind"] == "highlight"
    assert items[1]["kind"] == "normal"
    assert items[0]["exports"][0]["aspect"] == "9:16"


def test_existing_job_result_backfills_timeline(clip_client, tmp_path) -> None:
    client, service, _clip_store = clip_client
    job = service.create_job(
        workflow="clip",
        input_path=tmp_path / "source.mp4",
        params={
            "project_id": "project-1",
            "asset_id": "asset-1",
            "source_name": "旧任务.mp4",
        },
        job_id="job-backfill",
        tenant_id="demo",
    )
    clip_path = str(service.work_dir(job.id) / "clips" / "old.mp4")
    service.store.mark_succeeded(
        job.id,
        {
            "probe": {"duration": 12},
            "select": {
                "segments": [
                    {
                        "start": 0,
                        "end": 12,
                        "title": "旧片段",
                        "reason": "历史结果",
                        "score": 0.8,
                    }
                ]
            },
            "cut": {"clips": [{"path": clip_path}]},
            "export": {"outputs": []},
        },
        10,
    )
    items = client.get(f"/api/v1/jobs/{job.id}/segments").json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "旧片段"
