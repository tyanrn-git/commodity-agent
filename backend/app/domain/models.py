import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Atlantic/Madeira")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="user")
    opportunities: Mapped[list["Opportunity"]] = relationship(
        back_populates="owner", foreign_keys="Opportunity.owner_id"
    )
    deals: Mapped[list["Deal"]] = relationship(back_populates="owner")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="actor")
    ai_budget_settings: Mapped["AIBudgetSettings | None"] = relationship(
        back_populates="user", uselist=False
    )
    research_campaigns: Mapped[list["ResearchCampaign"]] = relationship(back_populates="owner")
    counterparties: Mapped[list["Counterparty"]] = relationship(
        back_populates="owner", foreign_keys="Counterparty.owner_id"
    )
    company_settings: Mapped["CompanySettings | None"] = relationship(
        back_populates="user", uselist=False
    )
    monitoring_rules: Mapped[list["MonitoringRule"]] = relationship(back_populates="owner")
    internet_sources: Mapped[list["InternetSource"]] = relationship(back_populates="owner")
    internet_source_search_runs: Mapped[list["InternetSourceSearchRun"]] = relationship(back_populates="owner")
    automation_settings: Mapped["AutomationSettings | None"] = relationship(
        back_populates="user", uselist=False
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="sessions")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    actor: Mapped["User | None"] = relationship(back_populates="audit_logs")


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False, default="base_oil")
    aliases: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    hs_codes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    typical_units: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    dangerous_goods_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    specification_profiles: Mapped[list["ProductSpecificationProfile"]] = relationship(
        back_populates="product"
    )
    opportunities: Mapped[list["Opportunity"]] = relationship(back_populates="product")
    requirements: Mapped[list["Requirement"]] = relationship(back_populates="product")


class ProductSpecificationProfile(Base, TimestampMixin):
    __tablename__ = "product_specification_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    parameter_name: Mapped[str] = mapped_column(String(128), nullable=False)
    aliases: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False, default="decimal")
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    minimum_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    maximum_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parameter_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="VARIANT")
    variation_materiality: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_count: Mapped[int] = mapped_column(nullable=False, default=0)

    product: Mapped["Product"] = relationship(back_populates="specification_profiles")


class Opportunity(Base, TimestampMixin):
    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    buyer_or_supplier_hint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    quantity_min: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    quantity_max: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    origin_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quote_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    indicative_economics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    owner: Mapped["User"] = relationship(back_populates="opportunities", foreign_keys=[owner_id])
    status_changer: Mapped["User | None"] = relationship(foreign_keys=[status_changed_by_id])
    product: Mapped["Product | None"] = relationship(back_populates="opportunities")
    sources: Mapped[list["Source"]] = relationship(back_populates="opportunity")
    deal: Mapped["Deal | None"] = relationship(back_populates="origin_opportunity", uselist=False)
    tasks: Mapped[list["Task"]] = relationship(back_populates="opportunity")
    supplier_lead_context: Mapped["SupplierLeadContext | None"] = relationship(
        back_populates="opportunity", uselist=False
    )
    supplier_lead_matches: Mapped[list["SupplierLeadMatch"]] = relationship(
        back_populates="supplier_opportunity",
        foreign_keys="SupplierLeadMatch.supplier_opportunity_id",
    )
    spec_values: Mapped[list["OpportunitySpecValue"]] = relationship(back_populates="opportunity")
    status_events: Mapped[list["OpportunityStatusEvent"]] = relationship(back_populates="opportunity")
    agent_tasks: Mapped[list["AgentTask"]] = relationship(back_populates="opportunity")


class OpportunityStatusEvent(Base, TimestampMixin):
    __tablename__ = "opportunity_status_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status_code: Mapped[str] = mapped_column(String(32), nullable=False)
    status_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="OPPORTUNITY")
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="USER")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="status_events")
    changed_by: Mapped["User | None"] = relationship(foreign_keys=[changed_by_id])


class ResearchCampaign(Base, TimestampMixin):
    __tablename__ = "research_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    product_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    target_buy_regions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    target_sell_regions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    quantity_range: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    preferred_incoterms: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    excluded_regions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    research_hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    viability_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    viability_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_opportunity_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    search_budget: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    ai_budget: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped["User"] = relationship(back_populates="research_campaigns")
    leads: Mapped[list["ResearchLead"]] = relationship(back_populates="campaign")
    outreach_drafts: Mapped[list["OutreachDraft"]] = relationship(back_populates="campaign")
    commercial_facts: Mapped[list["CommercialFact"]] = relationship(back_populates="campaign")
    sources: Mapped[list["Source"]] = relationship(back_populates="research_campaign")


