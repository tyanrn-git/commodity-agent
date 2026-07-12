import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import (
    ApprovalStatus,
    AuditAction,
    BindingClass,
    ConfigurationStatus,
    DealPartyRole,
    DisclosureStatus,
    OfferStatus,
)
from app.domain.models import (
    ApprovalRequest,
    Contact,
    Counterparty,
    Deal,
    DealParty,
    FulfilmentConfiguration,
    Offer,
    User,
)
from app.services.audit import log_audit
from app.services.configuration import get_configuration
from app.services.formatting import format_amount, format_quantity


def _snapshot_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _active_offer_approval(db: Session, offer: Offer) -> ApprovalRequest | None:
    return db.scalar(
        select(ApprovalRequest)
        .where(ApprovalRequest.offer_id == offer.id)
        .order_by(ApprovalRequest.created_at.desc())
        .limit(1)
    )


def _build_recipients(party: DealParty) -> list[dict]:
    recipients = []
    if party.counterparty:
        for contact in party.counterparty.contacts:
            if contact.email:
                recipients.append(
                    {
                        "email": contact.email,
                        "name": contact.full_name or party.counterparty.trade_name or party.counterparty.legal_name,
                        "deal_party_id": str(party.id),
                    }
                )
                break
    return recipients


def _compliance_warnings(party: DealParty) -> list[str]:
    warnings = []
    counterparty = party.counterparty
    if counterparty is None:
        warnings.append("missing_counterparty")
        return warnings
    if counterparty.compliance_review_status == "NOT_REVIEWED":
        warnings.append("counterparty_not_reviewed")
    if party.disclosure_status == DisclosureStatus.HIDDEN.value:
        warnings.append("buyer_not_disclosed")
    if not _build_recipients(party):
        warnings.append("missing_recipient_email")
    return warnings


def _build_offer_body(*, deal: Deal, config: FulfilmentConfiguration, party: DealParty) -> tuple[str, str]:
    buyer_name = party.counterparty.trade_name or party.counterparty.legal_name if party.counterparty else "Buyer"
    lot = config.shipment_lots[0] if config.shipment_lots else None
    product = lot.product_name if lot else "product"
    qty = config.target_quantity or (lot.quantity if lot else "")
    unit = config.target_quantity_unit or (lot.quantity_unit if lot else "MT")
    destination = config.destination or deal.title
    price = config.sales_price_per_unit
    currency = config.sales_currency or deal.base_currency
    incoterm = lot.incoterm if lot else "CIF"

    subject = f"Commercial offer: {product} to {destination}"
    body = (
        f"Dear {buyer_name},\n\n"
        f"Please find our indicative commercial offer:\n\n"
        f"Product: {product}\n"
        f"Quantity: {format_quantity(qty, unit)}\n"
        f"Destination: {destination}\n"
        f"Incoterm: {incoterm}\n"
        f"Price: {format_amount(price)} {currency} per {unit}\n\n"
        f"This is an indicative offer subject to final confirmation.\n\n"
        f"Best regards"
    )
    return subject, body


def _configuration_payload(config: FulfilmentConfiguration) -> dict:
    return {
        "id": str(config.id),
        "name": config.name,
        "status": config.status,
        "is_stale": config.is_stale,
        "revenue": str(config.revenue),
        "total_cost": str(config.total_cost),
        "gross_margin": str(config.gross_margin),
        "cost_breakdown": config.cost_breakdown,
        "spec_match_summary": config.spec_match_summary,
    }


def get_offer(db: Session, *, user: User, offer_id: uuid.UUID) -> Offer:
    offer = db.scalar(
        select(Offer)
        .where(Offer.id == offer_id)
        .options(
            joinedload(Offer.target_deal_party).joinedload(DealParty.counterparty).joinedload(Counterparty.contacts),
            joinedload(Offer.configuration),
        )
    )
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    deal = db.get(Deal, offer.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    return offer


def list_offers(db: Session, *, user: User, deal_id: uuid.UUID) -> list[Offer]:
    deal = db.scalar(select(Deal).where(Deal.id == deal_id, Deal.owner_id == user.id))
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return list(
        db.scalars(
            select(Offer)
            .where(Offer.deal_id == deal_id)
            .options(joinedload(Offer.configuration), joinedload(Offer.target_deal_party))
            .order_by(Offer.created_at.desc())
        ).unique()
    )


def create_offer_from_configuration(
    db: Session,
    *,
    user: User,
    deal: Deal,
    configuration_id: uuid.UUID,
    target_deal_party_id: uuid.UUID,
) -> Offer:
    if deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    config = get_configuration(db, user=user, configuration_id=configuration_id)
    if config.deal_id != deal.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
    if config.is_stale:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Configuration is stale")
    if config.status not in {ConfigurationStatus.SELECTED.value, ConfigurationStatus.FEASIBLE.value}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configuration must be FEASIBLE or SELECTED",
        )

    party = db.scalar(
        select(DealParty)
        .where(DealParty.id == target_deal_party_id, DealParty.deal_id == deal.id)
        .options(joinedload(DealParty.counterparty).joinedload(Counterparty.contacts))
    )
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal party not found")
    if party.role != DealPartyRole.BUYER.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Offer target must be BUYER party")

    subject, body = _build_offer_body(deal=deal, config=config, party=party)
    economics_snapshot = {
        "revenue": str(config.revenue),
        "total_cost": str(config.total_cost),
        "gross_margin": str(config.gross_margin),
        "gross_margin_percent": str(config.gross_margin_percent),
        "cost_breakdown": config.cost_breakdown,
        "scenario": "CONFIRMED" if config.status == ConfigurationStatus.SELECTED.value else "CURRENT",
    }

    offer = Offer(
        deal_id=deal.id,
        configuration_id=config.id,
        target_deal_party_id=party.id,
        subject=subject,
        body=body,
        status=OfferStatus.DRAFT.value,
        configuration_snapshot=_configuration_payload(config),
        economics_snapshot=economics_snapshot,
        disclosure_snapshot={
            "disclosure_status": party.disclosure_status,
            "counterparty_name": party.counterparty.legal_name if party.counterparty else None,
            "show_supplier_identity": party.disclosure_status != DisclosureStatus.HIDDEN.value,
        },
        validity_until=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(offer)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="Offer",
        entity_id=offer.id,
        new_value={"deal_id": str(deal.id), "configuration_id": str(config.id)},
    )
    db.commit()
    return get_offer(db, user=user, offer_id=offer.id)


