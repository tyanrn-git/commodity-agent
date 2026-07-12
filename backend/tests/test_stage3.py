import pytest
from sqlalchemy import select

from app.domain.enums import DealRiskFlag, MessageLinkStatus, RFQStatus
from app.domain.models import Deal, Message, SupplyOffer
from app.integrations.email.base import InboundEmail
from app.integrations.email.mock_provider import MockEmailProvider
from app.services.opportunity import create_buyer_led_opportunity, create_requirement

pytestmark = pytest.mark.usefixtures("setup_database")


def _eml_bytes(subject: str, body: str, from_addr: str = "supplier@example.com", in_reply_to: str = "") -> bytes:
    headers = (
        f"Subject: {subject}\r\n"
        f"From: {from_addr}\r\n"
        f"To: trader@example.com\r\n"
    )
    if in_reply_to:
        headers += f"In-Reply-To: {in_reply_to}\r\n"
    return (headers + "\r\n" + body).encode()


def _deal_with_party_and_rfq(auth_client, db):
    from app.config import settings
    from app.domain.models import Product, User

    user = db.scalar(select(User).where(User.email == settings.admin_email))
    product = db.scalar(select(Product).where(Product.normalized_name == "SN500"))
    opp = create_buyer_led_opportunity(db, user=user, title="Email loop test")
    auth_client.post(f"/opportunities/{opp.id}/convert")
    deal_id = auth_client.get("/deals").json()[0]["id"]
    deal = db.get(Deal, deal_id)
    create_requirement(
        db,
        user=user,
        deal=deal,
        product_id=product.id,
        quantity_min=100,
        quantity_unit="MT",
        destination="Rotterdam",
        requested_incoterm="CIF",
    )

    cp = auth_client.post(
        "/counterparties",
        json={
            "legal_name": "Gulf Supplier",
            "organization_type": "PRODUCER",
            "primary_domain": "example.com",
            "website": "https://example.com",
        },
    ).json()
    auth_client.post(
        f"/counterparties/{cp['id']}/contacts",
        json={"full_name": "Sales", "email": "sales@example.com", "is_primary": True},
    )
    party_id = auth_client.post(
        f"/deals/{deal_id}/parties",
        json={"counterparty_id": cp["id"], "role": "SUPPLIER"},
    ).json()["id"]
    rfq = auth_client.post(
        f"/deals/{deal_id}/rfqs",
        json={"target_deal_party_id": party_id, "rfq_type": "PRODUCT"},
    ).json()
    auth_client.post(f"/rfqs/{rfq['id']}/submit-for-approval")
    auth_client.post(f"/rfqs/{rfq['id']}/approve", json={"acknowledge_warnings": True})
    return deal_id, rfq["id"]


def test_send_approved_rfq(auth_client, db):
    _, rfq_id = _deal_with_party_and_rfq(auth_client, db)
    response = auth_client.post(f"/rfqs/{rfq_id}/send")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == RFQStatus.SENT.value
    assert data["message_id"]

    inbox = auth_client.get("/inbox")
    assert inbox.status_code == 200
    assert len(inbox.json()) >= 1


def test_import_reply_creates_supply_offer(auth_client, db):
    deal_id, rfq_id = _deal_with_party_and_rfq(auth_client, db)
    send = auth_client.post(f"/rfqs/{rfq_id}/send").json()
    mailbox_message_id = send["mailbox_message_id"]

    eml = _eml_bytes(
        "Re: RFQ SN500",
        "Base Oil SN500 100 MT CIF Rotterdam USD 850/MT TT payment",
        in_reply_to=mailbox_message_id,
    )
    response = auth_client.post(
        "/inbox/import-eml",
        files={"file": ("reply.eml", eml, "message/rfc822")},
        data={"deal_id": deal_id, "rfq_id": rfq_id},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["supply_offer"] is not None
    assert payload["supply_offer"]["price"] in {"850", "850.000000"}
    assert payload["supply_offer"]["currency"] == "USD"

    rfq = auth_client.get(f"/rfqs/{rfq_id}").json()
    assert rfq["status"] in {RFQStatus.ANSWERED.value, RFQStatus.PARTIALLY_ANSWERED.value}

    offers = auth_client.get(f"/deals/{deal_id}/supply-offers")
    assert offers.status_code == 200
    assert len(offers.json()) >= 1


def test_unlinked_import_and_manual_link(auth_client, db):
    deal_id, rfq_id = _deal_with_party_and_rfq(auth_client, db)
    eml = _eml_bytes("Unknown reply", "Base Oil SN500 100 MT CIF USD 850")
    response = auth_client.post(
        "/inbox/import-eml",
        files={"file": ("unknown.eml", eml, "message/rfc822")},
    )
    assert response.status_code == 200
    message_id = response.json()["message"]["id"]
    assert response.json()["message"]["link_status"] == MessageLinkStatus.UNLINKED.value

    unlinked = auth_client.get("/inbox/unlinked")
    assert any(m["id"] == message_id for m in unlinked.json())

    linked = auth_client.post(f"/messages/{message_id}/link", json={"rfq_id": rfq_id})
    assert linked.status_code == 200
    assert linked.json()["supply_offer"]["incoterm"] == "CIF"


def test_delete_rfq_draft(auth_client, db):
    deal_id, rfq_id = _deal_with_party_and_rfq(auth_client, db)

    deleted = auth_client.delete(f"/rfqs/{rfq_id}")
    assert deleted.status_code == 204
    assert auth_client.get(f"/rfqs/{rfq_id}").status_code == 404
    assert auth_client.get(f"/deals/{deal_id}/rfqs").json() == []


def test_delete_sent_rfq_forbidden(auth_client, db):
    _, rfq_id = _deal_with_party_and_rfq(auth_client, db)
    auth_client.post(f"/rfqs/{rfq_id}/send")

    deleted = auth_client.delete(f"/rfqs/{rfq_id}")
    assert deleted.status_code == 400


def test_bank_details_changed_blocks_send(auth_client, db):
    deal_id, rfq_id = _deal_with_party_and_rfq(auth_client, db)
    deal = db.get(Deal, deal_id)
    deal.risk_flags = [DealRiskFlag.BANK_DETAILS_CHANGED.value]
    db.commit()

    response = auth_client.post(f"/rfqs/{rfq_id}/send")
    assert response.status_code == 400
    assert "BANK_DETAILS_CHANGED" in response.text


def test_bank_details_in_reply_sets_flag(auth_client, db):
    deal_id, rfq_id = _deal_with_party_and_rfq(auth_client, db)
    eml = _eml_bytes(
        "Re: quote",
        "Please send payment to new bank account IBAN DE89370400440532013000",
    )
    auth_client.post(
        "/inbox/import-eml",
        files={"file": ("bank.eml", eml, "message/rfc822")},
        data={"deal_id": deal_id, "rfq_id": rfq_id},
    )
    deal = db.get(Deal, deal_id)
    assert DealRiskFlag.BANK_DETAILS_CHANGED.value in (deal.risk_flags or [])