class ResearchLead(Base, TimestampMixin):
    __tablename__ = "research_leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    organization_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lead_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    campaign: Mapped["ResearchCampaign"] = relationship(back_populates="leads")
    outreach_drafts: Mapped[list["OutreachDraft"]] = relationship(back_populates="target_lead")


class OutreachDraft(Base, TimestampMixin):
    __tablename__ = "outreach_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_leads.id", ondelete="SET NULL"), nullable=True
    )
    outreach_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    campaign: Mapped["ResearchCampaign"] = relationship(back_populates="outreach_drafts")
    target_lead: Mapped["ResearchLead | None"] = relationship(back_populates="outreach_drafts")


class CommercialFact(Base):
    __tablename__ = "commercial_facts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_campaigns.id", ondelete="CASCADE"), nullable=True, index=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    field_path: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    confirmation_level: Mapped[str] = mapped_column(String(32), nullable=False, default="ESTIMATE")
    evidence_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    campaign: Mapped["ResearchCampaign | None"] = relationship(back_populates="commercial_facts")


class Deal(Base, TimestampMixin):
    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    origin_opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opportunities.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="QUALIFICATION")
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    risk_flags: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    owner: Mapped["User"] = relationship(back_populates="deals")
    origin_opportunity: Mapped["Opportunity"] = relationship(back_populates="deal")
    requirements: Mapped[list["Requirement"]] = relationship(back_populates="deal")
    deal_parties: Mapped[list["DealParty"]] = relationship(back_populates="deal")
    rfqs: Mapped[list["RFQ"]] = relationship(back_populates="deal")
    communication_threads: Mapped[list["CommunicationThread"]] = relationship(back_populates="deal")
    supply_offers: Mapped[list["SupplyOffer"]] = relationship(back_populates="deal")
    fulfilment_configurations: Mapped[list["FulfilmentConfiguration"]] = relationship(
        back_populates="deal"
    )
    offers: Mapped[list["Offer"]] = relationship(back_populates="deal")


class Requirement(Base, TimestampMixin):
    __tablename__ = "requirements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    quantity_min: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    quantity_max: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_incoterm: Mapped[str | None] = mapped_column(String(16), nullable=True)
    packaging: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commercial_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    deal: Mapped["Deal"] = relationship(back_populates="requirements")
    product: Mapped["Product | None"] = relationship(back_populates="requirements")
    evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="requirement")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    research_campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_campaigns.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    file_size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    opportunity: Mapped["Opportunity | None"] = relationship(back_populates="sources")
    research_campaign: Mapped["ResearchCampaign | None"] = relationship(back_populates="sources")
    evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="source")
    extractions: Mapped[list["ExtractionResult"]] = relationship(back_populates="source")


class AIBudgetSettings(Base, TimestampMixin):
    __tablename__ = "ai_budget_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    monthly_budget_usd: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=100)
    first_warning_percent: Mapped[int] = mapped_column(nullable=False, default=75)
    second_warning_percent: Mapped[int] = mapped_column(nullable=False, default=90)
    hard_limit_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    budget_reset_day: Mapped[int] = mapped_column(nullable=False, default=1)
    preferred_default_model: Mapped[str] = mapped_column(String(128), nullable=False)
    fallback_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="ai_budget_settings")


class AIUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    research_campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    input_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class ExtractionResult(Base, TimestampMixin):
    __tablename__ = "extraction_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    operation: Mapped[str] = mapped_column(String(64), nullable=False, default="opportunity_extraction")
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validation_errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    missing_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0)

    source: Mapped["Source"] = relationship(back_populates="extractions")


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=True, index=True
    )
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    related_entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    opportunity: Mapped["Opportunity | None"] = relationship(back_populates="tasks")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    field_path: Mapped[str] = mapped_column(String(255), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    requirement: Mapped["Requirement"] = relationship(back_populates="evidence_items")
    source: Mapped["Source | None"] = relationship(back_populates="evidence_items")


class CompanySettings(Base, TimestampMixin):
    __tablename__ = "company_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    legal_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    trade_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_rfq_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    email_signature_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_signature_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user: Mapped["User"] = relationship(back_populates="company_settings")


class Counterparty(Base, TimestampMixin):
    __tablename__ = "counterparties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    legal_name: Mapped[str] = mapped_column(String(512), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    organization_type: Mapped[str] = mapped_column(String(32), nullable=False, default="OTHER")
    incorporation_country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    operating_countries: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    primary_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="DISCOVERED")
    compliance_review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_REVIEWED")
    compliance_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    compliance_reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    risk_flags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    domain_verification_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    owner: Mapped["User"] = relationship(
        back_populates="counterparties", foreign_keys=[owner_id]
    )
    compliance_reviewer: Mapped["User | None"] = relationship(foreign_keys=[compliance_reviewed_by_id])
    contacts: Mapped[list["Contact"]] = relationship(back_populates="counterparty")
    deal_parties: Mapped[list["DealParty"]] = relationship(back_populates="counterparty")
    capabilities: Mapped[list["CounterpartyCapability"]] = relationship(back_populates="counterparty")


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    counterparty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="DISCOVERED")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    counterparty: Mapped["Counterparty"] = relationship(back_populates="contacts")


class CounterpartyCapability(Base, TimestampMixin):
    __tablename__ = "counterparty_capabilities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    counterparty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capability_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    rough_product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    regions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    routes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    incoterms: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmation_level: Mapped[str] = mapped_column(String(32), nullable=False, default="ESTIMATE")
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    evidence_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    extracted_by_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    counterparty: Mapped["Counterparty"] = relationship(back_populates="capabilities")
    product: Mapped["Product | None"] = relationship()
    source: Mapped["Source | None"] = relationship()


class OpportunitySpecValue(Base, TimestampMixin):
    __tablename__ = "opportunity_spec_values"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parameter_name: Mapped[str] = mapped_column(String(128), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    value_min: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    value_max: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="MISSING")
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    evidence_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="spec_values")
    source: Mapped["Source | None"] = relationship()


class DealParty(Base, TimestampMixin):
    __tablename__ = "deal_parties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    counterparty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparties.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    confidentiality_level: Mapped[str] = mapped_column(String(32), nullable=False, default="STANDARD")
    disclosure_status: Mapped[str] = mapped_column(String(32), nullable=False, default="HIDDEN")
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="DISCOVERED")
    selected_for_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    selected_for_configuration: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    deal: Mapped["Deal"] = relationship(back_populates="deal_parties")
    counterparty: Mapped["Counterparty"] = relationship(back_populates="deal_parties")
    rfqs: Mapped[list["RFQ"]] = relationship(back_populates="target_deal_party")


class RFQTemplate(Base, TimestampMixin):
    __tablename__ = "rfq_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rfq_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    subject_template: Mapped[str] = mapped_column(String(512), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    default_requested_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class RFQ(Base, TimestampMixin):
    __tablename__ = "rfqs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_deal_party_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deal_parties.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfq_templates.id", ondelete="SET NULL"), nullable=True
    )
    rfq_type: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    subject: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)
    response_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )

    deal: Mapped["Deal"] = relationship(back_populates="rfqs")
    target_deal_party: Mapped["DealParty"] = relationship(back_populates="rfqs")
    contact: Mapped["Contact | None"] = relationship()
    template: Mapped["RFQTemplate | None"] = relationship()
    approvals: Mapped[list["ApprovalRequest"]] = relationship(back_populates="rfq")
    source_message: Mapped["Message | None"] = relationship(foreign_keys=[source_message_id])
    communication_threads: Mapped[list["CommunicationThread"]] = relationship(back_populates="rfq")


class ApprovalRequest(Base, TimestampMixin):
    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rfq_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfqs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    offer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    proposed_action: Mapped[str] = mapped_column(String(64), nullable=False, default="SEND_RFQ")
    exact_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    recipients: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    disclosed_information: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    binding_class: Mapped[str] = mapped_column(String(32), nullable=False, default="REQUEST")
    risk_flags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    compliance_warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)
    approved_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    rfq: Mapped["RFQ | None"] = relationship(back_populates="approvals")
    offer: Mapped["Offer | None"] = relationship(back_populates="approvals")


