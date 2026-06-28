from __future__ import annotations

from typing import Any, AsyncIterator

try:
    import aioboto3
    from botocore.config import Config as BotocoreConfig
except ImportError:
    raise ImportError("pip install fast-agent-stack[bedrock]") from None

from fast_agent_stack.core.ai.llm import CompletionResult, Message


class BedrockLLMBackend:
    def __init__(
        self,
        model_id: str,
        region_name: str = "us-east-1",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._model_id = model_id
        self._region = region_name
        self._timeout = timeout
        self._session = aioboto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
        )
        self._boto_config = BotocoreConfig(
            connect_timeout=timeout,
            read_timeout=timeout,
        )

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def session(self) -> Any:
        """Escape hatch (I4): direct access to the underlying aioboto3.Session."""
        return self._session

    def _convert_messages(
        self, messages: list[Message]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        system = [{"text": m.content} for m in messages if m.role == "system"]
        conv = [
            {"role": m.role, "content": [{"text": m.content}]}
            for m in messages
            if m.role != "system"
        ]
        return system, conv

    async def complete(
        self, messages: list[Message], **kwargs: Any
    ) -> CompletionResult:
        system, conv = self._convert_messages(messages)
        async with self._session.client(
            "bedrock-runtime",
            region_name=self._region,
            config=self._boto_config,
        ) as client:
            response = await client.converse(
                modelId=self._model_id,
                messages=conv,
                system=system,
                **kwargs,
            )
        output = response.get("output", {}).get("message", {}).get("content", [])
        content = output[0]["text"] if output else ""
        usage = response.get("usage", {})
        return CompletionResult(
            content=content,
            model=self._model_id,
            prompt_tokens=usage.get("inputTokens", 0),
            completion_tokens=usage.get("outputTokens", 0),
            total_tokens=usage.get("totalTokens", 0),
            cost=None,
        )

    async def stream(
        self, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[str | CompletionResult]:
        system, conv = self._convert_messages(messages)
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        async with self._session.client(
            "bedrock-runtime",
            region_name=self._region,
            config=self._boto_config,
        ) as client:
            response = await client.converse_stream(
                modelId=self._model_id,
                messages=conv,
                system=system,
                **kwargs,
            )
            async for event in response["stream"]:
                if "contentBlockDelta" in event:
                    chunk = event["contentBlockDelta"]["delta"].get("text", "")
                    if chunk:
                        yield chunk
                elif "metadata" in event:
                    usage = event["metadata"].get("usage", {})
                    prompt_tokens = usage.get("inputTokens", 0)
                    completion_tokens = usage.get("outputTokens", 0)
                    total_tokens = usage.get("totalTokens", 0)
        # ADR-036: sentinel is the absolute last item — no content after this
        yield CompletionResult(
            content="",
            model=self._model_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=None,
        )

    async def count_tokens(self, messages: list[Message]) -> int:
        # Bedrock has no public token-count endpoint for the converse API.
        # Character-count estimate: ~4 chars per token.
        return sum(len(m.content) for m in messages) // 4
