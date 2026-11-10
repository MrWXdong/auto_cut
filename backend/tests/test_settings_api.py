from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_studio_store
from app.api.main import app
from app.config import get_settings
from app.studio.store import StudioStore


@pytest.fixture
def client(tmp_path):
    store = StudioStore(tmp_path / "studio.db", tmp_path / "work")
    app.dependency_overrides[get_studio_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_defaults_round_trip(client: TestClient) -> None:
    initial = client.get("/api/v1/settings/defaults")
    assert initial.status_code == 200
    assert initial.json()["models"] == {}

    saved = client.put(
        "/api/v1/settings/defaults",
        json={"models": {"image.generate": "qwen:qwen-image"}},
    )
    assert saved.status_code == 200
    assert saved.json()["models"]["image.generate"] == "qwen:qwen-image"

    reloaded = client.get("/api/v1/settings/defaults").json()
    assert reloaded["models"]["image.generate"] == "qwen:qwen-image"


def test_model_catalog_separates_chat_and_wired_capabilities(client: TestClient) -> None:
    items = client.get("/api/v1/settings/models").json()["items"]
    zhipu = next(item for item in items if item["provider"] == "zhipu")
    assert {"glm-4-flash", "glm-4-plus", "glm-4.5-air", "glm-5"} <= set(
        zhipu["chat_models"]
    )
    assert zhipu["wired_capabilities"] == ["chat", "image.generate"]
    assert zhipu["status"] == "needs_key"

    minimax = next(item for item in items if item["provider"] == "minimax")
    assert "chat" not in minimax["capabilities"]
    assert minimax["wired_capabilities"] == []


def test_defaults_include_cheapest_auto_models(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("AUTOCUT_LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    monkeypatch.setenv("AUTOCUT_LLM_API_KEY", "test-zhipu-key")
    monkeypatch.setenv("AUTOCUT_IMAGE_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    monkeypatch.setenv("AUTOCUT_IMAGE_API_KEY", "")
    get_settings.cache_clear()
    try:
        response = client.get("/api/v1/settings/defaults")
    finally:
        get_settings.cache_clear()
    assert response.status_code == 200
    assert response.json()["auto"]["chat"] == "zhipu:glm-4-flash"
    assert response.json()["auto"]["image.generate"] == "zhipu:cogview-3-flash"


def test_doubao_catalog_has_current_models(client: TestClient) -> None:
    items = client.get("/api/v1/settings/models").json()["items"]
    doubao = next(item for item in items if item["provider"] == "doubao")
    assert {
        "doubao-seed-2-1-pro-260915",
        "doubao-seed-2-1-lite-260915",
        "doubao-seed-2-1-turbo-260628",
        "doubao-seed-2-0-mini-260428",
    } <= set(doubao["chat_models"])
    assert {
        "doubao-seedream-5-0-pro-260628",
        "doubao-seedream-5-0-flash-260915",
        "doubao-seedream-4-5-251128",
        "doubao-seedream-4-0-250828",
    } <= set(doubao["image_models"])
    assert "doubao-embedding-large-text-250515" in doubao["embedding_models"]
    assert "doubao-seedance-2-5-260628" in doubao["video_models"]
    assert {"chat", "image.generate"} <= set(doubao["wired_capabilities"])


def test_workspace_preferences_and_status(client: TestClient) -> None:
    initial = client.get("/api/v1/settings/preferences")
    assert initial.status_code == 200
    assert initial.json()["default_quality"] == "standard"
    assert initial.json()["storage_root"]

    updated = client.put(
        "/api/v1/settings/preferences",
        json={
            "default_platform": "小红书",
            "default_aspect": "4:5",
            "default_quality": "high",
            "auto_bgm": True,
            "notify_low_credits": False,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["default_platform"] == "小红书"
    assert updated.json()["default_quality"] == "high"
    assert updated.json()["auto_bgm"] is True

    invalid = client.put(
        "/api/v1/settings/preferences",
        json={"default_aspect": "invalid"},
    )
    assert invalid.status_code == 422

    status = client.get("/api/v1/settings/status")
    assert status.status_code == 200
    assert "llm" in status.json()
    assert status.json()["storage"]["mode"] == "local"


def test_storage_root_can_be_changed(client: TestClient, tmp_path) -> None:
    store_response = client.get("/api/v1/settings/status")
    old_root = store_response.json()["storage"]["root"]
    marker = Path(old_root) / "projects" / "storage-marker.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("keep me", encoding="utf-8")

    new_root = tmp_path / "custom-storage"
    response = client.put(
        "/api/v1/settings/storage",
        json={"root": str(new_root)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["storage_root"] == str(new_root.resolve())
    assert (new_root / "projects" / "storage-marker.txt").read_text(encoding="utf-8") == "keep me"


def test_storage_browser_lists_directories(client: TestClient, tmp_path) -> None:
    target = tmp_path / "browse-target"
    child = target / "child-folder"
    child.mkdir(parents=True)
    response = client.get(
        "/api/v1/settings/storage/browse",
        params={"path": str(target)},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["current"] == str(target.resolve())
    assert payload["parent"]
    assert any(item["name"] == "child-folder" for item in payload["items"])
    assert payload["roots"]


@pytest.mark.skipif(os.name != "nt", reason="native picker is Windows-only")
def test_storage_folder_picker_returns_selected_path(
    client: TestClient,
    monkeypatch,
    tmp_path,
) -> None:
    target = tmp_path / "picked-folder"
    target.mkdir()

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=str(target).encode(),
            stderr=b"",
        )

    monkeypatch.setattr("app.api.routers.settings.subprocess.run", fake_run)
    response = client.post(
        "/api/v1/settings/storage/pick",
        json={"initial": str(tmp_path)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["path"] == str(target.resolve())
