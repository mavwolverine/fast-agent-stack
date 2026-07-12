from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings

__all__ = ["RerankerProtocol", "RerankResult", "get_reranker"]


@dataclass(frozen=True)
class RerankResult:
    """A reranked document with its relevance score (ADR-045)."""

    content: str
    score: float
    index: int  # original position in the input documents list


@runtime_checkable
class RerankerProtocol(Protocol):
    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_k: int = 5,
    ) -> list[RerankResult]:
        """Rerank documents by relevance to the query.

        Returns top_k results ordered by score descending (highest relevance first).
        """
        ...


def get_reranker(settings: BaseSettings) -> RerankerProtocol | None:
    """Factory: resolves alias or ADR-012 dotted path. Returns None when provider='none'."""
    provider = settings.reranker_provider
    match provider:
        case "none":
            return None
        case "ollama":
            from fast_agent_stack.core.ai.reranker.ollama import OllamaReranker

            return OllamaReranker(settings)
        case "openai":
            from fast_agent_stack.core.ai.reranker.openai import OpenAIReranker

            return OpenAIReranker(settings)
        case _:
            module_path, _, class_name = provider.rpartition(".")
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            return cls(settings)  # type: ignore[no-any-return]
