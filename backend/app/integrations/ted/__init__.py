from app.integrations.ted.base import TedSearchProvider, TedSearchResult
from app.integrations.ted.provider import OfficialTedSearchProvider, is_ted_api_url, is_ted_source, is_ted_web_portal

_default_provider: TedSearchProvider | None = None


def get_ted_search_provider() -> TedSearchProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = OfficialTedSearchProvider()
    return _default_provider


__all__ = [
    "TedSearchProvider",
    "TedSearchResult",
    "OfficialTedSearchProvider",
    "get_ted_search_provider",
    "is_ted_api_url",
    "is_ted_source",
    "is_ted_web_portal",
]
