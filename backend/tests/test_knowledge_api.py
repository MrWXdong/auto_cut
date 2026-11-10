from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_rag_store
from app.api.main import app
from app.rag.store import RagStore


@pytest.fixture
def client(tmp_path):
    store = RagStore(tmp_path / "rag.db")
    app.dependency_overrides[get_rag_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_kb(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "品牌库", "description": "品牌规范"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_upload_list_and_search(client: TestClient) -> None:
    kb = create_kb(client)
    response = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        files={
            "file": (
                "brand.md",
                "品牌主色是墨绿色。产品主打温和不刺激。".encode(),
                "text/markdown",
            )
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["chunk_count"] >= 1

    documents = client.get(f"/api/v1/knowledge-bases/{kb['id']}/documents")
    assert documents.status_code == 200
    assert len(documents.json()["items"]) == 1

    hits = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/search",
        json={"query": "墨绿色"},
    )
    assert hits.status_code == 200
    assert hits.json()["hits"]


def test_unknown_knowledge_base_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/knowledge-bases/missing/search",
        json={"query": "测试"},
    )
    assert response.status_code == 404


def test_delete_document(client: TestClient) -> None:
    kb = create_kb(client)
    uploaded = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/documents",
        files={"file": ("a.md", b"hello world", "text/markdown")},
    ).json()
    deleted = client.delete(
        f"/api/v1/knowledge-bases/{kb['id']}/documents/{uploaded['id']}"
    )
    assert deleted.status_code == 200
