import pytest
from sqlalchemy import select

from app.domain.enums import ApprovalStatus, RFQStatus
from app.domain.models import ApprovalRequest, Counterparty, RFQTemplate
from app.services.opportunity import create_buyer_led_opportunity, create_requirement

pytestmark = pytest.mark.usefixtures("setup_database")


def _deal_with_requirement(auth_client, db):
    from app.config import settings
    from app.domain.models import Product, User

    user = db.scalar(select(User).where(User.email == settings.admin_email))
    product = db.scalar(select(Product).where(Product.normalized_name == "SN500"))
    opp = create_buyer_led_opportunity(db, user=user, title="RFQ stage2 test")
    auth_client.post(f"/opportunities/{opp.id}/convert")
    deal_resp = auth_client.get("/deals")
    deal_id = deal_resp.json()[0]["id"]
    from app.domain.models import Deal

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
    return deal_id


def _supplier(auth_client):
    response = auth_client.post(
        "/counterparties",
        json={
            "legal_name": "Gulf Base Oil Refinery",
            "trade_name": "Gulf Base Oil",
            "organization_type": "PRODUCER",
            "website": "https://example.com",
            "primary_domain": "example.com",
        },
    )
    assert response.status_code == 201
    cp = response.json()
    auth_client.post(
        f"/counterparties/{cp['id']}/contacts",
        json={
            "full_name": "Sales Manager",
            "email": "sales@example.com",
            "is_primary": True,
        },
    )
    return cp


def test_counterparty_crud_and_templates(auth_client):
    cp = _supplier(auth_client)
    assert cp["compliance_review_status"] == "NOT_REVIEWED"

    templates = auth_client.get("/rfq-templates")
    assert templates.status_code == 200
    assert len(templates.json()) >= 2

    company = auth_client.get("/settings/company")
    assert company.status_code == 200
    assert company.json()["legal_name"]


def test_domain_verification_flow(auth_client, db):
    cp = _supplier(auth_client)
    verify = auth_client.post(f"/counterparties/{cp['id']}/verify-domain")
    assert verify.status_code == 200
    report = verify.json()
    assert "mx" in report

    counterparty = db.get(Counterparty, cp["id"])
    counterparty.domain_verification_report = {
        **report,
        "ready_for_user_confirmation": True,
    }
    db.commit()

    confirm = auth_client.post(f"/counterparties/{cp['id']}/confirm-domain")
    assert confirm.status_code == 200
    assert confirm.json()["verification_status"] == "DOMAIN_VERIFIED"


def test_rfq_lifecycle_and_approval_invalidation(auth_client, db):
    deal_id = _deal_with_requirement(auth_client, db)
    cp = _supplier(auth_client)

    party = auth_client.post(
        f"/deals/{deal_id}/parties",
        json={"counterparty_id": cp["id"], "role": "SUPPLIER"},
    )
    assert party.status_code == 201
    party_id = party.json()["id"]

    parties = auth_client.get(f"/deals/{deal_id}/parties")
    assert parties.status_code == 200
    assert len(parties.json()) == 1
    assert parties.json()[0]["counterparty"]["legal_name"]

    rfq = auth_client.post(
        f"/deals/{deal_id}/rfqs",
        json={"target_deal_party_id": party_id, "rfq_type": "PRODUCT"},
    )
    assert rfq.status_code == 201
    rfq_id = rfq.json()["id"]
    assert rfq.json()["status"] == RFQStatus.DRAFT.value
    assert rfq.json()["subject"]

    submit = auth_client.post(f"/rfqs/{rfq_id}/submit-for-approval")
    assert submit.status_code == 200
    assert submit.json()["status"] == RFQStatus.PENDING_APPROVAL.value

    approve = auth_client.post(
        f"/rfqs/{rfq_id}/approve",
        json={"acknowledge_warnings": True},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == RFQStatus.APPROVED.value

    patch = auth_client.patch(
        f"/rfqs/{rfq_id}",
        json={"body": "Updated RFQ body after approval"},
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == RFQStatus.DRAFT.value

    approval = db.scalar(select(ApprovalRequest).where(ApprovalRequest.rfq_id == rfq_id))
    assert approval.approval_status == ApprovalStatus.INVALIDATED.value


def test_approval_preview_shows_compliance_warning(auth_client, db):
    deal_id = _deal_with_requirement(auth_client, db)
    cp = _supplier(auth_client)
    party_id = auth_client.post(
        f"/deals/{deal_id}/parties",
        json={"counterparty_id": cp["id"], "role": "SUPPLIER"},
    ).json()["id"]
    rfq_id = auth_client.post(
        f"/deals/{deal_id}/rfqs",
        json={"target_deal_party_id": party_id, "rfq_type": "PRODUCT"},
    ).json()["id"]

    preview = auth_client.get(f"/rfqs/{rfq_id}/approval-preview")
    assert preview.status_code == 200
    data = preview.json()
    assert "counterparty_not_reviewed" in data["compliance_warnings"]
    assert data["counterparty"]["compliance_review_status"] == "NOT_REVIEWED"


def test_ai_draft_updates_rfq(auth_client, db):
    deal_id = _deal_with_requirement(auth_client, db)
    cp = _supplier(auth_client)
    party_id = auth_client.post(
        f"/deals/{deal_id}/parties",
        json={"counterparty_id": cp["id"], "role": "SUPPLIER"},
    ).json()["id"]
    rfq_id = auth_client.post(
        f"/deals/{deal_id}/rfqs",
        json={"target_deal_party_id": party_id, "rfq_type": "PRODUCT"},
    ).json()["id"]

    drafted = auth_client.post(f"/rfqs/{rfq_id}/draft-with-ai")
    assert drafted.status_code == 200
    assert "[AI adapted]" in drafted.json()["subject"]
