import pytest

from app.domain.enums import InternetSourceFetchStrategy, InternetSourceKind, MonitoringAccessMode
from app.domain.models import InternetSource, Product
from app.services.product_keyword_localization import (
    build_keyword_search_set,
    equivalent_terms_for_languages,
    localize_keywords_for_source,
)

pytestmark = pytest.mark.usefixtures("setup_database")


def _make_source(*, languages: list[str], product_tags: list[str] | None = None) -> InternetSource:
    return InternetSource(
        owner_id=None,
        name="Test source",
        base_url="https://example.com/tenders",
        source_kind=InternetSourceKind.TENDER_PORTAL.value,
        access_mode=MonitoringAccessMode.PUBLIC.value,
        fetch_strategy=InternetSourceFetchStrategy.HTML.value,
        regions=["Global"],
        product_tags=product_tags or [],
        languages=languages,
        is_active=True,
        priority=50,
    )


def test_localize_russian_keyword_for_english_platform(db):
    db.add(
        Product(
            normalized_name="Urea",
            category="fertilizer",
            aliases=["urea", "carbamide", "карбамид"],
            typical_units=["MT"],
        )
    )
    db.commit()

    source = _make_source(
        languages=["en"],
        product_tags=["urea", "carbamide", "fertilizer", "карбамид"],
    )
    search_set = build_keyword_search_set(db, ["карбамид"])
    localized = localize_keywords_for_source(search_set, source=source)

    assert "urea" in [term.lower() for term in localized]
    assert "carbamide" in [term.lower() for term in localized]
    assert not any("карбамид" == term.lower() for term in localized)


def test_localize_russian_keyword_for_spanish_platform(db):
    source = _make_source(languages=["es"])
    search_set = build_keyword_search_set(db, ["карбамид"])
    localized = localize_keywords_for_source(search_set, source=source)

    lowered = [term.lower() for term in localized]
    assert "carbamida" in lowered or "fertilizante" in lowered or "urea" in lowered
    assert not any("карбамид" == term.lower() for term in localized)


def test_localize_russian_keyword_for_french_platform(db):
    source = _make_source(languages=["fr"])
    search_set = build_keyword_search_set(db, ["карбамид"])
    localized = localize_keywords_for_source(search_set, source=source)

    lowered = [term.lower() for term in localized]
    assert "urée" in lowered or "engrais" in lowered or "carbamide" in lowered
    assert not any("карбамид" == term.lower() for term in localized)


def test_localize_russian_keyword_for_arabic_platform(db):
    source = _make_source(languages=["ar"])
    search_set = build_keyword_search_set(db, ["карбамид"])
    localized = localize_keywords_for_source(search_set, source=source)

    assert any("يوريا" in term or "أسمدة" in term or "كرباميد" in term for term in localized)
    assert not any("карбамид" == term.lower() for term in localized)


def test_localize_keeps_russian_for_russian_platform(db):
    source = _make_source(languages=["ru", "en"], product_tags=["карбамид", "urea"])
    search_set = build_keyword_search_set(db, ["карбамид"])
    localized = localize_keywords_for_source(search_set, source=source)

    assert "карбамид" in [term.lower() for term in localized]
    assert "urea" in [term.lower() for term in localized]


def test_spanish_input_for_french_platform(db):
    source = _make_source(languages=["fr"])
    search_set = build_keyword_search_set(db, ["fertilizante"])
    localized = localize_keywords_for_source(search_set, source=source)

    lowered = [term.lower() for term in localized]
    assert "engrais" in lowered or "urée" in lowered
    assert "fertilizante" not in lowered


def test_localize_russian_gum_keyword_for_english_platform(db):
    source = _make_source(languages=["en"])
    search_set = build_keyword_search_set(db, ["камедь"])
    localized = localize_keywords_for_source(search_set, source=source)

    lowered = [term.lower() for term in localized]
    assert "gum arabic" in lowered or "guar gum" in lowered
    assert not any(term.lower() == "камедь" for term in localized)


def test_equivalent_terms_support_multiple_languages():
    spanish = equivalent_terms_for_languages("карбамид", ["es"])
    french = equivalent_terms_for_languages("карбамид", ["fr"])
    arabic = equivalent_terms_for_languages("карбамид", ["ar"])

    assert spanish
    assert french
    assert arabic
