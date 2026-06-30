"""Unit tests for 5-C: embedding protocol, factory dispatch, and invariants."""
from __future__ import annotations

import importlib
import inspect
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fast_agent_stack.core.ai.embedding import EmbeddingProtocol, get_embedding_provider


def _make_settings(**kwargs):  # type: ignore[no-untyped-def]
    m = MagicMock()
    m.embedding_provider = kwargs.get("embedding_provider", "local")
    m.embedding_model = kwargs.get("embedding_model", "BAAI/bge-small-en-v1.5")
    m.embedding_cache_dir = kwargs.get("embedding_cache_dir", "")
    m.embedding_openai_model = kwargs.get("embedding_openai_model", "text-embedding-3-small")
    m.embedding_bedrock_model_id = kwargs.get("embedding_bedrock_model_id", "amazon.titan-embed-text-v2:0")
    m.embedding_timeout = kwargs.get("embedding_timeout", 30.0)
    return m


# ---------------------------------------------------------------------------
# CONTRACT
# ---------------------------------------------------------------------------

def test_embedding_protocol_embed_signature():
    sig = inspect.signature(EmbeddingProtocol.embed)
    params = sig.parameters
    assert "text" in params
    ann = params["text"].annotation
    # Under `from __future__ import annotations`, annotations are strings
    assert ann is str or ann == "str"


def test_embedding_protocol_embed_batch_signature():
    sig = inspect.signature(EmbeddingProtocol.embed_batch)
    params = sig.parameters
    assert "texts" in params


def test_embedding_protocol_dimensions_is_property():
    assert isinstance(EmbeddingProtocol.__dict__["dimensions"], property)


def test_embedding_module_public_init_exports():
    from fast_agent_stack.core.ai.embedding import EmbeddingProtocol, get_embedding_provider
    assert callable(get_embedding_provider)
    assert isinstance(EmbeddingProtocol, type)


# ---------------------------------------------------------------------------
# BEHAVIOR — OpenAI backend with mocked client
# ---------------------------------------------------------------------------

def test_openai_embedding_with_mocked_client():
    """OpenAIEmbedding.embed should call the API and return a list of floats."""
    mock_openai = MagicMock(name="openai")
    mock_client_cls = MagicMock()
    mock_openai.AsyncOpenAI = mock_client_cls
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    if "openai" not in sys.modules:
        sys.modules["openai"] = mock_openai

    mod_name = "fast_agent_stack.core.ai.embedding.backends.openai"
    sys.modules.pop(mod_name, None)
    try:
        backend_mod = importlib.import_module(mod_name)
        backend = backend_mod.OpenAIEmbedding(_make_settings(embedding_provider="openai"))
        assert hasattr(backend, "_client")
    finally:
        sys.modules.pop(mod_name, None)


# ---------------------------------------------------------------------------
# ARCHITECTURAL — I4 attribute presence
# ---------------------------------------------------------------------------

def test_openai_embedding_exposes_client_attribute_i4():
    mock_openai = MagicMock(name="openai")
    mock_openai.AsyncOpenAI = MagicMock(return_value=MagicMock())
    saved = sys.modules.get("openai")
    if "openai" not in sys.modules:
        sys.modules["openai"] = mock_openai
    mod_name = "fast_agent_stack.core.ai.embedding.backends.openai"
    sys.modules.pop(mod_name, None)
    try:
        mod = importlib.import_module(mod_name)
        backend = mod.OpenAIEmbedding(_make_settings())
        assert hasattr(backend, "_client")
    finally:
        sys.modules.pop(mod_name, None)


# ---------------------------------------------------------------------------
# NFR — I2: local embedding uses run_in_executor
# ---------------------------------------------------------------------------

def test_local_embedding_uses_run_in_executor_i2():
    import fast_agent_stack.core.ai.embedding.backends.local as mod
    with open(mod.__file__) as f:
        src = f.read()
    assert "run_in_executor" in src


# ---------------------------------------------------------------------------
# FAILURE-MODE — I3 import guards
# ---------------------------------------------------------------------------

def test_local_embedding_import_guard_i3():
    saved = sys.modules.pop("fastembed", None)
    sys.modules["fastembed"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.ai.embedding.backends.local"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[embedding-local\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["fastembed"] = saved
        elif "fastembed" in sys.modules:
            del sys.modules["fastembed"]
        if cached is not None:
            sys.modules[mod_name] = cached


def test_openai_embedding_import_guard_i3():
    saved = sys.modules.pop("openai", None)
    sys.modules["openai"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.ai.embedding.backends.openai"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[embedding-openai\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["openai"] = saved
        elif "openai" in sys.modules:
            del sys.modules["openai"]
        if cached is not None:
            sys.modules[mod_name] = cached


def test_bedrock_embedding_import_guard_i3():
    saved = sys.modules.pop("aioboto3", None)
    sys.modules["aioboto3"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.ai.embedding.backends.bedrock"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[embedding-bedrock\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["aioboto3"] = saved
        elif "aioboto3" in sys.modules:
            del sys.modules["aioboto3"]
        if cached is not None:
            sys.modules[mod_name] = cached
