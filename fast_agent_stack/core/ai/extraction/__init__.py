from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["ExtractionProtocol", "get_extractor"]

_MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@runtime_checkable
class ExtractionProtocol(Protocol):
    async def extract(self, data: bytes) -> str: ...


def get_extractor(content_type: str) -> ExtractionProtocol | None:
    """Return the extractor for the given MIME type, or None if unsupported."""
    if content_type == "application/pdf":
        from fast_agent_stack.core.ai.extraction.backends.pdf import PdfExtractor
        return PdfExtractor()
    if content_type == _MIME_DOCX:
        from fast_agent_stack.core.ai.extraction.backends.docx import DocxExtractor
        return DocxExtractor()
    if content_type == _MIME_XLSX:
        from fast_agent_stack.core.ai.extraction.backends.xlsx import XlsxExtractor
        return XlsxExtractor()
    if content_type == "message/rfc822":
        from fast_agent_stack.core.ai.extraction.backends.eml import EmlExtractor
        return EmlExtractor()
    return None
