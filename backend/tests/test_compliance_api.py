from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_compliance_service, get_studio_store
from app.api.main import app
from app.studio.compliance import ComplianceService, ComplianceStore
from app.studio.store import StudioStore


@pytest.fixture
def client(tmp_path):
    compliance = ComplianceService(ComplianceStore(tmp_path / "compliance.db"))
    studio = StudioStore(tmp_path / "studio.db", tmp_path / "work")
    app.dependency_overrides[get_compliance_service] = lambda: compliance
    app.dependency_overrides[get_studio_store] = lambda: studio
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_compliance_text_rules_and_reports(client: TestClient) -> None:
    response = client.post(
        "/api/v1/compliance/check",
        json={
            "platform": "抖音",
            "text": "这是全网最佳的产品，包治百病，100%有效，加微信领取。",
        },
    )
    assert response.status_code == 201, response.text
    report = response.json()
    assert report["level"] == "fail"
    assert report["score"] < 60
    categories = {item["category"] for item in report["issues"]}
    assert {"广告法", "医疗功效", "夸大宣传", "平台引流"} <= categories

    listed = client.get("/api/v1/compliance/reports")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == report["id"]

    deleted = client.delete(f"/api/v1/compliance/reports/{report['id']}")
    assert deleted.status_code == 200


def test_compliance_clean_text_passes(client: TestClient) -> None:
    response = client.post(
        "/api/v1/compliance/check",
        json={
            "platform": "小红书",
            "text": "这款产品适合日常通勤使用，质地清爽，下面是真实使用感受。",
        },
    )
    assert response.status_code == 201
    assert response.json()["level"] == "pass"
    assert response.json()["score"] == 100
