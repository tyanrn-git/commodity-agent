from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas_monitoring import (
    MonitoringHealthResponse,
    MonitoringRuleCreate,
    MonitoringRuleResponse,
    MonitoringRunResponse,
    MonitoredPublicationResponse,
)
from app.db.session import get_db
from app.domain.models import User
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.monitoring import (
    check_monitoring_health,
    create_monitoring_rule,
    get_monitoring_rule,
    get_monitoring_run,
    list_monitoring_rules,
    list_publications,
    run_monitoring_rule,
)

router = APIRouter(tags=["monitoring"])


@router.get("/monitoring-rules", response_model=list[MonitoringRuleResponse])
def get_monitoring_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_monitoring_rules(db, user=current_user)


@router.post("/monitoring-rules", response_model=MonitoringRuleResponse, status_code=status.HTTP_201_CREATED)
def post_monitoring_rule(
    payload: MonitoringRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_monitoring_rule(
        db,
        user=current_user,
        name=payload.name,
        connector_type=payload.connector_type,
        source_url=payload.source_url,
        poll_interval_hours=payload.poll_interval_hours,
        filters=payload.filters,
        access_mode=payload.access_mode,
        connector_config=payload.connector_config,
    )


@router.get("/monitoring-rules/{rule_id}", response_model=MonitoringRuleResponse)
def get_monitoring_rule_route(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_monitoring_rule(db, user=current_user, rule_id=rule_id)


@router.get("/monitoring-rules/{rule_id}/health", response_model=MonitoringHealthResponse)
def monitoring_health_route(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = get_monitoring_rule(db, user=current_user, rule_id=rule_id)
    result = check_monitoring_health(db, user=current_user, rule=rule)
    return MonitoringHealthResponse(
        rule_id=rule.id,
        health_status=result["health_status"],
        message=result["message"],
    )


@router.post("/monitoring-rules/{rule_id}/run", response_model=MonitoringRunResponse)
def run_monitoring_rule_route(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = get_monitoring_rule(db, user=current_user, rule_id=rule_id)
    storage = LocalFilesystemStorage()
    return run_monitoring_rule(db, user=current_user, rule=rule, storage=storage)


@router.get("/monitoring-runs/{run_id}", response_model=MonitoringRunResponse)
def get_monitoring_run_route(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_monitoring_run(db, user=current_user, run_id=run_id)


@router.get("/monitoring-rules/{rule_id}/publications", response_model=list[MonitoredPublicationResponse])
def list_publications_route(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_publications(db, user=current_user, rule_id=rule_id)
