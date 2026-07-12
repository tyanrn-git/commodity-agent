from decimal import Decimal

import pytest
from sqlalchemy import select

from app.ai.schemas import OpportunityExtractionOutput
from app.domain.models import AuditLog
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.ai_budget import (
    check_budget,
    ensure_ai_budget_settings,
    log_ai_usage,
    update_ai_budget_settings,
)
from app.services.extraction import extract_opportunity_from_source, save_document_source
from app.services.opportunity import create_buyer_led_opportunity

pytestmark = pytest.mark.usefixtures("setup_database")


def _eml_bytes(body: str, subject: str = "RFQ SN500") -> bytes:
    return (
        f"Subject: {subject}\r\n"
        f"From: buyer@example.com\r\n"
        f"To: seller@example.com\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n"
        f"{body}"
    ).encode()


def test_ai_budget_settings_created_for_user(auth_client, db):
    from app.config import settings
    from app.domain.models import User

    user = db.scalar(select(User).where(User.email == settings.admin_email))
    cfg = ensure_ai_budget_settings(db, user)
    assert cfg.monthly_budget_usd == Decimal("100")
    assert cfg.ai_enabled is True


def test_budget_update_creates_audit(auth_client, db):
    from app.config import settings
    from app.domain.models import User

    user = db.scalar(select(User).where(User.email == settings.admin_email))
    update_ai_budget_settings(db, user=user, data={"monthly_budget_usd": Decimal("80")})
    logs = list(
        db.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "AIBudgetSettings",
                AuditLog.action == "UPDATE",
            )
        )
    )
    assert len(logs) >= 1


def test_hard_limit_blocks_ai_call(auth_client, db):
    from app.config import settings
    from app.domain.models import User

    user = db.scalar(select(User).where(User.email == settings.admin_email))
    cfg = ensure_ai_budget_settings(db, user)
    cfg.monthly_budget_usd = Decimal("0.0001")
    cfg.hard_limit_enabled = True
    db.commit()

    log_ai_usage(
        db,
        user=user,
        model="mock-model",
        operation="extraction",
        cost_usd=Decimal("0.001"),
        input_tokens=100,
        output_tokens=50,
    )
    db.commit()

    result = check_budget(db, user=user)
    assert result.allowed is False
    assert "budget" in (result.reason or "").lower()


def test_extraction_with_mock_provider(auth_client, db):
    from app.config import settings
    from app.domain.models import User

    user = db.scalar(select(User).where(User.email == settings.admin_email))
    cfg = ensure_ai_budget_settings(db, user)
    cfg.monthly_budget_usd = Decimal("100")
    db.commit()

    opp = create_buyer_led_opportunity(db, user=user, title="SN500 extraction test")
    storage = LocalFilesystemStorage()
    eml_content = _eml_bytes(
        "Please quote Base Oil SN500 100-200 MT CIF Rotterdam flexitank deadline 2026-08-31"
    )
    source = save_document_source(
        db,
        user=user,
        opportunity=opp,
        filename="rfq.eml",
        content=eml_content,
        mime_type="message/rfc822",
        storage=storage,
        source_type="EMAIL",
    )

    result = extract_opportunity_from_source(
        db,
        user=user,
        source=source,
        storage=storage,
        force=True,
    )
    assert result.status in {"SUCCESS", "NEEDS_REVIEW", "CACHED"}
    assert result.extracted_data is not None
    parsed = OpportunityExtractionOutput.model_validate(result.extracted_data)
    assert parsed.raw_product_name == "Base Oil SN500"
    assert parsed.quantity_min == Decimal("100")


def test_extraction_cache(auth_client, db):
    from app.config import settings
    from app.domain.models import User

    user = db.scalar(select(User).where(User.email == settings.admin_email))
    opp = create_buyer_led_opportunity(db, user=user, title="Cache test")
    storage = LocalFilesystemStorage()
    content = _eml_bytes("SN500 100 MT Rotterdam CIF")
    source1 = save_document_source(
        db,
        user=user,
        opportunity=opp,
        filename="a.eml",
        content=content,
        mime_type="message/rfc822",
        storage=storage,
        source_type="EMAIL",
    )
    first = extract_opportunity_from_source(db, user=user, source=source1, storage=storage, force=True)

    source2 = save_document_source(
        db,
        user=user,
        opportunity=opp,
        filename="b.eml",
        content=content,
        mime_type="message/rfc822",
        storage=storage,
        source_type="EMAIL",
    )
    second = extract_opportunity_from_source(db, user=user, source=source2, storage=storage, force=False)
    assert second.status == "CACHED"
    assert second.extracted_data == first.extracted_data


def test_ai_usage_api(auth_client):
    budget = auth_client.get("/settings/ai-budget")
    assert budget.status_code == 200
    assert budget.json()["monthly_budget_usd"] == "100.0000"

    usage = auth_client.get("/settings/ai-usage")
    assert usage.status_code == 200
    assert "spent_usd" in usage.json()


def test_extract_endpoint(auth_client, db):
    create = auth_client.post("/opportunities", json={"title": "API extract"})
    opp_id = create.json()["id"]
    eml = _eml_bytes("SN500 100 MT to Rotterdam CIF flexitank deadline 2026-08-31")
    upload = auth_client.post(
        f"/opportunities/{opp_id}/import-eml",
        files={"file": ("msg.eml", eml, "message/rfc822")},
    )
    assert upload.status_code == 201
    source_id = upload.json()["id"]
    extract = auth_client.post(f"/sources/{source_id}/extract", json={"force": True})
    assert extract.status_code == 200
    body = extract.json()
    assert body["extracted_data"] is not None
    assert body["status"] in {"SUCCESS", "NEEDS_REVIEW"}
