from __future__ import annotations

from app.rag.retrieval import (
    RetrievalResult,
    analyze_query,
    diversify,
    dynamic_cut,
    pack_context,
    rewrite_query,
)
from app.rag.store import RagStore


class RagService:
    def __init__(self, store: RagStore) -> None:
        self._store = store

    def search(
        self,
        kb_id: str,
        query: str,
        requested_top_k: int = 6,
        token_budget: int = 1200,
        tenant_id: str = "demo",
    ) -> RetrievalResult:
        normalized = rewrite_query(query)
        profile = analyze_query(normalized)
        requested = max(1, min(int(requested_top_k or 6), 12))
        budget = max(200, min(int(token_budget or 1200), 4000))

        candidates = self._store.search(
            kb_id,
            normalized,
            top_k=max(20, requested * 4),
            tenant_id=tenant_id,
        )
        selected = dynamic_cut(candidates, requested, profile)
        selected = diversify(selected, max_per_document=2)
        context, used = pack_context(selected, normalized, budget)
        return RetrievalResult(
            hits=selected,
            context=context,
            tokens=used,
            top_k=len(selected),
            profile=profile,
        )
