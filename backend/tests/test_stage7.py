import pytest
from decimal import Decimal

from app.domain.enums import DealDirection, OpportunityType, SupplierLeadMatchStatus
from app.domain.models import Product

pytestmark = pytest.mark.usefixtures("setup_database")


def _sn500_product_id(auth_client) -> str:
    products = auth_client.get("/products").json()
    return next(p["id"] for p in products if p["normalized_name"] == "SN500")


def _create_buyer_need(auth_client, product_id: str) -> dict:
    return auth_client.post(
        "/opportunities",
        json={
            "title": "Buyer need SN500 Rotterdam",
            "normalized_product_id": product_id,
            "raw_product_name": "Base Oil SN500",
            "quantity_min": "80",
            "quantity_max": "120",
            "quantity_unit": "MT",
            "destination_hint": "Rotterdam",
            "buyer_or_supplier_hint": "North Sea Refinery",
        },
    ).json()


def test_supplier_led_full_flow(auth_client):
    product_id = _sn500_product_id(auth_client)
    buyer = _create_buyer_need(auth_client, product_id)

    supplier = auth_client.post(
        "/opportunities/supplier-led",
        json={
            "title": "Gulf SN500 availability",
            "normalized_product_id": product_id,
            "raw_product_name": "Base Oil SN500",
            "quantity_min": "100",
            "quantity_max": "100",
            "quantity_unit": "MT",
            "origin_hint": "Jebel Ali",
            "buyer_or_supplier_hint": "Gulf Base Oil",
            "unit_price": "850",
            "currency": "USD",
            "incoterm": "FOB",
            "origin": "Jebel Ali",
        },
    )
    assert supplier.status_code == 201
    supplier_id = supplier.json()["id"]
    assert supplier.json()["type"] == OpportunityType.SUPPLIER_OFFER.value

    detail = auth_client.get(f"/opportunities/{supplier_id}/supplier-lead")
    assert detail.status_code == 200
    assert detail.json()["context"]["unit_price"] == "850.000000"

    matches = auth_client.post(f"/opportunities/{supplier_id}/match-buyer-needs")
    assert matches.status_code == 200
    match_list = matches.json()
    assert len(match_list) >= 1
    top = match_list[0]
    assert float(top["score"]) >= 30
    assert buyer["id"] in {m["matched_opportunity_id"] for m in match_list}

    route = auth_client.post(f"/supplier-lead-matches/{top['id']}/build-route")
    assert route.status_code == 200
    route_data = route.json()["route_proposal"]
    assert route_data["origin"] == "Jebel Ali"
    assert route_data["destination"] == "Rotterdam"
    assert route_data["executable"] is True
    assert route.json()["market_comparison"]["confirmation_level"] == "ESTIMATE"

    outreach = auth_client.post(f"/supplier-lead-matches/{top['id']}/draft-outreach")
    assert outreach.status_code == 200
    assert outreach.json()["status"] == SupplierLeadMatchStatus.OUTREACH_DRAFTED.value
    assert "Indicative offer" in outreach.json()["outreach_subject"]
    assert "non-binding" in outreach.json()["outreach_body"].lower()

    deal = auth_client.post(f"/opportunities/{supplier_id}/convert").json()
    assert deal["direction"] == DealDirection.SUPPLIER_LED.value


def test_supplier_led_rejects_buyer_opportunity(auth_client):
    product_id = _sn500_product_id(auth_client)
    buyer = _create_buyer_need(auth_client, product_id)

    response = auth_client.post(f"/opportunities/{buyer['id']}/match-buyer-needs")
    assert response.status_code == 400


def test_supplier_led_from_supply_offer(auth_client, db):
    from sqlalchemy import select

    from app.domain.models import SupplyOffer
    from app.security.auth import ensure_admin_user
    from app.services.opportunity import convert_opportunity_to_deal, create_buyer_led_opportunity

    admin = ensure_admin_user(db)
    product = db.scalar(select(Product).where(Product.normalized_name == "SN500"))
    opp = create_buyer_led_opportunity(
        db,
        user=admin,
        title="Deal for supply offer",
        normalized_product_id=product.id,
    )
    deal = convert_opportunity_to_deal(db, user=admin, opportunity=opp)
    offer = SupplyOffer(
        deal_id=deal.id,
        product_name="Base Oil SN500",
        available_quantity=Decimal("100"),
        quantity_unit="MT",
        price=Decimal("840"),
        currency="USD",
        incoterm="FOB",
        origin="Jebel Ali",
        user_confirmed=True,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)

    created = auth_client.post(
        f"/supply-offers/{offer.id}/supplier-led",
        json={"title": "From confirmed offer"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["type"] == OpportunityType.SUPPLIER_OFFER.value
    assert body["title"] == "From confirmed offer"

    detail = auth_client.get(f"/opportunities/{body['id']}/supplier-lead").json()
    assert detail["context"]["supply_offer_id"] == str(offer.id)
    assert detail["context"]["unit_price"] == "840.000000"
