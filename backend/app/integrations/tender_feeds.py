import re
from datetime import datetime, timedelta, timezone

import httpx

from app.ai.schemas import TenderSearchHitOutput

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
}


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


def search_ted_notices(
    *,
    keywords: list[str],
    search_date: datetime,
    limit: int = 10,
) -> tuple[list[TenderSearchHitOutput], str]:
    keywords = _prioritize_ted_keywords(keywords)
    date_from = (search_date.astimezone(timezone.utc) - timedelta(days=30)).strftime("%Y%m%d")
    query = f"{_keyword_query(keywords)} AND PD>={date_from}"
    payload = {
        "query": query,
        "fields": ["ND", "PD", "TI", "publication-number", "buyer-name"],
        "limit": limit,
        "scope": "ACTIVE",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            "https://api.ted.europa.eu/v3/notices/search",
            json=payload,
            headers={**DEFAULT_HEADERS, "Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

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
        hits.append(
            TenderSearchHitOutput(
                title=title,
                url=url,
                product=_product_from_notice_text(title, keywords),
                buyer=str(buyer) if buyer else None,
                publication_date=publication_date,
                body=title,
                confidence=0.95,
                evidence_excerpt=f"TED notice {publication_number}: {title}",
            )
        )
    return hits, "API"


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
