from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_lists_workflows() -> None:
    response = client.get("/api/v1/workflows")
    assert response.status_code == 200
    names = {item["name"] for item in response.json()["items"]}
    assert {"subtitle", "clip"} <= names


def test_unknown_workflow_returns_404() -> None:
    response = client.get("/api/v1/workflows/missing")
    assert response.status_code == 404


def test_demo_web_assets_disable_cache() -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert "no-store" in page.headers["cache-control"]

    asset = client.get("/assets/styles.css")
    assert asset.status_code == 200
    assert "no-store" in asset.headers["cache-control"]