class MailboxConnection(Base, TimestampMixin):
    __tablename__ = "mailbox_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="MOCK")
    email_address: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_cursor: Mapped[str | None] = mapped_column(String(255), nullable=True)


class CommunicationThread(Base, TimestampMixin):
    __tablename__ = "communication_threads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=True, index=True
    )
    deal_party_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deal_parties.id", ondelete="SET NULL"), nullable=True
    )
    rfq_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfqs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    mailbox_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped["User"] = relationship()
    deal: Mapped["Deal | None"] = relationship(back_populates="communication_threads")
    rfq: Mapped["RFQ | None"] = relationship(back_populates="communication_threads")
    messages: Mapped[list["Message"]] = relationship(back_populates="thread")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("communication_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rfq_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfqs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    link_status: Mapped[str] = mapped_column(String(16), nullable=False, default="UNLINKED", index=True)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    from_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_addresses: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    binding_class: Mapped[str] = mapped_column(String(32), nullable=False, default="INFORMATIONAL")
    mailbox_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    thread: Mapped["CommunicationThread"] = relationship(back_populates="messages")
    rfq: Mapped["RFQ | None"] = relationship(foreign_keys=[rfq_id])
    source: Mapped["Source | None"] = relationship()


class SupplyOffer(Base, TimestampMixin):
    __tablename__ = "supply_offers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rfq_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfqs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    supplier_counterparty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparties.id", ondelete="SET NULL"), nullable=True
    )
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    available_quantity: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String(16), nullable=True)
    origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    loading_point: Mapped[str | None] = mapped_column(String(255), nullable=True)
    offer_valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_terms: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extracted_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    missing_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="EXTRACTED")
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    deal: Mapped["Deal"] = relationship(back_populates="supply_offers")
    rfq: Mapped["RFQ | None"] = relationship()
    supplier: Mapped["Counterparty | None"] = relationship()
    source_message: Mapped["Message | None"] = relationship()
    shipment_lots: Mapped[list["ShipmentLot"]] = relationship(back_populates="supply_offer")


class FulfilmentConfiguration(Base, TimestampMixin):
    __tablename__ = "fulfilment_configurations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_quantity: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_quantity_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stale_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stale_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    sales_price_per_unit: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    sales_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    revenue: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    total_cost: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    gross_margin: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    gross_margin_percent: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    cost_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fx_rates_used: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    spec_match_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    completeness_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    last_calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    deal: Mapped["Deal"] = relationship(back_populates="fulfilment_configurations")
    shipment_lots: Mapped[list["ShipmentLot"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan"
    )
    transport_legs: Mapped[list["TransportLeg"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan"
    )
    service_quotes: Mapped[list["ServiceQuote"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan"
    )
    economics_snapshots: Mapped[list["EconomicsSnapshot"]] = relationship(
        back_populates="configuration", cascade="all, delete-orphan"
    )
    offers: Mapped[list["Offer"]] = relationship(back_populates="configuration")


class Offer(Base, TimestampMixin):
    __tablename__ = "offers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    configuration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fulfilment_configurations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    target_deal_party_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deal_parties.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subject: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT", index=True)
    configuration_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    economics_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    disclosure_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validity_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )

    deal: Mapped["Deal"] = relationship(back_populates="offers")
    configuration: Mapped["FulfilmentConfiguration"] = relationship(back_populates="offers")
    target_deal_party: Mapped["DealParty"] = relationship()
    source_message: Mapped["Message | None"] = relationship(foreign_keys=[source_message_id])
    approvals: Mapped[list["ApprovalRequest"]] = relationship(back_populates="offer")


class ShipmentLot(Base, TimestampMixin):
    __tablename__ = "shipment_lots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    configuration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fulfilment_configurations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supply_offer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supply_offers.id", ondelete="SET NULL"), nullable=True
    )
    supplier_counterparty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparties.id", ondelete="SET NULL"), nullable=True
    )
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    purchase_price_per_unit: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String(16), nullable=True)
    origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    packaging: Mapped[str | None] = mapped_column(String(255), nullable=True)
    allocation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PLANNED")

    configuration: Mapped["FulfilmentConfiguration"] = relationship(back_populates="shipment_lots")
    supply_offer: Mapped["SupplyOffer | None"] = relationship(back_populates="shipment_lots")
    supplier: Mapped["Counterparty | None"] = relationship()


