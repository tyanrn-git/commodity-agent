from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResearchCampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    product_ids: list[UUID]
    target_buy_regions: list[str] | None = None
    target_sell_regions: list[str] | None = None
    quantity_range: dict | None = None
    preferred_incoterms: list[str] | None = None
    excluded_regions: list[str] | None = None
    research_hypothesis: str | None = None


class ResearchCampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    product_ids: list
    target_buy_regions: list | None
    target_sell_regions: list | None
    quantity_range: dict | None
    preferred_incoterms: list | None
    excluded_regions: list | None
    research_hypothesis: str | None
    status: str
    viability_status: str
    viability_report: dict | None
    created_opportunity_ids: list | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ResearchLeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    lead_type: str
    title: str
    organization_name: str | None
    region: str | None
    country: str | None
    url: str | None
    notes: str | None
    relevance_score: Decimal | None
    source_type: str | None
    lead_metadata: dict | None = None


class OutreachDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    target_lead_id: UUID | None
    outreach_type: str
    subject: str
    body: str
    language: str
    status: str
    sent_at: datetime | None
    created_at: datetime


class CommercialFactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    research_campaign_id: UUID | None
    opportunity_id: UUID | None
    source_id: UUID | None
    entity_type: str
    field_path: str
    value: str
    unit: str | None
    currency: str | None
    confirmation_level: str
    evidence_excerpt: str | None
    user_confirmed: bool
    created_at: datetime


class CreateOpportunityFromCampaignRequest(BaseModel):
    lead_id: UUID | None = None
    opportunity_type: str = "BUYER_NEED"
