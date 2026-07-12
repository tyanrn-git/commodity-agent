from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas_parties import (
    DealPartyCreate,
    DealPartyResponse,
    DealPartyUpdate,
    RFQApproveRequest,
    RFQCreate,
    RFQResponse,
    RFQTemplateResponse,
    RFQUpdate,
)
from app.db.session import get_db
from app.domain.models import Deal, DealParty, RFQ, RFQTemplate, User
from app.services.deal_party import add_deal_party, list_deal_parties, update_deal_party
from app.services.rfq import (
    approve_rfq,
    build_approval_preview,
    create_rfq,
    delete_rfq,
    draft_rfq_with_ai,
    get_rfq,
    submit_rfq_for_approval,
    update_rfq,
)

router = APIRouter(tags=["deals-rfq"])


@router.get("/rfq-templates", response_model=list[RFQTemplateResponse])
def list_rfq_templates(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return list(db.scalars(select(RFQTemplate).where(RFQTemplate.is_active.is_(True))))


@router.get("/deals/{deal_id}/parties", response_model=list[DealPartyResponse])
def get_deal_parties(
    deal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_deal_parties(db, user=current_user, deal_id=deal_id)


@router.post("/deals/{deal_id}/parties", response_model=DealPartyResponse, status_code=status.HTTP_201_CREATED)
def create_deal_party(
    deal_id: UUID,
    payload: DealPartyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = db.scalar(select(Deal).where(Deal.id == deal_id, Deal.owner_id == current_user.id))
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return add_deal_party(
        db,
        user=current_user,
        deal=deal,
        counterparty_id=payload.counterparty_id,
        role=payload.role,
        disclosure_status=payload.disclosure_status,
        selected_for_contact=payload.selected_for_contact,
    )


@router.patch("/deal-parties/{party_id}", response_model=DealPartyResponse)
def patch_deal_party(
    party_id: UUID,
    payload: DealPartyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    party = db.get(DealParty, party_id)
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal party not found")
    return update_deal_party(
        db, user=current_user, party=party, data=payload.model_dump(exclude_unset=True)
    )


@router.get("/deals/{deal_id}/rfqs", response_model=list[RFQResponse])
def list_deal_rfqs(
    deal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = db.scalar(select(Deal).where(Deal.id == deal_id, Deal.owner_id == current_user.id))
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return list(db.scalars(select(RFQ).where(RFQ.deal_id == deal_id).order_by(RFQ.created_at.desc())))


@router.post("/deals/{deal_id}/rfqs", response_model=RFQResponse, status_code=status.HTTP_201_CREATED)
def create_deal_rfq(
    deal_id: UUID,
    payload: RFQCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = db.scalar(select(Deal).where(Deal.id == deal_id, Deal.owner_id == current_user.id))
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return create_rfq(
        db,
        user=current_user,
        deal=deal,
        target_deal_party_id=payload.target_deal_party_id,
        rfq_type=payload.rfq_type,
        contact_id=payload.contact_id,
        template_id=payload.template_id,
        requested_fields=payload.requested_fields,
        language=payload.language,
    )


@router.get("/rfqs/{rfq_id}", response_model=RFQResponse)
def get_rfq_route(
    rfq_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_rfq(db, user=current_user, rfq_id=rfq_id)


@router.patch("/rfqs/{rfq_id}", response_model=RFQResponse)
def patch_rfq(
    rfq_id: UUID,
    payload: RFQUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rfq = get_rfq(db, user=current_user, rfq_id=rfq_id)
    return update_rfq(db, user=current_user, rfq=rfq, data=payload.model_dump(exclude_unset=True))


@router.delete("/rfqs/{rfq_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rfq_route(
    rfq_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rfq = get_rfq(db, user=current_user, rfq_id=rfq_id)
    delete_rfq(db, user=current_user, rfq=rfq)


@router.post("/rfqs/{rfq_id}/draft-with-ai", response_model=RFQResponse)
def draft_with_ai(
    rfq_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rfq = get_rfq(db, user=current_user, rfq_id=rfq_id)
    return draft_rfq_with_ai(db, user=current_user, rfq=rfq)


@router.get("/rfqs/{rfq_id}/approval-preview")
def approval_preview(
    rfq_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rfq = get_rfq(db, user=current_user, rfq_id=rfq_id)
    return build_approval_preview(db, rfq=rfq)


@router.post("/rfqs/{rfq_id}/submit-for-approval", response_model=RFQResponse)
def submit_for_approval(
    rfq_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rfq = get_rfq(db, user=current_user, rfq_id=rfq_id)
    return submit_rfq_for_approval(db, user=current_user, rfq=rfq)


@router.post("/rfqs/{rfq_id}/approve", response_model=RFQResponse)
def approve_rfq_route(
    rfq_id: UUID,
    payload: RFQApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rfq = get_rfq(db, user=current_user, rfq_id=rfq_id)
    return approve_rfq(
        db,
        user=current_user,
        rfq=rfq,
        acknowledge_warnings=payload.acknowledge_warnings,
    )
