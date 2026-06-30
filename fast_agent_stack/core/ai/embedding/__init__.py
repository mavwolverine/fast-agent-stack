from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings

__all__ = ["EmbeddingProtocol", "get_embedding_provider"]


@runtime_checkable
class EmbeddingProtocol(Protocol):
    async def embed(self, text: str) -> list[float]: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimensions(self) -> int: ...


def get_embedding_provider(settings: "BaseSettings") -> EmbeddingProtocol:
    """Factory: resolves alias or ADR-012 dotted path."""
    provider = settings.embedding_provider
    if provider == "local":
        from fast_agent_stack.core.ai.embedding.backends.local import LocalEmbedding
        return LocalEmbedding(settings)
    if provider == "openai":
        from fast_agent_stack.core.ai.embedding.backends.openai import OpenAIEmbedding
        return OpenAIEmbedding(settings)
    if provider == "bedrock":
        from fast_agent_stack.core.ai.embedding.backends.bedrock import BedrockEmbedding
        return BedrockEmbedding(settings)
    module_path, _, class_name = provider.rpartition(".")
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    return cls(settings)
