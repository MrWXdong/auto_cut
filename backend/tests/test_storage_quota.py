from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_platform_store,
    get_service,
    get_studio_store,
)
from app.api.main import app
from app.bootstrap import build_registry
from app.config import get_settings
from app.platform.store import PlatformStore
from app.service import JobService
from app.storage import JobStore
from app.studio.store import StudioStore


@pytest.fixture
def storage_context(tmp_path):
    studio = StudioStore(tmp_path / "studio.db", tmp_path / "work")
    platform = PlatformStore(tmp_path / "platform.db")
    platform.seed(get_settings())
    platform.update_tenant("demo", {"storage_gb": 1})
    job_store = JobStore(tmp_path / "jobs.db")
    service = JobService(job_store, tmp_path / "job-work", build_registry())
    app.dependency_overrides[get_studio_store] = lambda: studio
    app.dependency_overrides[get_platform_store] = lambda: platform
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app) as client:
        yield client, studio
    app.dependency_overrides.clear()


def test_storage_quota_blocks_upload_and_reports_usage(storage_context) -> None:
    client, studio = storage_context
    project = client.post(
        "/api/v1/projects",
        json={"name": "额度测试", "aspect_ratio": "9:16"},
    ).json()
    studio.add_asset(
        project["id"],
        "existing.mp4",
        "projects/fake/existing.mp4",
        1024 * 1024 * 1024,
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        files={"file": ("extra.mp4", b"x", "video/mp4")},
    )
    assert response.status_code == 413
    assert "存储空间不足" in response.text

    quotas = client.get("/api/v1/quotas")
    assert quotas.status_code == 200
    storage = next(
        item for item in quotas.json()["items"] if item["kind"] == "storage_bytes"
    )
    assert storage["used"] >= 1024 * 1024 * 1024
    assert storage["limit"] == 1024 * 1024 * 1024
