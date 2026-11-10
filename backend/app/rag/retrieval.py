from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

CJK = re.compile(r"[\u4e00-\u9fff]")
WORD = re.compile(r"[A-Za-z0-9_]+")
TERM = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{1,4}")

FILLERS = ("帮我", "请", "能不能", "可以", "我想", "麻烦", "一下", "请问")


def estimate_tokens(text: str) -> int:
    cjk = len(CJK.findall(text))
    words = len(WORD.findall(text))
    return cjk + math.ceil(words * 1.3) + 1


def rewrite_query(query: str) -> str:
    text = query.strip()
    for filler in FILLERS:
        text = text.replace(filler, " ")
    text = re.sub(r"\s+", " ", text).strip(" ?？。！!")
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    return text or query.strip()


def analyze_query(query: str) -> dict[str, Any]:
    return {
        "length": len(query),
        "short": len(query) <= 8,
        "question": any(
            token in query
            for token in ("怎么", "如何", "为什么", "什么", "哪些", "是否", "吗", "？", "?")
        ),
        "quoted": '"' in query or "“" in query,
    }


def dynamic_cut(
    hits: list[dict[str, Any]],
    requested: int,
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    if not hits:
        return []

    top = float(hits[0]["score"])
    filtered = [hit for hit in hits if float(hit["score"]) >= top * 0.25]
    base = max(1, min(requested, len(filtered)))

    if profile["short"]:
        base = min(base, 3)
    elif profile["question"]:
        base = min(max(base, 4), len(filtered))

    if len(filtered) > base:
        ratios = []
        for index in range(1, len(filtered)):
            previous = float(filtered[index - 1]["score"]) or 1e-9
            current = float(filtered[index]["score"])
            ratios.append((current / previous, index))
        if ratios:
            ratio, index = min(ratios, key=lambda item: item[0])
            if ratio < 0.55 and index >= 2:
                base = min(base, index)

    return filtered[:base]


def diversify(
    hits: list[dict[str, Any]],
    max_per_document: int = 2,
) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for hit in hits:
        document_id = str(hit.get("document_id") or "")
        if counts.get(document_id, 0) >= max_per_document:
            continue
        counts[document_id] = counts.get(document_id, 0) + 1
        selected.append(hit)
    return selected or hits[:1]


def compress_chunk(content: str, query: str, max_chars: int = 360) -> str:
    clean = re.sub(r"\s+", " ", content).strip()
    if len(clean) <= max_chars:
        return clean

    terms = [term for term in TERM.findall(query) if term]
    positions = [clean.find(term) for term in terms if clean.find(term) >= 0]
    position = min(positions) if positions else -1
    if position < 0:
        return f"{clean[:max_chars]}..."

    start = max(0, position - max_chars // 3)
    end = min(len(clean), start + max_chars)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(clean) else ""
    return f"{prefix}{clean[start:end]}{suffix}"


def pack_context(
    hits: list[dict[str, Any]],
    query: str,
    token_budget: int,
) -> tuple[str, int]:
    blocks: list[str] = []
    used = 0

    for hit in hits:
        snippet = compress_chunk(str(hit["content"]), query)
        block = f"[{hit['filename']}#{hit['ordinal']}] {snippet}"
        cost = estimate_tokens(block)
        if blocks and used + cost > token_budget:
            break
        if not blocks and cost > token_budget:
            block = block[: max(40, token_budget // 2)]
            cost = estimate_tokens(block)
        blocks.append(block)
        used += cost

    return "\n\n".join(blocks), used


@dataclass
class RetrievalResult:
    hits: list[dict[str, Any]] = field(default_factory=list)
    context: str = ""
    tokens: int = 0
    top_k: int = 0
    profile: dict[str, Any] = field(default_factory=dict)
