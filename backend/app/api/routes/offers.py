from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas_offer import (
    OfferApproveRequest,
    OfferCreate,
    OfferResponse,
    OfferUpdate,
    SendOfferResponse,
)
from app.db.session import get_db
from app.domain.models import Deal, User
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.email_loop import send_approved_offer
from app.services.offer import (
    approve_offer,
    build_offer_approval_preview,
    create_offer_from_configuration,
    delete_offer,
    get_offer,
    list_offers,
    submit_offer_for_approval,
    update_offer,
)

router = APIRouter(tags=["offers"])


@router.get("/deals/{deal_id}/offers", response_model=list[OfferResponse])
def get_deal_offers(
    deal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_offers(db, user=current_user, deal_id=deal_id)


@router.post("/deals/{deal_id}/offers", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
def create_deal_offer(
    deal_id: UUID,
    payload: OfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = db.get(Deal, deal_id)
    if deal is None or deal.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Deal not found")
    return create_offer_from_configuration(
        db,
        user=current_user,
        deal=deal,
        configuration_id=payload.configuration_id,
        target_deal_party_id=payload.target_deal_party_id,
    )


@router.get("/offers/{offer_id}", response_model=OfferResponse)
def get_offer_route(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_offer(db, user=current_user, offer_id=offer_id)


@router.patch("/offers/{offer_id}", response_model=OfferResponse)
def update_offer_route(
    offer_id: UUID,
    payload: OfferUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offer = get_offer(db, user=current_user, offer_id=offer_id)
    return update_offer(db, user=current_user, offer=offer, data=payload.model_dump(exclude_unset=True))


@router.delete("/offers/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_offer_route(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offer = get_offer(db, user=current_user, offer_id=offer_id)
    delete_offer(db, user=current_user, offer=offer)


@router.get("/offers/{offer_id}/approval-preview")
def offer_approval_preview(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offer = get_offer(db, user=current_user, offer_id=offer_id)
    return build_offer_approval_preview(db, offer=offer)


@router.post("/offers/{offer_id}/submit-for-approval", response_model=OfferResponse)
def submit_offer_route(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offer = get_offer(db, user=current_user, offer_id=offer_id)
    return submit_offer_for_approval(db, user=current_user, offer=offer)


@router.post("/offers/{offer_id}/approve", response_model=OfferResponse)
def approve_offer_route(
    offer_id: UUID,
    payload: OfferApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offer = get_offer(db, user=current_user, offer_id=offer_id)
    return approve_offer(
        db,
        user=current_user,
        offer=offer,
        acknowledge_warnings=payload.acknowledge_warnings,
    )


@router.post("/offers/{offer_id}/send", response_model=SendOfferResponse)
def send_offer_route(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offer = get_offer(db, user=current_user, offer_id=offer_id)
    storage = LocalFilesystemStorage()
    offer, message = send_approved_offer(db, user=current_user, offer=offer, storage=storage)
    return SendOfferResponse(
        offer_id=offer.id,
        status=offer.status,
        message_id=message.id,
        mailbox_message_id=message.mailbox_message_id,
    )
