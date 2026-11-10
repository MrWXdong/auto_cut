"""Retrieval shell."""

from .base import NullRetriever, RetrievalHit, Retriever
from .chunker import chunk_text
from .retrieval import RetrievalResult, estimate_tokens, pack_context, rewrite_query
from .service import RagService
from .store import RagStore

__all__ = [
    "NullRetriever",
    "RagService",
    "RagStore",
    "RetrievalHit",
    "RetrievalResult",
    "Retriever",
    "chunk_text",
    "estimate_tokens",
    "pack_context",
    "rewrite_query",
]
