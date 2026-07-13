from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.ai.schemas import TenderSearchHitOutput
from app.domain.enums import InternetSourceFetchStrategy
from app.domain.models import InternetSource
from app.integrations.ted import get_ted_search_provider
from app.integrations.ted.provider import (
    OfficialTedSearchProvider,
    _keyword_query,
    _prioritize_ted_keywords,
    is_ted_source,
    is_ted_web_portal,
)
from app.integrations.tender_feeds import search_ted_notices
from app.services.internet_source_search import _dedupe_ted_sources

pytestmark = pytest.mark.usefixtures("setup_database")


def test_is_ted_source_detects_api_and_portal_urls():
    api_source = InternetSource(
        name="TED API",
        base_url="https://api.ted.europa.eu/v3/notices/search",
        fetch_strategy=InternetSourceFetchStrategy.TED_API.value,
    )
    portal_source = InternetSource(
        name="TED Portal",
        base_url="https://ted.europa.eu/en/",
        fetch_strategy=InternetSourceFetchStrategy.HTML.value,
    )
    other_source = InternetSource(
        name="Other",
        base_url="https://example.com/tenders",
        fetch_strategy=InternetSourceFetchStrategy.HTML.value,
    )

    assert is_ted_source(api_source) is True
    assert is_ted_source(portal_source) is True
    assert is_ted_source(other_source) is False
    assert is_ted_web_portal("https://www.ted.europa.eu/en/notice/1/html") is True


def test_keyword_query_uses_phrases_for_multi_word_terms():
    query = _keyword_query(["guar gum", "gum arabic"])
    assert 'FT~"guar gum"' in query
    assert 'FT~"gum arabic"' in query
    assert " OR " in query


def test_prioritize_ted_keywords_prefers_specific_terms():
    ranked = _prioritize_ted_keywords(["gum", "guar gum", "gum arabic"], max_terms=2)
    assert "guar gum" in ranked
    assert len(ranked) == 2


def test_dedupe_ted_sources_keeps_official_api_source():
    api_source = InternetSource(
        name="TED — EU Notices API",
        base_url="https://api.ted.europa.eu/v3/notices/search",
        fetch_strategy=InternetSourceFetchStrategy.TED_API.value,
        priority=95,
    )
    portal_source = InternetSource(
        name="TED Europa",
        base_url="https://ted.europa.eu/",
        fetch_strategy=InternetSourceFetchStrategy.HTML.value,
        priority=80,
    )
    other_source = InternetSource(
        name="World Bank",
        base_url="https://search.worldbank.org/api/v2/procnotices",
        fetch_strategy=InternetSourceFetchStrategy.WORLD_BANK_API.value,
        priority=90,
    )

    deduped = _dedupe_ted_sources([portal_source, api_source, other_source])
    ted_sources = [source for source in deduped if is_ted_source(source)]
    assert len(ted_sources) == 1
    assert ted_sources[0].name == "TED — EU Notices API"
    assert len(deduped) == 2


@patch("app.integrations.ted.provider.httpx.Client")
def test_official_ted_search_provider(mock_client_cls):
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

    provider = OfficialTedSearchProvider()
    result = provider.search_notices(
        keywords=["urea"],
        search_date=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    assert result.status == "API"
    assert len(result.hits) == 1
    assert result.hits[0].url.startswith("https://ted.europa.eu/")


@patch("app.integrations.ted.provider.fetch_public_url_text")
def test_enrich_notice_documents_fetches_deadline_fallback(mock_fetch):
    mock_fetch.return_value = (
        "Submission deadline: 2026-08-01\nProcurement details about urea.",
        b"",
    )
    provider = get_ted_search_provider()
    hit = TenderSearchHitOutput(
        title="Urea procurement",
        url="https://ted.europa.eu/en/notice/12345/html",
        body="Urea procurement",
        confidence=0.95,
        evidence_excerpt="TED notice 12345",
    )
    enriched = provider.enrich_notice_documents(hit)
    assert enriched.submission_deadline == "2026-08-01"
    assert "Procurement details" in (enriched.evidence_excerpt or "")


@patch("app.integrations.ted.provider.httpx.Client")
def test_tender_feeds_wrapper_delegates_to_provider(mock_client_cls):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"notices": []}
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    hits, status = search_ted_notices(
        keywords=["urea"],
        search_date=datetime(2026, 7, 10, tzinfo=timezone.utc),
    )
    assert status == "API"
    assert hits == []
