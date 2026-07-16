from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from fast_agent_stack.core.ai.llm import CompletionResult
from fast_agent_stack.core.ai.usage import UsageService

logger = logging.getLogger(__name__)

_usage_service = UsageService()


async def stream_sse(
    iterator: AsyncIterator[str | CompletionResult],
    *,
    user_id: UUID | None,
    api_key_id: UUID | None,
    agent_name: str,
    conversation_id: UUID | None,
    db: AsyncSession | None = None,
) -> StreamingResponse:
    async def _generate() -> AsyncIterator[bytes]:
        async for item in iterator:
            if isinstance(item, CompletionResult):
                # Sentinel intercepted — NOT sent to client.
                # Failures swallowed per I21.
                try:
                    await _usage_service.log_usage(
                        item,
                        user_id=user_id,
                        api_key_id=api_key_id,
                        agent_name=agent_name,
                        conversation_id=conversation_id,
                        db=db,
                    )
                except Exception:
                    logger.warning(
                        "stream_sse: log_usage raised unexpectedly (swallowed — usage write must not abort response)",
                        exc_info=True,
                    )
                return
            # str chunk → SSE data event. Do NOT catch iteration errors here —
            # upstream LLM exceptions must propagate (ADR-036 error-before-sentinel).
            yield f"data: {json.dumps(item)}\n\n".encode()

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
