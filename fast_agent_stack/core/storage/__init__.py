from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings

__all__ = ["StorageProtocol", "KeyNotFoundError", "get_storage"]


class KeyNotFoundError(Exception):
    """Raised when a requested storage key does not exist."""


@runtime_checkable
class StorageProtocol(Protocol):
    async def upload(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str: ...

    async def download(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...

    async def url(self, key: str, *, expires_in: int = 3600) -> str: ...


def get_storage(settings: "BaseSettings") -> StorageProtocol:
    """Factory: resolves alias or ADR-012 dotted path."""
    backend = settings.storage_backend
    if backend == "local":
        from fast_agent_stack.core.storage.backends.local import LocalStorage
        return LocalStorage(settings)
    if backend == "s3":
        from fast_agent_stack.core.storage.backends.s3 import S3Storage
        return S3Storage(settings)
    if backend == "minio":
        from fast_agent_stack.core.storage.backends.minio import MinIOStorage
        return MinIOStorage(settings)
    # ADR-012 dotted-path custom backend
    module_path, _, class_name = backend.rpartition(".")
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    return cls(settings)
