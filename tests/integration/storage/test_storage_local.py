"""Integration tests for LocalStorage — uses real filesystem via tmpdir."""
from __future__ import annotations

import pytest

pytest.importorskip("aiofiles")

from unittest.mock import MagicMock

from fast_agent_stack.core.storage import KeyNotFoundError
from fast_agent_stack.core.storage.backends.local import LocalStorage


def _make_settings(root: str) -> MagicMock:
    m = MagicMock()
    m.storage_local_root = root
    m.storage_timeout = 30.0
    return m


@pytest.fixture
def storage(tmp_path):  # type: ignore[no-untyped-def]
    return LocalStorage(_make_settings(str(tmp_path)))


@pytest.mark.integration
async def test_local_upload_returns_key(storage):  # type: ignore[no-untyped-def]
    result = await storage.upload("docs/file.txt", b"hello")
    assert result == "docs/file.txt"
    assert (storage._root / "docs/file.txt").exists()


@pytest.mark.integration
async def test_local_download_round_trips_bytes(storage):  # type: ignore[no-untyped-def]
    await storage.upload("img.png", b"\x89PNG\r\n")
    data = await storage.download("img.png")
    assert data == b"\x89PNG\r\n"


@pytest.mark.integration
async def test_local_exists_true_and_false(storage):  # type: ignore[no-untyped-def]
    await storage.upload("present.txt", b"x")
    assert await storage.exists("present.txt") is True
    assert await storage.exists("absent.txt") is False


@pytest.mark.integration
async def test_local_delete_removes_file(storage):  # type: ignore[no-untyped-def]
    await storage.upload("tmp.bin", b"data")
    await storage.delete("tmp.bin")
    assert await storage.exists("tmp.bin") is False


@pytest.mark.integration
async def test_local_url_returns_file_uri(storage):  # type: ignore[no-untyped-def]
    await storage.upload("a.txt", b"content")
    url = await storage.url("a.txt")
    assert isinstance(url, str)
    assert url.startswith("file://")


@pytest.mark.integration
async def test_local_upload_creates_intermediate_directories(storage):  # type: ignore[no-untyped-def]
    await storage.upload("a/b/c/file.txt", b"data")
    assert (storage._root / "a/b/c/file.txt").exists()


@pytest.mark.integration
async def test_local_upload_empty_bytes(storage):  # type: ignore[no-untyped-def]
    await storage.upload("empty.txt", b"")
    data = await storage.download("empty.txt")
    assert data == b""


@pytest.mark.integration
async def test_local_download_missing_key_raises_key_not_found(storage):  # type: ignore[no-untyped-def]
    with pytest.raises(KeyNotFoundError):
        await storage.download("nonexistent.txt")
