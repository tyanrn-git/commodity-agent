#!/usr/bin/env python3
"""Reset and recreate the demo deal flow for manual testing."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import delete, select

from app.config import settings
from app.db.session import SessionLocal
from app.domain.enums import DealStage
from app.domain.models import (
    ApprovalRequest,
    CommunicationThread,
    Counterparty,
    Deal,
    DealParty,
    EconomicsSnapshot,
    Evidence,
    FulfilmentConfiguration,
    Message,
    Offer,
    Product,
    Requirement,
    RFQ,
    ServiceQuote,
    ShipmentLot,
    SupplyOffer,
    TransportLeg,
    User,
)
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.configuration import (
    confirm_configuration_scenario,
    create_configuration_from_supply_offer,
    get_configuration,
    recalculate_configuration,
    upsert_transport_leg,
)
from app.services.counterparty import mark_compliance_reviewed, seed_demo_counterparties
from app.services.deal_party import add_deal_party
from app.services.email_loop import _process_inbound, send_approved_rfq
from app.services.offer import create_offer_from_configuration
from app.services.opportunity import create_requirement, seed_products
from app.services.quote_extraction import parse_eml_headers_and_body
from app.services.research import seed_product_specifications
from app.services.rfq import approve_rfq, create_rfq, seed_rfq_templates, submit_rfq_for_approval

DEMO_EML = b"""Subject: Re: RFQ: Base Oil SN500 export availability
From: sales@gulfbasoil.example.com
To: trader@example.com
In-Reply-To: <rfq-outbound>

Dear Trader,

Product: Base Oil SN500
Quantity: 100 MT
Incoterm: CIF Rotterdam
Price: USD 850 per MT
Loading: Jebel Ali, UAE

