import pytest
from sqlalchemy import select

from app.domain.enums import ConfigurationStatus, OfferStatus
from app.domain.models import Deal

pytestmark = pytest.mark.usefixtures("setup_database")


def _deal_with_configuration(auth_client, db):
    from app.config import settings
    from app.domain.models import Product, User

    user = db.scalar(select(User).where(User.email == settings.admin_email))
    product = db.scalar(select(Product).where(Product.normalized_name == "SN500"))
    from app.services.opportunity import create_buyer_led_opportunity, create_requirement

    opp = create_buyer_led_opportunity(db, user=user, title="Offer test")
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

    supplier = auth_client.post(
        "/counterparties",
        json={
            "legal_name": "Gulf Supplier",
            "organization_type": "PRODUCER",
            "primary_domain": "example.com",
            "website": "https://example.com",
        },
    ).json()
    auth_client.post(
        f"/counterparties/{supplier['id']}/contacts",
        json={"full_name": "Sales", "email": "sales@example.com", "is_primary": True},
    )
    supplier_party = auth_client.post(
        f"/deals/{deal_id}/parties",
        json={"counterparty_id": supplier["id"], "role": "SUPPLIER"},
    ).json()["id"]

    buyer = auth_client.post(
        "/counterparties",
        json={
            "legal_name": "EU Buyer BV",
            "organization_type": "TRADER",
            "primary_domain": "buyer.example.com",
            "website": "https://buyer.example.com",
        },
    ).json()
    auth_client.post(
        f"/counterparties/{buyer['id']}/contacts",
        json={"full_name": "Buyer", "email": "buyer@example.com", "is_primary": True},
    )
    buyer_party = auth_client.post(
        f"/deals/{deal_id}/parties",
        json={"counterparty_id": buyer["id"], "role": "BUYER"},
    ).json()["id"]

    rfq = auth_client.post(
        f"/deals/{deal_id}/rfqs",
        json={"target_deal_party_id": supplier_party, "rfq_type": "PRODUCT"},
    ).json()
    eml = (
        b"Subject: Re: RFQ\r\nFrom: sales@example.com\r\nTo: trader@example.com\r\n\r\n"
        b"Base Oil SN500 100 MT CIF Rotterdam USD 850/MT"
    )
    imported = auth_client.post(
        "/inbox/import-eml",
        files={"file": ("reply.eml", eml, "message/rfc822")},
        data={"deal_id": deal_id, "rfq_id": rfq["id"]},
    ).json()
    offer_id = imported["supply_offer"]["id"]
    auth_client.post(f"/supply-offers/{offer_id}/confirm")

    config = auth_client.post(
        f"/deals/{deal_id}/configurations",
        json={
            "supply_offer_id": offer_id,
            "name": "Offer config",
            "sales_price_per_unit": 920,
        },
    ).json()
    auth_client.post(f"/configurations/{config['id']}/confirm")

    return deal_id, config["id"], buyer_party


def test_offer_lifecycle(auth_client, db):
    deal_id, config_id, buyer_party = _deal_with_configuration(auth_client, db)

    created = auth_client.post(
        f"/deals/{deal_id}/offers",
        json={"configuration_id": config_id, "target_deal_party_id": buyer_party},
    )
    assert created.status_code == 201
    offer_id = created.json()["id"]
    assert created.json()["status"] == OfferStatus.DRAFT.value
    assert created.json()["economics_snapshot"]["gross_margin"]
    body = created.json()["body"]
    assert "100 MT" in body
    assert "920" in body
    assert "gross margin" not in body.lower()

    submit = auth_client.post(f"/offers/{offer_id}/submit-for-approval")
    assert submit.status_code == 200
    assert submit.json()["status"] == OfferStatus.PENDING_APPROVAL.value

    approve = auth_client.post(
        f"/offers/{offer_id}/approve",
        json={"acknowledge_warnings": True},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == OfferStatus.APPROVED.value

    send = auth_client.post(f"/offers/{offer_id}/send")
    assert send.status_code == 200
    assert send.json()["status"] == OfferStatus.SENT.value


def test_offer_edit_invalidates_approval(auth_client, db):
    deal_id, config_id, buyer_party = _deal_with_configuration(auth_client, db)
    offer = auth_client.post(
        f"/deals/{deal_id}/offers",
        json={"configuration_id": config_id, "target_deal_party_id": buyer_party},
    ).json()
    auth_client.post(f"/offers/{offer['id']}/submit-for-approval")
    auth_client.post(f"/offers/{offer['id']}/approve", json={"acknowledge_warnings": True})

    patched = auth_client.patch(
        f"/offers/{offer['id']}",
        json={"body": "Updated offer body"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == OfferStatus.DRAFT.value

    send = auth_client.post(f"/offers/{offer['id']}/send")
    assert send.status_code == 400


def test_delete_offer_draft(auth_client, db):
    deal_id, config_id, buyer_party = _deal_with_configuration(auth_client, db)
    created = auth_client.post(
        f"/deals/{deal_id}/offers",
        json={"configuration_id": config_id, "target_deal_party_id": buyer_party},
    )
    offer_id = created.json()["id"]

    deleted = auth_client.delete(f"/offers/{offer_id}")
    assert deleted.status_code == 204
    assert auth_client.get(f"/offers/{offer_id}").status_code == 404
    assert auth_client.get(f"/deals/{deal_id}/offers").json() == []


def test_delete_sent_offer_forbidden(auth_client, db):
    deal_id, config_id, buyer_party = _deal_with_configuration(auth_client, db)
    offer_id = auth_client.post(
        f"/deals/{deal_id}/offers",
        json={"configuration_id": config_id, "target_deal_party_id": buyer_party},
    ).json()["id"]
    auth_client.post(f"/offers/{offer_id}/submit-for-approval")
    auth_client.post(f"/offers/{offer_id}/approve", json={"acknowledge_warnings": True})
    auth_client.post(f"/offers/{offer_id}/send")

    deleted = auth_client.delete(f"/offers/{offer_id}")
    assert deleted.status_code == 400
