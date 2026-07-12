"""offers and approval extension

Revision ID: 007
Revises: 006
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configuration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_deal_party_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("configuration_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("economics_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("disclosure_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validity_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["configuration_id"], ["fulfilment_configurations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_deal_party_id"], ["deal_parties.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_offers_deal_id"), "offers", ["deal_id"], unique=False)
    op.create_index(op.f("ix_offers_configuration_id"), "offers", ["configuration_id"], unique=False)
    op.create_index(op.f("ix_offers_status"), "offers", ["status"], unique=False)
    op.create_index(op.f("ix_offers_target_deal_party_id"), "offers", ["target_deal_party_id"], unique=False)

    op.alter_column("approval_requests", "rfq_id", existing_type=postgresql.UUID(), nullable=True)
    op.add_column(
        "approval_requests",
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(op.f("ix_approval_requests_offer_id"), "approval_requests", ["offer_id"], unique=False)
    op.create_foreign_key(
        "fk_approval_requests_offer_id",
        "approval_requests",
        "offers",
        ["offer_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_approval_requests_offer_id", "approval_requests", type_="foreignkey")
    op.drop_index(op.f("ix_approval_requests_offer_id"), table_name="approval_requests")
    op.drop_column("approval_requests", "offer_id")
    op.alter_column("approval_requests", "rfq_id", existing_type=postgresql.UUID(), nullable=False)
    op.drop_table("offers")
