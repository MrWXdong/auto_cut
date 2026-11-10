from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_auth_service
from app.api.main import app
from app.auth.service import AuthService
from app.auth.store import AuthStore
from app.config import get_settings


@pytest.fixture
def client(tmp_path):
    service = AuthService(AuthStore(tmp_path / "auth.db"), get_settings())
    app.dependency_overrides[get_auth_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_lists_login_methods(client: TestClient) -> None:
    response = client.get("/api/v1/auth/methods")
    assert response.status_code == 200
    methods = {item["id"]: item for item in response.json()["items"]}
    assert methods["password"]["enabled"] is True
    assert methods["sms"]["enabled"] is True
    assert methods["wechat"]["enabled"] is False


def test_sms_send_and_verify(client: TestClient) -> None:
    sent = client.post("/api/v1/auth/sms/send", json={"phone": "13800138000"})
    assert sent.status_code == 200, sent.text
    code = sent.json()["demo_code"]

    verified = client.post(
        "/api/v1/auth/sms/verify",
        json={"phone": "13800138000", "code": code},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["access_token"]
    assert verified.json()["user"]["role"] == "owner"


def test_sms_wrong_code_is_rejected(client: TestClient) -> None:
    client.post("/api/v1/auth/sms/send", json={"phone": "13800138000"})
    response = client.post(
        "/api/v1/auth/sms/verify",
        json={"phone": "13800138000", "code": "000000"},
    )
    assert response.status_code == 422


def test_sms_invalid_phone_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/auth/sms/send", json={"phone": "123"})
    assert response.status_code == 422


def test_wechat_requires_configuration(client: TestClient) -> None:
    response = client.get("/api/v1/auth/wechat/url")
    assert response.status_code == 501


def test_password_login_still_works(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@local", "password": "demo"},
    )
    assert response.status_code == 200
