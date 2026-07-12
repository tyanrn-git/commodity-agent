import pytest
from datetime import datetime, timezone

from app.ai.schemas import TenderSearchHitOutput
from app.services.tender_hit_evaluation import evaluate_tender_hit

pytestmark = pytest.mark.usefixtures("setup_database")


def test_expired_submission_deadline():
    hit = TenderSearchHitOutput(
        title="Urea procurement Finland",
        product="urea",
        body="Finland urea tender",
        deadline="2020-01-01",
        submission_deadline="2020-01-01",
        confidence=0.9,
    )
    evaluation = evaluate_tender_hit(
        hit,
        user_keywords=["urea"],
        reference_date=datetime(2026, 7, 12, tzinfo=timezone.utc),
    )
    assert evaluation.submission_expired is True
    assert evaluation.display_status == "EXPIRED"


def test_product_mismatch():
    hit = TenderSearchHitOutput(
        title="Office furniture procurement",
        product="furniture",
        body="Chairs and desks",
        confidence=0.9,
    )
    evaluation = evaluate_tender_hit(
        hit,
        user_keywords=["urea"],
        reference_date=datetime(2026, 7, 12, tzinfo=timezone.utc),
    )
    assert evaluation.product_match is False
    assert evaluation.display_status == "MISMATCH"


def test_active_matching_tender():
    hit = TenderSearchHitOutput(
        title="Finland - Urea procurement 2026",
        product="urea",
        body="Procurement of urea fertilizer",
        submission_deadline="2026-12-31",
        quantity=1000,
        quantity_unit="MT",
        confidence=0.9,
    )
    evaluation = evaluate_tender_hit(
        hit,
        user_keywords=["карбамид"],
        reference_date=datetime(2026, 7, 12, tzinfo=timezone.utc),
    )
    assert evaluation.product_match is True
    assert evaluation.display_status == "ACTIVE"
    assert evaluation.volume == "1000 MT"
