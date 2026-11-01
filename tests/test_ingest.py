"""Tests for the ingest module."""

from src.ingest import _clean, _chunk_text


def test_clean_normalises_whitespace():
    assert _clean("hello   world") == "hello world"


def test_clean_collapses_newlines():
    assert _clean("a\n\n\n\nb") == "a\n\nb"


def test_chunk_text_basic():
    text = "a" * 100
    chunks = _chunk_text(text, size=30, overlap=10)
    assert len(chunks) >= 4
    assert chunks[0] == "a" * 30


def test_chunk_text_overlap():
    text = "0123456789" * 5  # 50 chars
    chunks = _chunk_text(text, size=20, overlap=5)
    # second chunk starts at position 15
    assert chunks[1][:5] == text[15:20]
