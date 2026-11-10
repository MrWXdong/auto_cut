from __future__ import annotations

from app.rag.store import RagStore


def make_store(tmp_path) -> RagStore:
    return RagStore(tmp_path / "rag.db")


def test_create_add_and_search(tmp_path) -> None:
    store = make_store(tmp_path)
    kb = store.create_kb("品牌库")
    document = store.add_document(
        kb["id"],
        "brand.md",
        "我们的品牌主色是墨绿色。产品主打温和不刺激，适合敏感肌。",
    )
    assert document["chunk_count"] >= 1

    hits = store.search(kb["id"], "墨绿色")
    assert hits
    assert hits[0]["filename"] == "brand.md"
    assert "墨绿色" in hits[0]["content"]


def test_duplicate_document_is_detected(tmp_path) -> None:
    store = make_store(tmp_path)
    kb = store.create_kb("品牌库")
    content = "同一份内容只应该保存一次。"
    first = store.add_document(kb["id"], "a.md", content)
    second = store.add_document(kb["id"], "b.md", content)
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert len(store.list_documents(kb["id"])) == 1


def test_tenant_isolation(tmp_path) -> None:
    store = make_store(tmp_path)
    store.create_kb("租户一", tenant_id="tenant-a")
    assert len(store.list_kbs("tenant-a")) == 1
    assert store.list_kbs("tenant-b") == []


def test_delete_kb_removes_documents(tmp_path) -> None:
    store = make_store(tmp_path)
    kb = store.create_kb("临时库")
    store.add_document(kb["id"], "a.md", "这是一段会被一起删除的内容。")
    assert store.delete_kb(kb["id"]) is True
    assert store.get_kb(kb["id"]) is None
    assert store.list_documents(kb["id"]) == []


def test_search_is_scoped_to_knowledge_base(tmp_path) -> None:
    store = make_store(tmp_path)
    first = store.create_kb("库一")
    second = store.create_kb("库二")
    store.add_document(first["id"], "a.md", "墨绿色是品牌主色。")
    assert store.search(second["id"], "墨绿色") == []
