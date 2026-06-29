"""Create token_usage_log table (Phase 4c — ADR-035).

Revision ID: fas_ai_002
Revises: fas_ai_001
Create Date: 2026-06-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "fas_ai_002"
down_revision: str | None = "fas_ai_001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "token_usage_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("api_key_id", sa.Uuid(), nullable=True),
        sa.Column("agent_name", sa.String(255), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        # ADR-035: 1/10000 cents; formula: round(cost_dollars * 1_000_000)
        sa.Column("cost_microcents", sa.Integer(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_token_usage_log_user_id", "token_usage_log", ["user_id"])
    op.create_index(
        "ix_token_usage_log_created_at", "token_usage_log", ["created_at"]
    )
    op.create_index(
        "ix_token_usage_log_agent_name", "token_usage_log", ["agent_name"]
    )


def downgrade() -> None:
    op.drop_index("ix_token_usage_log_agent_name", table_name="token_usage_log")
    op.drop_index("ix_token_usage_log_created_at", table_name="token_usage_log")
    op.drop_index("ix_token_usage_log_user_id", table_name="token_usage_log")
    op.drop_table("token_usage_log")
