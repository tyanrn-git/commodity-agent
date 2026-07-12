from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AutomationSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    auto_follow_up_enabled: bool
    follow_up_after_days: int
    max_follow_ups_per_rfq: int
    min_days_between_follow_ups: int
    max_auto_actions_per_day: int
    created_at: datetime
    updated_at: datetime


class AutomationSettingsUpdate(BaseModel):
    auto_follow_up_enabled: bool | None = None
    follow_up_after_days: int | None = Field(default=None, ge=1, le=30)
    max_follow_ups_per_rfq: int | None = Field(default=None, ge=0, le=10)
    min_days_between_follow_ups: int | None = Field(default=None, ge=1, le=30)
    max_auto_actions_per_day: int | None = Field(default=None, ge=1, le=100)


class AutomationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    actions_evaluated: int
    actions_sent: int
    actions_blocked: int
    actions_skipped: int
    actions_rate_limited: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class AutomatedActionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    automation_run_id: UUID
    action_type: str
    action_category: str
    binding_class: str
    entity_type: str
    entity_id: UUID
    status: str
    reason: str | None
    message_id: UUID | None
    payload: dict | None
    created_at: datetime


class AutomationValidateRequest(BaseModel):
    action_type: str
    binding_class: str


class AutomationValidateResponse(BaseModel):
    allowed: bool
    reason: str | None = None
    action_category: str | None = None
