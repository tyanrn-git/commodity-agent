import pytest
from sqlalchemy import select

from app.domain.enums import ConfigurationStatus, EconomicsScenario, SpecMatchResult
from app.domain.models import Deal, FulfilmentConfiguration, SupplyOffer
from app.services.opportunity import create_buyer_led_opportunity, create_requirement
from app.services.spec_matcher import build_spec_summary

pytestmark = pytest.mark.usefixtures("setup_database")


def _deal_with_confirmed_offer(auth_client, db):
    from app.config import settings
    from app.domain.models import Product, User

    user = db.scalar(select(User).where(User.email == settings.admin_email))
    product = db.scalar(select(Product).where(Product.normalized_name == "SN500"))
    opp = create_buyer_led_opportunity(db, user=user, title="Economics test")
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
    return deal_id, offer_id


def test_spec_matcher_sn500_match():
    summary = build_spec_summary("SN500", "Base Oil SN500")
    assert summary["overall"] == SpecMatchResult.MATCH.value
    assert summary["health_status"] == "OK"


def test_create_configuration_and_calculate(auth_client, db):
    deal_id, offer_id = _deal_with_confirmed_offer(auth_client, db)
    response = auth_client.post(
        f"/deals/{deal_id}/configurations",
        json={
            "supply_offer_id": offer_id,
            "name": "Gulf CIF Rotterdam",
            "sales_price_per_unit": 920,
            "sales_currency": "USD",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] in {ConfigurationStatus.FEASIBLE.value, ConfigurationStatus.INCOMPLETE.value}
    assert data["revenue"] == "92000.000000"
    assert data["total_cost"] == "85000.000000"
    assert data["gross_margin"] == "7000.000000"
    assert len(data["shipment_lots"]) == 1
    assert data["spec_match_summary"]["overall"] == SpecMatchResult.MATCH.value


def test_add_freight_recalculates_margin(auth_client, db):
    deal_id, offer_id = _deal_with_confirmed_offer(auth_client, db)
    created = auth_client.post(
        f"/deals/{deal_id}/configurations",
        json={
            "supply_offer_id": offer_id,
            "name": "With freight",
            "sales_price_per_unit": 920,
        },
    ).json()
    config_id = created["id"]

    leg = auth_client.post(
        f"/configurations/{config_id}/transport-legs",
        json={
            "origin": "Jebel Ali",
            "destination": "Rotterdam",
            "cost": 5000,
            "currency": "USD",
            "mode": "SEA",
        },
    )
    assert leg.status_code == 201

    updated = auth_client.post(f"/configurations/{config_id}/recalculate").json()
    assert updated["cost_breakdown"]["main_freight"] == "5000.000000"
    assert updated["gross_margin"] == "2000.000000"

    leg2 = auth_client.post(
        f"/configurations/{config_id}/transport-legs",
        json={
            "origin": "Jebel Ali",
            "destination": "Rotterdam",
            "cost": 3000,
            "currency": "USD",
            "mode": "SEA",
        },
    )
    assert leg2.status_code == 201
    replaced = auth_client.post(f"/configurations/{config_id}/recalculate").json()
    assert replaced["cost_breakdown"]["main_freight"] == "3000.000000"
    assert replaced["gross_margin"] == "4000.000000"
    assert len(replaced["transport_legs"]) == 1


def test_service_quote_upsert_replaces(auth_client, db):
    deal_id, offer_id = _deal_with_confirmed_offer(auth_client, db)
    created = auth_client.post(
        f"/deals/{deal_id}/configurations",
        json={
            "supply_offer_id": offer_id,
            "name": "Services",
            "sales_price_per_unit": 920,
        },
    ).json()
    config_id = created["id"]

    auth_client.post(
        f"/configurations/{config_id}/service-quotes",
        json={"quote_type": "INSURANCE", "amount": 1000, "currency": "USD"},
    )
    auth_client.post(
        f"/configurations/{config_id}/service-quotes",
        json={"quote_type": "INSURANCE", "amount": 1500, "currency": "USD"},
    )
    updated = auth_client.post(f"/configurations/{config_id}/recalculate").json()
    assert updated["cost_breakdown"]["insurance"] == "1500.000000"
    assert len(updated["service_quotes"]) == 1


def test_confirm_scenario_snapshot(auth_client, db):
    deal_id, offer_id = _deal_with_confirmed_offer(auth_client, db)
    created = auth_client.post(
        f"/deals/{deal_id}/configurations",
        json={
            "supply_offer_id": offer_id,
            "name": "Confirm me",
            "sales_price_per_unit": 920,
        },
    ).json()
    confirmed = auth_client.post(f"/configurations/{created['id']}/confirm").json()
    assert confirmed["status"] == ConfigurationStatus.SELECTED.value
    scenarios = [s["scenario"] for s in confirmed["economics_snapshots"]]
    assert EconomicsScenario.CURRENT.value in scenarios
    assert EconomicsScenario.CONFIRMED.value in scenarios


def test_supply_offer_confirm_marks_configuration_stale(auth_client, db):
    deal_id, offer_id = _deal_with_confirmed_offer(auth_client, db)
    created = auth_client.post(
        f"/deals/{deal_id}/configurations",
        json={
            "supply_offer_id": offer_id,
            "name": "Stale test",
            "sales_price_per_unit": 920,
        },
    ).json()
    config_id = created["id"]
    assert created["is_stale"] is False

    offer = db.get(SupplyOffer, offer_id)
    offer.price = 860
    db.commit()

    auth_client.post(f"/supply-offers/{offer_id}/confirm")
    config = auth_client.get(f"/configurations/{config_id}").json()
    assert config["is_stale"] is True
    assert "Supply offer" in (config["stale_reason"] or "")
