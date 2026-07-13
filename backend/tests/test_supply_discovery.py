import pytest

from app.config import settings
from app.domain.enums import TenderPromotionMode

pytestmark = pytest.mark.usefixtures("setup_database")


@pytest.fixture(autouse=True)
def use_mock_ai(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "mock")
    monkeypatch.setattr(settings, "openai_api_key", "")


def test_supply_discovery_for_opportunity(db, auth_client):
    opp = auth_client.post("/opportunities", json={"title": "Urea tender Finland", "raw_product_name": "urea"}).json()
    response = auth_client.post(f"/opportunities/{opp['id']}/supply-discovery")
    assert response.status_code == 200
    body = response.json()
    assert body["supplier_hint"]
    assert body["indicative_economics"]["source"] == "supply_discovery_ai"
    assert body["economics_preview"]

    refreshed = auth_client.get(f"/opportunities/{opp['id']}").json()
    assert refreshed["indicative_economics"]["seller_name"] == body["supplier_hint"]


def test_manual_promote_runs_supply_discovery_when_enabled(db, auth_client, monkeypatch):
    from tests.test_tender_promotion import _seed_hit
    from app.domain.models import User

    monkeypatch.setattr(settings, "tender_promotion_mode", TenderPromotionMode.MANUAL.value)
    monkeypatch.setattr(settings, "auto_supply_discovery_after_promote", True)

    user = db.scalar(__import__("sqlalchemy").select(User).limit(1))
    hit = _seed_hit(db, user)
    auth_client.post(f"/internet-sources/search/hits/{hit.id}/qualify")
    promote = auth_client.post(f"/internet-sources/search/hits/{hit.id}/promote")
    assert promote.status_code == 200
    opp_id = promote.json()["opportunity_id"]

    opp = auth_client.get(f"/opportunities/{opp_id}").json()
    assert opp["indicative_economics"]["source"] == "supply_discovery_ai"
    assert opp["indicative_economics"].get("seller_name")
