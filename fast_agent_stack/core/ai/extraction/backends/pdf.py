from __future__ import annotations

import asyncio
import io

try:
    import pdfplumber
except ImportError:
    raise ImportError("pip install fast-agent-stack[extract-pdf]") from None


class PdfExtractor:
    async def extract(self, data: bytes) -> str:
        def _sync() -> str:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)

        return await asyncio.to_thread(_sync)
