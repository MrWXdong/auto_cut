from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_credit_service, get_studio_store
from app.api.main import app
from app.billing.credits import CreditService
from app.studio.store import StudioStore


@pytest.fixture
def context(tmp_path):
    database = tmp_path / "studio.db"
    store = StudioStore(database, tmp_path / "work")
    credits = CreditService(database)
    credits.grant("demo", 2000, "test seed")
    app.dependency_overrides[get_studio_store] = lambda: store
    app.dependency_overrides[get_credit_service] = lambda: credits
    with TestClient(app) as client:
        yield client, store
    app.dependency_overrides.clear()


def create_style(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/styles",
        json={
            "name": "科技蓝光感",
            "description": "适合数码产品",
            "prompt": "冷色调，科技感，产品居中",
            "negative_prompt": "杂乱背景，低清晰度",
            "model_ref": "doubao-seedream",
            "palette": ["#0f766e", "#2563eb"],
            "shot_rhythm": "卡点",
            "subtitle_style": "关键词高亮",
            "lora_name": "科技产品 LoRA",
            "lora_trigger": "tech_product",
            "lora_base_model": "Flux",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_style_crud_and_default(context) -> None:
    client, _ = context
    assert client.get("/api/v1/styles").json()["items"] == []

    style = create_style(client)
    assert style["name"] == "科技蓝光感"
    assert style["palette"] == ["#0f766e", "#2563eb"]
    assert style["is_default"] is False

    updated = client.patch(
        f"/api/v1/styles/{style['id']}",
        json={"name": "科技蓝光感 2.0", "palette": ["#111111", "#eeeeee"]},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "科技蓝光感 2.0"

    defaulted = client.post(f"/api/v1/styles/{style['id']}/default")
    assert defaulted.status_code == 200
    assert defaulted.json()["is_default"] is True
    assert client.get("/api/v1/styles").json()["items"][0]["is_default"] is True


def test_style_rejects_invalid_palette(context) -> None:
    client, _ = context
    response = client.post(
        "/api/v1/styles",
        json={"name": "bad", "palette": ["red"]},
    )
    assert response.status_code == 422


def test_lora_training_requires_images(context) -> None:
    client, store = context
    style = create_style(client)
    project = store.create_project("品牌素材")
    response = client.post(
        f"/api/v1/styles/{style['id']}/lora/train",
        json={"project_id": project["id"]},
    )
    assert response.status_code == 422


def test_lora_training_queues_job_and_reserves_credits(context) -> None:
    client, store = context
    style = create_style(client)
    project = store.create_project("品牌素材")
    for index in range(3):
        store.add_asset(
            project["id"],
            f"{index}.png",
            f"projects/{project['id']}/assets/{index}.png",
            100,
        )

    response = client.post(
        f"/api/v1/styles/{style['id']}/lora/train",
        json={"project_id": project["id"]},
    )
    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["module"] == "lora"
    assert payload["mode"] == "train"
    assert payload["credits_cost"] == 500

    saved = client.get(f"/api/v1/styles/{style['id']}").json()
    assert saved["lora_status"] == "queued"
    assert saved["lora_job_id"] == payload["id"]
