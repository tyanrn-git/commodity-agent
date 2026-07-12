import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import AuditAction, DisclosureStatus
from app.domain.models import Counterparty, Deal, DealParty, User
from app.services.audit import log_audit
from app.services.counterparty import get_counterparty


def add_deal_party(
    db: Session,
    *,
    user: User,
    deal: Deal,
    counterparty_id: uuid.UUID,
    role: str,
    disclosure_status: str = DisclosureStatus.HIDDEN.value,
    selected_for_contact: bool = True,
) -> DealParty:
    if deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    counterparty = get_counterparty(db, user=user, counterparty_id=counterparty_id)
    existing = db.scalar(
        select(DealParty).where(
            DealParty.deal_id == deal.id,
            DealParty.counterparty_id == counterparty.id,
            DealParty.role == role,
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Deal party already exists")

    party = DealParty(
        deal_id=deal.id,
        counterparty_id=counterparty.id,
        role=role,
        disclosure_status=disclosure_status,
        verification_status=counterparty.verification_status,
        selected_for_contact=selected_for_contact,
    )
    db.add(party)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="DealParty",
        entity_id=party.id,
        new_value={
            "deal_id": str(deal.id),
            "counterparty_id": str(counterparty.id),
            "role": role,
        },
    )
    db.commit()
    party = db.scalars(
        select(DealParty)
        .where(DealParty.id == party.id)
        .options(joinedload(DealParty.counterparty).joinedload(Counterparty.contacts))
    ).unique().one()
    return party


def list_deal_parties(db: Session, *, user: User, deal_id: uuid.UUID) -> list[DealParty]:
    deal = db.scalar(select(Deal).where(Deal.id == deal_id, Deal.owner_id == user.id))
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return list(
        db.scalars(
            select(DealParty)
            .where(DealParty.deal_id == deal_id)
            .options(joinedload(DealParty.counterparty).joinedload(Counterparty.contacts))
            .order_by(DealParty.created_at.asc())
        ).unique()
    )


def update_deal_party(
    db: Session, *, user: User, party: DealParty, data: dict
) -> DealParty:
    deal = db.get(Deal, party.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal party not found")

    for key, value in data.items():
        if value is not None and hasattr(party, key):
            setattr(party, key, value)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="DealParty",
        entity_id=party.id,
        new_value=data,
    )
    db.commit()
    db.refresh(party)
    return party
