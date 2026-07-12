from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas_email import (
    LinkMessageRequest,
    MessageResponse,
    SendRfqResponse,
    SupplyOfferResponse,
)
from app.db.session import get_db
from app.domain.models import Message, User
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.email_loop import (
    import_inbound_eml,
    link_message_to_rfq,
    list_inbox,
    list_supply_offers,
    send_approved_rfq,
    sync_mailbox,
)
from app.services.rfq import get_rfq

router = APIRouter(tags=["inbox"])


@router.post("/rfqs/{rfq_id}/send", response_model=SendRfqResponse)
def send_rfq(
    rfq_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rfq = get_rfq(db, user=current_user, rfq_id=rfq_id)
    storage = LocalFilesystemStorage()
    rfq, message = send_approved_rfq(db, user=current_user, rfq=rfq, storage=storage)
    return SendRfqResponse(
        rfq_id=rfq.id,
        status=rfq.status,
        message_id=message.id,
        mailbox_message_id=message.mailbox_message_id,
    )


@router.get("/inbox", response_model=list[MessageResponse])
def get_linked_inbox(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_inbox(db, user=current_user, linked_only=True)


@router.get("/inbox/unlinked", response_model=list[MessageResponse])
def get_unlinked_inbox(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_inbox(db, user=current_user, linked_only=False)


@router.post("/inbox/sync", response_model=list[MessageResponse])
def sync_inbox(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    storage = LocalFilesystemStorage()
    return sync_mailbox(db, user=current_user, storage=storage)


@router.post("/inbox/import-eml")
def import_eml_to_inbox(
    file: UploadFile = File(...),
    deal_id: UUID | None = Form(default=None),
    rfq_id: UUID | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    storage = LocalFilesystemStorage()
    message, offer = import_inbound_eml(
        db,
        user=current_user,
        file=file,
        storage=storage,
        deal_id=deal_id,
        rfq_id=rfq_id,
    )
    return {
        "message": MessageResponse.model_validate(message),
        "supply_offer": SupplyOfferResponse.model_validate(offer) if offer else None,
    }


@router.post("/messages/{message_id}/link")
def link_message(
    message_id: UUID,
    payload: LinkMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message = db.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    message, offer = link_message_to_rfq(
        db, user=current_user, message=message, rfq_id=payload.rfq_id
    )
    return {
        "message": MessageResponse.model_validate(message),
        "supply_offer": SupplyOfferResponse.model_validate(offer),
    }


@router.get("/deals/{deal_id}/supply-offers", response_model=list[SupplyOfferResponse])
def get_supply_offers(
    deal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_supply_offers(db, user=current_user, deal_id=deal_id)


@router.post("/supply-offers/{offer_id}/confirm", response_model=SupplyOfferResponse)
def confirm_supply_offer(
    offer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.domain.models import Deal, SupplyOffer

    offer = db.get(SupplyOffer, offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supply offer not found")
    deal = db.get(Deal, offer.deal_id)
    if deal.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supply offer not found")
    offer.user_confirmed = True
    offer.status = "CONFIRMED"
    from app.services.configuration import mark_configurations_stale_for_supply_offer

    mark_configurations_stale_for_supply_offer(
        db,
        supply_offer_id=offer.id,
        reason="Supply offer confirmed; configuration inputs changed",
    )
    db.commit()
    db.refresh(offer)
    return offer
