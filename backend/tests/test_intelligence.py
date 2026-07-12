import pytest

from app.domain.models import CounterpartyCapability, OpportunitySpecValue

pytestmark = pytest.mark.usefixtures("setup_database")


def test_product_resolution_mock(auth_client):
    opp = auth_client.post(
        "/opportunities",
        json={"title": "Base oil inquiry"},
    ).json()

    result = auth_client.post(
        f"/opportunities/{opp['id']}/resolve-product",
        json={"rough_product_name": "base oil group II SN500"},
    )
    assert result.status_code == 200
    data = result.json()
    assert data["normalized_product_name"] == "SN500"
    assert data["confidence"] >= 0.5
    assert len(data["spec_values"]) >= 2
    assert any(s["parameter_name"] == "kinematic_viscosity_40c" for s in data["spec_values"])

    listed = auth_client.get(f"/opportunities/{opp['id']}/spec-values").json()
    assert len(listed) == len(data["spec_values"])

    extracted = next(s for s in listed if s["parameter_name"] == "kinematic_viscosity_40c")
    confirmed = auth_client.post(f"/opportunity-spec-values/{extracted['id']}/confirm").json()
    assert confirmed["user_confirmed"] is True
    assert confirmed["status"] == "CONFIRMED"


def test_product_resolution_no_catalog_match(auth_client):
    opp = auth_client.post(
        "/opportunities",
        json={"title": "Guar inquiry"},
    ).json()

    result = auth_client.post(
        f"/opportunities/{opp['id']}/resolve-product",
        json={"rough_product_name": "гуар для нефтесервиса", "create_if_missing": False},
    )
    assert result.status_code == 200
    data = result.json()
    assert data["matched"] is False
    assert data["normalized_product_name"] is None
    assert data["normalized_product_id"] is None
    assert data["rough_product_name"] == "гуар для нефтесервиса"
    assert data["confidence"] < 0.5
    assert data["proposed_new_product"] is not None
    assert data["proposed_new_product"]["normalized_name"] == "Guar Gum"


def test_counterparty_enrichment_mock(auth_client):
    cp = auth_client.post(
        "/counterparties",
        json={
            "legal_name": "Gulf Base Oil Refinery LLC",
            "trade_name": "Gulf Base Oil",
            "organization_type": "PRODUCER",
            "incorporation_country": "UAE",
            "website": "https://gulfbasoil.example.com",
        },
    ).json()

    enrich = auth_client.post(
        f"/counterparties/{cp['id']}/enrich",
        json={
            "source_text": "Gulf Base Oil exports SN500 base oil from Jebel Ali. Contact sales@gulfbasoil.example.com"
        },
    )
    assert enrich.status_code == 200
    body = enrich.json()
    assert len(body["capabilities"]) >= 1
    assert body["capabilities"][0]["capability_type"] == "PRODUCT"
    assert body["capabilities"][0]["extracted_by_ai"] is True
    assert len(body["contact_hints"]) >= 1

    caps = auth_client.get(f"/counterparties/{cp['id']}/capabilities").json()
    assert len(caps) >= 1

    cap_id = caps[0]["id"]
    confirmed = auth_client.post(f"/counterparty-capabilities/{cap_id}/confirm").json()
    assert confirmed["user_confirmed"] is True