def build_offer_approval_preview(db: Session, *, offer: Offer) -> dict:
    party = offer.target_deal_party
    recipients = _build_recipients(party) if party else []
    warnings = _compliance_warnings(party) if party else ["missing_counterparty"]
    counterparty = party.counterparty if party else None
    config = offer.configuration
    return {
        "offer_id": str(offer.id),
        "status": offer.status,
        "subject": offer.subject,
        "body": offer.body,
        "recipients": recipients,
        "binding_class": BindingClass.COMMERCIAL_SENSITIVE.value,
        "compliance_warnings": warnings,
        "configuration_is_stale": config.is_stale if config else True,
        "economics_snapshot": offer.economics_snapshot,
        "disclosure_snapshot": offer.disclosure_snapshot,
        "counterparty": {
            "id": str(counterparty.id) if counterparty else None,
            "legal_name": counterparty.legal_name if counterparty else None,
            "compliance_review_status": counterparty.compliance_review_status if counterparty else None,
        },
        "can_submit": bool(recipients) and offer.subject and offer.body and not (config and config.is_stale),
    }


def update_offer(db: Session, *, user: User, offer: Offer, data: dict) -> Offer:
    deal = db.get(Deal, offer.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    if offer.status == OfferStatus.SENT.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Offer cannot be edited")

    content_changed = any(key in data and data[key] is not None for key in ("subject", "body"))
    if content_changed and offer.status in {
        OfferStatus.PENDING_APPROVAL.value,
        OfferStatus.APPROVED.value,
    }:
        approval = _active_offer_approval(db, offer)
        if approval:
            approval.approval_status = ApprovalStatus.INVALIDATED.value
        offer.status = OfferStatus.DRAFT.value

    for key in ("subject", "body"):
        if key in data and data[key] is not None:
            setattr(offer, key, data[key])

    db.commit()
    return get_offer(db, user=user, offer_id=offer.id)


def submit_offer_for_approval(db: Session, *, user: User, offer: Offer) -> Offer:
    deal = db.get(Deal, offer.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    if offer.status != OfferStatus.DRAFT.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Offer is not in DRAFT status")

    preview = build_offer_approval_preview(db, offer=offer)
    if not preview["can_submit"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Offer is incomplete or configuration stale")

    approval = ApprovalRequest(
        offer_id=offer.id,
        proposed_action="SEND_OFFER",
        exact_payload={"subject": offer.subject, "body": offer.body},
        recipients=preview["recipients"],
        disclosed_information=offer.disclosure_snapshot,
        binding_class=BindingClass.COMMERCIAL_SENSITIVE.value,
        risk_flags=preview["compliance_warnings"],
        compliance_warnings=preview["compliance_warnings"],
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        approval_status=ApprovalStatus.PENDING.value,
    )
    db.add(approval)
    offer.status = OfferStatus.PENDING_APPROVAL.value
    db.commit()
    return get_offer(db, user=user, offer_id=offer.id)


def approve_offer(db: Session, *, user: User, offer: Offer, acknowledge_warnings: bool = False) -> Offer:
    deal = db.get(Deal, offer.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    if offer.status != OfferStatus.PENDING_APPROVAL.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Offer is not pending approval")

    approval = _active_offer_approval(db, offer)
    if approval is None or approval.approval_status != ApprovalStatus.PENDING.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approval request missing")

    preview = build_offer_approval_preview(db, offer=offer)
    if preview["compliance_warnings"] and not acknowledge_warnings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Compliance warnings require acknowledgement",
        )

    if preview["configuration_is_stale"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Configuration is stale")

    approval.approval_status = ApprovalStatus.APPROVED.value
    approval.approved_at = datetime.now(timezone.utc)
    approval.approved_by_id = user.id
    approval.approved_snapshot_hash = _snapshot_hash(approval.exact_payload)
    offer.status = OfferStatus.APPROVED.value
    db.commit()
    return get_offer(db, user=user, offer_id=offer.id)


def delete_offer(db: Session, *, user: User, offer: Offer) -> None:
    deal = db.get(Deal, offer.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    if offer.status == OfferStatus.SENT.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sent offer cannot be deleted",
        )

    offer_id = offer.id
    deal_id = str(deal.id)
    status_value = offer.status
    db.delete(offer)
    log_audit(
        db,
        actor=user,
        action=AuditAction.DELETE,
        entity_type="Offer",
        entity_id=offer_id,
        old_value={"deal_id": deal_id, "status": status_value},
    )
    db.commit()
