from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ShipmentLotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    configuration_id: UUID
    supply_offer_id: UUID | None
    supplier_counterparty_id: UUID | None
    product_name: str | None
    quantity: Decimal | None
    quantity_unit: str | None
    purchase_price_per_unit: Decimal | None
    currency: str | None
    incoterm: str | None
    origin: str | None
    packaging: str | None
    allocation_status: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("quantity", "purchase_price_per_unit")
    def serialize_lot_decimal(self, value: Decimal | float | str | None) -> str | None:
        return None if value is None else str(value)


class TransportLegResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    configuration_id: UUID
    sequence: int
    mode: str
    origin: str | None
    destination: str | None
    carrier_name: str | None
    equipment: str | None
    quantity: Decimal | None
    quantity_unit: str | None
    cost: Decimal | None
    currency: str | None
    risk_transfer_point: str | None
    leg_incoterm: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("quantity", "cost")
    def serialize_leg_decimal(self, value: Decimal | float | str | None) -> str | None:
        return None if value is None else str(value)


class ServiceQuoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deal_id: UUID
    configuration_id: UUID | None
    quote_type: str
    provider_name: str | None
    description: str | None
    amount: Decimal | None
    currency: str | None
    user_confirmed: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("amount")
    def serialize_quote_decimal(self, value: Decimal | float | str | None) -> str | None:
        return None if value is None else str(value)


class EconomicsSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    configuration_id: UUID
    scenario: str
    snapshot_data: dict
    created_at: datetime


class ConfigurationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    deal_id: UUID
    name: str
    target_quantity: Decimal | None
    target_quantity_unit: str | None
    destination: str | None
    status: str
    is_stale: bool
    stale_since: datetime | None
    stale_reason: str | None
    sales_price_per_unit: Decimal | None
    sales_currency: str | None
    revenue: Decimal | None
    total_cost: Decimal | None
    gross_margin: Decimal | None
    gross_margin_percent: Decimal | None
    cost_breakdown: dict | None
    fx_rates_used: dict | None
    spec_match_summary: dict | None
    completeness_score: Decimal | None
    last_calculated_at: datetime | None
    shipment_lots: list[ShipmentLotResponse] = []
    transport_legs: list[TransportLegResponse] = []
    service_quotes: list[ServiceQuoteResponse] = []
    economics_snapshots: list[EconomicsSnapshotResponse] = []
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        "target_quantity",
        "sales_price_per_unit",
        "revenue",
        "total_cost",
        "gross_margin",
        "gross_margin_percent",
        "completeness_score",
    )
    def serialize_config_decimal(self, value: Decimal | float | str | None) -> str | None:
        return None if value is None else str(value)


class ConfigurationCreate(BaseModel):
    supply_offer_id: UUID
    name: str = Field(min_length=1, max_length=255)
    sales_price_per_unit: float = Field(gt=0)
    sales_currency: str | None = None


class TransportLegCreate(BaseModel):
    sequence: int = 1
    mode: str = "SEA"
    origin: str | None = None
    destination: str | None = None
    carrier_name: str | None = None
    equipment: str | None = None
    quantity: float | None = None
    quantity_unit: str | None = None
    cost: float = Field(ge=0)
    currency: str | None = None
    risk_transfer_point: str | None = None
    leg_incoterm: str | None = None


class ServiceQuoteCreate(BaseModel):
    quote_type: str
    provider_name: str | None = None
    description: str | None = None
    amount: float = Field(ge=0)
    currency: str | None = None
    user_confirmed: bool = False
