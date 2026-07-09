from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING

try:
    from fastembed import TextEmbedding
except ImportError:
    raise ImportError("pip install fast-agent-stack[embedding-local]") from None

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings


class LocalEmbedding:
    def __init__(self, settings: BaseSettings) -> None:
        model_name = settings.embedding_model or "BAAI/bge-small-en-v1.5"
        cache_dir = settings.embedding_cache_dir or None
        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)
        # Pre-compute dimensions by embedding a single token
        sample = list(self._model.embed(["x"]))[0]
        self._dimensions = len(sample)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> list[float]:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, functools.partial(self._sync_embed, text))
        return result

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(self._sync_embed_batch, texts))

    def _sync_embed(self, text: str) -> list[float]:
        return list(next(iter(self._model.embed([text]))))

    def _sync_embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [list(v) for v in self._model.embed(texts)]
