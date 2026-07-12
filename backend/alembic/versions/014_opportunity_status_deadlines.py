"""opportunity status deadlines and history

Revision ID: 014
Revises: 013
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("quote_deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("opportunities", sa.Column("delivery_deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("opportunities", sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("opportunities", sa.Column("status_note", sa.Text(), nullable=True))
    op.add_column(
        "opportunities",
        sa.Column("status_changed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_opportunities_status_changed_by_id_users",
        "opportunities",
        "users",
        ["status_changed_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        UPDATE opportunities SET status = 'IN_ANALYSIS' WHERE status = 'REVIEWING';
        UPDATE opportunities SET status = 'NEEDS_INPUT' WHERE status = 'NEEDS_USER_INPUT';
        UPDATE opportunities SET status = 'ACCEPTED' WHERE status = 'QUALIFIED';
        UPDATE opportunities SET quote_deadline = deadline WHERE deadline IS NOT NULL AND quote_deadline IS NULL;
        UPDATE opportunities SET status_changed_at = updated_at WHERE status_changed_at IS NULL;
        """
    )

    op.create_table(
        "opportunity_status_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status_code", sa.String(length=32), nullable=False),
        sa.Column("status_kind", sa.String(length=16), nullable=False, server_default="OPPORTUNITY"),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.String(length=16), nullable=False, server_default="USER"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_opportunity_status_events_opportunity_id",
        "opportunity_status_events",
        ["opportunity_id"],
    )

    op.execute(
        """
        INSERT INTO opportunity_status_events (
            id, opportunity_id, status_code, status_kind, changed_at, actor_type, note, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            id,
            status,
            'OPPORTUNITY',
            COALESCE(status_changed_at, updated_at, created_at),
            'SYSTEM',
            'Migrated existing status',
            now(),
            now()
        FROM opportunities;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_opportunity_status_events_opportunity_id", table_name="opportunity_status_events")
    op.drop_table("opportunity_status_events")
    op.drop_constraint("fk_opportunities_status_changed_by_id_users", "opportunities", type_="foreignkey")
    op.drop_column("opportunities", "status_changed_by_id")
    op.drop_column("opportunities", "status_note")
    op.drop_column("opportunities", "status_changed_at")
    op.drop_column("opportunities", "delivery_deadline")
    op.drop_column("opportunities", "quote_deadline")
