from __future__ import annotations

import asyncio

try:
    import pymupdf
except ImportError:
    raise ImportError("pip install fast-agent-stack[extract-pdf]") from None


class PdfExtractor:
    async def extract(self, data: bytes) -> str:
        def _sync() -> str:
            doc = pymupdf.open(stream=data, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)

        return await asyncio.to_thread(_sync)
