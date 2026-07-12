from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas_ai import (
    AIBudgetSettingsResponse,
    AIBudgetSettingsUpdate,
    AIUsageSummaryResponse,
)
from app.db.session import get_db
from app.domain.models import User
from app.services.ai_budget import ensure_ai_budget_settings, get_usage_summary, update_ai_budget_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/ai-budget", response_model=AIBudgetSettingsResponse)
def get_ai_budget(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ensure_ai_budget_settings(db, current_user)


@router.patch("/ai-budget", response_model=AIBudgetSettingsResponse)
def patch_ai_budget(
    payload: AIBudgetSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = payload.model_dump(exclude_unset=True)
    return update_ai_budget_settings(db, user=current_user, data=data)


@router.get("/ai-usage", response_model=AIUsageSummaryResponse)
def get_ai_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_usage_summary(db, current_user)
