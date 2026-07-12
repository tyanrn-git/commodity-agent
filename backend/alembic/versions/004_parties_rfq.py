"""parties and rfq tables

Revision ID: 004
Revises: 003
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_name", sa.String(length=512), nullable=True),
        sa.Column("trade_name", sa.String(length=512), nullable=True),
        sa.Column("brand_name", sa.String(length=255), nullable=True),
        sa.Column("registration_number", sa.String(length=128), nullable=True),
        sa.Column("tax_id", sa.String(length=128), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("default_rfq_language", sa.String(length=8), nullable=False),
        sa.Column("email_signature_text", sa.Text(), nullable=True),
        sa.Column("email_signature_html", sa.Text(), nullable=True),
        sa.Column("bank_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "counterparties",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_name", sa.String(length=512), nullable=False),
        sa.Column("trade_name", sa.String(length=512), nullable=True),
        sa.Column("organization_type", sa.String(length=32), nullable=False),
        sa.Column("incorporation_country", sa.String(length=128), nullable=True),
        sa.Column("operating_countries", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("registration_number", sa.String(length=128), nullable=True),
        sa.Column("tax_id", sa.String(length=128), nullable=True),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("primary_domain", sa.String(length=255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("compliance_review_status", sa.String(length=32), nullable=False),
        sa.Column("compliance_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("compliance_reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("risk_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("domain_verification_report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["compliance_reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_counterparties_owner_id"), "counterparties", ["owner_id"], unique=False)

    op.create_table(
        "rfq_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("rfq_type", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("subject_template", sa.String(length=512), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("default_requested_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rfq_templates_rfq_type"), "rfq_templates", ["rfq_type"], unique=False)

    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("counterparty_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("role_title", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("preferred_language", sa.String(length=8), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["counterparty_id"], ["counterparties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contacts_counterparty_id"), "contacts", ["counterparty_id"], unique=False)
    op.create_index(op.f("ix_contacts_email"), "contacts", ["email"], unique=False)

    op.create_table(
        "deal_parties",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("counterparty_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("confidentiality_level", sa.String(length=32), nullable=False),
        sa.Column("disclosure_status", sa.String(length=32), nullable=False),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("selected_for_contact", sa.Boolean(), nullable=False),
        sa.Column("selected_for_configuration", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["counterparty_id"], ["counterparties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deal_id", "counterparty_id", "role", name="uq_deal_parties_deal_counterparty_role"),
    )
    op.create_index(op.f("ix_deal_parties_deal_id"), "deal_parties", ["deal_id"], unique=False)
    op.create_index(op.f("ix_deal_parties_counterparty_id"), "deal_parties", ["counterparty_id"], unique=False)

    op.create_table(
        "rfqs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_deal_party_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rfq_type", sa.String(length=32), nullable=False),
        sa.Column("requested_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("response_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_deal_party_id"], ["deal_parties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_id"], ["rfq_templates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rfqs_deal_id"), "rfqs", ["deal_id"], unique=False)
    op.create_index(op.f("ix_rfqs_status"), "rfqs", ["status"], unique=False)
    op.create_index(op.f("ix_rfqs_target_deal_party_id"), "rfqs", ["target_deal_party_id"], unique=False)

    op.create_table(
        "approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rfq_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposed_action", sa.String(length=64), nullable=False),
        sa.Column("exact_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recipients", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("disclosed_information", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("binding_class", sa.String(length=32), nullable=False),
        sa.Column("risk_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("compliance_warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_status", sa.String(length=32), nullable=False),
        sa.Column("approved_snapshot_hash", sa.String(length=64), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rfq_id"], ["rfqs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_approval_requests_rfq_id"), "approval_requests", ["rfq_id"], unique=False)
    op.create_index(op.f("ix_approval_requests_approval_status"), "approval_requests", ["approval_status"], unique=False)


def downgrade() -> None:
    op.drop_table("approval_requests")
    op.drop_table("rfqs")
    op.drop_table("deal_parties")
    op.drop_table("contacts")
    op.drop_table("rfq_templates")
    op.drop_table("counterparties")
    op.drop_table("company_settings")
