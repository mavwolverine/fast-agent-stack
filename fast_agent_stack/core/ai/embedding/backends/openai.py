from __future__ import annotations

from typing import TYPE_CHECKING

try:
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError("pip install fast-agent-stack[embedding-openai]") from None

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings

_DIMENSION_MAP = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbedding:
    def __init__(self, settings: BaseSettings) -> None:
        self._model = settings.embedding_openai_model
        self._client = AsyncOpenAI(timeout=settings.embedding_timeout)
        self._dimensions = _DIMENSION_MAP.get(self._model, 1536)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> list[float]:
        resp = await self._client.embeddings.create(model=self._model, input=text)
        return resp.data[0].embedding  # type: ignore[no-any-return]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        resp = await self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
