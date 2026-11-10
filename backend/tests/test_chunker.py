from __future__ import annotations

from app.rag.chunker import chunk_text, normalize, split_sentences


def test_splits_chinese_sentences() -> None:
    assert split_sentences("你好。世界！") == ["你好。", "世界！"]


def test_chunks_respect_max_chars() -> None:
    chunks = chunk_text("第一句话。" * 100, max_chars=100)
    assert chunks
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert "第一句话" in chunks[0]


def test_hard_splits_long_sentence() -> None:
    chunks = chunk_text("长" * 250, max_chars=100)
    assert len(chunks) == 3
    assert all(len(chunk) <= 100 for chunk in chunks)


def test_empty_text_returns_no_chunks() -> None:
    assert chunk_text("   \n\n ") == []


def test_normalize_collapses_blank_lines() -> None:
    assert normalize("a\r\n\r\n\r\nb") == "a\n\nb"
