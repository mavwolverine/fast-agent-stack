from __future__ import annotations

from typing import TYPE_CHECKING

try:
    import httpx
except ImportError:
    raise ImportError("pip install fast-agent-stack[reranker-ollama]") from None

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings

from fast_agent_stack.core.ai.reranker import RerankResult


class OllamaReranker:
    """Ollama cross-encoder reranker via POST /api/rerank (Ollama 0.5+, ADR-045)."""

    def __init__(self, settings: BaseSettings) -> None:
        self._model = settings.reranker_model
        self._client = httpx.AsyncClient(
            base_url=settings.reranker_url,
            timeout=settings.reranker_timeout,
        )

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_k: int = 5,
    ) -> list[RerankResult]:
        if not documents:
            return []
        resp = await self._client.post(
            "/api/rerank",
            json={
                "model": self._model,
                "query": query,
                "documents": documents,
                "top_n": top_k,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        results = [
            RerankResult(
                content=documents[item["index"]],
                score=float(item["relevance_score"]),
                index=item["index"],
            )
            for item in data.get("results", [])
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]
