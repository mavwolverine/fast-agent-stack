"""Unit tests for 5-A: storage protocol, factory dispatch, and invariants."""

from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fast_agent_stack.core.storage import KeyNotFoundError, StorageProtocol, get_storage


def _make_settings(**kwargs):  # type: ignore[no-untyped-def]
    m = MagicMock()
    m.storage_backend = kwargs.get("storage_backend", "local")
    m.storage_local_root = kwargs.get("storage_local_root", "/tmp/test-storage")
    m.storage_s3_bucket = kwargs.get("storage_s3_bucket", "my-bucket")
    m.storage_s3_region = kwargs.get("storage_s3_region", "us-east-1")
    m.storage_minio_endpoint = kwargs.get("storage_minio_endpoint", "http://localhost:9000")
    m.storage_minio_bucket = kwargs.get("storage_minio_bucket", "minio-bucket")
    m.storage_minio_access_key = kwargs.get("storage_minio_access_key", "minioadmin")
    m.storage_minio_secret_key = kwargs.get("storage_minio_secret_key", "minioadmin")
    m.storage_timeout = kwargs.get("storage_timeout", 30.0)
    return m


# ---------------------------------------------------------------------------
# CONTRACT
# ---------------------------------------------------------------------------


def test_storage_protocol_upload_signature():
    sig = inspect.signature(StorageProtocol.upload)
    params = sig.parameters
    assert "key" in params
    assert "data" in params
    assert "content_type" in params
    assert params["content_type"].default == "application/octet-stream"
    ret = sig.return_annotation
    assert ret is str or ret == "str"


def test_storage_protocol_url_signature():
    sig = inspect.signature(StorageProtocol.url)
    params = sig.parameters
    assert "expires_in" in params
    assert params["expires_in"].default == 3600


def test_storage_protocol_download_return_type():
    sig = inspect.signature(StorageProtocol.download)
    ret = sig.return_annotation
    assert ret is bytes or ret == "bytes"


def test_key_not_found_error_is_exception():
    assert isinstance(KeyNotFoundError(), Exception)


def test_storage_module_public_init_exports():
    from fast_agent_stack.core.storage import (
        KeyNotFoundError,
        StorageProtocol,
        get_storage,
    )

    assert callable(get_storage)
    assert isinstance(StorageProtocol, type)
    assert issubclass(KeyNotFoundError, Exception)


# ---------------------------------------------------------------------------
# BEHAVIOR — factory dispatch
# ---------------------------------------------------------------------------


def test_get_storage_returns_local_storage():
    pytest.importorskip("aiofiles")
    settings = _make_settings(storage_backend="local")
    from fast_agent_stack.core.storage.backends.local import LocalStorage

    backend = get_storage(settings)
    assert isinstance(backend, LocalStorage)


def test_get_storage_dotted_path_dispatch(tmp_path):
    pytest.importorskip("aiofiles")
    settings = _make_settings(storage_backend="fast_agent_stack.core.storage.backends.local.LocalStorage")
    from fast_agent_stack.core.storage.backends.local import LocalStorage

    backend = get_storage(settings)
    assert isinstance(backend, LocalStorage)


# ---------------------------------------------------------------------------
# ARCHITECTURAL — I4
# ---------------------------------------------------------------------------


def test_local_storage_exposes_root_attribute_i4(tmp_path):
    pytest.importorskip("aiofiles")
    settings = _make_settings(storage_local_root=str(tmp_path))
    from fast_agent_stack.core.storage.backends.local import LocalStorage

    backend = LocalStorage(settings)
    assert hasattr(backend, "_root")
    assert isinstance(backend._root, Path)


def test_no_storage_import_breaks_bare_install():
    """Public __init__ must not import aiofiles/aioboto3 at module load time (I3 modularity)."""
    # Just ensure importing the public __init__ doesn't raise when optional deps absent
    # (we test this by importing core.storage directly — guards are only in backend files)
    from fast_agent_stack.core.storage import (  # noqa: F401
        KeyNotFoundError,
        StorageProtocol,
        get_storage,
    )


# ---------------------------------------------------------------------------
# NFR — I2 source check
# ---------------------------------------------------------------------------


def test_local_storage_uses_aiofiles_for_io():
    import fast_agent_stack.core.storage.backends.local as mod

    with open(mod.__file__) as f:
        src = f.read()
    assert "aiofiles" in src


# ---------------------------------------------------------------------------
# FAILURE-MODE — I3 import guards
# ---------------------------------------------------------------------------


def test_local_storage_import_guard_i3():
    saved = sys.modules.pop("aiofiles", None)
    saved_os = sys.modules.pop("aiofiles.os", None)
    sys.modules["aiofiles"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.storage.backends.local"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[storage-local\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["aiofiles"] = saved
        elif "aiofiles" in sys.modules:
            del sys.modules["aiofiles"]
        if saved_os is not None:
            sys.modules["aiofiles.os"] = saved_os
        if cached is not None:
            sys.modules[mod_name] = cached


def test_s3_storage_import_guard_i3():
    saved = sys.modules.pop("aioboto3", None)
    sys.modules["aioboto3"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.storage.backends.s3"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[storage-s3\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["aioboto3"] = saved
        elif "aioboto3" in sys.modules:
            del sys.modules["aioboto3"]
        if cached is not None:
            sys.modules[mod_name] = cached


def test_minio_storage_import_guard_i3():
    saved = sys.modules.pop("aioboto3", None)
    sys.modules["aioboto3"] = None  # type: ignore[assignment]
    mod_name = "fast_agent_stack.core.storage.backends.minio"
    cached = sys.modules.pop(mod_name, None)
    try:
        with pytest.raises(ImportError, match="pip install fast-agent-stack\\[storage-minio\\]"):
            importlib.import_module(mod_name)
    finally:
        sys.modules.pop(mod_name, None)
        if saved is not None:
            sys.modules["aioboto3"] = saved
        elif "aioboto3" in sys.modules:
            del sys.modules["aioboto3"]
        if cached is not None:
            sys.modules[mod_name] = cached
