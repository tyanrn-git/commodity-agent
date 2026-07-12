from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class EvidenceHint(BaseModel):
    field_path: str
    excerpt: str | None = None
    page_number: int | None = None


class OpportunityExtractionOutput(BaseModel):
    raw_product_name: str | None = None
    buyer_or_supplier_hint: str | None = None
    quantity_min: Decimal | None = None
    quantity_max: Decimal | None = None
    quantity_unit: str | None = None
    origin_hint: str | None = None
    destination_hint: str | None = None
    requested_incoterm: str | None = None
    packaging: str | None = None
    deadline: str | None = Field(
        default=None, description="ISO date or datetime string if found in document"
    )
    notes: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    evidence_hints: list[EvidenceHint] = Field(default_factory=list)


class AICompletionUsage(BaseModel):
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    raw_response: dict[str, Any] | None = None


class RFQDraftOutput(BaseModel):
    subject: str
    body: str


class SpecParameterOutput(BaseModel):
    parameter_name: str
    unit: str | None = None
    value_text: str | None = None
    value_min: Decimal | None = None
    value_max: Decimal | None = None
    status: str = "MISSING"
    evidence_excerpt: str | None = None
    is_mandatory: bool = False
    parameter_kind: str = "VARIANT"
    variation_materiality: str = "UNKNOWN"
    description: str | None = None


class ProductSpecChangeOutput(BaseModel):
    action: str = "upsert"
    parameter_name: str
    parameter_kind: str = "VARIANT"
    variation_materiality: str = "UNKNOWN"
    unit: str | None = None
    value_min: Decimal | None = None
    value_max: Decimal | None = None
    is_mandatory: bool = False
    description: str | None = None
    reasoning: str | None = None


class ProductAssistantOutput(BaseModel):
    reply: str
    category: str | None = None
    aliases: list[str] = Field(default_factory=list)
    spec_changes: list[ProductSpecChangeOutput] = Field(default_factory=list)


class ProductAutoFillOutput(BaseModel):
    parameters: list[SpecParameterOutput] = Field(default_factory=list)
    reasoning: str | None = None


class ProposedProductOutput(BaseModel):
    normalized_name: str
    category: str
    aliases: list[str] = Field(default_factory=list)
    typical_units: list[str] = Field(default_factory=list)
    parameters: list[SpecParameterOutput] = Field(default_factory=list)
    reasoning: str | None = None


class ProductResolutionOutput(BaseModel):
    normalized_product_name: str | None = None
    normalized_product_id: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str | None = None
    parameters: list[SpecParameterOutput] = Field(default_factory=list)
    missing_mandatory: list[str] = Field(default_factory=list)
    proposed_new_product: ProposedProductOutput | None = None


class CapabilityItemOutput(BaseModel):
    capability_type: str
    title: str
    rough_product_name: str | None = None
    normalized_product_name: str | None = None
    regions: list[str] = Field(default_factory=list)
    routes: list[str] = Field(default_factory=list)
    incoterms: list[str] = Field(default_factory=list)
    notes: str | None = None
    evidence_excerpt: str | None = None
    confirmation_level: str = "ESTIMATE"


class ContactHintOutput(BaseModel):
    full_name: str | None = None
    role_title: str | None = None
    email: str | None = None
    department: str | None = None
    evidence_excerpt: str | None = None


class CounterpartyEnrichmentOutput(BaseModel):
    summary: str | None = None
    capabilities: list[CapabilityItemOutput] = Field(default_factory=list)
    contact_hints: list[ContactHintOutput] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class TenderSearchHitOutput(BaseModel):
    title: str
    url: str | None = None
    product: str | None = None
    quantity: Decimal | None = None
    quantity_unit: str | None = None
    destination: str | None = None
    buyer: str | None = None
    deadline: str | None = Field(default=None, description="Submission deadline ISO date or datetime")
    submission_deadline: str | None = Field(default=None, description="Bid submission deadline")
    delivery_deadline: str | None = Field(default=None, description="Delivery or contract deadline")
    publication_date: str | None = Field(default=None, description="ISO date or datetime")
    body: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_excerpt: str | None = None


class TenderSearchOutput(BaseModel):
    hits: list[TenderSearchHitOutput] = Field(default_factory=list)
    notes: str | None = None


class TenderFeasibilityOutput(BaseModel):
    feasible: bool
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    summary: str
    supplier_hint: str | None = None
    supplier_reasoning: str | None = None
    buy_price_per_unit: Decimal | None = None
    buy_currency: str | None = None
    buy_incoterm: str | None = None
    buy_basis: str | None = None
    sell_price_per_unit: Decimal | None = None
    sell_currency: str | None = None
    sell_incoterm: str | None = None
    sell_basis: str | None = None
    transport_cost: Decimal | None = None
    gross_margin: Decimal | None = None
    gross_margin_percent: float | None = None
    margin_currency: str | None = None
    risks: list[str] = Field(default_factory=list)
