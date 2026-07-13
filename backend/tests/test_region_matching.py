from app.domain.enums import InternetSourceFetchStrategy
from app.domain.models import InternetSource
from app.services.internet_source_catalog import (
    _source_region_matches,
    expand_region_filters,
    match_internet_sources,
)


def test_expand_region_filters_russia_aliases():
    expanded = expand_region_filters(["Russia"])
    assert "russia" in expanded
    assert "россия" in expanded
    assert "ru" in expanded


def test_global_source_does_not_match_russia_only():
    source = InternetSource(
        name="World Bank",
        base_url="https://example.com",
        regions=["Global"],
        fetch_strategy=InternetSourceFetchStrategy.WORLD_BANK_API.value,
    )
    assert _source_region_matches(source, ["Russia"]) is False


def test_global_source_matches_when_global_requested():
    source = InternetSource(
        name="World Bank",
        base_url="https://example.com",
        regions=["Global"],
    )
    assert _source_region_matches(source, ["Global"]) is True


def test_russia_source_matches_russia_filter():
    source = InternetSource(
        name="Zakupki",
        base_url="https://zakupki.gov.ru/",
        regions=["Russia"],
    )
    assert _source_region_matches(source, ["Russia"]) is True
    assert _source_region_matches(source, ["Россия"]) is True


def test_eu_source_does_not_match_russia_filter():
    source = InternetSource(
        name="TED",
        base_url="https://api.ted.europa.eu/",
        regions=["EU", "Europe"],
        fetch_strategy=InternetSourceFetchStrategy.TED_API.value,
        product_tags=["transformer oil", "procurement"],
        is_active=True,
        priority=95,
    )
    assert _source_region_matches(source, ["Russia"]) is False


def test_match_russia_excludes_eu_portals_with_global_tag():
    sources = [
        InternetSource(
            name="EEX",
            base_url="https://eex.com/",
            regions=["EU", "Global"],
            product_tags=["трансформаторное масло"],
            is_active=True,
            priority=70,
        ),
        InternetSource(
            name="Zakupki",
            base_url="https://zakupki.gov.ru/",
            regions=["Russia"],
            product_tags=["трансформаторное масло", "procurement"],
            is_active=True,
            priority=90,
        ),
    ]
    matched = match_internet_sources(
        sources,
        product_keywords=["трансформаторное масло"],
        regions=["Russia"],
    )
    names = [source.name for source in matched]
    assert "Zakupki" in names
    assert "EEX" not in names
