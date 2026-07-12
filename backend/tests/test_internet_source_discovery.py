import pytest

from app.config import settings
from app.services.internet_source_catalog import list_internet_sources, match_internet_sources
from app.services.internet_source_discovery import discover_and_register_sources, normalize_source_url
from app.services.product_keyword_localization import expand_product_keywords

pytestmark = pytest.mark.usefixtures("setup_database")


@pytest.fixture(autouse=True)
def use_mock_ai(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "mock")
    monkeypatch.setattr(settings, "openai_api_key", "")


def test_normalize_source_url_strips_www_and_trailing_slash():
    assert (
        normalize_source_url("https://www.GEM.gov.in/tenders/")
        == normalize_source_url("https://gem.gov.in/tenders")
    )


def test_discover_adds_only_new_sources(db, auth_client):
    before = auth_client.get("/internet-sources").json()
    before_urls = {normalize_source_url(item["base_url"]) for item in before}

    response = auth_client.post(
        "/internet-sources/discover",
        json={
            "product_keywords": ["гуаровая камедь"],
            "regions": ["India"],
            "force": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["added_count"] >= 1

    after = auth_client.get("/internet-sources").json()
    after_urls = {normalize_source_url(item["base_url"]) for item in after}
    assert len(after_urls) > len(before_urls)

    rediscover = auth_client.post(
        "/internet-sources/discover",
        json={
            "product_keywords": ["гуаровая камедь"],
            "regions": ["India"],
            "force": True,
        },
    ).json()
    assert rediscover["added_count"] == 0


def test_match_endpoint_auto_discovers_sources(auth_client):
    response = auth_client.get(
        "/internet-sources/match",
        params={
            "product_keywords": "гуаровая камедь",
            "regions": "India,Global",
            "auto_discover": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matched_count"] >= 1
