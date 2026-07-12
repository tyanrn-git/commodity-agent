"""internet source catalog

Revision ID: 015
Revises: 014
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "internet_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("access_mode", sa.String(length=32), nullable=False),
        sa.Column("regions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("product_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("languages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("search_hints", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_internet_sources_owner_id"), "internet_sources", ["owner_id"], unique=False)
    op.create_index(
        "uq_internet_sources_system_base_url",
        "internet_sources",
        ["base_url"],
        unique=True,
        postgresql_where=sa.text("owner_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_internet_sources_system_base_url", table_name="internet_sources")
    op.drop_index(op.f("ix_internet_sources_owner_id"), table_name="internet_sources")
    op.drop_table("internet_sources")
