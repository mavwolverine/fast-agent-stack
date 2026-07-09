"""Unit tests for chunking functions."""

from __future__ import annotations

from fast_agent_stack.core.ai.rag.chunking import fixed_chunker, paragraph_chunker


def test_paragraph_chunker_splits_on_double_newline():
    result = paragraph_chunker("Para one.\n\nPara two.\n\nPara three.")
    assert result == ["Para one.", "Para two.", "Para three."]


def test_paragraph_chunker_ignores_empty_paragraphs():
    result = paragraph_chunker("A\n\n\n\nB")
    assert result == ["A", "B"]


def test_paragraph_chunker_single_paragraph_no_split():
    result = paragraph_chunker("single paragraph text")
    assert result == ["single paragraph text"]


def test_paragraph_chunker_empty_input():
    assert paragraph_chunker("") == []


def test_fixed_chunker_single_chunk_when_text_fits():
    text = "A" * 100
    result = fixed_chunker(text)
    assert result == [text]


def test_fixed_chunker_empty_input_returns_empty_list():
    assert fixed_chunker("") == []


def test_fixed_chunker_multi_chunk():
    # chunk_size=512 tokens * 4 chars = 2048 chars window
    # chunk_overlap=64 tokens * 4 chars = 256 chars overlap
    # step = (512-64)*4 = 1792 chars
    text = "X" * 5000
    result = fixed_chunker(text, chunk_size=512, chunk_overlap=64)
    assert len(result) > 1
    for chunk in result:
        assert len(chunk) <= 512 * 4


def test_fixed_chunker_overlap_region():
    """Consecutive chunks share an overlap region."""
    text = "A" * 5000
    result = fixed_chunker(text, chunk_size=512, chunk_overlap=64)
    if len(result) >= 2:
        overlap_size = 64 * 4  # 256 chars
        end_of_first = result[0][-overlap_size:]
        start_of_second = result[1][:overlap_size]
        assert end_of_first == start_of_second


def test_fixed_chunker_first_chunk_starts_at_zero():
    text = "HELLO" * 1000
    result = fixed_chunker(text)
    assert result[0] == text[: 512 * 4]
