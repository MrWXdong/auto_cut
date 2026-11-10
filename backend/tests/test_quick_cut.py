from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_credit_service, get_service, get_studio_store
from app.api.main import app
from app.billing.credits import CreditService
from app.bootstrap import build_registry
from app.core.workflow.context import RunContext
from app.nodes.media import CutClipsNode, ExportVideoNode, SplitEvenNode
from app.service import JobService
from app.storage import JobStore
from app.studio.store import StudioStore


@pytest.mark.asyncio
async def test_split_even_segments(tmp_path) -> None:
    result = await SplitEvenNode().run(
        RunContext(job_id="job", work_dir=tmp_path),
        {"params": {"count": 3}, "data": {"duration": 120}},
    )
    assert [item["start"] for item in result["segments"]] == [0.0, 40.0, 80.0]
    assert result["segments"][-1]["end"] == 120.0


@pytest.mark.asyncio
async def test_split_even_short_video(tmp_path) -> None:
    result = await SplitEvenNode().run(
        RunContext(job_id="job", work_dir=tmp_path),
        {"params": {"count": 3}, "data": {"duration": 8}},
    )
    assert result["count"] == 1
    assert len(result["segments"]) == 1


@pytest.mark.asyncio
async def test_cut_clips_skips_zero_length_segments(tmp_path, monkeypatch) -> None:
    source = tmp_path / "input.mp4"
    source.write_bytes(b"fake-video")
    calls: list[tuple[float, float]] = []

    async def fake_cut(_source, start, end, _output) -> None:
        calls.append((start, end))

    monkeypatch.setattr("app.nodes.media._cut_video", fake_cut)
    result = await CutClipsNode().run(
        RunContext(job_id="job", work_dir=tmp_path),
        {
            "params": {
                "segments": [
                    {"start": 0, "end": 0},
                    {"start": 12, "end": 12},
                    {"start": 12, "end": 18},
                    {"start": 18, "end": 20},
                ],
            },
            "data": {"path": str(source)},
            "job_params": {"source_name": "陈泽.mp4"},
        },
    )
    assert calls == [(12.0, 18.0), (18.0, 20.0)]
    assert [Path(item["path"]).name for item in result["clips"]] == [
        "陈泽_切片01_6s.mp4",
        "陈泽_切片02_2s.mp4",
    ]


@pytest.mark.asyncio
async def test_export_uses_source_name_and_slice_order(tmp_path, monkeypatch) -> None:
    captured: list[str] = []

    async def fake_run_command(command, timeout) -> None:
        output = Path(command[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"video")
        captured.append(output.name)

    monkeypatch.setattr("app.nodes.media.run_command", fake_run_command)
    result = await ExportVideoNode().run(
        RunContext(job_id="job", work_dir=tmp_path),
        {
            "params": {"aspects": ["9:16"]},
            "data": {
                "clips": [
                    {"path": str(tmp_path / "clips" / "陈泽_切片01_6s.mp4")},
                    {"path": str(tmp_path / "clips" / "陈泽_切片02_2s.mp4")},
                ],
            },
        },
    )
    assert captured == [
        "陈泽_切片01_6s_1080x1920.mp4",
        "陈泽_切片02_2s_1080x1920.mp4",
    ]
    assert [Path(item["path"]).name for item in result["outputs"]] == captured


@pytest.fixture
def client(tmp_path):
    studio = StudioStore(tmp_path / "studio.db", tmp_path / "work")
    service = JobService(
        JobStore(tmp_path / "jobs.db"),
        tmp_path / "job-work",
        build_registry(),
    )
    credits = CreditService(tmp_path / "credits.db")
    credits.grant("demo", 10000, "test")
    app.dependency_overrides[get_studio_store] = lambda: studio
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_credit_service] = lambda: credits
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_edit_job_from_video_asset(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "剪辑项目"}).json()
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        files={"file": ("clip.mp4", b"fake-video", "video/mp4")},
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/edit-jobs",
        json={
            "asset_id": asset["id"],
            "params": {"count": 2, "aspects": ["9:16"]},
        },
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["workflow"] == "quick_cut"
    assert job["params"]["count"] == 2

    jobs = client.get("/api/v1/jobs").json()["items"]
    assert any(item["id"] == job["id"] for item in jobs)


def test_edit_job_rejects_non_video(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "剪辑项目"}).json()
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        files={"file": ("note.txt", b"text", "text/plain")},
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/edit-jobs",
        json={"asset_id": asset["id"]},
    )
    assert response.status_code == 422


def test_auto_edit_uses_rule_workflow(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "自动成片"}).json()
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        files={"file": ("clip.mp4", b"fake-video", "video/mp4")},
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/auto-edit",
        json={
            "asset_id": asset["id"],
            "count": 4,
            "aspects": ["1:1"],
            "brief": "保留动作场面，避开片头",
        },
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["workflow"] == "quick_cut"
    assert job["params"]["mode"] == "rule"
    assert job["params"]["count"] == 4
    assert job["params"]["aspects"] == ["1:1"]
    assert job["params"]["brief"] == "保留动作场面，避开片头"


def test_auto_edit_clip_uses_requested_slice_count(
    client: TestClient,
    monkeypatch,
) -> None:
    project = client.post("/api/v1/projects", json={"name": "AI 切片项目"}).json()
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        files={"file": ("clip.mp4", b"fake-video", "video/mp4")},
    ).json()
    monkeypatch.setattr(
        "app.api.routers.projects.choose_workflow",
        lambda _settings: ("clip", "ai"),
    )
    response = client.post(
        f"/api/v1/projects/{project['id']}/auto-edit",
        json={"asset_id": asset["id"], "count": 3},
    )
    assert response.status_code == 202, response.text
    assert response.json()["params"]["max_clips"] == 3
    assert response.json()["params"]["min_seconds"] == 1.0
    assert response.json()["params"]["max_seconds"] == 0.0


def test_auto_edit_accepts_custom_clip_duration_range(
    client: TestClient,
    monkeypatch,
) -> None:
    project = client.post("/api/v1/projects", json={"name": "自定义切片项目"}).json()
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        files={"file": ("clip.mp4", b"fake-video", "video/mp4")},
    ).json()
    monkeypatch.setattr(
        "app.api.routers.projects.choose_workflow",
        lambda _settings: ("clip", "ai"),
    )
    response = client.post(
        f"/api/v1/projects/{project['id']}/auto-edit",
        json={
            "asset_id": asset["id"],
            "count": 3,
            "min_seconds": 2.5,
            "max_seconds": 30,
        },
    )
    assert response.status_code == 202, response.text
    assert response.json()["params"]["min_seconds"] == 2.5
    assert response.json()["params"]["max_seconds"] == 30.0


def test_auto_edit_rejects_inverted_clip_duration_range(
    client: TestClient,
    monkeypatch,
) -> None:
    project = client.post("/api/v1/projects", json={"name": "切片时长校验"}).json()
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        files={"file": ("clip.mp4", b"fake-video", "video/mp4")},
    ).json()
    monkeypatch.setattr(
        "app.api.routers.projects.choose_workflow",
        lambda _settings: ("clip", "ai"),
    )
    response = client.post(
        f"/api/v1/projects/{project['id']}/auto-edit",
        json={
            "asset_id": asset["id"],
            "count": 3,
            "min_seconds": 40,
            "max_seconds": 30,
        },
    )
    assert response.status_code == 422


def test_edit_capabilities(client: TestClient) -> None:
    response = client.get("/api/v1/edit/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["rule_ready"] is True
    assert "ffmpeg" in payload
