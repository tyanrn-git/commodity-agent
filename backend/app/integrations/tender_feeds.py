import re
from datetime import datetime, timedelta, timezone

import httpx

from app.ai.schemas import TenderSearchHitOutput
from app.integrations.ted import get_ted_search_provider

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
}


def _product_from_notice_text(text: str, keywords: list[str]) -> str | None:
    haystack = text.lower()
    for keyword in sorted(keywords, key=lambda value: (-len(value.split()), -len(value))):
        cleaned = keyword.strip()
        if cleaned and cleaned.lower() in haystack:
            return cleaned
    return None


def search_ted_notices(
    *,
    keywords: list[str],
    search_date: datetime,
    limit: int = 10,
) -> tuple[list[TenderSearchHitOutput], str]:
    result = get_ted_search_provider().search_notices(
        keywords=keywords,
        search_date=search_date,
        limit=limit,
    )
    return result.hits, result.status


def search_world_bank_notices(
    *,
    keywords: list[str],
    search_date: datetime,
    limit: int = 10,
) -> tuple[list[TenderSearchHitOutput], str]:
    term = next(
        (
            keyword
            for keyword in keywords
            if re.search(r"[a-zA-Z]", keyword) and len(keyword.strip()) >= 3
        ),
        keywords[0] if keywords else "procurement",
    )
    params = {"format": "json", "qterm": term, "rows": str(limit)}
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(
            "https://search.worldbank.org/api/v2/procnotices",
            params=params,
            headers=DEFAULT_HEADERS,
        )
        response.raise_for_status()
        data = response.json()

    target_day = search_date.astimezone(timezone.utc).date()
    window_start = target_day - timedelta(days=30)
    hits: list[TenderSearchHitOutput] = []
    for notice in data.get("procnotices", []):
        noticedate = notice.get("noticedate")
        parsed_date = None
        if noticedate:
            try:
                parsed_date = datetime.strptime(str(noticedate), "%d-%b-%Y").date()
            except ValueError:
                parsed_date = None
        if parsed_date and (parsed_date < window_start or parsed_date > target_day):
            continue

        title = notice.get("bid_description") or notice.get("project_name") or notice.get("id")
        body = str(notice.get("bid_description") or notice.get("project_name") or "")
        url = f"https://projects.worldbank.org/en/projects-operations/procurement-detail/{notice.get('id')}"
        hits.append(
            TenderSearchHitOutput(
                title=str(title),
                url=url,
                product=_product_from_notice_text(body or str(title), keywords),
                buyer=notice.get("project_ctry_name"),
                destination=notice.get("project_ctry_name"),
                publication_date=parsed_date.isoformat() if parsed_date else None,
                submission_deadline=notice.get("submission_date"),
                deadline=notice.get("submission_date"),
                body=body,
                confidence=0.93,
                evidence_excerpt=(
                    f"World Bank {notice.get('id')}: {notice.get('bid_description') or notice.get('project_name')}"
                ),
            )
        )
    return hits[:limit], "API"


def extract_html_keyword_hits(
    *,
    page_text: str,
    keywords: list[str],
    source_name: str,
    source_url: str,
    max_hits: int = 5,
) -> list[TenderSearchHitOutput]:
    if not page_text.strip():
        return []

    hits: list[TenderSearchHitOutput] = []
    seen: set[str] = set()
    for raw_line in page_text.splitlines():
        line = " ".join(raw_line.split())
        if len(line) < 20:
            continue
        lower = line.lower()
        if not any(keyword.lower() in lower for keyword in keywords):
            continue
        key = line[:160].lower()
        if key in seen:
            continue
        seen.add(key)
        hits.append(
            TenderSearchHitOutput(
                title=line[:240],
                url=source_url,
                product=next((k for k in keywords if k.lower() in lower), keywords[0]),
                body=line,
                confidence=0.72,
                evidence_excerpt=line[:300],
            )
        )
        if len(hits) >= max_hits:
            break
    if not hits and any(keyword.lower() in page_text.lower() for keyword in keywords):
        excerpt = page_text[:400].strip()
        hits.append(
            TenderSearchHitOutput(
                title=f"Keyword match on {source_name}",
                url=source_url,
                product=keywords[0],
                body=excerpt,
                confidence=0.55,
                evidence_excerpt=excerpt,
            )
        )
    return hits
