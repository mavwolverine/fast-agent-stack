from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import DateTime, Index, Integer, String, Uuid, func, select
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


@dataclass(frozen=True)
class UsageSummary:
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_cost_microcents: int
    request_count: int
    period_start: datetime | None = None
    period_end: datetime | None = None


@dataclass(frozen=True)
class UsageByModel:
    model: str
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    cost_microcents: int
    request_count: int


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

    def _build_filters(
        self,
        *,
        user_id: UUID | None,
        api_key_id: UUID | None,
        agent_name: str | None,
        period_start: datetime | None,
        period_end: datetime | None,
    ) -> tuple[list, datetime, datetime]:
        if user_id is None and api_key_id is None and agent_name is None:
            raise ValueError(
                "At least one identity filter (user_id, api_key_id, agent_name) must be provided."
            )
        now = datetime.now(tz=timezone.utc)
        start = period_start or (now - timedelta(hours=24))
        end = period_end or now
        conditions = [
            TokenUsageLog.created_at >= start,
            TokenUsageLog.created_at <= end,
        ]
        if user_id is not None:
            conditions.append(TokenUsageLog.user_id == user_id)
        if api_key_id is not None:
            conditions.append(TokenUsageLog.api_key_id == api_key_id)
        if agent_name is not None:
            conditions.append(TokenUsageLog.agent_name == agent_name)
        return conditions, start, end

    async def get_usage(
        self,
        *,
        user_id: UUID | None = None,
        api_key_id: UUID | None = None,
        agent_name: str | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        db: AsyncSession,
    ) -> UsageSummary | None:
        conditions, start, end = self._build_filters(
            user_id=user_id,
            api_key_id=api_key_id,
            agent_name=agent_name,
            period_start=period_start,
            period_end=period_end,
        )
        stmt = select(
            func.sum(TokenUsageLog.total_tokens).label("total_tokens"),
            func.sum(TokenUsageLog.prompt_tokens).label("prompt_tokens"),
            func.sum(TokenUsageLog.completion_tokens).label("completion_tokens"),
            func.coalesce(func.sum(TokenUsageLog.cost_microcents), 0).label("total_cost_microcents"),
            func.count(TokenUsageLog.id).label("request_count"),
        ).where(*conditions)
        result = await db.execute(stmt)
        row = result.one_or_none()
        if row is None or row.request_count == 0:
            return None
        return UsageSummary(
            total_tokens=row.total_tokens or 0,
            prompt_tokens=row.prompt_tokens or 0,
            completion_tokens=row.completion_tokens or 0,
            total_cost_microcents=row.total_cost_microcents or 0,
            request_count=row.request_count,
            period_start=start,
            period_end=end,
        )

    async def get_usage_by_model(
        self,
        *,
        user_id: UUID | None = None,
        api_key_id: UUID | None = None,
        agent_name: str | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        db: AsyncSession,
    ) -> list[UsageByModel]:
        conditions, _start, _end = self._build_filters(
            user_id=user_id,
            api_key_id=api_key_id,
            agent_name=agent_name,
            period_start=period_start,
            period_end=period_end,
        )
        stmt = (
            select(
                TokenUsageLog.model,
                func.sum(TokenUsageLog.total_tokens).label("total_tokens"),
                func.sum(TokenUsageLog.prompt_tokens).label("prompt_tokens"),
                func.sum(TokenUsageLog.completion_tokens).label("completion_tokens"),
                func.coalesce(func.sum(TokenUsageLog.cost_microcents), 0).label("cost_microcents"),
                func.count(TokenUsageLog.id).label("request_count"),
            )
            .where(*conditions)
            .group_by(TokenUsageLog.model)
            .order_by(func.sum(TokenUsageLog.total_tokens).desc())
        )
        result = await db.execute(stmt)
        return [
            UsageByModel(
                model=row.model,
                total_tokens=row.total_tokens or 0,
                prompt_tokens=row.prompt_tokens or 0,
                completion_tokens=row.completion_tokens or 0,
                cost_microcents=row.cost_microcents or 0,
                request_count=row.request_count,
            )
            for row in result.all()
        ]
