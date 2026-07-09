"""Auth models — User, Group, Permission, join tables, tokens, API keys (ADR-028, ADR-031)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fast_agent_stack.core.database import Base, BaseModel

# ---------------------------------------------------------------------------
# Join tables (ADR-028)
# ---------------------------------------------------------------------------

user_groups = Table(
    "user_groups",
    Base.metadata,
    Column("user_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", Uuid, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
)

group_permissions = Table(
    "group_permissions",
    Base.metadata,
    Column("group_id", Uuid, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        Uuid,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

user_permissions = Table(
    "user_permissions",
    Base.metadata,
    Column("user_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        Uuid,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class User(BaseModel):
    """Framework user model (ADR-028)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    date_joined: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    groups: Mapped[list[Group]] = relationship(secondary=user_groups, back_populates="users", lazy="selectin")
    direct_permissions: Mapped[list[Permission]] = relationship(
        secondary=user_permissions, back_populates="direct_users", lazy="selectin"
    )


class Group(BaseModel):
    """Named collection of users sharing permissions (ADR-028)."""

    __tablename__ = "groups"

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    users: Mapped[list[User]] = relationship(secondary=user_groups, back_populates="groups", lazy="selectin")
    permissions: Mapped[list[Permission]] = relationship(
        secondary=group_permissions, back_populates="groups", lazy="selectin"
    )


class Permission(BaseModel):
    """Resource + action pair for RBAC (ADR-028)."""

    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("resource", "action", name="uq_permission_resource_action"),)

    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)

    groups: Mapped[list[Group]] = relationship(
        secondary=group_permissions, back_populates="permissions", lazy="selectin"
    )
    direct_users: Mapped[list[User]] = relationship(
        secondary=user_permissions, back_populates="direct_permissions", lazy="selectin"
    )


class AuthVerificationToken(BaseModel):
    """Token for email verification and password reset flows."""

    __tablename__ = "auth_verification_token"

    token: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # "email_verification" | "password_reset"
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApiKey(BaseModel):
    """API key (ADR-031): SHA-256 at rest, show-once, key_prefix for UI."""

    __tablename__ = "api_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    scopes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
