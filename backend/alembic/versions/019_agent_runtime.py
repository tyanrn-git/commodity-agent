"""agent runtime tables

Revision ID: 019
Revises: 018
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("research_campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("internet_source_search_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("internet_source_search_hit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_type", sa.String(length=64), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["internet_source_search_hit_id"], ["internet_source_search_hits.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["internet_source_search_run_id"], ["internet_source_search_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["research_campaign_id"], ["research_campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_tasks_agent_type"), "agent_tasks", ["agent_type"], unique=False)
    op.create_index(op.f("ix_agent_tasks_deal_id"), "agent_tasks", ["deal_id"], unique=False)
    op.create_index(op.f("ix_agent_tasks_internet_source_search_hit_id"), "agent_tasks", ["internet_source_search_hit_id"], unique=False)
    op.create_index(op.f("ix_agent_tasks_internet_source_search_run_id"), "agent_tasks", ["internet_source_search_run_id"], unique=False)
    op.create_index(op.f("ix_agent_tasks_opportunity_id"), "agent_tasks", ["opportunity_id"], unique=False)
    op.create_index(op.f("ix_agent_tasks_research_campaign_id"), "agent_tasks", ["research_campaign_id"], unique=False)
    op.create_index(op.f("ix_agent_tasks_status"), "agent_tasks", ["status"], unique=False)
    op.create_index(op.f("ix_agent_tasks_task_type"), "agent_tasks", ["task_type"], unique=False)
    op.create_index(op.f("ix_agent_tasks_created_by_id"), "agent_tasks", ["created_by_id"], unique=False)

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="mock"),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("toolset_version", sa.String(length=64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(precision=12, scale=6), nullable=False, server_default="0"),
        sa.Column("actual_cost", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("ai_usage_log_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="RUNNING"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_task_id"], ["agent_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_runs_agent_task_id"), "agent_runs", ["agent_task_id"], unique=False)
    op.create_index(op.f("ix_agent_runs_ai_usage_log_id"), "agent_runs", ["ai_usage_log_id"], unique=False)
    op.create_index(op.f("ix_agent_runs_status"), "agent_runs", ["status"], unique=False)

    op.create_table(
        "agent_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result_type", sa.String(length=64), nullable=False),
        sa.Column("structured_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["applied_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_results_agent_run_id"), "agent_results", ["agent_run_id"], unique=False)
    op.create_index(op.f("ix_agent_results_result_type"), "agent_results", ["result_type"], unique=False)

    op.add_column(
        "ai_usage_logs",
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(op.f("ix_ai_usage_logs_agent_run_id"), "ai_usage_logs", ["agent_run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_usage_logs_agent_run_id"), table_name="ai_usage_logs")
    op.drop_column("ai_usage_logs", "agent_run_id")
    op.drop_index(op.f("ix_agent_results_result_type"), table_name="agent_results")
    op.drop_index(op.f("ix_agent_results_agent_run_id"), table_name="agent_results")
    op.drop_table("agent_results")
    op.drop_index(op.f("ix_agent_runs_status"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_ai_usage_log_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_agent_task_id"), table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index(op.f("ix_agent_tasks_created_by_id"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_task_type"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_status"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_research_campaign_id"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_opportunity_id"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_internet_source_search_run_id"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_internet_source_search_hit_id"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_deal_id"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_agent_type"), table_name="agent_tasks")
    op.drop_table("agent_tasks")
