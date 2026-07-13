import pytest
from unittest.mock import MagicMock, patch

from app.integrations.tender_feeds import search_ted_notices, search_world_bank_notices
from app.domain.enums import InternetSourceSearchRunStatus, OpportunityType

pytestmark = pytest.mark.usefixtures("setup_database")


@pytest.mark.integration
def test_ai_catalog_search_real_apis(auth_client):
    response = auth_client.post(
        "/internet-sources/search",
        json={
            "product_keywords": ["urea", "fertilizer"],
            "regions": ["India", "EU", "Global"],
            "access_mode": "PUBLIC",
            "verify_real": True,
        },
    )
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == InternetSourceSearchRunStatus.SUCCESS.value
    assert run["sources_matched"] >= 1
    assert run["hits_found"] >= 1

    hits = auth_client.get(f"/internet-sources/search/runs/{run['id']}/hits").json()
    api_hits = [h for h in hits if h.get("fetch_status") == "API"]
    assert len(api_hits) >= 1
    assert any(h.get("canonical_url") for h in api_hits)
    assert any(h.get("monitoring_row") for h in api_hits)
    assert not any("example.com" in (h.get("canonical_url") or "") for h in hits)


@patch("app.services.internet_source_search.get_ted_search_provider")
def test_search_works_for_unlisted_product(mock_get_provider, auth_client):
    mock_provider = MagicMock()
    mock_provider.search_notices.return_value = MagicMock(hits=[], status="API", error=None)
    mock_get_provider.return_value = mock_provider
    response = auth_client.post(
        "/internet-sources/search",
        json={
            "product_keywords": ["SN500"],
            "regions": ["EU", "Global"],
            "access_mode": "PUBLIC",
            "verify_real": True,
        },
    )
    assert response.status_code == 200
    run = response.json()
    assert run["sources_matched"] >= 1
    assert mock_provider.search_notices.called


@patch("app.services.internet_source_search.get_ted_search_provider")
def test_search_uses_localized_keywords_for_russian_input(mock_get_provider, auth_client):
    mock_provider = MagicMock()
    mock_provider.search_notices.return_value = MagicMock(hits=[], status="API", error=None)
    mock_get_provider.return_value = mock_provider
    response = auth_client.post(
        "/internet-sources/search",
        json={
            "product_keywords": ["карбамид"],
            "regions": ["EU", "Global"],
            "access_mode": "PUBLIC",
            "verify_real": True,
        },
    )
    assert response.status_code == 200
    assert mock_provider.search_notices.called
    used_keywords = mock_provider.search_notices.call_args.kwargs["keywords"]
    assert "urea" in [keyword.lower() for keyword in used_keywords]


@patch("app.integrations.ted.provider.httpx.Client")
def test_ted_parser(mock_client_cls):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "notices": [
            {
                "publication-number": "12345-2026",
                "PD": "2026-07-10+02:00",
                "TI": {"eng": "Finland - Urea procurement 2026"},
                "buyer-name": "Test Buyer",
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    hits, status = search_ted_notices(
        keywords=["urea"],
        search_date=__import__("datetime").datetime(2026, 7, 10, tzinfo=__import__("datetime").timezone.utc),
    )
    assert status == "API"
    assert len(hits) == 1
    assert "Urea" in hits[0].title or "urea" in hits[0].title.lower()
    assert hits[0].url.startswith("https://ted.europa.eu/")


@patch("app.integrations.tender_feeds.httpx.Client")
def test_world_bank_parser(mock_client_cls):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "procnotices": [
            {
                "id": "OP00456143",
                "noticedate": "10-Jul-2026",
                "bid_description": "Afar procurement of fertilizer",
                "project_name": "Emergency Program",
                "project_ctry_name": "Ethiopia",
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.get.return_value = mock_response
    mock_client_cls.return_value = mock_client

    hits, status = search_world_bank_notices(
        keywords=["fertilizer"],
        search_date=__import__("datetime").datetime(2026, 7, 10, tzinfo=__import__("datetime").timezone.utc),
    )
    assert status == "API"
    assert len(hits) == 1
    assert "fertilizer" in hits[0].title.lower()
