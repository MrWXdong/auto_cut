from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.rag.chunker import chunk_text

SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL REFERENCES knowledge_bases (id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (kb_id, sha256)
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    kb_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    content TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_kb ON documents (kb_id, tenant_id);
CREATE INDEX IF NOT EXISTS idx_chunks_kb ON chunks (kb_id, tenant_id);
"""


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _terms(query: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9_]+", query.lower())
    cjk = re.findall(r"[\u4e00-\u9fff]", query)
    terms = list(dict.fromkeys(words + cjk))
    return terms or [query.lower()]


class RagStore:
    """SQLite-backed retrieval.

    v1 uses term frequency instead of embeddings so it works without a model.
    Swap the search method for pgvector + cloud embeddings later.
    """

    def __init__(self, database_path: Path) -> None:
        self._path = Path(database_path)
        self._cache: dict[tuple[str, str, str, int], list[dict[str, Any]]] = {}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.isolation_level = None
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def create_kb(
        self,
        name: str,
        description: str = "",
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValueError("knowledge base name is required")
        kb_id = uuid.uuid4().hex[:8]
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO knowledge_bases (id, tenant_id, name, description, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (kb_id, tenant_id, name, description.strip(), utcnow()),
            )
            connection.commit()
        return self.get_kb(kb_id, tenant_id) or {}

    def get_kb(self, kb_id: str, tenant_id: str = "demo") -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT kb.*,
                    (SELECT COUNT(*) FROM documents d
                     WHERE d.kb_id = kb.id AND d.tenant_id = kb.tenant_id) AS document_count,
                    (SELECT COUNT(*) FROM chunks c
                     WHERE c.kb_id = kb.id AND c.tenant_id = kb.tenant_id) AS chunk_count
                FROM knowledge_bases kb
                WHERE kb.id = ? AND kb.tenant_id = ?
                """,
                (kb_id, tenant_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_kbs(self, tenant_id: str = "demo") -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT kb.*,
                    (SELECT COUNT(*) FROM documents d
                     WHERE d.kb_id = kb.id AND d.tenant_id = kb.tenant_id) AS document_count,
                    (SELECT COUNT(*) FROM chunks c
                     WHERE c.kb_id = kb.id AND c.tenant_id = kb.tenant_id) AS chunk_count
                FROM knowledge_bases kb
                WHERE kb.tenant_id = ?
                ORDER BY kb.created_at DESC
                """,
                (tenant_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_kb(self, kb_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM knowledge_bases WHERE id = ? AND tenant_id = ?",
                (kb_id, tenant_id),
            )
            connection.commit()
            self._cache.clear()
            return cursor.rowcount == 1

    def add_document(
        self,
        kb_id: str,
        filename: str,
        content: str,
        source: str = "",
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        normalized = content.strip()
        if not normalized:
            raise ValueError("document is empty")
        chunks = chunk_text(normalized)
        if not chunks:
            raise ValueError("document produced no chunks")

        sha256 = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            kb = connection.execute(
                "SELECT id FROM knowledge_bases WHERE id = ? AND tenant_id = ?",
                (kb_id, tenant_id),
            ).fetchone()
            if kb is None:
                connection.rollback()
                raise KeyError(f"knowledge base not found: {kb_id}")

            existing = connection.execute(
                "SELECT * FROM documents WHERE kb_id = ? AND sha256 = ?",
                (kb_id, sha256),
            ).fetchone()
            if existing is not None:
                connection.rollback()
                result = dict(existing)
                result["duplicate"] = True
                return result

            document_id = uuid.uuid4().hex[:10]
            connection.execute(
                """
                INSERT INTO documents (
                    id, kb_id, tenant_id, filename, source, sha256,
                    size_bytes, chunk_count, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    kb_id,
                    tenant_id,
                    filename,
                    source,
                    sha256,
                    len(normalized.encode("utf-8")),
                    len(chunks),
                    utcnow(),
                ),
            )
            connection.executemany(
                """
                INSERT INTO chunks (id, document_id, kb_id, tenant_id, ordinal, content)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (uuid.uuid4().hex, document_id, kb_id, tenant_id, index, chunk)
                    for index, chunk in enumerate(chunks)
                ],
            )
            connection.commit()

        self._cache.clear()
        document = self.get_document(document_id, kb_id, tenant_id)
        if document is None:
            raise RuntimeError("failed to save document")
        document["duplicate"] = False
        return document

    def get_document(
        self,
        document_id: str,
        kb_id: str,
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT * FROM documents
                WHERE id = ? AND kb_id = ? AND tenant_id = ?
                """,
                (document_id, kb_id, tenant_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_documents(self, kb_id: str, tenant_id: str = "demo") -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM documents
                WHERE kb_id = ? AND tenant_id = ?
                ORDER BY created_at DESC
                """,
                (kb_id, tenant_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_document(
        self,
        document_id: str,
        kb_id: str,
        tenant_id: str = "demo",
    ) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                DELETE FROM documents
                WHERE id = ? AND kb_id = ? AND tenant_id = ?
                """,
                (document_id, kb_id, tenant_id),
            )
            connection.commit()
            self._cache.clear()
            return cursor.rowcount == 1

    def search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
        tenant_id: str = "demo",
    ) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        cache_key = (tenant_id, kb_id, query.lower(), top_k)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return [dict(hit) for hit in cached]

        terms = _terms(query)
        lowered = query.lower()

        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT c.id AS chunk_id, c.document_id, c.ordinal, c.content,
                       d.filename
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.kb_id = ? AND c.tenant_id = ?
                """,
                (kb_id, tenant_id),
            ).fetchall()

        hits: list[dict[str, Any]] = []
        for row in rows:
            content = str(row["content"])
            text = content.lower()
            score = 0.0
            matched = 0
            for term in terms:
                count = text.count(term)
                if count:
                    matched += 1
                    score += 1.0 + math.log1p(count)
            if terms:
                score += (matched / len(terms)) * 1.5
            if lowered in text:
                score += 2.0
            if lowered in str(row["filename"]).lower():
                score += 1.0
            if score <= 0:
                continue
            score /= 1.0 + math.log1p(len(content) / 200.0)
            hits.append(
                {
                    "chunk_id": row["chunk_id"],
                    "document_id": row["document_id"],
                    "filename": row["filename"],
                    "ordinal": row["ordinal"],
                    "content": content,
                    "score": round(score, 4),
                }
            )

        hits.sort(key=lambda item: item["score"], reverse=True)
        result = hits[: max(1, min(top_k, 40))]
        if len(self._cache) > 128:
            self._cache.clear()
        self._cache[cache_key] = [dict(hit) for hit in result]
        return result
