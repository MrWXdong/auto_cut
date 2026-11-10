from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_credit_service, get_service
from app.api.main import app
from app.billing.credits import CreditService
from app.bootstrap import build_registry
from app.service import JobService
from app.storage import JobStore


@pytest.fixture
def client(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    service = JobService(store, tmp_path, build_registry())
    credits = CreditService(tmp_path / "credits.db")
    credits.grant("demo", 10000, "test")
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_credit_service] = lambda: credits
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_job(client: TestClient, workflow: str = "subtitle") -> dict:
    response = client.post(
        "/api/v1/jobs",
        data={"workflow": workflow},
        files={"file": ("input.mp4", b"not a real video", "video/mp4")},
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_creates_and_lists_job(client: TestClient) -> None:
    job = create_job(client)
    assert job["status"] == "queued"
    assert job["source_name"] == "input.mp4"
    assert job["segment_count"] == 0
    listed = client.get("/api/v1/jobs").json()["items"]
    assert [item["id"] for item in listed] == [job["id"]]


def test_unknown_workflow_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/jobs",
        data={"workflow": "missing"},
        files={"file": ("input.mp4", b"x", "video/mp4")},
    )
    assert response.status_code == 404


def test_cancel_only_queued_job(client: TestClient) -> None:
    job = create_job(client)
    assert client.post(f"/api/v1/jobs/{job['id']}/cancel").status_code == 200
    assert client.post(f"/api/v1/jobs/{job['id']}/cancel").status_code == 409
    assert client.get(f"/api/v1/jobs/{job['id']}").json()["job"]["status"] == "canceled"


def test_artifacts_are_empty_before_run(client: TestClient) -> None:
    job = create_job(client)
    response = client.get(f"/api/v1/jobs/{job['id']}/artifacts")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_rejects_path_traversal(client: TestClient) -> None:
    job = create_job(client)
    response = client.get(f"/api/v1/jobs/{job['id']}/files/../../etc/passwd")
    assert response.status_code in {400, 404}


def test_delete_job_removes_record_and_files(client: TestClient) -> None:
    service = app.dependency_overrides[get_service]()
    job = create_job(client)
    upload_dir = service.work_root / "uploads" / job["id"]
    work_dir = service.work_dir(job["id"])
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "clip.mp4").write_bytes(b"video")
    service.store.mark_succeeded(
        job["id"],
        {"export": {"path": str(work_dir / "clip.mp4")}},
        10,
    )

    assert client.delete(f"/api/v1/jobs/{job['id']}").status_code == 200
    assert client.get(f"/api/v1/jobs/{job['id']}").status_code == 404
    assert not upload_dir.exists()
    assert not work_dir.exists()


def test_delete_running_job_is_rejected(client: TestClient) -> None:
    service = app.dependency_overrides[get_service]()
    job = create_job(client)
    claimed = service.store.claim_next()
    assert claimed is not None
    assert claimed.id == job["id"]
    assert client.delete(f"/api/v1/jobs/{job['id']}").status_code == 409


def test_retry_clears_stale_checkpoint(client: TestClient) -> None:
    service = app.dependency_overrides[get_service]()
    job = create_job(client)
    work_dir = service.work_dir(job["id"])
    work_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = work_dir / "系统文件" / "任务断点.json"
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text('{"nodes": {"select": {"outputs": {}}}}', encoding="utf-8")
    service.store.mark_failed(job["id"], "failed", 10)

    response = client.post(f"/api/v1/jobs/{job['id']}/retry")
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "queued"
    assert not checkpoint.exists()


def test_delete_single_artifact_file(client: TestClient) -> None:
    service = app.dependency_overrides[get_service]()
    job = create_job(client)
    work_dir = service.work_dir(job["id"])
    work_dir.mkdir(parents=True, exist_ok=True)
    artifact = work_dir / "clip.mp4"
    artifact.write_bytes(b"video")
    service.store.mark_succeeded(
        job["id"],
        {"export": {"path": str(artifact)}},
        10,
    )

    response = client.delete(f"/api/v1/jobs/{job['id']}/files/clip.mp4")
    assert response.status_code == 200
    assert not artifact.exists()
    assert client.delete(f"/api/v1/jobs/{job['id']}/files/clip.mp4").status_code == 404


def test_batch_export_selected_and_all_final_artifacts(client: TestClient) -> None:
    service = app.dependency_overrides[get_service]()
    job = create_job(client)
    work_dir = service.work_dir(job["id"])
    exports_dir = work_dir / "成片"
    clips_dir = work_dir / "切片"
    exports_dir.mkdir(parents=True)
    clips_dir.mkdir(parents=True)
    final_a = exports_dir / "陈泽_切片01_10s_1080x1920.mp4"
    final_b = exports_dir / "陈泽_切片02_8s_1080x1920.mp4"
    clip_a = clips_dir / "陈泽_切片01_10s.mp4"
    for path in (final_a, final_b, clip_a):
        path.write_bytes(b"video")
    service.store.mark_succeeded(
        job["id"],
        {
            "clips": {"clips": [{"path": str(clip_a)}]},
            "export": {
                "outputs": [
                    {"path": str(final_a)},
                    {"path": str(final_b)},
                ]
            },
        },
        10,
    )

    all_final = client.get(f"/api/v1/jobs/{job['id']}/artifacts/export")
    assert all_final.status_code == 200
    assert all_final.headers["content-type"].startswith("application/zip")
    with zipfile.ZipFile(io.BytesIO(all_final.content)) as archive:
        assert sorted(archive.namelist()) == sorted([final_a.name, final_b.name])

    selected = client.get(
        f"/api/v1/jobs/{job['id']}/artifacts/export",
        params={"path": "成片/陈泽_切片01_10s_1080x1920.mp4"},
    )
    assert selected.status_code == 200
    with zipfile.ZipFile(io.BytesIO(selected.content)) as archive:
        assert archive.namelist() == [final_a.name]

    invalid = client.get(
        f"/api/v1/jobs/{job['id']}/artifacts/export",
        params={"path": "../outside.mp4"},
    )
    assert invalid.status_code == 400


@pytest.mark.asyncio
async def test_run_job_marks_failed_when_work_dir_is_not_writable(
    tmp_path,
    monkeypatch,
) -> None:
    database = tmp_path / "jobs.db"
    store = JobStore(database)
    service = JobService(store, tmp_path / "work", build_registry())
    job = service.create_job(
        workflow="clip",
        input_path=tmp_path / "input.mp4",
        job_id="job-permission",
        tenant_id="demo",
    )

    def denied(_job_id):
        raise PermissionError("denied")

    monkeypatch.setattr(service, "work_dir", denied)
    await service.run_job(job)
    saved = store.get(job.id, "demo")
    assert saved is not None
    assert saved.status.value == "failed"
    assert "PermissionError" in (saved.error or "")


def test_worker_heartbeat_is_reported(client: TestClient) -> None:
    service = app.dependency_overrides[get_service]()
    service.store.heartbeat(
        "worker-test",
        "test-host",
        1234,
        status="idle",
    )
    payload = client.get("/api/v1/system/workers").json()
    assert payload["online"] == 1
    assert payload["items"][0]["worker_id"] == "worker-test"
    assert payload["items"][0]["host"] == "test-host"
    service.store.remove_worker("worker-test")
    assert client.get("/api/v1/system/workers").json()["online"] == 0
