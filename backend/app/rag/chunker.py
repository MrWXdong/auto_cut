from __future__ import annotations

import re

SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？!?.\n])")


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_BOUNDARY.split(text) if part.strip()]


def chunk_text(text: str, max_chars: int = 400, min_chars: int = 20) -> list[str]:
    if max_chars < 50:
        raise ValueError("max_chars must be at least 50")

    normalized = normalize(text)
    if not normalized:
        return []

    chunks: list[str] = []
    buffer = ""

    for sentence in split_sentences(normalized):
        while len(sentence) > max_chars:
            if buffer:
                chunks.append(buffer.strip())
                buffer = ""
            chunks.append(sentence[:max_chars].strip())
            sentence = sentence[max_chars:]
        if not sentence:
            continue
        if len(buffer) + len(sentence) <= max_chars:
            buffer += sentence
        else:
            if buffer:
                chunks.append(buffer.strip())
            buffer = sentence

    if buffer:
        chunks.append(buffer.strip())

    filtered = [chunk for chunk in chunks if len(chunk) >= min_chars]
    return filtered or chunks
