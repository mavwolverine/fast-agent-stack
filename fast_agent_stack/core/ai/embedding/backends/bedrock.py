from __future__ import annotations

import json
from typing import TYPE_CHECKING

try:
    import aioboto3
except ImportError:
    raise ImportError("pip install fast-agent-stack[embedding-bedrock]") from None

if TYPE_CHECKING:
    from fast_agent_stack.core.config import BaseSettings

_DIMENSION_MAP = {
    "amazon.titan-embed-text-v2:0": 1024,
    "amazon.titan-embed-text-v1": 1536,
    "cohere.embed-english-v3": 1024,
    "cohere.embed-multilingual-v3": 1024,
}


class BedrockEmbedding:
    def __init__(self, settings: BaseSettings) -> None:
        self._model_id = settings.embedding_bedrock_model_id
        self._timeout = settings.embedding_timeout
        self._client = aioboto3.Session()
        self._dimensions = _DIMENSION_MAP.get(self._model_id, 1024)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed(self, text: str) -> list[float]:
        body = json.dumps({"inputText": text})
        async with self._client.client("bedrock-runtime") as client:
            resp = await client.invoke_model(
                modelId=self._model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            data = json.loads(await resp["body"].read())
        return data.get("embedding", [])

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed(t) for t in texts]
