"""email loop tables

Revision ID: 005
Revises: 004
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("risk_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "rfqs",
        sa.Column("source_message_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.create_table(
        "mailbox_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("email_address", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_cursor", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "communication_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deal_party_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("mailbox_thread_id", sa.String(length=255), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deal_party_id"], ["deal_parties.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rfq_id"], ["rfqs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_communication_threads_deal_id"), "communication_threads", ["deal_id"], unique=False)
    op.create_index(op.f("ix_communication_threads_owner_id"), "communication_threads", ["owner_id"], unique=False)
    op.create_index(op.f("ix_communication_threads_rfq_id"), "communication_threads", ["rfq_id"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("link_status", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("from_address", sa.String(length=255), nullable=True),
        sa.Column("to_addresses", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("binding_class", sa.String(length=32), nullable=False),
        sa.Column("mailbox_message_id", sa.String(length=255), nullable=True),
        sa.Column("in_reply_to", sa.String(length=255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["rfq_id"], ["rfqs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["thread_id"], ["communication_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_link_status"), "messages", ["link_status"], unique=False)
    op.create_index(op.f("ix_messages_mailbox_message_id"), "messages", ["mailbox_message_id"], unique=False)
    op.create_index(op.f("ix_messages_rfq_id"), "messages", ["rfq_id"], unique=False)
    op.create_index(op.f("ix_messages_thread_id"), "messages", ["thread_id"], unique=False)

    op.create_foreign_key(
        "fk_rfqs_source_message_id",
        "rfqs",
        "messages",
        ["source_message_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "supply_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("supplier_counterparty_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_name", sa.String(length=255), nullable=True),
        sa.Column("available_quantity", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("quantity_unit", sa.String(length=32), nullable=True),
        sa.Column("price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("incoterm", sa.String(length=16), nullable=True),
        sa.Column("origin", sa.String(length=255), nullable=True),
        sa.Column("loading_point", sa.String(length=255), nullable=True),
        sa.Column("offer_valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_terms", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extracted_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("missing_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rfq_id"], ["rfqs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supplier_counterparty_id"], ["counterparties.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_supply_offers_deal_id"), "supply_offers", ["deal_id"], unique=False)
    op.create_index(op.f("ix_supply_offers_rfq_id"), "supply_offers", ["rfq_id"], unique=False)


def downgrade() -> None:
    op.drop_table("supply_offers")
    op.drop_constraint("fk_rfqs_source_message_id", "rfqs", type_="foreignkey")
    op.drop_table("messages")
    op.drop_table("communication_threads")
    op.drop_table("mailbox_connections")
    op.drop_column("rfqs", "source_message_id")
    op.drop_column("deals", "risk_flags")
