from __future__ import annotations

import asyncio
import io

try:
    from docx import Document
except ImportError:
    raise ImportError("pip install fast-agent-stack[extract-docx]") from None


class DocxExtractor:
    async def extract(self, data: bytes) -> str:
        def _sync() -> str:
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)

        return await asyncio.to_thread(_sync)