class TransportLeg(Base, TimestampMixin):
    __tablename__ = "transport_legs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    configuration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fulfilment_configurations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(nullable=False, default=1)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="SEA")
    origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True)
    carrier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    equipment: Mapped[str | None] = mapped_column(String(128), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cost: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    risk_transfer_point: Mapped[str | None] = mapped_column(String(255), nullable=True)
    leg_incoterm: Mapped[str | None] = mapped_column(String(16), nullable=True)
    service_quote_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_quotes.id", ondelete="SET NULL"), nullable=True
    )

    configuration: Mapped["FulfilmentConfiguration"] = relationship(back_populates="transport_legs")
    service_quote: Mapped["ServiceQuote | None"] = relationship(back_populates="transport_legs")


class ServiceQuote(Base, TimestampMixin):
    __tablename__ = "service_quotes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    configuration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fulfilment_configurations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    quote_type: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    validity_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    configuration: Mapped["FulfilmentConfiguration | None"] = relationship(back_populates="service_quotes")
    transport_legs: Mapped[list["TransportLeg"]] = relationship(back_populates="service_quote")


class EconomicsSnapshot(Base):
    __tablename__ = "economics_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    configuration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fulfilment_configurations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    snapshot_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    configuration: Mapped["FulfilmentConfiguration"] = relationship(back_populates="economics_snapshots")


class MonitoringRule(Base, TimestampMixin):
    __tablename__ = "monitoring_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(32), nullable=False, default="MOCK")
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    poll_interval_hours: Mapped[int] = mapped_column(nullable=False, default=24)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    access_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="PUBLIC")
    connector_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    health_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    health_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped["User"] = relationship(back_populates="monitoring_rules")
    runs: Mapped[list["MonitoringRun"]] = relationship(back_populates="rule")
    publications: Mapped[list["MonitoredPublication"]] = relationship(back_populates="rule")


class MonitoringRun(Base, TimestampMixin):
    __tablename__ = "monitoring_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitoring_rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitoring_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RUNNING", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items_found: Mapped[int] = mapped_column(nullable=False, default=0)
    items_new: Mapped[int] = mapped_column(nullable=False, default=0)
    opportunities_created: Mapped[int] = mapped_column(nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")

    rule: Mapped["MonitoringRule"] = relationship(back_populates="runs")


class MonitoredPublication(Base, TimestampMixin):
    __tablename__ = "monitored_publications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    monitoring_rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitoring_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_snapshot_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SEEN", index=True)
    extracted_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True, index=True
    )

    rule: Mapped["MonitoringRule"] = relationship(back_populates="publications")
    opportunity: Mapped["Opportunity | None"] = relationship()


class InternetSource(Base, TimestampMixin):
    __tablename__ = "internet_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="TENDER_PORTAL")
    access_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="PUBLIC")
    regions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    product_tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    languages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_hints: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(nullable=False, default=50)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetch_strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="HTML")
    fetch_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    owner: Mapped["User | None"] = relationship(back_populates="internet_sources")
    search_hits: Mapped[list["InternetSourceSearchHit"]] = relationship(back_populates="source")


class InternetSourceSearchRun(Base, TimestampMixin):
    __tablename__ = "internet_source_search_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    regions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    search_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    access_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    catalog_specs_added: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RUNNING", index=True)
    sources_matched: Mapped[int] = mapped_column(nullable=False, default=0)
    sources_scanned: Mapped[int] = mapped_column(nullable=False, default=0)
    hits_found: Mapped[int] = mapped_column(nullable=False, default=0)
    hits_new: Mapped[int] = mapped_column(nullable=False, default=0)
    opportunities_created: Mapped[int] = mapped_column(nullable=False, default=0)
    ai_calls: Mapped[int] = mapped_column(nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped["User"] = relationship(back_populates="internet_source_search_runs")
    product: Mapped["Product | None"] = relationship()
    hits: Mapped[list["InternetSourceSearchHit"]] = relationship(back_populates="search_run")


class InternetSourceSearchHit(Base, TimestampMixin):
    __tablename__ = "internet_source_search_hits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("internet_source_search_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    internet_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("internet_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="FOUND", index=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    evidence_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetch_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    extracted_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True, index=True
    )

    search_run: Mapped["InternetSourceSearchRun"] = relationship(back_populates="hits")
    source: Mapped["InternetSource"] = relationship(back_populates="search_hits")
    opportunity: Mapped["Opportunity | None"] = relationship()


class SupplierLeadContext(Base, TimestampMixin):
    __tablename__ = "supplier_lead_contexts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    supply_offer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("supply_offers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    unit_price: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    incoterm: Mapped[str | None] = mapped_column(String(16), nullable=True)
    origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    supplier_hint: Mapped[str | None] = mapped_column(String(512), nullable=True)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="supplier_lead_context")
    supply_offer: Mapped["SupplyOffer | None"] = relationship()


