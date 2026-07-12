import pytest
from sqlalchemy import select

from app.domain.enums import ChainViabilityStatus, OutreachStatus, ResearchCampaignStatus
from app.domain.models import CommercialFact, Product, ProductSpecificationProfile, ResearchCampaign

pytestmark = pytest.mark.usefixtures("setup_database")


def _eml_bytes(body: str) -> bytes:
    return (
        "Subject: Re: SN500 quote\r\n"
        "From: supplier@example.com\r\n"
        "To: trader@example.com\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        f"{body}"
    ).encode()


def _create_campaign(auth_client, db):
    product = db.scalar(select(Product).where(Product.normalized_name == "SN500"))
    assert product is not None
    response = auth_client.post(
        "/research-campaigns",
        json={
            "name": "SN500 EU chain pilot",
            "product_ids": [str(product.id)],
            "target_buy_regions": ["EU", "Rotterdam"],
            "target_sell_regions": ["Middle East"],
            "research_hypothesis": "Test chain discovery",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_product_specifications_seeded(db):
    product = db.scalar(select(Product).where(Product.normalized_name == "SN500"))
    assert product is not None
    specs = list(
        db.scalars(
            select(ProductSpecificationProfile).where(ProductSpecificationProfile.product_id == product.id)
        )
    )
    assert len(specs) >= 3


def test_research_campaign_create_and_run(auth_client, db):
    campaign = _create_campaign(auth_client, db)
    assert campaign["status"] == ResearchCampaignStatus.DRAFT.value
    assert campaign["viability_status"] == ChainViabilityStatus.UNKNOWN.value

    run = auth_client.post(f"/research-campaigns/{campaign['id']}/run")
    assert run.status_code == 200
    data = run.json()
    assert data["status"] == ResearchCampaignStatus.ACTIVE.value

    leads = auth_client.get(f"/research-campaigns/{campaign['id']}/leads")
    assert leads.status_code == 200
    lead_items = leads.json()
    assert len(lead_items) == 7
    buyer_count = sum(1 for l in lead_items if "BUYER" in l["lead_type"])
    supplier_count = sum(1 for l in lead_items if l["lead_type"] == "SUPPLIER")
    route_count = sum(1 for l in lead_items if l["lead_type"] == "LOGISTICS_ROUTE")
    assert buyer_count == 3
    assert supplier_count == 3
    assert route_count == 1


def test_outreach_generation_and_mark_sent(auth_client, db):
    campaign = _create_campaign(auth_client, db)
    auth_client.post(f"/research-campaigns/{campaign['id']}/run")

    outreach = auth_client.post(f"/research-campaigns/{campaign['id']}/outreach")
    assert outreach.status_code == 200
    drafts = outreach.json()
    assert len(drafts) == 7
    assert all(d["status"] == OutreachStatus.DRAFT.value for d in drafts)

    mark = auth_client.post(f"/research-campaigns/outreach/{drafts[0]['id']}/mark-sent")
    assert mark.status_code == 200
    assert mark.json()["status"] == OutreachStatus.SENT_EXTERNALLY.value


def test_import_response_creates_commercial_facts(auth_client, db):
    campaign = _create_campaign(auth_client, db)
    auth_client.post(f"/research-campaigns/{campaign['id']}/run")

    eml = _eml_bytes("We can offer Base Oil SN500 100 MT CIF Rotterdam at USD 850/MT")
    response = auth_client.post(
        f"/research-campaigns/{campaign['id']}/import-response",
        files={"file": ("response.eml", eml, "message/rfc822")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["id"]
    fact_paths = {f["field_path"] for f in payload["facts"]}
    assert "price" in fact_paths
    assert "quantity" in fact_paths
    assert "incoterm" in fact_paths


def test_full_chain_viability_lifecycle(auth_client, db):
    campaign = _create_campaign(auth_client, db)
    campaign_id = campaign["id"]

    auth_client.post(f"/research-campaigns/{campaign_id}/run")
    drafts = auth_client.post(f"/research-campaigns/{campaign_id}/outreach").json()
    for draft in drafts:
        auth_client.post(f"/research-campaigns/outreach/{draft['id']}/mark-sent")

    eml = _eml_bytes("Base Oil SN500 100 MT CIF Rotterdam USD 850 per MT")
    auth_client.post(
        f"/research-campaigns/{campaign_id}/import-response",
        files={"file": ("reply.eml", eml, "message/rfc822")},
    )

    viability = auth_client.get(f"/research-campaigns/{campaign_id}/viability")
    assert viability.status_code == 200
    report = viability.json()
    assert report["viability_status"] == ChainViabilityStatus.VIABLE_CANDIDATE.value
    assert report["counts"]["buyers"] == 3
    assert report["counts"]["suppliers"] == 3
    assert report["counts"]["sent_outreach"] == 7
    assert report["counts"]["commercial_facts"] >= 3
    assert report["counts"]["opportunities"] >= 1

    updated = auth_client.get(f"/research-campaigns/{campaign_id}")
    assert updated.json()["viability_status"] == ChainViabilityStatus.VIABLE_CANDIDATE.value

    facts = list(
        db.scalars(
            select(CommercialFact).where(CommercialFact.research_campaign_id == campaign_id)
        )
    )
    assert len(facts) >= 3


def test_create_opportunity_from_campaign(auth_client, db):
    campaign = _create_campaign(auth_client, db)
    auth_client.post(f"/research-campaigns/{campaign['id']}/run")
    leads = auth_client.get(f"/research-campaigns/{campaign['id']}/leads").json()
    buyer = next(l for l in leads if "BUYER" in l["lead_type"])

    response = auth_client.post(
        f"/research-campaigns/{campaign['id']}/create-opportunity",
        json={"lead_id": buyer["id"], "opportunity_type": "BUYER_NEED"},
    )
    assert response.status_code == 200
    opp = response.json()
    assert opp["type"] == "BUYER_NEED"
    assert opp["title"] == buyer["title"]

    stored = db.get(ResearchCampaign, campaign["id"])
    assert stored is not None
    assert len(stored.created_opportunity_ids or []) == 1
