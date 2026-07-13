from app.domain.models import InternetSource
from app.services.internet_source_crawl import (
    build_source_visit_plan,
    discover_tender_links,
    extract_urls_from_hints,
)


def test_extract_urls_from_hints():
    hints = "Open https://example.com/tenders and also https://portal.gov.in/procurement page."
    urls = extract_urls_from_hints(hints)
    assert "https://example.com/tenders" in urls
    assert "https://portal.gov.in/procurement" in urls


def test_discover_tender_links_from_homepage():
    html = """
    <html><body>
      <a href="/about">About</a>
      <a href="/active-tenders">Active Tenders</a>
      <a href="https://other.com/tenders">External</a>
      <a href="/procurement/notices">Procurement notices</a>
    </body></html>
    """
    links = discover_tender_links("https://example.com/", html)
    assert "https://example.com/active-tenders" in links
    assert "https://example.com/procurement/notices" in links
    assert not any("other.com" in link for link in links)


def test_build_source_visit_plan_includes_hints_and_common_paths():
    source = InternetSource(
        name="Test portal",
        base_url="https://example.com/",
        search_hints="Check https://example.com/custom-tenders for bids",
    )
    plan = build_source_visit_plan(source)
    assert "https://example.com" in plan[0] or plan[0] == "https://example.com"
    assert "https://example.com/custom-tenders" in plan
    assert any("/tenders" in url or url.endswith("/tenders") for url in plan)
