from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_credit_service, get_platform_store
from app.api.main import app
from app.billing.credits import CreditService
from app.config import get_settings
from app.platform.store import PlatformStore


@pytest.fixture
def client(tmp_path):
    database = tmp_path / "platform.db"
    platform = PlatformStore(database)
    platform.seed(get_settings())
    credits = CreditService(database)
    app.dependency_overrides[get_platform_store] = lambda: platform
    app.dependency_overrides[get_credit_service] = lambda: credits
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_plans_and_upgrade_flow(client: TestClient) -> None:
    plans = client.get("/api/v1/public/plans")
    assert plans.status_code == 200
    assert [item["id"] for item in plans.json()["items"]] == [
        "trial",
        "basic",
        "pro",
        "enterprise",
    ]

    current = client.get("/api/v1/billing/plan")
    assert current.status_code == 200
    assert current.json()["code"] == "trial"

    upgraded = client.post("/api/v1/billing/upgrade", json={"plan": "pro"})
    assert upgraded.status_code == 200, upgraded.text
    assert upgraded.json()["plan"] == "pro"
    assert upgraded.json()["granted"] == 9700
    assert upgraded.json()["balance"] == 10000

    current = client.get("/api/v1/billing/plan").json()
    assert current["code"] == "pro"
    assert current["name"] == "高级版"

    downgraded = client.post("/api/v1/billing/upgrade", json={"plan": "basic"})
    assert downgraded.status_code == 422

    duplicate = client.post("/api/v1/billing/upgrade", json={"plan": "pro"})
    assert duplicate.status_code == 409

    unknown = client.post("/api/v1/billing/upgrade", json={"plan": "missing"})
    assert unknown.status_code == 422
