from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class RetrievalHit:
    content: str
    score: float
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class Retriever(Protocol):
    async def search(self, query: str, top_k: int = 5) -> list[RetrievalHit]: ...


class NullRetriever:
    """Placeholder until pgvector ingestion is wired up."""

    async def search(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        return []
