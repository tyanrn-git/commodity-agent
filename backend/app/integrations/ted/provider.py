from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from app.ai.schemas import TenderSearchHitOutput
from app.domain.enums import InternetSourceFetchStrategy
from app.domain.models import InternetSource
from app.integrations.ted.base import TedSearchProvider, TedSearchResult
from app.services.document_parser import fetch_public_url_text

TED_SEARCH_API_URL = "https://api.ted.europa.eu/v3/notices/search"
TED_WEB_HOSTS = frozenset({"ted.europa.eu", "www.ted.europa.eu"})
TED_API_HOSTS = frozenset({"api.ted.europa.eu"})

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
}


def _host_from_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return (parsed.netloc or "").lower()


def is_ted_api_url(url: str) -> bool:
    return _host_from_url(url) in TED_API_HOSTS


def is_ted_web_portal(url: str) -> bool:
    return _host_from_url(url) in TED_WEB_HOSTS


def is_ted_source(source: InternetSource) -> bool:
    strategy = source.fetch_strategy or InternetSourceFetchStrategy.HTML.value
    if strategy == InternetSourceFetchStrategy.TED_API.value:
        return True
    return is_ted_api_url(source.base_url) or is_ted_web_portal(source.base_url)


def _pick_title(title_field) -> str:
    if isinstance(title_field, dict):
        for key in ("eng", "en", "gle", "fra", "deu", "spa"):
            value = title_field.get(key)
            if value:
                return str(value)
        for value in title_field.values():
            if value:
                return str(value)
    return str(title_field or "Procurement notice")


def _keyword_query(keywords: list[str]) -> str:
    clauses: list[str] = []
    seen: set[str] = set()

    def add_clause(clause: str) -> None:
        if clause and clause not in seen:
            seen.add(clause)
            clauses.append(clause)

    for keyword in keywords:
        cleaned = keyword.strip()
        if not cleaned:
            continue
        if " " in cleaned:
            safe = cleaned.replace('"', "")
            add_clause(f'FT~"{safe}"')
            continue
        token = re.sub(r"[^\w\-]+", "", cleaned.lower())
        if token:
            add_clause(f"FT~{token}")

    if not clauses:
        return "FT~procurement"
    if len(clauses) == 1:
        return clauses[0]
    return " OR ".join(clauses)


def _prioritize_ted_keywords(keywords: list[str], *, max_terms: int = 6) -> list[str]:
    generic = {"gum", "resin", "смола", "goma", "gomme"}
    ranked = sorted(keywords, key=lambda value: (-len(value.split()), -len(value), value.lower()))
    selected: list[str] = []
    for keyword in ranked:
        cleaned = keyword.strip()
        if not cleaned:
            continue
        if cleaned.lower() in generic and len(ranked) > 1:
            continue
        if cleaned not in selected:
            selected.append(cleaned)
        if len(selected) >= max_terms:
            break
    return selected or [keyword.strip() for keyword in keywords if keyword.strip()][:max_terms]


def _product_from_notice_text(text: str, keywords: list[str]) -> str | None:
    haystack = text.lower()
    for keyword in sorted(keywords, key=lambda value: (-len(value.split()), -len(value))):
        cleaned = keyword.strip()
        if cleaned and cleaned.lower() in haystack:
            return cleaned
    return None


def _parse_submission_deadline(page_text: str) -> str | None:
    patterns = [
        r"submission deadline[:\s]+([0-9]{4}-[0-9]{2}-[0-9]{2})",
        r"deadline for receipt of tenders[:\s]+([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})",
        r"deadline[:\s]+([0-9]{4}-[0-9]{2}-[0-9]{2})",
    ]
    lower = page_text.lower()
    for pattern in patterns:
        match = re.search(pattern, lower, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


class OfficialTedSearchProvider(TedSearchProvider):
    def search_notices(
        self,
        *,
        keywords: list[str],
        search_date: datetime,
        limit: int = 10,
    ) -> TedSearchResult:
        keywords = _prioritize_ted_keywords(keywords)
        date_from = (search_date.astimezone(timezone.utc) - timedelta(days=30)).strftime("%Y%m%d")
        query = f"{_keyword_query(keywords)} AND PD>={date_from}"
        payload = {
            "query": query,
            "fields": ["ND", "PD", "TI", "publication-number", "buyer-name"],
            "limit": limit,
            "scope": "ACTIVE",
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    TED_SEARCH_API_URL,
                    json=payload,
                    headers={**DEFAULT_HEADERS, "Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            return TedSearchResult(hits=[], status="FAILED", error=str(exc))

        hits: list[TenderSearchHitOutput] = []
        for notice in data.get("notices", []):
            publication_number = notice.get("publication-number") or notice.get("ND")
            title = _pick_title(notice.get("TI"))
            publication_date = str(notice.get("PD") or "")[:10] or None
            buyer = notice.get("buyer-name")
            if isinstance(buyer, dict):
                buyer = _pick_title(buyer)
            url = (
                f"https://ted.europa.eu/en/notice/{publication_number}/html"
                if publication_number
                else "https://ted.europa.eu/"
            )
            hit = TenderSearchHitOutput(
                title=title,
                url=url,
                product=_product_from_notice_text(title, keywords),
                buyer=str(buyer) if buyer else None,
                publication_date=publication_date,
                body=title,
                confidence=0.95,
                evidence_excerpt=f"TED notice {publication_number}: {title}",
            )
            hits.append(self.enrich_notice_documents(hit))
        return TedSearchResult(hits=hits, status="API")

    def enrich_notice_documents(self, hit: TenderSearchHitOutput) -> TenderSearchHitOutput:
        if not hit.url or hit.submission_deadline:
            return hit
        try:
            page_text, _ = fetch_public_url_text(hit.url, timeout=6.0)
        except Exception:
            return hit
        if not page_text.strip():
            return hit

        submission_deadline = _parse_submission_deadline(page_text)
        excerpt = hit.evidence_excerpt or ""
        if len(page_text) > len(excerpt):
            excerpt = f"{excerpt}\n{page_text[:500].strip()}".strip()

        return hit.model_copy(
            update={
                "submission_deadline": submission_deadline or hit.submission_deadline,
                "deadline": submission_deadline or hit.deadline,
                "body": page_text[:4000] if len(page_text) > len(hit.body or "") else hit.body,
                "evidence_excerpt": excerpt[:1000],
            }
        )
