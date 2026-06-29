from __future__ import annotations

import logging
import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, Integer, String, Uuid, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from fast_agent_stack.core.ai.llm import CompletionResult
from fast_agent_stack.core.database import Base

logger = logging.getLogger(__name__)


class TokenUsageLog(Base):
    __tablename__ = "token_usage_log"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Soft references — no DB-level FK so AI works without auth tables.
    user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    api_key_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    # ADR-035: stored as 1/10000 cents; formula: round(cost_dollars * 1_000_000)
    cost_microcents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Soft reference to conversation_log.id — no FK, log survives conversation deletion.
    conversation_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_token_usage_log_user_id", "user_id"),
        Index("ix_token_usage_log_created_at", "created_at"),
        Index("ix_token_usage_log_agent_name", "agent_name"),
    )


class UsageService:
    async def log_usage(
        self,
        result: CompletionResult,
        *,
        user_id: UUID | None,
        api_key_id: UUID | None,
        agent_name: str,
        conversation_id: UUID | None,
        db: AsyncSession | None = None,
    ) -> None:
        if db is None:
            return
        cost_microcents: int | None = (
            round(result.cost * 1_000_000) if result.cost is not None else None
        )
        row = TokenUsageLog(
            user_id=user_id,
            api_key_id=api_key_id,
            agent_name=agent_name,
            model=result.model,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            cost_microcents=cost_microcents,
            conversation_id=conversation_id,
        )
        db.add(row)
        await db.flush()
