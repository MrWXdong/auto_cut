from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_studio_store
from app.api.main import app
from app.studio.store import StudioStore


@pytest.fixture
def client(tmp_path):
    store = StudioStore(tmp_path / "studio.db", tmp_path / "work")
    app.dependency_overrides[get_studio_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_brand_kit_round_trip(client: TestClient) -> None:
    initial = client.get("/api/v1/brand-kit")
    assert initial.status_code == 200
    assert initial.json()["brand_name"] == ""
    assert initial.json()["primary_color"] == "#0f766e"
    assert initial.json()["configured"] is False

    updated = client.put(
        "/api/v1/brand-kit",
        json={
            "brand_name": "星河面膜",
            "slogan": "让每一次护肤都值得",
            "primary_color": "#123abc",
            "secondary_color": "#fedcba",
            "font_family": "Microsoft YaHei",
            "watermark_text": "星河出品",
            "voice_tone": "专业、克制、可信",
            "intro_text": "三秒了解新配方",
            "outro_text": "点击主页了解更多",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["brand_name"] == "星河面膜"
    assert updated.json()["primary_color"] == "#123abc"
    assert updated.json()["configured"] is True

    reloaded = client.get("/api/v1/brand-kit").json()
    assert reloaded["watermark_text"] == "星河出品"
    assert reloaded["outro_text"] == "点击主页了解更多"


def test_brand_kit_rejects_invalid_color(client: TestClient) -> None:
    response = client.put(
        "/api/v1/brand-kit",
        json={"primary_color": "red"},
    )
    assert response.status_code == 422


def test_brand_logo_upload_and_download(client: TestClient) -> None:
    missing = client.get("/api/v1/brand-kit/logo")
    assert missing.status_code == 404

    content = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
    uploaded = client.post(
        "/api/v1/brand-kit/logo",
        files={"file": ("logo.svg", content, "image/svg+xml")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["logo_filename"] == "logo.svg"
    assert uploaded.json()["logo_storage_key"].startswith("brands/demo/logo-")

    downloaded = client.get("/api/v1/brand-kit/logo")
    assert downloaded.status_code == 200
    assert downloaded.content == content


def test_brand_logo_rejects_unsupported_file(client: TestClient) -> None:
    response = client.post(
        "/api/v1/brand-kit/logo",
        files={"file": ("logo.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 422
