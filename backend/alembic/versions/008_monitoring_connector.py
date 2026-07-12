"""monitoring connector

Revision ID: 008
Revises: 007
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monitoring_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("connector_type", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("poll_interval_hours", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("health_status", sa.String(length=32), nullable=False),
        sa.Column("health_message", sa.Text(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_monitoring_rules_owner_id"), "monitoring_rules", ["owner_id"], unique=False)

    op.create_table(
        "monitoring_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monitoring_rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_found", sa.Integer(), nullable=False),
        sa.Column("items_new", sa.Integer(), nullable=False),
        sa.Column("opportunities_created", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("health_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["monitoring_rule_id"], ["monitoring_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_monitoring_runs_monitoring_rule_id"), "monitoring_runs", ["monitoring_rule_id"], unique=False)
    op.create_index(op.f("ix_monitoring_runs_status"), "monitoring_runs", ["status"], unique=False)

    op.create_table(
        "monitored_publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monitoring_rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_item_id", sa.String(length=255), nullable=False),
        sa.Column("canonical_url", sa.String(length=1024), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_snapshot_key", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("extracted_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["monitoring_rule_id"], ["monitoring_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_monitored_publications_monitoring_rule_id"),
        "monitored_publications",
        ["monitoring_rule_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_monitored_publications_content_hash"),
        "monitored_publications",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_monitored_publications_status"),
        "monitored_publications",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_monitored_publications_opportunity_id"),
        "monitored_publications",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        "uq_monitored_publications_rule_source_item",
        "monitored_publications",
        ["monitoring_rule_id", "source_item_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_monitored_publications_rule_source_item", table_name="monitored_publications")
    op.drop_index(op.f("ix_monitored_publications_opportunity_id"), table_name="monitored_publications")
    op.drop_index(op.f("ix_monitored_publications_status"), table_name="monitored_publications")
    op.drop_index(op.f("ix_monitored_publications_content_hash"), table_name="monitored_publications")
    op.drop_index(op.f("ix_monitored_publications_monitoring_rule_id"), table_name="monitored_publications")
    op.drop_table("monitored_publications")
    op.drop_index(op.f("ix_monitoring_runs_status"), table_name="monitoring_runs")
    op.drop_index(op.f("ix_monitoring_runs_monitoring_rule_id"), table_name="monitoring_runs")
    op.drop_table("monitoring_runs")
    op.drop_index(op.f("ix_monitoring_rules_owner_id"), table_name="monitoring_rules")
    op.drop_table("monitoring_rules")
