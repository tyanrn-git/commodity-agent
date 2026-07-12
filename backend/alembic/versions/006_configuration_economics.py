"""configuration and economics tables

Revision ID: 006
Revises: 005
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fulfilment_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("target_quantity", sa.Numeric(18, 6), nullable=True),
        sa.Column("target_quantity_unit", sa.String(length=32), nullable=True),
        sa.Column("destination", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False),
        sa.Column("stale_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stale_reason", sa.Text(), nullable=True),
        sa.Column("sales_price_per_unit", sa.Numeric(18, 6), nullable=True),
        sa.Column("sales_currency", sa.String(length=8), nullable=True),
        sa.Column("revenue", sa.Numeric(18, 6), nullable=True),
        sa.Column("total_cost", sa.Numeric(18, 6), nullable=True),
        sa.Column("gross_margin", sa.Numeric(18, 6), nullable=True),
        sa.Column("gross_margin_percent", sa.Numeric(8, 4), nullable=True),
        sa.Column("cost_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fx_rates_used", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("spec_match_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("completeness_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("last_calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_fulfilment_configurations_deal_id"),
        "fulfilment_configurations",
        ["deal_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fulfilment_configurations_status"),
        "fulfilment_configurations",
        ["status"],
        unique=False,
    )

    op.create_table(
        "service_quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configuration_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quote_type", sa.String(length=32), nullable=False),
        sa.Column("provider_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("source_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("validity_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["configuration_id"], ["fulfilment_configurations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_service_quotes_deal_id"), "service_quotes", ["deal_id"], unique=False)
    op.create_index(
        op.f("ix_service_quotes_configuration_id"),
        "service_quotes",
        ["configuration_id"],
        unique=False,
    )

    op.create_table(
        "shipment_lots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configuration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supply_offer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("supplier_counterparty_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_name", sa.String(length=255), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=True),
        sa.Column("quantity_unit", sa.String(length=32), nullable=True),
        sa.Column("purchase_price_per_unit", sa.Numeric(18, 6), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("incoterm", sa.String(length=16), nullable=True),
        sa.Column("origin", sa.String(length=255), nullable=True),
        sa.Column("packaging", sa.String(length=255), nullable=True),
        sa.Column("allocation_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["configuration_id"], ["fulfilment_configurations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_counterparty_id"], ["counterparties.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supply_offer_id"], ["supply_offers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_shipment_lots_configuration_id"), "shipment_lots", ["configuration_id"], unique=False)

    op.create_table(
        "transport_legs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configuration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("origin", sa.String(length=255), nullable=True),
        sa.Column("destination", sa.String(length=255), nullable=True),
        sa.Column("carrier_name", sa.String(length=255), nullable=True),
        sa.Column("equipment", sa.String(length=128), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=True),
        sa.Column("quantity_unit", sa.String(length=32), nullable=True),
        sa.Column("cost", sa.Numeric(18, 6), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("risk_transfer_point", sa.String(length=255), nullable=True),
        sa.Column("leg_incoterm", sa.String(length=16), nullable=True),
        sa.Column("service_quote_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["configuration_id"], ["fulfilment_configurations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["service_quote_id"], ["service_quotes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transport_legs_configuration_id"), "transport_legs", ["configuration_id"], unique=False)

    op.create_table(
        "economics_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configuration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario", sa.String(length=32), nullable=False),
        sa.Column("snapshot_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["configuration_id"], ["fulfilment_configurations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_economics_snapshots_configuration_id"),
        "economics_snapshots",
        ["configuration_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_economics_snapshots_scenario"),
        "economics_snapshots",
        ["scenario"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("economics_snapshots")
    op.drop_table("transport_legs")
    op.drop_table("shipment_lots")
    op.drop_table("service_quotes")
    op.drop_table("fulfilment_configurations")
