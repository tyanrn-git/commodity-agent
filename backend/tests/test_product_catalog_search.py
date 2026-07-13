import pytest
from sqlalchemy import select

from app.domain.models import Product, ProductSpecificationProfile
from app.services.product_assistant import bootstrap_product_spec_scaffold
from app.services.product_catalog import create_product
from app.services.product_catalog_search import ensure_catalog_product_for_keywords, find_catalog_product_by_keywords
from app.services.internet_source_search import run_internet_source_search
from app.security.auth import ensure_admin_user

pytestmark = pytest.mark.usefixtures("setup_database")


def test_bootstrap_product_spec_scaffold_creates_profiles(db):
    user = ensure_admin_user(db)
    product = create_product(
        db,
        user=user,
        normalized_name="Test Scaffold Product",
        category="other",
        auto_bootstrap_specs=False,
    )
    result = bootstrap_product_spec_scaffold(db, user=user, product=product)
    assert result["parameters_added"] >= 1
    profiles = list(
        db.scalars(
            select(ProductSpecificationProfile).where(ProductSpecificationProfile.product_id == product.id)
        )
    )
    assert len(profiles) >= 1


def test_create_product_auto_scaffolds_specs(db):
    user = ensure_admin_user(db)
    product = create_product(
        db,
        user=user,
        normalized_name="Auto Scaffold Widget",
        category="chemicals",
    )
    profiles = list(
        db.scalars(
            select(ProductSpecificationProfile).where(ProductSpecificationProfile.product_id == product.id)
        )
    )
    assert len(profiles) >= 1


def test_ensure_catalog_product_for_keywords_creates_product(db):
    user = ensure_admin_user(db)
    unique_keyword = "RareCommodityXYZ-42"
    product, created = ensure_catalog_product_for_keywords(db, user=user, keywords=[unique_keyword])
    assert product.normalized_name
    assert find_catalog_product_by_keywords(db, [unique_keyword]) is not None
    if created:
        assert product.normalized_name.lower() in {unique_keyword.lower(), "rarecommodityxyz-42"}


def test_ensure_catalog_product_reuses_existing(db):
    user = ensure_admin_user(db)
    unique_name = "UniqueTestOil-99"
    existing = create_product(
        db,
        user=user,
        normalized_name=unique_name,
        category="base_oil",
        auto_bootstrap_specs=False,
    )
    product, created = ensure_catalog_product_for_keywords(
        db,
        user=user,
        keywords=[unique_name],
    )
    assert created is False
    assert product.id == existing.id


def test_search_run_links_product_id(db):
    user = ensure_admin_user(db)
    run, _ = run_internet_source_search(
        db,
        user=user,
        product_keywords=["guar gum"],
        regions=["EU"],
        verify_real=False,
        auto_discover_sources=False,
        max_sources=1,
    )
    assert run.product_id is not None
    product = db.get(Product, run.product_id)
    assert product is not None
