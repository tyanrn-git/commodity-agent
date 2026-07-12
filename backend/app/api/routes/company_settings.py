from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas_parties import CompanySettingsResponse, CompanySettingsUpdate
from app.db.session import get_db
from app.domain.models import User
from app.services.counterparty import ensure_company_settings, update_company_settings

router = APIRouter(prefix="/settings", tags=["company-settings"])


@router.get("/company", response_model=CompanySettingsResponse)
def get_company_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ensure_company_settings(db, current_user)


@router.patch("/company", response_model=CompanySettingsResponse)
def patch_company_settings(
    payload: CompanySettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_company_settings(
        db, user=current_user, data=payload.model_dump(exclude_unset=True)
    )
