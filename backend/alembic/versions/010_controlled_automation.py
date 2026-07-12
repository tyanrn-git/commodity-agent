"""controlled automation

Revision ID: 010
Revises: 009
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "automation_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("auto_follow_up_enabled", sa.Boolean(), nullable=False),
        sa.Column("follow_up_after_days", sa.Integer(), nullable=False),
        sa.Column("max_follow_ups_per_rfq", sa.Integer(), nullable=False),
        sa.Column("min_days_between_follow_ups", sa.Integer(), nullable=False),
        sa.Column("max_auto_actions_per_day", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_automation_settings_user_id"), "automation_settings", ["user_id"], unique=False)

    op.create_table(
        "automation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actions_evaluated", sa.Integer(), nullable=False),
        sa.Column("actions_sent", sa.Integer(), nullable=False),
        sa.Column("actions_blocked", sa.Integer(), nullable=False),
        sa.Column("actions_skipped", sa.Integer(), nullable=False),
        sa.Column("actions_rate_limited", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_automation_runs_owner_id"), "automation_runs", ["owner_id"], unique=False)
    op.create_index(op.f("ix_automation_runs_status"), "automation_runs", ["status"], unique=False)

    op.create_table(
        "automated_action_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("automation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("action_category", sa.String(length=32), nullable=False),
        sa.Column("binding_class", sa.String(length=32), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["automation_run_id"], ["automation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_automated_action_logs_automation_run_id"),
        "automated_action_logs",
        ["automation_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_automated_action_logs_created_at"),
        "automated_action_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_automated_action_logs_entity_id"),
        "automated_action_logs",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_automated_action_logs_owner_id"),
        "automated_action_logs",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_automated_action_logs_status"),
        "automated_action_logs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_automated_action_logs_status"), table_name="automated_action_logs")
    op.drop_index(op.f("ix_automated_action_logs_owner_id"), table_name="automated_action_logs")
    op.drop_index(op.f("ix_automated_action_logs_entity_id"), table_name="automated_action_logs")
    op.drop_index(op.f("ix_automated_action_logs_created_at"), table_name="automated_action_logs")
    op.drop_index(op.f("ix_automated_action_logs_automation_run_id"), table_name="automated_action_logs")
    op.drop_table("automated_action_logs")
    op.drop_index(op.f("ix_automation_runs_status"), table_name="automation_runs")
    op.drop_index(op.f("ix_automation_runs_owner_id"), table_name="automation_runs")
    op.drop_table("automation_runs")
    op.drop_index(op.f("ix_automation_settings_user_id"), table_name="automation_settings")
    op.drop_table("automation_settings")
