import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.ai.schemas import TenderHitEnrichmentOutput, TenderSearchHitOutput
from app.services.tender_hit_enrichment import enrich_tender_hits_with_ai, hit_needs_enrichment
from app.services.tender_hit_evaluation import evaluate_tender_hit

pytestmark = pytest.mark.usefixtures("setup_database")


def test_hit_needs_enrichment_when_deadline_missing():
    hit = TenderSearchHitOutput(title="Oil tender", url="https://example.com/1", confidence=0.9)
    assert hit_needs_enrichment(hit) is True


def test_hit_needs_enrichment_false_when_complete():
    hit = TenderSearchHitOutput(
        title="Oil tender",
        submission_deadline="2026-12-31",
        quantity=500,
        quantity_unit="MT",
        estimated_value=1200000,
        estimated_value_currency="EUR",
        confidence=0.9,
    )
    assert hit_needs_enrichment(hit) is False


@patch("app.services.tender_hit_enrichment.fetch_public_url_text")
def test_enrich_tender_hits_with_ai_merges_fields(mock_fetch, db):
    from app.security.auth import ensure_admin_user

    mock_fetch.return_value = (
        "Submission deadline: 2026-09-15\nQuantity: 2 500 MT\nEstimated contract value 1 200 000 EUR",
        b"",
    )
    hit = TenderSearchHitOutput(
        title="Transformer oil procurement",
        url="https://ted.europa.eu/en/notice/123/html",
        body="Transformer oil procurement",
        confidence=0.9,
    )
    user = ensure_admin_user(db)

    enriched, calls = enrich_tender_hits_with_ai(
        db,
        user=user,
        hits=[hit],
        product_keywords=["transformer oil"],
        verify_real=False,
    )
    assert calls == 1
    assert enriched[0].submission_deadline == "2026-09-15"
    assert str(enriched[0].quantity) == "2500"
    assert enriched[0].quantity_unit == "MT"
    assert str(enriched[0].estimated_value) == "1200000"
    assert enriched[0].estimated_value_currency == "EUR"


def test_expired_deadline_after_enrichment():
    hit = TenderSearchHitOutput(
        title="Old tender",
        product="oil",
        body="transformer oil",
        submission_deadline="2020-01-01",
        confidence=0.9,
    )
    evaluation = evaluate_tender_hit(
        hit,
        user_keywords=["transformer oil"],
        reference_date=datetime(2026, 7, 12, tzinfo=timezone.utc),
    )
    assert evaluation.submission_expired is True
    assert evaluation.display_status == "EXPIRED"


def test_unknown_deadline_label():
    hit = TenderSearchHitOutput(
        title="Transformer oil procurement",
        product="transformer oil",
        body="Procurement of insulating oil",
        confidence=0.9,
    )
    evaluation = evaluate_tender_hit(
        hit,
        user_keywords=["трансформаторное масло"],
        reference_date=datetime(2026, 7, 12, tzinfo=timezone.utc),
    )
    assert evaluation.deadline_known is False
    assert "срок не указан" in evaluation.display_status_label
