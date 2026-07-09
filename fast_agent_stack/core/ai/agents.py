from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from fast_agent_stack.core.ai.llm import CompletionResult, LLMBackend, Message
from fast_agent_stack.core.ai.streaming import stream_sse
from fast_agent_stack.core.ai.usage import UsageService
from fast_agent_stack.core.database import get_async_session

logger = logging.getLogger(__name__)

_usage_service = UsageService()


class _MessageIn(BaseModel):
    role: str
    content: str


class AgentRequest(BaseModel):
    messages: list[_MessageIn]
    conversation_id: UUID | None = None


async def dispatch(
    handler: Callable[..., Any],
    backend: LLMBackend,
    messages: list[Message],
    *,
    user_id: UUID | None,
    api_key_id: UUID | None,
    agent_name: str,
    conversation_id: UUID | None,
    db: AsyncSession,
) -> Any:
    """Route a request to the streaming or non-streaming path (ADR-036)."""
    if inspect.isasyncgenfunction(handler):
        gen = handler(
            messages,
            user_id=user_id,
            api_key_id=api_key_id,
            conversation_id=conversation_id,
        )
        return await stream_sse(
            gen,
            user_id=user_id,
            api_key_id=api_key_id,
            agent_name=agent_name,
            conversation_id=conversation_id,
            db=db,
        )
    else:
        text: str = await handler(
            messages,
            user_id=user_id,
            api_key_id=api_key_id,
            conversation_id=conversation_id,
        )
        result: CompletionResult = await backend.complete([Message(role="user", content=text)])
        try:
            await _usage_service.log_usage(
                result,
                user_id=user_id,
                api_key_id=api_key_id,
                agent_name=agent_name,
                conversation_id=conversation_id,
                db=db,
            )
        except Exception:
            logger.warning("dispatch: log_usage raised (swallowed per I21)", exc_info=True)
        return JSONResponse({"content": result.content, "model": result.model})


def make_agent_route_func(
    name: str,
    handler: Callable[..., Any],
    backend: LLMBackend,
) -> Callable[..., Any]:
    """Return a FastAPI-compatible async route handler for the named agent."""

    async def route_func(
        body: AgentRequest,
        db: AsyncSession = Depends(get_async_session),
    ) -> Any:
        messages = [Message(role=m.role, content=m.content) for m in body.messages]
        return await dispatch(
            handler,
            backend,
            messages,
            user_id=None,
            api_key_id=None,
            agent_name=name,
            conversation_id=body.conversation_id,
            db=db,
        )

    # Unique name lets FastAPI generate a distinct operation_id per agent.
    route_func.__name__ = f"agent_{name}"
    route_func.__qualname__ = f"agent_{name}"
    return route_func
