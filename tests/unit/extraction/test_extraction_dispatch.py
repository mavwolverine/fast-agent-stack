"""Unit tests for 5-D: document extraction protocol and dispatch."""

from __future__ import annotations

import importlib
import inspect
import sys

import pytest

from fast_agent_stack.core.ai.extraction import ExtractionProtocol, get_extractor
from fast_agent_stack.core.ai.extraction.backends.eml import EmlExtractor

# ---------------------------------------------------------------------------
# BEHAVIOR
# ---------------------------------------------------------------------------


def test_get_extractor_pdf_returns_pdf_extractor():
    pytest.importorskip("pymupdf")
    from fast_agent_stack.core.ai.extraction.backends.pdf import PdfExtractor

    result = get_extractor("application/pdf")
    assert isinstance(result, PdfExtractor)


def test_get_extractor_docx_returns_docx_extractor():
    pytest.importorskip("docx")
    from fast_agent_stack.core.ai.extraction.backends.docx import DocxExtractor

    result = get_extractor("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert isinstance(result, DocxExtractor)


def test_get_extractor_xlsx_returns_xlsx_extractor():
    pytest.importorskip("openpyxl")
    from fast_agent_stack.core.ai.extraction.backends.xlsx import XlsxExtractor

    result = get_extractor("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert isinstance(result, XlsxExtractor)


def test_get_extractor_eml_returns_eml_extractor_without_extra():
    result = get_extractor("message/rfc822")
    assert isinstance(result, EmlExtractor)


async def test_eml_extractor_extract_returns_body_text():
    eml_bytes = (
        b"From: sender@example.com\r\n"
        b"To: recipient@example.com\r\n"
        b"Subject: Test\r\n"
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"Meeting at 3pm"
    )
    extractor = EmlExtractor()
    result = await extractor.extract(eml_bytes)
    assert "Meeting at 3pm" in result


async def test_pdf_extractor_uses_to_thread():
    pytest.importorskip("pymupdf")
    import fast_agent_stack.core.ai.extraction.backends.pdf as mod

    with open(mod.__file__) as f:
        src = f.read()
    assert "asyncio.to_thread" in src


async def test_docx_extractor_uses_to_thread():
    pytest.importorskip("docx")
    import fast_agent_stack.core.ai.extraction.backends.docx as mod

    with open(mod.__file__) as f:
        src = f.read()
    assert "asyncio.to_thread" in src


async def test_xlsx_extractor_uses_to_thread():
    pytest.importorskip("openpyxl")
    import fast_agent_stack.core.ai.extraction.backends.xlsx as mod

    with open(mod.__file__) as f:
        src = f.read()
    assert "asyncio.to_thread" in src


# ---------------------------------------------------------------------------
# CONTRACT
# ---------------------------------------------------------------------------


def test_extraction_protocol_extract_is_async():
    # ExtractionProtocol.extract should be a coroutine function
    assert inspect.iscoroutinefunction(ExtractionProtocol.extract)


def test_extraction_protocol_exports():
    from fast_agent_stack.core.ai.extraction import ExtractionProtocol, get_extractor

    assert callable(get_extractor)
    assert isinstance(ExtractionProtocol, type)


def test_extraction_protocol_extract_signature():
    sig = inspect.signature(ExtractionProtocol.extract)
    params = list(sig.parameters.keys())
    assert "self" in params
    assert "data" in params
    ann = sig.parameters["data"].annotation
    assert ann is bytes or ann == "bytes"


# ---------------------------------------------------------------------------
# FAILURE-MODE
# ---------------------------------------------------------------------------


def test_get_extractor_returns_none_for_unsupported_mime():
    assert get_extractor("image/jpeg") is None
    assert get_extractor("text/plain") is None
    assert get_extractor("application/octet-stream") is None


def test_pdf_extractor_import_guard_i3():
    saved = sys.modules.pop("pymupdf", None)
    sys.modules["pymupdf"] = None  # type: ignore[assignment]
    # Remove cached backend module so it reimports
    mod_name = "fast_agent_stack.core.ai.extraction.backends.pdf"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[extract-pdf\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["pymupdf"] = saved
        elif "pymupdf" in sys.modules:
            del sys.modules["pymupdf"]
        if cached is not None:
            sys.modules[mod_name] = cached


def test_docx_extractor_import_guard_i3():
    saved = sys.modules.pop("docx", None)
    sys.modules["docx"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.ai.extraction.backends.docx"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[extract-docx\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["docx"] = saved
        elif "docx" in sys.modules:
            del sys.modules["docx"]
        if cached is not None:
            sys.modules[mod_name] = cached


def test_xlsx_extractor_import_guard_i3():
    saved = sys.modules.pop("openpyxl", None)
    sys.modules["openpyxl"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.ai.extraction.backends.xlsx"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[extract-xlsx\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["openpyxl"] = saved
        elif "openpyxl" in sys.modules:
            del sys.modules["openpyxl"]
        if cached is not None:
            sys.modules[mod_name] = cached
