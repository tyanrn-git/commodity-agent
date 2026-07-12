"""supplier lead scenario

Revision ID: 009
Revises: 008
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "supplier_lead_contexts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supply_offer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("incoterm", sa.String(length=16), nullable=True),
        sa.Column("origin", sa.String(length=255), nullable=True),
        sa.Column("supplier_hint", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supply_offer_id"], ["supply_offers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("opportunity_id"),
    )
    op.create_index(
        op.f("ix_supplier_lead_contexts_opportunity_id"),
        "supplier_lead_contexts",
        ["opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_lead_contexts_supply_offer_id"),
        "supplier_lead_contexts",
        ["supply_offer_id"],
        unique=False,
    )

    op.create_table(
        "supplier_lead_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplier_opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_type", sa.String(length=32), nullable=False),
        sa.Column("matched_opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("matched_deal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("matched_requirement_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("score", sa.Numeric(6, 2), nullable=False),
        sa.Column("match_summary", sa.String(length=512), nullable=False),
        sa.Column("match_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("route_proposal", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("market_comparison", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("outreach_subject", sa.String(length=512), nullable=True),
        sa.Column("outreach_body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["matched_deal_id"], ["deals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_opportunity_id"], ["opportunities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_requirement_id"], ["requirements.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supplier_opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_supplier_lead_matches_matched_deal_id"),
        "supplier_lead_matches",
        ["matched_deal_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_lead_matches_matched_opportunity_id"),
        "supplier_lead_matches",
        ["matched_opportunity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_lead_matches_matched_requirement_id"),
        "supplier_lead_matches",
        ["matched_requirement_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supplier_lead_matches_supplier_opportunity_id"),
        "supplier_lead_matches",
        ["supplier_opportunity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_supplier_lead_matches_supplier_opportunity_id"), table_name="supplier_lead_matches")
    op.drop_index(op.f("ix_supplier_lead_matches_matched_requirement_id"), table_name="supplier_lead_matches")
    op.drop_index(op.f("ix_supplier_lead_matches_matched_opportunity_id"), table_name="supplier_lead_matches")
    op.drop_index(op.f("ix_supplier_lead_matches_matched_deal_id"), table_name="supplier_lead_matches")
    op.drop_table("supplier_lead_matches")
    op.drop_index(op.f("ix_supplier_lead_contexts_supply_offer_id"), table_name="supplier_lead_contexts")
    op.drop_index(op.f("ix_supplier_lead_contexts_opportunity_id"), table_name="supplier_lead_contexts")
    op.drop_table("supplier_lead_contexts")
