from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, String, Text, Uuid, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from fast_agent_stack.core.database import Base


class ConversationLog(Base):
    __tablename__ = "conversation_log"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Soft reference to users.id — no DB-level FK so AI works without auth tables.
    user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_conversation_log_user_id", "user_id"),
        Index("ix_conversation_log_agent_name", "agent_name"),
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_conversation_messages_conversation_id", "conversation_id"),)


class ConversationService:
    async def create_conversation(
        self,
        *,
        agent_name: str,
        user_id: UUID | None = None,
        db: AsyncSession,
    ) -> ConversationLog:
        log = ConversationLog(agent_name=agent_name, user_id=user_id)
        db.add(log)
        await db.flush()
        return log

    async def append_message(
        self,
        *,
        conversation_id: UUID,
        role: str,
        content: str,
        db: AsyncSession,
    ) -> ConversationMessage:
        msg = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        db.add(msg)
        await db.flush()
        return msg

    async def get_conversation(
        self,
        *,
        conversation_id: UUID,
        db: AsyncSession,
    ) -> ConversationLog | None:
        result = await db.execute(select(ConversationLog).where(ConversationLog.id == conversation_id))
        return result.scalar_one_or_none()

    async def get_messages(
        self,
        *,
        conversation_id: UUID,
        db: AsyncSession,
    ) -> Sequence[ConversationMessage]:
        result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.asc())
        )
        return result.scalars().all()
