import pytest
from sqlalchemy import func, select

from app.domain.enums import MonitoringRunStatus, MonitoredPublicationStatus, OpportunityType
from app.domain.models import MonitoredPublication, MonitoringRule, Opportunity

pytestmark = pytest.mark.usefixtures("setup_database")


def test_monitoring_health_and_run(auth_client):
    rules = auth_client.get("/monitoring-rules")
    assert rules.status_code == 200
    assert len(rules.json()) >= 1
    rule_id = rules.json()[0]["id"]

    health = auth_client.get(f"/monitoring-rules/{rule_id}/health")
    assert health.status_code == 200
    assert health.json()["health_status"] == "HEALTHY"

    first_run = auth_client.post(f"/monitoring-rules/{rule_id}/run")
    assert first_run.status_code == 200
    data = first_run.json()
    assert data["status"] == MonitoringRunStatus.SUCCESS.value
    assert data["items_found"] == 2
    assert data["items_new"] == 2
    assert data["opportunities_created"] == 1

    publications = auth_client.get(f"/monitoring-rules/{rule_id}/publications")
    assert publications.status_code == 200
    pubs = publications.json()
    assert len(pubs) == 2
    assert sum(1 for p in pubs if p["status"] == MonitoredPublicationStatus.OPPORTUNITY_CREATED.value) == 1
    assert sum(1 for p in pubs if p["status"] == MonitoredPublicationStatus.FILTERED_OUT.value) == 1

    opps = auth_client.get("/opportunities")
    auto = [o for o in opps.json() if o["type"] == OpportunityType.AUTO_DISCOVERED.value]
    assert len(auto) == 1
    assert "SN500" in auto[0]["title"]


def test_monitoring_run_is_idempotent(auth_client, db):
    rule_id = auth_client.get("/monitoring-rules").json()[0]["id"]

    auth_client.post(f"/monitoring-rules/{rule_id}/run")
    second = auth_client.post(f"/monitoring-rules/{rule_id}/run").json()

    assert second["items_found"] == 2
    assert second["items_new"] == 0
    assert second["opportunities_created"] == 0

    auto_count = db.scalar(
        select(func.count())
        .select_from(Opportunity)
        .where(Opportunity.type == OpportunityType.AUTO_DISCOVERED.value)
    )
    assert auto_count == 1

    pub_count = db.scalar(
        select(func.count())
        .select_from(MonitoredPublication)
        .where(MonitoredPublication.monitoring_rule_id == rule_id)
    )
    assert pub_count == 2


def test_create_custom_monitoring_rule(auth_client):
    created = auth_client.post(
        "/monitoring-rules",
        json={
            "name": "Custom feed",
            "connector_type": "MOCK",
            "source_url": "demo-feed.json",
            "filters": {"product_keywords": ["Urea"]},
        },
    )
    assert created.status_code == 201
    rule_id = created.json()["id"]

    run = auth_client.post(f"/monitoring-rules/{rule_id}/run").json()
    assert run["opportunities_created"] == 1

    pubs = auth_client.get(f"/monitoring-rules/{rule_id}/publications").json()
    assert len(pubs) == 2
    assert sum(1 for p in pubs if p["status"] == MonitoredPublicationStatus.OPPORTUNITY_CREATED.value) == 1

    opps = auth_client.get("/opportunities").json()
    urea_opps = [o for o in opps if o["type"] == OpportunityType.AUTO_DISCOVERED.value and "Urea" in (o.get("title") or "")]
    assert len(urea_opps) == 1
