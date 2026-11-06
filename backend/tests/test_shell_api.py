from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_meta_reports_shell_features() -> None:
    response = client.get("/api/v1/meta")
    assert response.status_code == 200
    payload = response.json()
    assert payload["features"]["video_skill"] == "shell"
    assert payload["features"]["rag"] == "shell"


def test_chat_routes_video_intent() -> None:
    response = client.post(
        "/api/v1/chat",
        json={"message": "帮我把这个视频剪成竖屏"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"]["name"] == "video.generate"
    assert payload["plan"]["workflow"] == "clip"


def test_chat_routes_prompt_intent() -> None:
    response = client.post(
        "/api/v1/chat",
        json={"message": "帮我写一个口红带货的提示词"},
    )
    payload = response.json()
    assert payload["intent"]["name"] == "prompt.generate"


def test_prompt_skill_returns_fallback_prompt() -> None:
    response = client.post(
        "/api/v1/skills/prompt",
        json={"product": "面膜", "platform": "小红书", "style": "测评"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["shell"] is True
    assert "面膜" in payload["prompt"]


def test_model_catalog_contains_domestic_providers() -> None:
    response = client.get("/api/v1/settings/models")
    providers = {item["provider"] for item in response.json()["items"]}
    assert {"deepseek", "qwen", "doubao", "kling"}.issubset(providers)


def test_video_and_subtitle_skills_are_shells() -> None:
    assert client.post("/api/v1/skills/video").status_code == 501
    assert client.post("/api/v1/skills/subtitle").status_code == 501


def test_demo_login_returns_owner() -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@local", "password": "demo"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "owner"
