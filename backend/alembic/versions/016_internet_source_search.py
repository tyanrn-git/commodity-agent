"""internet source AI search runs

Revision ID: 016
Revises: 015
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "internet_source_search_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("regions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("search_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("access_mode", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sources_matched", sa.Integer(), nullable=False),
        sa.Column("sources_scanned", sa.Integer(), nullable=False),
        sa.Column("hits_found", sa.Integer(), nullable=False),
        sa.Column("hits_new", sa.Integer(), nullable=False),
        sa.Column("opportunities_created", sa.Integer(), nullable=False),
        sa.Column("ai_calls", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_internet_source_search_runs_owner_id"),
        "internet_source_search_runs",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_internet_source_search_runs_status"),
        "internet_source_search_runs",
        ["status"],
        unique=False,
    )

    op.create_table(
        "internet_source_search_hits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("search_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("internet_source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("canonical_url", sa.String(length=1024), nullable=True),
        sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("evidence_excerpt", sa.Text(), nullable=True),
        sa.Column("fetch_status", sa.String(length=32), nullable=True),
        sa.Column("extracted_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["internet_source_id"], ["internet_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["search_run_id"], ["internet_source_search_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_internet_source_search_hits_search_run_id"),
        "internet_source_search_hits",
        ["search_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_internet_source_search_hits_internet_source_id"),
        "internet_source_search_hits",
        ["internet_source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_internet_source_search_hits_content_hash"),
        "internet_source_search_hits",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_internet_source_search_hits_status"),
        "internet_source_search_hits",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_internet_source_search_hits_opportunity_id"),
        "internet_source_search_hits",
        ["opportunity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_internet_source_search_hits_opportunity_id"), table_name="internet_source_search_hits")
    op.drop_index(op.f("ix_internet_source_search_hits_status"), table_name="internet_source_search_hits")
    op.drop_index(op.f("ix_internet_source_search_hits_content_hash"), table_name="internet_source_search_hits")
    op.drop_index(op.f("ix_internet_source_search_hits_internet_source_id"), table_name="internet_source_search_hits")
    op.drop_index(op.f("ix_internet_source_search_hits_search_run_id"), table_name="internet_source_search_hits")
    op.drop_table("internet_source_search_hits")
    op.drop_index(op.f("ix_internet_source_search_runs_status"), table_name="internet_source_search_runs")
    op.drop_index(op.f("ix_internet_source_search_runs_owner_id"), table_name="internet_source_search_runs")
    op.drop_table("internet_source_search_runs")
