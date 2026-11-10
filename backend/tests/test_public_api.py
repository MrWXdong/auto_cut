from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_platform_store
from app.api.main import app
from app.billing.credits import CreditService
from app.config import get_settings
from app.platform.store import PlatformStore


@pytest.fixture
def platform(tmp_path) -> PlatformStore:
    store = PlatformStore(tmp_path / "platform.db")
    store.seed(get_settings())
    return store


@pytest.fixture
def client(platform: PlatformStore):
    app.dependency_overrides[get_platform_store] = lambda: platform
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def platform_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/platform/auth/login",
        json={"email": "admin@local", "password": "admin"},
    )
    return response.json()["access_token"]


def test_public_plans_include_credits(client: TestClient) -> None:
    response = client.get("/api/v1/public/plans")
    assert response.status_code == 200
    plans = {item["id"]: item for item in response.json()["items"]}
    assert plans["basic"]["credits"] == 3000
    assert plans["basic"]["price_monthly_cents"] == 29900


def test_activation_code_auto_provision(client: TestClient, platform: PlatformStore) -> None:
    token = platform_token(client)
    codes = client.post(
        "/api/v1/platform/activation-codes",
        headers={"Authorization": f"Bearer {token}"},
        json={"plan": "basic", "count": 1, "duration_days": 30},
    ).json()["items"]
    code = codes[0]["code"]

    signup = client.post(
        "/api/v1/public/signup",
        json={
            "plan": "basic",
            "company_name": "自助开通企业",
            "owner_email": "self@example.com",
            "owner_password": "secret123",
            "activation_code": code,
        },
    )
    assert signup.status_code == 201, signup.text
    payload = signup.json()
    assert payload["tenant"]["plan"] == "basic"
    assert payload["user"]["tenant_id"] == payload["tenant"]["id"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["tenant_id"] == payload["tenant"]["id"]

    reused = client.post(
        "/api/v1/public/signup",
        json={
            "plan": "basic",
            "company_name": "重复企业",
            "owner_email": "other@example.com",
            "owner_password": "secret123",
            "activation_code": code,
        },
    )
    assert reused.status_code == 422


def test_checkout_creates_pending_order_and_webhook_needs_secret(
    client: TestClient,
) -> None:
    checkout = client.post(
        "/api/v1/public/checkout",
        json={
            "plan": "basic",
            "company_name": "支付企业",
            "owner_email": "pay@example.com",
            "owner_password": "secret123",
        },
    )
    assert checkout.status_code == 201
    order = checkout.json()["order"]
    assert order["status"] == "pending"

    webhook = client.post(
        "/api/v1/public/payments/webhook",
        json={"order_id": order["id"], "status": "paid"},
    )
    assert webhook.status_code == 501


def test_mark_order_paid_provisions_tenant(
    client: TestClient,
    platform: PlatformStore,
    tmp_path,
) -> None:
    order = platform.create_order(
        plan="basic",
        company_name="回调企业",
        owner_email="callback@example.com",
        owner_name="Owner",
        owner_password="secret123",
    )
    result = platform.mark_order_paid(order["id"], "external-1")
    tenant = result["tenant"]
    assert tenant is not None
    assert tenant["plan"] == "basic"

    credits = CreditService(tmp_path / "platform.db")
    assert credits.balance(tenant["id"]) == 3000
