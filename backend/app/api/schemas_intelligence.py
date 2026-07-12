from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas_products import SpecParameterCreate


class OpportunitySpecValueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    opportunity_id: UUID
    parameter_name: str
    unit: str | None
    value_text: str | None
    value_min: Decimal | None
    value_max: Decimal | None
    status: str
    source_id: UUID | None
    evidence_excerpt: str | None
    user_confirmed: bool
    is_mandatory: bool
    created_at: datetime
    updated_at: datetime


class ProductResolutionRequest(BaseModel):
    rough_product_name: str = Field(min_length=1, max_length=255)
    source_id: UUID | None = None
    source_text: str | None = None
    create_if_missing: bool = True


class ProposedProductResponse(BaseModel):
    normalized_name: str
    category: str
    aliases: list[str]
    typical_units: list[str]
    parameters: list[SpecParameterCreate]
    reasoning: str | None = None


class ProductResolutionResponse(BaseModel):
    opportunity_id: UUID
    normalized_product_id: UUID | None
    normalized_product_name: str | None
    rough_product_name: str
    matched: bool
    product_created: bool = False
    proposed_new_product: ProposedProductResponse | None = None
    catalog_products: list[str]
    confidence: float
    reasoning: str | None
    missing_mandatory: list[str]
    spec_values: list[OpportunitySpecValueResponse]
    ai_model: str
    ai_cost_usd: str


class CounterpartyCapabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    counterparty_id: UUID
    capability_type: str
    product_id: UUID | None
    title: str
    rough_product_name: str | None
    regions: list | None
    routes: list | None
    incoterms: list | None
    notes: str | None
    confirmation_level: str
    evidence_excerpt: str | None
    user_confirmed: bool
    extracted_by_ai: bool
    created_at: datetime
    updated_at: datetime


class ContactHintResponse(BaseModel):
    full_name: str | None = None
    role_title: str | None = None
    email: str | None = None
    department: str | None = None
    evidence_excerpt: str | None = None


class CounterpartyEnrichmentRequest(BaseModel):
    source_text: str | None = None


class CounterpartyEnrichmentResponse(BaseModel):
    summary: str | None
    capabilities: list[CounterpartyCapabilityResponse]
    contact_hints: list[ContactHintResponse]
    missing_fields: list[str]
    ai_model: str
    ai_cost_usd: str
