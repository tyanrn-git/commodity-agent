"""counterparty capabilities and opportunity spec values

Revision ID: 011
Revises: 010
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "counterparty_capabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("counterparty_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability_type", sa.String(length=32), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("rough_product_name", sa.String(length=255), nullable=True),
        sa.Column("regions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("routes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("incoterms", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmation_level", sa.String(length=32), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_excerpt", sa.Text(), nullable=True),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("extracted_by_ai", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["counterparty_id"], ["counterparties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_counterparty_capabilities_capability_type"),
        "counterparty_capabilities",
        ["capability_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_counterparty_capabilities_counterparty_id"),
        "counterparty_capabilities",
        ["counterparty_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_counterparty_capabilities_product_id"),
        "counterparty_capabilities",
        ["product_id"],
        unique=False,
    )

    op.create_table(
        "opportunity_spec_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parameter_name", sa.String(length=128), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("value_text", sa.String(length=255), nullable=True),
        sa.Column("value_min", sa.Numeric(18, 6), nullable=True),
        sa.Column("value_max", sa.Numeric(18, 6), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_excerpt", sa.Text(), nullable=True),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("opportunity_id", "parameter_name", name="uq_opportunity_spec_parameter"),
    )
    op.create_index(
        op.f("ix_opportunity_spec_values_opportunity_id"),
        "opportunity_spec_values",
        ["opportunity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_opportunity_spec_values_opportunity_id"), table_name="opportunity_spec_values")
    op.drop_table("opportunity_spec_values")
    op.drop_index(op.f("ix_counterparty_capabilities_product_id"), table_name="counterparty_capabilities")
    op.drop_index(op.f("ix_counterparty_capabilities_counterparty_id"), table_name="counterparty_capabilities")
    op.drop_index(op.f("ix_counterparty_capabilities_capability_type"), table_name="counterparty_capabilities")
    op.drop_table("counterparty_capabilities")
