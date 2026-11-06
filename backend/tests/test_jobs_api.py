from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_service
from app.api.main import app
from app.bootstrap import build_registry
from app.service import JobService
from app.storage import JobStore


@pytest.fixture
def client(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    service = JobService(store, tmp_path, build_registry())
    app.dependency_overrides[get_service] = lambda: service
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
