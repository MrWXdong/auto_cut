from __future__ import annotations

from app.rag.evaluate import evaluate_retrieval
from app.rag.retrieval import (
    analyze_query,
    diversify,
    dynamic_cut,
    estimate_tokens,
    pack_context,
    rewrite_query,
)
from app.rag.service import RagService
from app.rag.store import RagStore


def test_rewrite_query_removes_fillers() -> None:
    assert rewrite_query("帮我查一下品牌主色是什么？") == "查品牌主色是什么"


def test_estimate_tokens_is_positive() -> None:
    assert estimate_tokens("品牌主色是墨绿色") > 0
    assert estimate_tokens("brand color is teal") > 0


def test_dynamic_cut_uses_score_gap() -> None:
    hits = [
        {"score": 10.0, "document_id": "a"},
        {"score": 9.0, "document_id": "b"},
        {"score": 1.0, "document_id": "c"},
        {"score": 0.5, "document_id": "d"},
    ]
    selected = dynamic_cut(hits, requested=5, profile=analyze_query("品牌主色"))
    assert len(selected) == 2


def test_diversify_limits_chunks_per_document() -> None:
    hits = [
        {"score": 3.0, "document_id": "a"},
        {"score": 2.0, "document_id": "a"},
        {"score": 1.0, "document_id": "a"},
    ]
    selected = diversify(hits, max_per_document=2)
    assert len(selected) == 2


def test_pack_context_respects_budget() -> None:
    hits = [
        {
            "filename": "brand.md",
            "ordinal": 0,
            "content": "品牌主色是墨绿色。" * 80,
        }
    ]
    context, tokens = pack_context(hits, "墨绿色", 200)
    assert context
    assert tokens <= 200


def test_service_and_evaluation(tmp_path) -> None:
    store = RagStore(tmp_path / "rag.db")
    kb = store.create_kb("品牌库")
    brand = store.add_document(
        kb["id"],
        "brand.md",
        "品牌主色是墨绿色，辅助色是暖灰色。",
    )
    pricing = store.add_document(
        kb["id"],
        "pricing.md",
        "产品价格是 199 元，适合敏感肌。",
    )

    result = RagService(store).search(kb["id"], "墨绿色", requested_top_k=5)
    assert result.hits
    assert "墨绿色" in result.context
    assert result.tokens > 0

    report = evaluate_retrieval(
        store,
        kb["id"],
        [
            {"query": "品牌主色", "expected_document_id": brand["id"]},
            {"query": "价格", "expected_document_id": pricing["id"]},
        ],
        k=5,
    )
    assert report["recall@5"] == 1.0
    assert report["mrr"] == 1.0
