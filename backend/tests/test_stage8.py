from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.domain.enums import (
    AutomatedActionStatus,
    AutomationRunStatus,
    BindingClass,
    TaskType,
)
from app.domain.models import AutomatedActionLog, RFQ, Task

pytestmark = pytest.mark.usefixtures("setup_database")


def _deal_with_party_and_rfq(auth_client, db):
    from app.config import settings
    from app.domain.models import Deal, Product, User
    from app.services.opportunity import create_buyer_led_opportunity, create_requirement

    user = db.scalar(select(User).where(User.email == settings.admin_email))
    product = db.scalar(select(Product).where(Product.normalized_name == "SN500"))
    opp = create_buyer_led_opportunity(db, user=user, title="Automation RFQ test")
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


def _enable_automation(auth_client, **overrides):
    payload = {
        "auto_follow_up_enabled": True,
        "follow_up_after_days": 3,
        "max_follow_ups_per_rfq": 2,
        "min_days_between_follow_ups": 3,
        "max_auto_actions_per_day": 10,
    }
    payload.update(overrides)
    return auth_client.patch("/settings/automation", json=payload)


def _sent_rfq(auth_client, db):
    _, rfq_id = _deal_with_party_and_rfq(auth_client, db)
    send = auth_client.post(f"/rfqs/{rfq_id}/send")
    assert send.status_code == 200
    return rfq_id


def test_binding_classes_require_approval_via_validate(auth_client):
    allowed = auth_client.post(
        "/automation/validate",
        json={
            "action_type": "RFQ_FOLLOW_UP",
            "binding_class": BindingClass.INFORMATIONAL.value,
        },
    ).json()
    assert allowed["allowed"] is True

    for binding in (
        BindingClass.COMMERCIAL_SENSITIVE.value,
        BindingClass.POTENTIALLY_BINDING.value,
        BindingClass.BINDING.value,
        BindingClass.REQUEST.value,
    ):
        blocked = auth_client.post(
            "/automation/validate",
            json={"action_type": "RFQ_FOLLOW_UP", "binding_class": binding},
        ).json()
        assert blocked["allowed"] is False
        assert blocked["reason"]


def test_rfq_send_creates_follow_up_task(auth_client, db):
    rfq_id = _sent_rfq(auth_client, db)
    task = db.scalar(
        select(Task).where(
            Task.related_entity_type == "RFQ",
            Task.related_entity_id == rfq_id,
            Task.task_type == TaskType.FOLLOW_UP.value,
        )
    )
    assert task is not None
    assert task.title.startswith("Follow up:")


def test_auto_follow_up_sent_for_eligible_rfq(auth_client, db):
    rfq_id = _sent_rfq(auth_client, db)
    rfq = db.get(RFQ, rfq_id)
    rfq.sent_at = datetime.now(timezone.utc) - timedelta(days=5)
    db.commit()

    _enable_automation(auth_client)
    run = auth_client.post("/automation/run")
    assert run.status_code == 200
    data = run.json()
    assert data["status"] in {AutomationRunStatus.SUCCESS.value, AutomationRunStatus.PARTIAL.value}
    assert data["actions_sent"] == 1

    actions = auth_client.get("/automation/actions").json()
    sent = [a for a in actions if a["entity_id"] == rfq_id and a["status"] == AutomatedActionStatus.SENT.value]
    assert len(sent) == 1
    assert sent[0]["action_category"] == "NON_BINDING"
    assert sent[0]["binding_class"] == BindingClass.INFORMATIONAL.value
    assert "follow-up" in sent[0]["payload"]["subject"].lower() or sent[0]["payload"]["subject"].startswith("Re:")

    inbox = auth_client.get("/inbox").json()
    assert len(inbox) >= 2


def test_automation_disabled_skips_run(auth_client, db):
    _sent_rfq(auth_client, db)
    run = auth_client.post("/automation/run").json()
    assert run["status"] == AutomationRunStatus.SKIPPED.value
    assert run["actions_sent"] == 0


def test_rate_limit_blocks_second_follow_up(auth_client, db):
    rfq_ids = []
    for _ in range(2):
        _, rfq_id = _deal_with_party_and_rfq(auth_client, db)
        auth_client.post(f"/rfqs/{rfq_id}/send")
        rfq = db.get(RFQ, rfq_id)
        rfq.sent_at = datetime.now(timezone.utc) - timedelta(days=5)
        rfq_ids.append(rfq_id)
    db.commit()

    _enable_automation(auth_client, max_auto_actions_per_day=1)
    run = auth_client.post("/automation/run").json()
    assert run["actions_sent"] == 1
    assert run["actions_rate_limited"] == 1

    logs = auth_client.get("/automation/actions").json()
    rate_limited = [l for l in logs if l["status"] == AutomatedActionStatus.RATE_LIMITED.value]
    assert len(rate_limited) == 1


def test_max_follow_ups_per_rfq(auth_client, db):
    rfq_id = _sent_rfq(auth_client, db)
    rfq = db.get(RFQ, rfq_id)
    rfq.sent_at = datetime.now(timezone.utc) - timedelta(days=30)
    db.commit()

    _enable_automation(auth_client, max_follow_ups_per_rfq=1, min_days_between_follow_ups=1)

    first = auth_client.post("/automation/run").json()
    assert first["actions_sent"] == 1

    second = auth_client.post("/automation/run").json()
    assert second["actions_sent"] == 0
    assert second["actions_skipped"] >= 1

    count = db.scalar(
        select(func.count())
        .select_from(AutomatedActionLog)
        .where(
            AutomatedActionLog.entity_id == rfq_id,
            AutomatedActionLog.status == AutomatedActionStatus.SENT.value,
        )
    )
    assert count == 1
