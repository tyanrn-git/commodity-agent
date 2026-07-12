from uuid import UUID

from pydantic import BaseModel, Field


class ProductAssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    apply_changes: bool = False


class ProductSpecChangeResponse(BaseModel):
    action: str
    parameter_name: str
    parameter_kind: str
    variation_materiality: str
    unit: str | None = None
    value_min: str | None = None
    value_max: str | None = None
    is_mandatory: bool = False
    description: str | None = None
    reasoning: str | None = None


class ProductAssistantResponse(BaseModel):
    reply: str
    spec_changes: list[ProductSpecChangeResponse]
    applied_changes: list[str]
    ai_model: str
    ai_cost_usd: str
