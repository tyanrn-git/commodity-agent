from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class AIBudgetSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    monthly_budget_usd: Decimal
    first_warning_percent: int
    second_warning_percent: int
    hard_limit_enabled: bool
    allow_manual_override: bool
    budget_reset_day: int
    preferred_default_model: str
    fallback_model: str | None
    ai_enabled: bool
    effective_from: datetime
    created_at: datetime
    updated_at: datetime


class AIBudgetSettingsUpdate(BaseModel):
    monthly_budget_usd: Decimal | None = Field(default=None, gt=0)
    first_warning_percent: int | None = Field(default=None, ge=1, le=100)
    second_warning_percent: int | None = Field(default=None, ge=1, le=100)
    hard_limit_enabled: bool | None = None
    allow_manual_override: bool | None = None
    budget_reset_day: int | None = Field(default=None, ge=1, le=28)
    preferred_default_model: str | None = None
    fallback_model: str | None = None
    ai_enabled: bool | None = None


class AIUsageSummaryResponse(BaseModel):
    monthly_budget_usd: str
    spent_usd: str
    remaining_usd: str
    percent_used: float
    forecast_usd: str
    warning_level: str | None
    ai_enabled: bool
    by_model: list[dict]
    by_operation: list[dict]


class ExtractionResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    content_hash: str
    status: str
    operation: str
    model: str | None
    extracted_data: dict | None
    validation_errors: list | None
    missing_fields: list | None
    attempt_count: int
    created_at: datetime
    updated_at: datetime


class ExtractSourceRequest(BaseModel):
    force: bool = False
    allow_budget_override: bool = False


class ApplyExtractionRequest(BaseModel):
    extraction_id: UUID
    fields: list[str] | None = None


class ImportUrlRequest(BaseModel):
    url: HttpUrl