Best regards,
Gulf Base Oil
"""


def _reset_deal(db, deal_id: uuid.UUID) -> None:
    db.execute(
        delete(ApprovalRequest).where(
            ApprovalRequest.offer_id.in_(select(Offer.id).where(Offer.deal_id == deal_id))
        )
    )
    db.execute(delete(Offer).where(Offer.deal_id == deal_id))

    config_ids = select(FulfilmentConfiguration.id).where(FulfilmentConfiguration.deal_id == deal_id)
    db.execute(delete(EconomicsSnapshot).where(EconomicsSnapshot.configuration_id.in_(config_ids)))
    db.execute(delete(ServiceQuote).where(ServiceQuote.configuration_id.in_(config_ids)))
    db.execute(delete(TransportLeg).where(TransportLeg.configuration_id.in_(config_ids)))
    db.execute(delete(ShipmentLot).where(ShipmentLot.configuration_id.in_(config_ids)))
    db.execute(delete(FulfilmentConfiguration).where(FulfilmentConfiguration.deal_id == deal_id))

    db.execute(delete(SupplyOffer).where(SupplyOffer.deal_id == deal_id))

    rfq_ids = select(RFQ.id).where(RFQ.deal_id == deal_id)
    db.execute(delete(ApprovalRequest).where(ApprovalRequest.rfq_id.in_(rfq_ids)))
    thread_ids = select(CommunicationThread.id).where(CommunicationThread.deal_id == deal_id)
    db.execute(delete(Message).where(Message.thread_id.in_(thread_ids)))
    db.execute(delete(CommunicationThread).where(CommunicationThread.deal_id == deal_id))
    db.execute(delete(RFQ).where(RFQ.deal_id == deal_id))

    req_ids = select(Requirement.id).where(Requirement.deal_id == deal_id)
    db.execute(delete(Evidence).where(Evidence.requirement_id.in_(req_ids)))
    db.execute(delete(Requirement).where(Requirement.deal_id == deal_id))
    db.execute(delete(DealParty).where(DealParty.deal_id == deal_id))
    db.flush()


def _counterparty_by_name(db, user: User, legal_name: str) -> Counterparty:
    counterparty = db.scalar(
        select(Counterparty).where(
            Counterparty.owner_id == user.id,
            Counterparty.legal_name == legal_name,
        )
    )
    if counterparty is None:
        raise RuntimeError(f"Counterparty not found: {legal_name}")
    return counterparty


def seed_demo_flow(db, *, deal_id: uuid.UUID | None = None) -> dict:
    user = db.scalar(select(User).where(User.email == settings.admin_email))
    if user is None:
        raise RuntimeError(f"Admin user not found: {settings.admin_email}")

    seed_products(db)
    seed_product_specifications(db)
    seed_rfq_templates(db)
    seed_demo_counterparties(db, user)

    if deal_id is None:
        deal = db.scalar(select(Deal).where(Deal.owner_id == user.id).order_by(Deal.created_at.desc()))
    else:
        deal = db.get(Deal, deal_id)
    if deal is None:
        raise RuntimeError("No deal found to seed")

    _reset_deal(db, deal.id)
    deal.title = "Base Oil SN500 → Rotterdam"
    deal.stage = DealStage.CONFIGURATION.value
    db.flush()

    product = db.scalar(select(Product).where(Product.normalized_name == "SN500"))
    if product is None:
        raise RuntimeError("Product SN500 not found")

    create_requirement(
        db,
        user=user,
        deal=deal,
        product_id=product.id,
        quantity_min=Decimal("100"),
        quantity_unit="MT",
        destination="Rotterdam",
        requested_incoterm="CIF",
        user_confirmed=True,
    )

    gulf = _counterparty_by_name(db, user, "Gulf Base Oil Refinery LLC")
    buyer = _counterparty_by_name(db, user, "Rotterdam Base Oils BV")
    mark_compliance_reviewed(db, user=user, counterparty=gulf)
    mark_compliance_reviewed(db, user=user, counterparty=buyer)

    supplier_party = add_deal_party(
        db, user=user, deal=deal, counterparty_id=gulf.id, role="SUPPLIER"
    )
    buyer_party = add_deal_party(
        db, user=user, deal=deal, counterparty_id=buyer.id, role="BUYER"
    )

    rfq = create_rfq(
        db,
        user=user,
        deal=deal,
        target_deal_party_id=supplier_party.id,
        rfq_type="PRODUCT",
    )
    submit_rfq_for_approval(db, user=user, rfq=rfq)
    approve_rfq(db, user=user, rfq=rfq, acknowledge_warnings=True)

    storage = LocalFilesystemStorage()
    rfq, outbound = send_approved_rfq(db, user=user, rfq=rfq, storage=storage)

    eml = DEMO_EML.replace(
        b"<rfq-outbound>",
        (outbound.mailbox_message_id or f"rfq-{rfq.id}").encode(),
    )
    parsed = parse_eml_headers_and_body(eml)
    _, supply_offer = _process_inbound(
        db,
        user=user,
        content=eml,
        filename="demo-supplier-reply-sn500.eml",
        parsed=parsed,
        storage=storage,
        deal_id=deal.id,
        rfq_id=rfq.id,
        in_reply_to=outbound.mailbox_message_id,
    )
    if supply_offer is None:
        raise RuntimeError("Failed to extract supply offer from demo reply")

    supply_offer.user_confirmed = True
    supply_offer.status = "CONFIRMED"
    db.flush()

    config = create_configuration_from_supply_offer(
        db,
        user=user,
        deal=deal,
        supply_offer_id=supply_offer.id,
        name="Вариант поставки",
        sales_price_per_unit=920,
    )
    upsert_transport_leg(
        db,
        user=user,
        configuration=config,
        data={
            "mode": "SEA",
            "origin": "Jebel Ali",
            "destination": "Rotterdam",
            "cost": 4000,
            "currency": "USD",
        },
    )
    config = get_configuration(db, user=user, configuration_id=config.id)
    config = recalculate_configuration(db, user=user, configuration=config)
    config = confirm_configuration_scenario(db, user=user, configuration=config)

    offer = create_offer_from_configuration(
        db,
        user=user,
        deal=deal,
        configuration_id=config.id,
        target_deal_party_id=buyer_party.id,
    )

    db.commit()

    return {
        "deal_id": str(deal.id),
        "deal_number": deal.deal_number,
        "rfq_id": str(rfq.id),
        "rfq_status": rfq.status,
        "supply_offer_id": str(supply_offer.id),
        "configuration_id": str(config.id),
        "configuration_status": config.status,
        "offer_id": str(offer.id),
        "offer_status": offer.status,
        "gross_margin_in_body": "gross margin" in (offer.body or "").lower(),
    }


def main() -> None:
    db = SessionLocal()
    try:
        result = seed_demo_flow(db)
        print("Demo flow recreated:")
        for key, value in result.items():
            print(f"  {key}: {value}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
