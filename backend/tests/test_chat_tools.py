from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_rag_store, get_service, get_studio_store
from app.api.main import app
from app.bootstrap import build_registry
from app.rag.store import RagStore
from app.service import JobService
from app.storage import JobStore
from app.studio.store import StudioStore


@pytest.fixture
def client(tmp_path):
    studio = StudioStore(tmp_path / "studio.db", tmp_path / "work")
    rag = RagStore(tmp_path / "rag.db")
    service = JobService(
        JobStore(tmp_path / "jobs.db"),
        tmp_path / "job-work",
        build_registry(),
    )
    app.dependency_overrides[get_studio_store] = lambda: studio
    app.dependency_overrides[get_rag_store] = lambda: rag
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_project(client: TestClient) -> dict:
    return client.post("/api/v1/projects", json={"name": "对话项目"}).json()


def test_chat_generates_script(client: TestClient) -> None:
    project = create_project(client)
    response = client.post(
        "/api/v1/chat",
        json={
            "message": "帮我写一个面膜脚本",
            "project_id": project["id"],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["tool"] == "generate_script"
    assert "面膜" in payload["reply"]
    assert payload["files"]


def test_chat_generates_image_asset(client: TestClient) -> None:
    project = create_project(client)
    response = client.post(
        "/api/v1/chat",
        json={"message": "生成一个墨绿色护肤品封面", "project_id": project["id"]},
    )
    payload = response.json()
    assert payload["tool"] == "generate_image"
    assert payload["files"]


def test_chat_writes_markdown_file(client: TestClient) -> None:
    project = create_project(client)
    response = client.post(
        "/api/v1/chat",
        json={"message": "生成一个 markdown 文件，介绍产品卖点", "project_id": project["id"]},
    )
    payload = response.json()
    assert payload["tool"] == "write_file"
    assert payload["files"][0]["name"].endswith(".md")


def test_chat_searches_knowledge_base(client: TestClient) -> None:
    kb = client.post("/api/v1/knowledge-bases", json={"name": "品牌库"}).json()
    rag_store = app.dependency_overrides[get_rag_store]()
    rag_store.add_document(kb["id"], "brand.md", "品牌主色是墨绿色。")

    response = client.post(
        "/api/v1/chat",
        json={
            "message": "根据知识库，品牌主色是什么",
            "knowledge_base_id": kb["id"],
        },
    )
    payload = response.json()
    assert payload["tool"] == "search_knowledge"
    assert "墨绿色" in payload["reply"]


def test_conversation_persists_messages(client: TestClient) -> None:
    first = client.post("/api/v1/chat", json={"message": "你好"}).json()
    conversation_id = first["conversation_id"]
    client.post(
        "/api/v1/chat",
        json={"message": "再介绍一下你能做什么", "conversation_id": conversation_id},
    )
    detail = client.get(f"/api/v1/conversations/{conversation_id}").json()
    assert len(detail["messages"]) == 4


def test_chat_imports_material_from_url(client: TestClient, monkeypatch) -> None:
    project = create_project(client)

    async def fake_import(studio, project_id, url):
        return {
            "id": "asset-1",
            "filename": "clip.mp4",
            "kind": "video",
            "storage_key": "projects/x/assets/clip.mp4",
            "size_bytes": 10,
            "meta_json": "{}",
        }

    monkeypatch.setattr("app.agents.tools.import_asset_from_url", fake_import)
    response = client.post(
        "/api/v1/chat",
        json={
            "message": "帮我扒这个素材 https://example.com/a.mp4",
            "project_id": project["id"],
        },
    )
    payload = response.json()
    assert payload["tool"] == "import_material"
    assert payload["files"][0]["name"] == "clip.mp4"
