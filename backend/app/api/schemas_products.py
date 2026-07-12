from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SpecParameterCreate(BaseModel):
    parameter_name: str = Field(min_length=1, max_length=128)
    unit: str | None = None
    is_mandatory: bool = False
    minimum_value: Decimal | None = None
    maximum_value: Decimal | None = None
    parameter_kind: str = "VARIANT"
    variation_materiality: str = "UNKNOWN"
    description: str | None = None


class ProductSpecProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    parameter_name: str
    unit: str | None
    minimum_value: Decimal | None
    maximum_value: Decimal | None
    is_mandatory: bool
    parameter_kind: str
    variation_materiality: str
    description: str | None
    evidence_count: int
    created_at: datetime
    updated_at: datetime


class ProductCompletenessResponse(BaseModel):
    total_parameters: int
    filled_parameters: int
    completeness_percent: int
    identity_parameters: int = 0
    variant_parameters: int = 0


class ProductCreate(BaseModel):
    normalized_name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=128)
    aliases: list[str] = Field(default_factory=list)
    typical_units: list[str] = Field(default_factory=list)
    spec_parameters: list[SpecParameterCreate] = Field(default_factory=list)


class ProductDetailResponse(BaseModel):
    id: UUID
    normalized_name: str
    category: str
    aliases: list | None
    typical_units: list | None
    specification_profiles: list[ProductSpecProfileResponse]
    completeness: ProductCompletenessResponse
    created_at: datetime
    updated_at: datetime


class ProductListItemResponse(BaseModel):
    id: UUID
    normalized_name: str
    category: str
    aliases: list | None
    typical_units: list | None
    completeness: ProductCompletenessResponse
    created_at: datetime
    updated_at: datetime
