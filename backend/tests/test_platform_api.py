from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_platform_store, get_studio_store
from app.api.main import app
from app.config import get_settings
from app.platform.store import PlatformStore
from app.studio.store import StudioStore


@pytest.fixture
def client(tmp_path):
    platform = PlatformStore(tmp_path / "platform.db")
    platform.seed(get_settings())
    studio = StudioStore(tmp_path / "studio.db", tmp_path / "work")
    app.dependency_overrides[get_platform_store] = lambda: platform
    app.dependency_overrides[get_studio_store] = lambda: studio
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def platform_login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/platform/auth/login",
        json={"email": "admin@local", "password": "admin"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_platform_login_and_guard(client: TestClient) -> None:
    unauthorized = client.get("/api/v1/platform/tenants")
    assert unauthorized.status_code == 401

    wrong = client.post(
        "/api/v1/platform/auth/login",
        json={"email": "admin@local", "password": "wrong"},
    )
    assert wrong.status_code == 401

    token = platform_login(client)
    response = client.get(
        "/api/v1/platform/tenants",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def test_create_and_update_tenant(client: TestClient) -> None:
    token = platform_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/v1/platform/tenants",
        headers=headers,
        json={
            "name": "新客户",
            "plan": "basic",
            "owner_email": "owner@example.com",
            "owner_password": "secret123",
            "owner_name": "客户老板",
        },
    )
    assert created.status_code == 201, created.text
    tenant = created.json()
    assert tenant["plan"] == "basic"

    users = client.get(
        f"/api/v1/platform/tenants/{tenant['id']}/users",
        headers=headers,
    )
    assert users.status_code == 200
    assert users.json()["items"][0]["email"] == "owner@example.com"

    updated = client.patch(
        f"/api/v1/platform/tenants/{tenant['id']}",
        headers=headers,
        json={"status": "suspended"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "suspended"


def test_tenant_login_uses_real_account(client: TestClient) -> None:
    token = platform_login(client)
    created = client.post(
        "/api/v1/platform/tenants",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "登录客户",
            "plan": "trial",
            "owner_email": "login@example.com",
            "owner_password": "secret123",
        },
    ).json()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "secret123"},
    )
    assert login.status_code == 200, login.text
    tenant_token = login.json()["access_token"]
    assert tenant_token != "demo-token"

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert me.status_code == 200
    assert me.json()["tenant_id"] == created["id"]


def test_tenant_token_cannot_access_platform(client: TestClient) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@local", "password": "demo"},
    ).json()
    response = client.get(
        "/api/v1/platform/tenants",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert response.status_code == 403


def test_platform_manages_script_style_presets(client: TestClient) -> None:
    public = client.get("/api/v1/script-styles")
    assert public.status_code == 200
    names = {item["name"] for item in public.json()["items"]}
    assert {"口播", "测评", "知识科普", "高级克制"} <= names
    assert len(names) >= 15

    token = platform_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v1/platform/script-styles",
        headers=headers,
        json={
            "name": "品牌故事",
            "prompt": "用创始人视角讲品牌初心，真实、克制、有细节。",
        },
    )
    assert created.status_code == 201, created.text
    style = created.json()
    assert style["enabled"] is True
    assert style["id"].startswith("ss_")

    public_names = {
        item["name"] for item in client.get("/api/v1/script-styles").json()["items"]
    }
    assert "品牌故事" in public_names

    updated = client.patch(
        f"/api/v1/platform/script-styles/{style['id']}",
        headers=headers,
        json={"name": "品牌故事 2.0", "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "品牌故事 2.0"
    assert updated.json()["enabled"] is False
    public_names = {
        item["name"] for item in client.get("/api/v1/script-styles").json()["items"]
    }
    assert "品牌故事 2.0" not in public_names

    deleted = client.delete(
        f"/api/v1/platform/script-styles/{style['id']}",
        headers=headers,
    )
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"


def test_script_style_requires_platform_admin(client: TestClient) -> None:
    unauthorized = client.get("/api/v1/platform/script-styles")
    assert unauthorized.status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@local", "password": "demo"},
    ).json()
    forbidden = client.get(
        "/api/v1/platform/script-styles",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert forbidden.status_code == 403
