from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

try:
    import aiofiles
    import aiofiles.os
except ImportError:
    raise ImportError("pip install fast-agent-stack[storage-local]") from None

from fast_agent_stack.core.storage import KeyNotFoundError

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings


class LocalStorage:
    def __init__(self, settings: "BaseSettings") -> None:
        self._root = Path(settings.storage_local_root)
        self._timeout = settings.storage_timeout

    def _path(self, key: str) -> Path:
        return self._root / key

    async def upload(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        dest = self._path(key)
        await aiofiles.os.makedirs(dest.parent, exist_ok=True)
        async with aiofiles.open(dest, "wb") as f:
            await f.write(data)
        return key

    async def download(self, key: str) -> bytes:
        dest = self._path(key)
        if not dest.exists():
            raise KeyNotFoundError(key)
        async with aiofiles.open(dest, "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> None:
        dest = self._path(key)
        if dest.exists():
            await aiofiles.os.remove(dest)

    async def exists(self, key: str) -> bool:
        return self._path(key).exists()

    async def url(self, key: str, *, expires_in: int = 3600) -> str:
        return self._path(key).as_uri()
