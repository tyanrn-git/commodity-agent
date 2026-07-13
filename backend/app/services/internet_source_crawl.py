from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.domain.models import InternetSource

DEFAULT_HEADERS = {"User-Agent": "CommodityAgent/1.0"}

TENDER_PATH_KEYWORDS = (
    "tender",
    "tenders",
    "procurement",
    "procure",
    "bid",
    "bids",
    "rfp",
    "rfq",
    "notice",
    "notices",
    "auction",
    "e-procure",
    "eprocure",
    "закуп",
    "тендер",
    "закупк",
    "аукцион",
    "конкурс",
)

COMMON_TENDER_SUFFIXES = (
    "/tenders",
    "/tender",
    "/procurement",
    "/procure",
    "/bids",
    "/notices",
    "/eprocure",
    "/e-procure",
    "/active-tenders",
    "/latest-tenders",
)

MAX_PAGES_PER_SOURCE = 5
MAX_CHARS_PER_PAGE = 8000
MAX_COMBINED_CHARS = 28000

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


@dataclass(frozen=True)
class VisitedPage:
    url: str
    text: str
    status: str
    error: str | None = None


@dataclass
class SourcePageBundle:
    pages: list[VisitedPage] = field(default_factory=list)
    fetch_status: str = "OK"
    fetch_error: str | None = None

    @property
    def visited_urls(self) -> list[str]:
        return [page.url for page in self.pages if page.status == "OK"]

    @property
    def combined_text(self) -> str:
        return format_pages_for_ai(self.pages)


def _same_host(base_url: str, candidate_url: str) -> bool:
    base_host = urlparse(base_url).netloc.lower().removeprefix("www.")
    candidate_host = urlparse(candidate_url).netloc.lower().removeprefix("www.")
    return bool(base_host and candidate_host == base_host)


def _normalize_visit_url(base_url: str, raw_url: str) -> str | None:
    cleaned = raw_url.strip().rstrip(".,);]")
    if not cleaned or cleaned.startswith(("#", "mailto:", "javascript:")):
        return None
    full = urljoin(base_url, cleaned)
    parsed = urlparse(full)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    if not _same_host(base_url, full):
        return None
    return full.split("#", 1)[0].rstrip("/") or full


def extract_urls_from_hints(hints: str | None) -> list[str]:
    if not hints:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for match in _URL_RE.findall(hints):
        normalized = match.rstrip(".,);]")
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(normalized)
    return found


def discover_tender_links(base_url: str, html: str, *, max_links: int = 4) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    ranked: list[tuple[int, str]] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        full = _normalize_visit_url(base_url, href)
        if not full or full in seen:
            continue
        haystack = f"{href.lower()} {(anchor.get_text() or '').lower()}"
        score = sum(2 for keyword in TENDER_PATH_KEYWORDS if keyword in haystack)
        if score == 0:
            continue
        seen.add(full)
        ranked.append((score, full))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [url for _, url in ranked[:max_links]]


def build_source_visit_plan(source: InternetSource) -> list[str]:
    base = source.base_url.strip()
    plan: list[str] = []
    seen: set[str] = set()

    def add(url: str | None) -> None:
        if not url:
            return
        key = url.lower()
        if key in seen:
            return
        seen.add(key)
        plan.append(url)

    add(_normalize_visit_url(base, base) or base)
    for url in extract_urls_from_hints(source.search_hints):
        add(_normalize_visit_url(base, url))
    for suffix in COMMON_TENDER_SUFFIXES:
        add(_normalize_visit_url(base, urljoin(base, suffix)))

    return plan[: MAX_PAGES_PER_SOURCE * 2]


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))


def _fetch_page(url: str) -> tuple[VisitedPage, str | None]:
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=DEFAULT_HEADERS) as client:
            response = client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type.lower():
                raise ValueError("Only HTML pages are supported")
            html = response.text
        text = _html_to_text(html)[:MAX_CHARS_PER_PAGE]
        if not text.strip():
            raise ValueError("No text extracted from page")
        return VisitedPage(url=url, text=text, status="OK"), html
    except Exception as exc:
        return VisitedPage(url=url, text="", status="FAILED", error=str(exc)), None


def fetch_source_pages(source: InternetSource) -> SourcePageBundle:
    plan = build_source_visit_plan(source)
    if not plan:
        return SourcePageBundle(fetch_status="FAILED", fetch_error="No URLs to visit")

    bundle = SourcePageBundle()
    homepage_html: str | None = None

    for url in plan:
        if len(bundle.pages) >= MAX_PAGES_PER_SOURCE:
            break
        if any(page.url == url for page in bundle.pages):
            continue
        page, html = _fetch_page(url)
        bundle.pages.append(page)
        if page.status == "OK" and homepage_html is None:
            homepage_html = html

    if homepage_html and len(bundle.pages) < MAX_PAGES_PER_SOURCE:
        for link in discover_tender_links(source.base_url, homepage_html):
            if len(bundle.pages) >= MAX_PAGES_PER_SOURCE:
                break
            if any(page.url == link for page in bundle.pages):
                continue
            page, _ = _fetch_page(link)
            bundle.pages.append(page)

    ok_pages = [page for page in bundle.pages if page.status == "OK" and page.text.strip()]
    if ok_pages:
        bundle.fetch_status = "OK"
        return bundle

    errors = [page.error for page in bundle.pages if page.error]
    bundle.fetch_status = "FAILED"
    bundle.fetch_error = errors[0] if errors else "No page text fetched"
    return bundle


def format_pages_for_ai(pages: list[VisitedPage]) -> str:
    chunks: list[str] = []
    total = 0
    for page in pages:
        if page.status != "OK" or not page.text.strip():
            continue
        header = f"=== Page: {page.url} ==="
        block = f"{header}\n{page.text.strip()}"
        if total + len(block) > MAX_COMBINED_CHARS:
            remaining = MAX_COMBINED_CHARS - total
            if remaining <= len(header) + 20:
                break
            block = block[:remaining]
        chunks.append(block)
        total += len(block)
        if total >= MAX_COMBINED_CHARS:
            break
    return "\n\n".join(chunks)
