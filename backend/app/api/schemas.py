from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    timezone: str
    is_active: bool


class LoginRequest(BaseModel):
    email: str
    password: str


class UpdateProfileRequest(BaseModel):
    timezone: str | None = None


class OpportunityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    raw_product_name: str | None = None
    normalized_product_id: UUID | None = None
    buyer_or_supplier_hint: str | None = None
    quantity_min: Decimal | None = None
    quantity_max: Decimal | None = None
    quantity_unit: str | None = None
    origin_hint: str | None = None
    destination_hint: str | None = None
    deadline: datetime | None = None
    quote_deadline: datetime | None = None
    delivery_deadline: datetime | None = None
    notes: str | None = None


class OpportunityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    raw_product_name: str | None = None
    normalized_product_id: UUID | None = None
    buyer_or_supplier_hint: str | None = None
    quantity_min: Decimal | None = None
    quantity_max: Decimal | None = None
    quantity_unit: str | None = None
    origin_hint: str | None = None
    destination_hint: str | None = None
    deadline: datetime | None = None
    quote_deadline: datetime | None = None
    delivery_deadline: datetime | None = None
    status: str | None = None
    status_note: str | None = None
    notes: str | None = None


class OpportunityStatusTransition(BaseModel):
    status: str
    note: str | None = None


class OpportunityDisplayStatus(BaseModel):
    code: str
    label: str
    kind: str
    changed_at: datetime | None = None


class OpportunityStatusEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    opportunity_id: UUID
    status_code: str
    status_kind: str
    changed_at: datetime
    changed_by_id: UUID | None
    actor_type: str
    note: str | None
    created_at: datetime
    updated_at: datetime


class OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    title: str
    status: str
    raw_product_name: str | None
    normalized_product_id: UUID | None
    buyer_or_supplier_hint: str | None
    quantity_min: Decimal | None
    quantity_max: Decimal | None
    quantity_unit: str | None
    origin_hint: str | None
    destination_hint: str | None
    deadline: datetime | None
    quote_deadline: datetime | None = None
    delivery_deadline: datetime | None = None
    status_changed_at: datetime | None = None
    status_note: str | None = None
    notes: str | None
    source_url: str | None = None
    created_at: datetime
    updated_at: datetime


class OpportunityCommercialRow(BaseModel):
    buyer_name: str | None = None
    seller_name: str | None = None
    product_name: str | None = None
    volume: str | None = None
    buy_price_per_unit: float | None = None
    buy_currency: str | None = None
    buy_incoterm: str | None = None
    buy_basis: str | None = None
    sell_price_per_unit: float | None = None
    sell_currency: str | None = None
    sell_incoterm: str | None = None
    sell_basis: str | None = None
    transport_cost: float | None = None
    other_costs: float | None = None
    costs_currency: str | None = None
    gross_margin: float | None = None
    gross_margin_percent: float | None = None
    margin_currency: str | None = None
    data_completeness: str = "EMPTY"
    source: str | None = None


class OpportunityBoardDocument(BaseModel):
    id: UUID
    source_type: str
    label: str
    source_url: str | None = None


class OpportunityBoardItem(OpportunityResponse):
    type_label: str
    normalized_product_name: str | None = None
    commercial_summary: str
    commercial_row: OpportunityCommercialRow
    display_status: OpportunityDisplayStatus
    description: str | None = None
    origin_kind: str
    origin_label: str
    origin_explanation: str | None = None
    deal_id: UUID | None = None
    deal_number: str | None = None
    economics_preview: str | None = None
    monitoring_rule_name: str | None = None
    monitoring_publication_id: UUID | None = None
    sources_count: int = 0
    documents: list[OpportunityBoardDocument] = Field(default_factory=list)
    internet_source_name: str | None = None


