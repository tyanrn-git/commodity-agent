import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AgentRunResponse(BaseModel):
    id: uuid.UUID
    agent_task_id: uuid.UUID
    provider: str
    model: str | None
    prompt_version: str | None
    toolset_version: str | None
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    actual_cost: float | None
    ai_usage_log_id: uuid.UUID | None
    started_at: datetime
    completed_at: datetime | None
    status: str
    error: str | None

    model_config = {"from_attributes": True}


class AgentResultResponse(BaseModel):
    id: uuid.UUID
    agent_run_id: uuid.UUID
    result_type: str
    structured_payload: dict
    summary: str | None
    confidence: float | None
    requires_review: bool
    applied_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentTaskResponse(BaseModel):
    id: uuid.UUID
    opportunity_id: uuid.UUID | None
    deal_id: uuid.UUID | None
    research_campaign_id: uuid.UUID | None
    internet_source_search_run_id: uuid.UUID | None
    internet_source_search_hit_id: uuid.UUID | None
    agent_type: str
    task_type: str
    input_payload: dict
    priority: int
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    blocked_reason: str | None
    created_at: datetime
    runs: list[AgentRunResponse] = Field(default_factory=list)
    results: list[AgentResultResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AgentCapabilityResponse(BaseModel):
    agent_type: str
    label: str
    description: str
    allowed_task_types: list[str]
