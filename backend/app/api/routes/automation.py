from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas_automation import (
    AutomatedActionLogResponse,
    AutomationRunResponse,
    AutomationSettingsResponse,
    AutomationSettingsUpdate,
    AutomationValidateRequest,
    AutomationValidateResponse,
)
from app.db.session import get_db
from app.domain.enums import AutomationActionCategory
from app.domain.models import AutomatedActionLog, AutomationRun, User
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.automation import (
    ALLOWED_AUTO_ACTIONS,
    can_automate_action,
    ensure_automation_settings,
    run_automation,
    update_automation_settings,
)

router = APIRouter(tags=["automation"])


@router.get("/settings/automation", response_model=AutomationSettingsResponse)
def get_automation_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ensure_automation_settings(db, current_user)


@router.patch("/settings/automation", response_model=AutomationSettingsResponse)
def patch_automation_settings(
    payload: AutomationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = payload.model_dump(exclude_unset=True)
    return update_automation_settings(db, user=current_user, data=data)


@router.post("/automation/run", response_model=AutomationRunResponse)
def trigger_automation_run(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    storage = LocalFilesystemStorage()
    return run_automation(db, user=current_user, storage=storage)


@router.get("/automation/runs", response_model=list[AutomationRunResponse])
def list_automation_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(AutomationRun)
        .where(AutomationRun.owner_id == current_user.id)
        .order_by(AutomationRun.started_at.desc())
        .limit(50)
    )
    return list(db.scalars(stmt))


@router.get("/automation/actions", response_model=list[AutomatedActionLogResponse])
def list_automation_actions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(AutomatedActionLog)
        .where(AutomatedActionLog.owner_id == current_user.id)
        .order_by(AutomatedActionLog.created_at.desc())
        .limit(100)
    )
    return list(db.scalars(stmt))


@router.post("/automation/validate", response_model=AutomationValidateResponse)
def validate_automation_action(payload: AutomationValidateRequest):
    allowed, reason = can_automate_action(payload.action_type, payload.binding_class)
    category = ALLOWED_AUTO_ACTIONS.get(payload.action_type)
    return AutomationValidateResponse(
        allowed=allowed,
        reason=reason,
        action_category=category or AutomationActionCategory.NON_BINDING.value if allowed else None,
    )
