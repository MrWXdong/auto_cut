from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_studio_store
from app.api.main import app
from app.studio.quality import check_text, preset
from app.studio.store import StudioStore


@pytest.fixture
def client(tmp_path):
    store = StudioStore(tmp_path / "studio.db", tmp_path / "work")
    app.dependency_overrides[get_studio_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_presets() -> None:
    assert preset("draft")["candidates"] == 1
    assert preset("standard")["candidates"] == 2
    assert preset("high")["candidates"] == 3


def test_text_quality_checks() -> None:
    report = check_text("品牌主色是墨绿色，适合敏感肌。", required_keywords=["墨绿色"])
    assert report.passed is True

    bad = check_text(
        "根治",
        required_keywords=["墨绿色"],
        banned_words=["根治"],
    )
    assert bad.passed is False
    assert bad.score < 60


def test_quality_api_on_uploaded_text(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "质检项目"}).json()
    asset = client.post(
        f"/api/v1/projects/{project['id']}/assets",
        files={
            "file": (
                "brand.md",
                "品牌主色是墨绿色，适合敏感肌。".encode(),
                "text/markdown",
            )
        },
    ).json()

    response = client.post(
        "/api/v1/quality/check",
        json={
            "project_id": project["id"],
            "asset_id": asset["id"],
            "required_keywords": ["墨绿色"],
            "banned_words": ["根治"],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["score"] == 100
    assert payload["passed"] is True


def test_quality_api_rejects_missing_asset(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "质检项目"}).json()
    response = client.post(
        "/api/v1/quality/check",
        json={"project_id": project["id"], "asset_id": "missing"},
    )
    assert response.status_code == 404


def test_quality_feedback_round_trip(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "质检项目"}).json()
    created = client.post(
        "/api/v1/quality/feedback",
        json={
            "project_id": project["id"],
            "rating": 2,
            "tags": ["画面模糊", "主体不对"],
            "comment": "封面文字看不清",
        },
    )
    assert created.status_code == 201, created.text

    listed = client.get("/api/v1/quality/feedback").json()
    assert listed["items"][0]["rating"] == 2
    assert listed["summary"]["total"] == 1
    assert listed["summary"]["negative"] == 1

    overview = client.get("/api/v1/admin/overview").json()
    assert overview["feedback"]["total"] == 1
