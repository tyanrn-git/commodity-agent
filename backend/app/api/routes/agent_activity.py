import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.agents.registry import AGENT_REGISTRY
from app.api.schemas_agent_activity import (
    AgentCapabilityResponse,
    AgentResultResponse,
    AgentRunResponse,
    AgentTaskResponse,
)
from app.db.session import get_db
from app.domain.models import Opportunity, User
from app.api.deps import get_current_user
from app.services.agent_runtime import list_agent_activity

router = APIRouter(tags=["agent-activity"])


def _serialize_activity(items: list[dict]) -> list[AgentTaskResponse]:
    serialized: list[AgentTaskResponse] = []
    for item in items:
        task = item["task"]
        runs = [AgentRunResponse.model_validate(run) for run in item["runs"]]
        results = [AgentResultResponse.model_validate(result) for result in item["results"]]
        serialized.append(
            AgentTaskResponse(
                id=task.id,
                opportunity_id=task.opportunity_id,
                deal_id=task.deal_id,
                research_campaign_id=task.research_campaign_id,
                internet_source_search_run_id=task.internet_source_search_run_id,
                internet_source_search_hit_id=task.internet_source_search_hit_id,
                agent_type=task.agent_type,
                task_type=task.task_type,
                input_payload=task.input_payload or {},
                priority=task.priority,
                status=task.status,
                started_at=task.started_at,
                completed_at=task.completed_at,
                blocked_reason=task.blocked_reason,
                created_at=task.created_at,
                runs=runs,
                results=results,
            )
        )
    return serialized


@router.get("/agent-capabilities", response_model=list[AgentCapabilityResponse])
def list_agent_capabilities(
    current_user: User = Depends(get_current_user),
):
    return [
        AgentCapabilityResponse(
            agent_type=cap.agent_type,
            label=cap.label,
            description=cap.description,
            allowed_task_types=list(cap.allowed_task_types),
        )
        for cap in AGENT_REGISTRY.values()
    ]


@router.get("/agent-activity", response_model=list[AgentTaskResponse])
def list_agent_activity_route(
    opportunity_id: uuid.UUID | None = Query(default=None),
    deal_id: uuid.UUID | None = Query(default=None),
    agent_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = list_agent_activity(
        db,
        user=current_user,
        opportunity_id=opportunity_id,
        deal_id=deal_id,
        agent_type=agent_type,
        limit=limit,
    )
    return _serialize_activity(items)


@router.get("/opportunities/{opportunity_id}/agent-activity", response_model=list[AgentTaskResponse])
def list_opportunity_agent_activity(
    opportunity_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    items = list_agent_activity(
        db,
        user=current_user,
        opportunity_id=opportunity_id,
        limit=limit,
    )
    return _serialize_activity(items)
