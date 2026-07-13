import pytest

from app.config import settings
from app.domain.enums import (
    InternetSourceFetchStrategy,
    InternetSourceKind,
    InternetSourceSearchHitStatus,
    MonitoringAccessMode,
)
from app.domain.models import InternetSource, InternetSourceSearchHit, InternetSourceSearchRun, User

pytestmark = pytest.mark.usefixtures("setup_database")


@pytest.fixture(autouse=True)
def use_mock_ai(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "mock")
    monkeypatch.setattr(settings, "openai_api_key", "")


def _seed_hit(db, user: User) -> InternetSourceSearchHit:
    source = InternetSource(
        owner_id=None,
        name="TED — EU Notices API",
        base_url="https://api.ted.europa.eu/v3/notices/search",
        source_kind=InternetSourceKind.PROCUREMENT_FEED.value,
        access_mode=MonitoringAccessMode.PUBLIC.value,
        fetch_strategy=InternetSourceFetchStrategy.TED_API.value,
        regions=["EU"],
        product_tags=["urea"],
        languages=["en"],
        is_active=True,
        priority=90,
    )
    db.add(source)
    db.flush()
    run = InternetSourceSearchRun(
        owner_id=user.id,
        product_keywords=["urea"],
        regions=["EU"],
        search_date=__import__("datetime").datetime(2026, 7, 12, tzinfo=__import__("datetime").timezone.utc),
        access_mode="PUBLIC",
        status="SUCCESS",
        sources_matched=1,
        sources_scanned=1,
        hits_found=1,
        hits_new=1,
        opportunities_created=0,
        ai_calls=0,
        started_at=__import__("datetime").datetime(2026, 7, 12, tzinfo=__import__("datetime").timezone.utc),
        finished_at=__import__("datetime").datetime(2026, 7, 12, tzinfo=__import__("datetime").timezone.utc),
    )
    db.add(run)
    db.flush()
    hit = InternetSourceSearchHit(
        search_run_id=run.id,
        internet_source_id=source.id,
        title="Finland - Urea procurement 2026",
        canonical_url="https://ted.europa.eu/en/notice/12345/html",
        content_hash="abc123",
        status=InternetSourceSearchHitStatus.FOUND.value,
        confidence=0.95,
        evidence_excerpt="TED notice: Urea procurement",
        fetch_status="API",
        extracted_fields={
            "product": "urea",
            "buyer": "Test Buyer",
            "volume": "1000 MT",
            "destination": "Finland",
            "submission_deadline": "2026-12-31T00:00:00+00:00",
            "product_match": True,
            "product_match_reason": "match",
            "display_status": "ACTIVE",
            "display_status_label": "Актуальный",
            "submission_expired": False,
        },
    )
    db.add(hit)
    db.commit()
    db.refresh(hit)
    return hit


def test_list_search_runs_returns_last_run(db, auth_client):
    user = db.scalar(__import__("sqlalchemy").select(User).limit(1))
    hit = _seed_hit(db, user)
    response = auth_client.get("/internet-sources/search/runs")
    assert response.status_code == 200
    runs = response.json()
    assert len(runs) >= 1
    assert runs[0]["id"] == str(hit.search_run_id)

    hits = auth_client.get(f"/internet-sources/search/runs/{hit.search_run_id}/hits").json()
    assert len(hits) == 1
    assert hits[0]["id"] == str(hit.id)
    assert hits[0]["monitoring_row"]["product_name"] == "urea"


def test_promote_search_hit_creates_opportunity(db, auth_client):
    user = db.scalar(__import__("sqlalchemy").select(User).limit(1))
    hit = _seed_hit(db, user)
    response = auth_client.post(f"/internet-sources/search/hits/{hit.id}/promote")
    assert response.status_code == 200
    body = response.json()
    assert body["opportunity_id"]
    assert body["supplier_hint"]
    assert body["economics_preview"]

    refreshed = db.get(InternetSourceSearchHit, hit.id)
    assert refreshed.opportunity_id is not None
    assert refreshed.status == InternetSourceSearchHitStatus.OPPORTUNITY_CREATED.value


def test_promote_rejects_infeasible_hit(db, auth_client):
    user = db.scalar(__import__("sqlalchemy").select(User).limit(1))
    hit = _seed_hit(db, user)
    hit.evidence_excerpt = "Office furniture procurement — chairs and desks for municipal offices"
    hit.extracted_fields = {
        **(hit.extracted_fields or {}),
        "body": hit.evidence_excerpt,
    }
    db.commit()

    response = auth_client.post(f"/internet-sources/search/hits/{hit.id}/promote")

    assert response.status_code == 422
    refreshed = db.get(InternetSourceSearchHit, hit.id)
    assert refreshed.opportunity_id is None
    assert (refreshed.extracted_fields or {}).get("feasibility", {}).get("feasible") is False


def test_qualify_search_hit(db, auth_client):
    user = db.scalar(__import__("sqlalchemy").select(User).limit(1))
    hit = _seed_hit(db, user)
    response = auth_client.post(f"/internet-sources/search/hits/{hit.id}/qualify")
    assert response.status_code == 200
    body = response.json()
    assert body["qualification"]["qualified"] is True
    assert body["hit"]["qualification"]["qualified"] is True


def test_promote_requires_qualification_in_manual_mode(db, auth_client, monkeypatch):
    monkeypatch.setattr(settings, "tender_promotion_mode", "manual")
    user = db.scalar(__import__("sqlalchemy").select(User).limit(1))
    hit = _seed_hit(db, user)
    response = auth_client.post(f"/internet-sources/search/hits/{hit.id}/promote")
    assert response.status_code == 400


def test_manual_mode_qualify_then_promote(db, auth_client, monkeypatch):
    monkeypatch.setattr(settings, "tender_promotion_mode", "manual")
    user = db.scalar(__import__("sqlalchemy").select(User).limit(1))
    hit = _seed_hit(db, user)
    qualify = auth_client.post(f"/internet-sources/search/hits/{hit.id}/qualify")
    assert qualify.status_code == 200
    promote = auth_client.post(f"/internet-sources/search/hits/{hit.id}/promote")
    assert promote.status_code == 200
    assert promote.json()["opportunity_id"]
