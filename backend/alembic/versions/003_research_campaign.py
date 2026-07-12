"""research campaign tables

Revision ID: 003
Revises: 002
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("product_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("target_buy_regions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("target_sell_regions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("quantity_range", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("preferred_incoterms", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("excluded_regions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("research_hypothesis", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("viability_status", sa.String(length=32), nullable=False),
        sa.Column("viability_report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_opportunity_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("search_budget", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("ai_budget", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_research_campaigns_owner_id"), "research_campaigns", ["owner_id"], unique=False)

    op.create_table(
        "research_leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("organization_name", sa.String(length=512), nullable=True),
        sa.Column("region", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("relevance_score", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["research_campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_research_leads_campaign_id"), "research_leads", ["campaign_id"], unique=False)

    op.create_table(
        "outreach_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_lead_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("outreach_type", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["research_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_lead_id"], ["research_leads.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_outreach_drafts_campaign_id"), "outreach_drafts", ["campaign_id"], unique=False)

    op.create_table(
        "commercial_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("field_path", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("confirmation_level", sa.String(length=32), nullable=False),
        sa.Column("evidence_excerpt", sa.Text(), nullable=True),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["research_campaign_id"], ["research_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_commercial_facts_research_campaign_id"),
        "commercial_facts",
        ["research_campaign_id"],
        unique=False,
    )

    op.add_column(
        "sources",
        sa.Column("research_campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_sources_research_campaign_id",
        "sources",
        "research_campaigns",
        ["research_campaign_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_sources_research_campaign_id"), "sources", ["research_campaign_id"], unique=False)

    op.create_foreign_key(
        "fk_ai_usage_logs_research_campaign_id",
        "ai_usage_logs",
        "research_campaigns",
        ["research_campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_ai_usage_logs_research_campaign_id", "ai_usage_logs", type_="foreignkey")
    op.drop_index(op.f("ix_sources_research_campaign_id"), table_name="sources")
    op.drop_constraint("fk_sources_research_campaign_id", "sources", type_="foreignkey")
    op.drop_column("sources", "research_campaign_id")
    op.drop_table("commercial_facts")
    op.drop_table("outreach_drafts")
    op.drop_table("research_leads")
    op.drop_table("research_campaigns")
