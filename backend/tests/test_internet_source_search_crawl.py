import pytest
from unittest.mock import MagicMock, patch

from app.ai.schemas import TenderSearchHitOutput, TenderSearchOutput
from app.domain.enums import InternetSourceFetchStrategy
from app.domain.models import InternetSource
from app.services.internet_source_crawl import SourcePageBundle, VisitedPage
from app.services.internet_source_search import (
    SourceHitCollection,
    _ai_search_enabled,
    _collect_source_hits,
    _merge_tender_hits,
)

pytestmark = pytest.mark.usefixtures("setup_database")


def test_merge_tender_hits_deduplicates_by_url_and_title():
    a = TenderSearchHitOutput(title="Urea tender A", url="https://example.com/1", confidence=0.7)
    b = TenderSearchHitOutput(title="Urea tender A", url="https://example.com/1", confidence=0.9)
    c = TenderSearchHitOutput(title="Another tender", url="https://example.com/2", confidence=0.8)
    merged = _merge_tender_hits([a], [b, c])
    assert len(merged) == 2


@patch("app.services.internet_source_search.fetch_source_pages")
def test_html_source_always_enables_ai_when_pages_fetched(mock_fetch):
    mock_fetch.return_value = SourcePageBundle(
        pages=[VisitedPage(url="https://portal.example.com/tenders", text="Transformer oil tender deadline 2026-12-01", status="OK")],
        fetch_status="OK",
    )
    source = InternetSource(
        name="Test HTML portal",
        base_url="https://portal.example.com/",
        fetch_strategy=InternetSourceFetchStrategy.HTML.value,
        search_hints="See /tenders section",
    )
    collection = _collect_source_hits(
        source=source,
        keywords=["transformer oil"],
        regions=["EU"],
        search_date=__import__("datetime").datetime(2026, 7, 12, tzinfo=__import__("datetime").timezone.utc),
        verify_real=False,
    )
    assert isinstance(collection, SourceHitCollection)
    assert collection.use_ai_search is True
    assert collection.page_bundle is not None
    assert "https://portal.example.com/tenders" in collection.page_bundle.visited_urls
