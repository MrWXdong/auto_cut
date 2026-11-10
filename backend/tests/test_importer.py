from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_studio_store
from app.api.main import app
from app.studio.importer import guess_extension, validate_public_url
from app.studio.store import StudioStore


@pytest.fixture
def client(tmp_path):
    store = StudioStore(tmp_path / "studio.db", tmp_path / "work")
    app.dependency_overrides[get_studio_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/video.mp4",
        "http://10.0.0.1/video.mp4",
        "http://localhost/video.mp4",
        "file:///etc/passwd",
        "ftp://example.com/video.mp4",
    ],
)
def test_rejects_non_public_urls(url: str) -> None:
    with pytest.raises(ValueError):
        validate_public_url(url)


def test_guess_extension() -> None:
    assert guess_extension("https://example.com/a.mp4", "") == ".mp4"
    assert guess_extension("https://example.com/a", "image/png") == ".png"
    assert guess_extension("https://example.com/a", "application/octet-stream") == ".bin"


def test_import_endpoint_wires_asset(client: TestClient, monkeypatch) -> None:
    async def fake_import(studio, project_id, url):
        return {
            "id": "asset-1",
            "filename": "clip.mp4",
            "kind": "video",
            "storage_key": "projects/x/assets/clip.mp4",
            "size_bytes": 10,
            "meta_json": "{}",
        }

    monkeypatch.setattr("app.api.routers.projects.import_asset", fake_import)
    project = client.post("/api/v1/projects", json={"name": "导入项目"}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        json={"url": "https://example.com/video.mp4"},
    )
    assert response.status_code == 201
    assert response.json()["filename"] == "clip.mp4"


def test_import_rejects_non_http_url(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "导入项目"}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/assets/import",
        json={"url": "file:///etc/passwd"},
    )
    assert response.status_code == 422


def test_import_unknown_project(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects/missing/assets/import",
        json={"url": "https://example.com/video.mp4"},
    )
    assert response.status_code == 404
