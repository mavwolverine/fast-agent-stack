from __future__ import annotations

__all__ = ["fixed_chunker", "paragraph_chunker"]

_CHARS_PER_TOKEN = 4


def fixed_chunker(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[str]:
    """Split text into overlapping fixed-size token-approximate chunks."""
    if not text:
        return []
    window = chunk_size * _CHARS_PER_TOKEN
    step = (chunk_size - chunk_overlap) * _CHARS_PER_TOKEN
    if step <= 0:
        step = window
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunk = text[start : start + window]
        chunks.append(chunk)
        if start + window >= len(text):
            break
        start += step
    return chunks


def paragraph_chunker(text: str) -> list[str]:
    """Split text on double-newline boundaries, filtering empty paragraphs."""
    return [p.strip() for p in text.split("\n\n") if p.strip()]
