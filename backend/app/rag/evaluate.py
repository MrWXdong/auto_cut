from __future__ import annotations

from typing import Any

from app.rag.service import RagService
from app.rag.store import RagStore


def evaluate_retrieval(
    store: RagStore,
    kb_id: str,
    cases: list[dict[str, str]],
    k: int = 5,
) -> dict[str, Any]:
    service = RagService(store)
    recall_hits = 0
    reciprocal_rank = 0.0
    details: list[dict[str, Any]] = []

    for case in cases:
        expected = case["expected_document_id"]
        result = service.search(kb_id, case["query"], requested_top_k=k)
        document_ids = [hit["document_id"] for hit in result.hits[:k]]
        rank = document_ids.index(expected) + 1 if expected in document_ids else 0
        if rank:
            recall_hits += 1
            reciprocal_rank += 1 / rank
        details.append(
            {
                "query": case["query"],
                "expected": expected,
                "rank": rank,
                "top_k": result.top_k,
                "tokens": result.tokens,
            }
        )

    total = max(1, len(cases))
    return {
        "cases": len(cases),
        f"recall@{k}": round(recall_hits / total, 4),
        "mrr": round(reciprocal_rank / total, 4),
        "details": details,
    }
