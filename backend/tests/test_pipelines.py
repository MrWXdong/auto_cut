from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_credit_service, get_studio_store
from app.api.main import app
from app.billing.credits import CreditService
from app.studio.store import StudioStore


@pytest.fixture
def client(tmp_path):
    store = StudioStore(tmp_path / "studio.db", tmp_path / "work")
    credits = CreditService(tmp_path / "credits.db")
    credits.grant("demo", 100_000, "test grant")
    app.dependency_overrides[get_studio_store] = lambda: store
    app.dependency_overrides[get_credit_service] = lambda: credits
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_templates_and_create_pipeline(client: TestClient) -> None:
    templates = client.get("/api/v1/pipeline-templates").json()["items"]
    assert {"copy_to_video", "asset_to_video", "cover_pack"} <= {
        item["id"] for item in templates
    }

    response = client.post("/api/v1/pipelines", json={"template": "copy_to_video"})
    assert response.status_code == 201, response.text
    pipeline = response.json()
    assert pipeline["status"] == "queued"
    assert len(pipeline["steps"]) == 5
    assert pipeline["steps"][0]["module"] == "copywriting"
    assert all(step["status"] == "queued" for step in pipeline["steps"])


def test_custom_pipeline_and_cancel(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "流水线项目"}).json()
    response = client.post(
        "/api/v1/pipelines",
        json={
            "name": "自定义流水线",
            "project_id": project["id"],
            "steps": [{"module": "image", "mode": "cover", "prompt": "生成封面"}],
        },
    )
    assert response.status_code == 201, response.text
    pipeline = response.json()
    assert len(pipeline["steps"]) == 1

    canceled = client.post(f"/api/v1/pipelines/{pipeline['id']}/cancel")
    assert canceled.status_code == 200

    detail = client.get(f"/api/v1/pipelines/{pipeline['id']}").json()
    assert detail["status"] == "canceled"
    assert detail["steps"][0]["status"] == "canceled"


def test_unknown_template_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/pipelines", json={"template": "missing"})
    assert response.status_code == 404


def test_unknown_module_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/pipelines",
        json={"steps": [{"module": "missing"}]},
    )
    assert response.status_code == 422


def test_delete_pipeline(client: TestClient) -> None:
    pipeline = client.post(
        "/api/v1/pipelines",
        json={"template": "cover_pack"},
    ).json()
    deleted = client.delete(f"/api/v1/pipelines/{pipeline['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/pipelines/{pipeline['id']}").status_code == 404
    assert all(
        item["id"] != pipeline["id"]
        for item in client.get("/api/v1/pipelines").json()["items"]
    )
