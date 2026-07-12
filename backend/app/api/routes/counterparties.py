from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas_parties import (
    CompanySettingsResponse,
    CompanySettingsUpdate,
    ContactCreate,
    ContactResponse,
    CounterpartyCreate,
    CounterpartyListItemResponse,
    CounterpartyResponse,
    CounterpartyUpdate,
)
from app.db.session import get_db
from app.domain.models import User
from app.services.counterparty import (
    confirm_domain_verification,
    create_contact,
    create_counterparty,
    get_counterparty,
    list_counterparties_summary,
    mark_compliance_reviewed,
    run_domain_verification,
    update_counterparty,
)

router = APIRouter(prefix="/counterparties", tags=["counterparties"])


@router.get("", response_model=list[CounterpartyListItemResponse])
def list_counterparties(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = list_counterparties_summary(db, user=current_user)
    return [
        CounterpartyListItemResponse.model_validate(row["counterparty"]).model_copy(
            update={
                "contacts_count": row["contacts_count"],
                "capabilities_count": row["capabilities_count"],
                "confirmed_capabilities_count": row["confirmed_capabilities_count"],
            }
        )
        for row in rows
    ]


@router.post("", response_model=CounterpartyResponse, status_code=status.HTTP_201_CREATED)
def create_counterparty_route(
    payload: CounterpartyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_counterparty(db, user=current_user, data=payload.model_dump())


@router.get("/{counterparty_id}", response_model=CounterpartyResponse)
def get_counterparty_route(
    counterparty_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_counterparty(db, user=current_user, counterparty_id=counterparty_id)


@router.patch("/{counterparty_id}", response_model=CounterpartyResponse)
def update_counterparty_route(
    counterparty_id: UUID,
    payload: CounterpartyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    counterparty = get_counterparty(db, user=current_user, counterparty_id=counterparty_id)
    return update_counterparty(
        db, user=current_user, counterparty=counterparty, data=payload.model_dump(exclude_unset=True)
    )


@router.post("/{counterparty_id}/contacts", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
def create_contact_route(
    counterparty_id: UUID,
    payload: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    counterparty = get_counterparty(db, user=current_user, counterparty_id=counterparty_id)
    return create_contact(db, user=current_user, counterparty=counterparty, data=payload.model_dump())


@router.post("/{counterparty_id}/verify-domain")
def verify_domain_route(
    counterparty_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    counterparty = get_counterparty(db, user=current_user, counterparty_id=counterparty_id)
    return run_domain_verification(db, user=current_user, counterparty=counterparty)


@router.post("/{counterparty_id}/confirm-domain", response_model=CounterpartyResponse)
def confirm_domain_route(
    counterparty_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    counterparty = get_counterparty(db, user=current_user, counterparty_id=counterparty_id)
    return confirm_domain_verification(db, user=current_user, counterparty=counterparty)


@router.post("/{counterparty_id}/mark-reviewed", response_model=CounterpartyResponse)
def mark_reviewed_route(
    counterparty_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    counterparty = get_counterparty(db, user=current_user, counterparty_id=counterparty_id)
    return mark_compliance_reviewed(db, user=current_user, counterparty=counterparty)
