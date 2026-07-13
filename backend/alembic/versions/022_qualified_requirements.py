"""qualified requirements for tender hits

Revision ID: 022
Revises: 021
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "qualified_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("internet_source_search_hit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("qualified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("qualification_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("structured_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("missing_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["internet_source_search_hit_id"], ["internet_source_search_hits.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("internet_source_search_hit_id"),
    )
    op.create_index(op.f("ix_qualified_requirements_owner_id"), "qualified_requirements", ["owner_id"], unique=False)
    op.create_index(op.f("ix_qualified_requirements_status"), "qualified_requirements", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_qualified_requirements_status"), table_name="qualified_requirements")
    op.drop_index(op.f("ix_qualified_requirements_owner_id"), table_name="qualified_requirements")
    op.drop_table("qualified_requirements")
