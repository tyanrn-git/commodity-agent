from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MonitoringRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    connector_type: str = "MOCK"
    source_url: str = Field(min_length=1, max_length=1024)
    poll_interval_hours: int = Field(default=24, ge=1, le=168)
    filters: dict = Field(default_factory=dict)
    access_mode: str = "PUBLIC"
    connector_config: dict = Field(default_factory=dict)


class MonitoringRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    connector_type: str
    source_url: str
    poll_interval_hours: int
    is_active: bool
    filters: dict
    access_mode: str
    connector_config: dict
    health_status: str
    health_message: str | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MonitoringRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    monitoring_rule_id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    items_found: int
    items_new: int
    opportunities_created: int
    error_message: str | None
    health_status: str
    created_at: datetime
    updated_at: datetime


class MonitoringHealthResponse(BaseModel):
    rule_id: UUID
    health_status: str
    message: str


class MonitoredPublicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    monitoring_rule_id: UUID
    source_item_id: str
    canonical_url: str | None
    title: str
    publication_date: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    content_hash: str
    status: str
    extracted_fields: dict | None
    opportunity_id: UUID | None
    created_at: datetime
    updated_at: datetime