class SkippedMonitoringItem(BaseModel):
    id: UUID
    monitoring_rule_id: UUID
    monitoring_rule_name: str | None
    title: str
    product: str | None = None
    destination: str | None = None
    buyer: str | None = None
    quantity: float | None = None
    quantity_unit: str | None = None
    first_seen_at: datetime
    filter_explanation: str | None = None


class OpportunityBoardResponse(BaseModel):
    opportunities: list[OpportunityBoardItem]
    skipped_monitoring: list[SkippedMonitoringItem]


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    opportunity_id: UUID | None
    source_type: str
    source_url: str | None = None
    original_filename: str | None
    mime_type: str | None
    storage_key: str
    file_size_bytes: int | None
    is_immutable: bool
    created_at: datetime


class DealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deal_number: str
    title: str
    origin_opportunity_id: UUID
    direction: str
    base_currency: str
    stage: str
    outcome: str
    deadline: datetime | None
    created_at: datetime
    updated_at: datetime


class EvidenceInput(BaseModel):
    source_id: UUID | None = None
    field_path: str
    excerpt: str | None = None
    page_number: int | None = None
    user_confirmed: bool = False


class RequirementCreate(BaseModel):
    product_id: UUID | None = None
    quantity_min: Decimal | None = None
    quantity_max: Decimal | None = None
    quantity_unit: str | None = None
    destination: str | None = None
    requested_incoterm: str | None = None
    packaging: str | None = None
    commercial_deadline: datetime | None = None
    user_confirmed: bool = False
    evidence: list[EvidenceInput] = Field(default_factory=list)


class RequirementUpdate(BaseModel):
    product_id: UUID | None = None
    quantity_min: Decimal | None = None
    quantity_max: Decimal | None = None
    quantity_unit: str | None = None
    destination: str | None = None
    requested_incoterm: str | None = None
    packaging: str | None = None
    commercial_deadline: datetime | None = None
    user_confirmed: bool | None = None


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    requirement_id: UUID
    source_id: UUID | None
    field_path: str
    excerpt: str | None
    page_number: int | None
    user_confirmed: bool
    created_at: datetime


class RequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deal_id: UUID
    product_id: UUID | None
    quantity_min: Decimal | None
    quantity_max: Decimal | None
    quantity_unit: str | None
    destination: str | None
    requested_incoterm: str | None
    packaging: str | None
    commercial_deadline: datetime | None
    user_confirmed: bool
    evidence_items: list[EvidenceResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    normalized_name: str
    category: str
    aliases: list | None
    typical_units: list | None


class SupplierLedOpportunityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    raw_product_name: str | None = None
    normalized_product_id: UUID | None = None
    buyer_or_supplier_hint: str | None = None
    quantity_min: Decimal | None = None
    quantity_max: Decimal | None = None
    quantity_unit: str | None = None
    origin_hint: str | None = None
    destination_hint: str | None = None
    deadline: datetime | None = None
    notes: str | None = None
    unit_price: Decimal | None = None
    currency: str = "USD"
    incoterm: str | None = None
    origin: str | None = None


class SupplierLeadContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    opportunity_id: UUID
    supply_offer_id: UUID | None
    unit_price: Decimal | None
    currency: str | None
    incoterm: str | None
    origin: str | None
    supplier_hint: str | None
    created_at: datetime
    updated_at: datetime


class SupplierLeadMatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    supplier_opportunity_id: UUID
    match_type: str
    matched_opportunity_id: UUID | None
    matched_deal_id: UUID | None
    matched_requirement_id: UUID | None
    score: Decimal
    match_summary: str
    match_reasons: list
    route_proposal: dict | None
    market_comparison: dict | None
    outreach_subject: str | None
    outreach_body: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class SupplierLeadDetailResponse(BaseModel):
    context: SupplierLeadContextResponse | None
    matches: list[SupplierLeadMatchResponse]
    market_comparison: dict | None


class SupplierLedFromSupplyOfferCreate(BaseModel):
    title: str | None = None
