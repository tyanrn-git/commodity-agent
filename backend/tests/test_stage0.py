from decimal import Decimal

import pytest
from sqlalchemy import select

from app.domain.models import AuditLog, Opportunity

pytestmark = pytest.mark.usefixtures("setup_database")


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_and_me(client):
    response = client.post(
        "/auth/login",
        json={"email": "admin@localhost", "password": "changeme"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "admin@localhost"

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["timezone"] == "Atlantic/Madeira"


def test_create_opportunity_creates_audit(auth_client, db):
    response = auth_client.post(
        "/opportunities",
        json={
            "title": "SN500 buyer need",
            "raw_product_name": "Base Oil SN500",
            "quantity_min": "100",
            "quantity_max": "200",
            "quantity_unit": "MT",
            "destination_hint": "Rotterdam",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "BUYER_NEED"
    assert data["status"] == "NEW"
    assert Decimal(str(data["quantity_min"])) == Decimal("100")

    logs = list(db.scalars(select(AuditLog).where(AuditLog.entity_type == "Opportunity")))
    assert len(logs) >= 1


def test_upload_pdf_source(auth_client, db):
    create = auth_client.post("/opportunities", json={"title": "PDF test"})
    opp_id = create.json()["id"]

    pdf_bytes = b"%PDF-1.4 test document"
    response = auth_client.post(
        f"/opportunities/{opp_id}/sources",
        files={"file": ("tender.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201
    source = response.json()
    assert source["is_immutable"] is True
    assert source["original_filename"] == "tender.pdf"

    sources = auth_client.get(f"/opportunities/{opp_id}/sources")
    assert sources.status_code == 200
    assert len(sources.json()) == 1


def test_convert_and_create_requirement(auth_client):
    products = auth_client.get("/products")
    product_id = products.json()[0]["id"]

    create = auth_client.post(
        "/opportunities",
        json={"title": "Convert test", "normalized_product_id": product_id},
    )
    opp_id = create.json()["id"]

    convert = auth_client.post(f"/opportunities/{opp_id}/convert")
    assert convert.status_code == 200
    deal = convert.json()
    assert deal["direction"] == "BUYER_LED"
    assert deal["stage"] == "QUALIFICATION"

    requirement = auth_client.post(
        f"/deals/{deal['id']}/requirements",
        json={
            "product_id": product_id,
            "quantity_min": "50",
            "quantity_unit": "MT",
            "destination": "Hamburg",
            "requested_incoterm": "CIF",
            "user_confirmed": False,
            "evidence": [
                {"field_path": "quantity_min", "excerpt": "50 MT", "user_confirmed": False}
            ],
        },
    )
    assert requirement.status_code == 201
    req = requirement.json()
    assert req["user_confirmed"] is False
    assert len(req["evidence_items"]) == 1
    assert req["evidence_items"][0]["field_path"] == "quantity_min"

    opp = auth_client.get(f"/opportunities/{opp_id}")
    assert opp.json()["status"] == "CONVERTED"
