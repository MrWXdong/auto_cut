from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_publish_service
from app.api.main import app
from app.studio.publishing import PublishService, PublishStore


@pytest.fixture
def client(tmp_path):
    service = PublishService(PublishStore(tmp_path / "publish.db"))
    app.dependency_overrides[get_publish_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_publish_account_and_job_lifecycle(client: TestClient) -> None:
    account = client.post(
        "/api/v1/publish/accounts",
        json={
            "platform": "抖音",
            "name": "品牌主账号",
            "handle": "@brand",
            "followers": 12000,
        },
    )
    assert account.status_code == 201, account.text
    account_id = account.json()["id"]

    scheduled_at = (datetime.now().astimezone() + timedelta(hours=2)).isoformat(
        timespec="seconds"
    )
    created = client.post(
        "/api/v1/publish/jobs",
        json={
            "title": "秋冬护肤新品发布",
            "scheduled_at": scheduled_at,
            "account_id": account_id,
        },
    )
    assert created.status_code == 201, created.text
    job = created.json()
    assert job["status"] == "scheduled"
    assert job["platform"] == "抖音"
    assert job["account_name"] == "品牌主账号"

    listed = client.get("/api/v1/publish/jobs")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == job["id"]

    run = client.post(f"/api/v1/publish/jobs/{job['id']}/run")
    assert run.status_code == 200
    assert run.json()["status"] == "manual_required"

    published = client.post(
        f"/api/v1/publish/jobs/{job['id']}/published",
        json={"result_url": "https://example.com/post/1"},
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["result_url"].endswith("/post/1")

    assert client.delete(f"/api/v1/publish/jobs/{job['id']}").status_code == 200
    assert client.delete(f"/api/v1/publish/accounts/{account_id}").status_code == 200