class SupplierLeadMatch(Base, TimestampMixin):
    __tablename__ = "supplier_lead_matches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_type: Mapped[str] = mapped_column(String(32), nullable=False)
    matched_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    matched_deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    matched_requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requirements.id", ondelete="SET NULL"), nullable=True, index=True
    )
    score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    match_summary: Mapped[str] = mapped_column(String(512), nullable=False)
    match_reasons: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    route_proposal: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    market_comparison: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    outreach_subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    outreach_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="SUGGESTED")

    supplier_opportunity: Mapped["Opportunity"] = relationship(
        back_populates="supplier_lead_matches",
        foreign_keys=[supplier_opportunity_id],
    )
    matched_opportunity: Mapped["Opportunity | None"] = relationship(
        foreign_keys=[matched_opportunity_id],
    )
    matched_deal: Mapped["Deal | None"] = relationship()
    matched_requirement: Mapped["Requirement | None"] = relationship()


class AutomationSettings(Base, TimestampMixin):
    __tablename__ = "automation_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    auto_follow_up_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    follow_up_after_days: Mapped[int] = mapped_column(nullable=False, default=3)
    max_follow_ups_per_rfq: Mapped[int] = mapped_column(nullable=False, default=2)
    min_days_between_follow_ups: Mapped[int] = mapped_column(nullable=False, default=3)
    max_auto_actions_per_day: Mapped[int] = mapped_column(nullable=False, default=10)

    user: Mapped["User"] = relationship(back_populates="automation_settings")


class AutomationRun(Base, TimestampMixin):
    __tablename__ = "automation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RUNNING", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actions_evaluated: Mapped[int] = mapped_column(nullable=False, default=0)
    actions_sent: Mapped[int] = mapped_column(nullable=False, default=0)
    actions_blocked: Mapped[int] = mapped_column(nullable=False, default=0)
    actions_skipped: Mapped[int] = mapped_column(nullable=False, default=0)
    actions_rate_limited: Mapped[int] = mapped_column(nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner: Mapped["User"] = relationship()
    action_logs: Mapped[list["AutomatedActionLog"]] = relationship(back_populates="run")


class AutomatedActionLog(Base):
    __tablename__ = "automated_action_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    automation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("automation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    action_category: Mapped[str] = mapped_column(String(32), nullable=False)
    binding_class: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    owner: Mapped["User"] = relationship()
    run: Mapped["AutomationRun"] = relationship(back_populates="action_logs")
    message: Mapped["Message | None"] = relationship()


class AgentTask(Base, TimestampMixin):
    __tablename__ = "agent_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=True, index=True
    )
    research_campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_campaigns.id", ondelete="CASCADE"), nullable=True, index=True
    )
    internet_source_search_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("internet_source_search_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    internet_source_search_hit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("internet_source_search_hits.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    priority: Mapped[int] = mapped_column(nullable=False, default=50)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    opportunity: Mapped["Opportunity | None"] = relationship(back_populates="agent_tasks")
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])
    runs: Mapped[list["AgentRun"]] = relationship(back_populates="agent_task")


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    toolset_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    estimated_cost: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    actual_cost: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    ai_usage_log_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RUNNING", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent_task: Mapped["AgentTask"] = relationship(back_populates="runs")
    results: Mapped[list["AgentResult"]] = relationship(back_populates="agent_run")


class AgentResult(Base, TimestampMixin):
    __tablename__ = "agent_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    result_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    structured_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    requires_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    agent_run: Mapped["AgentRun"] = relationship(back_populates="results")
    applied_by: Mapped["User | None"] = relationship(foreign_keys=[applied_by_id])
