from datetime import datetime, timezone
import uuid

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import (
    AuditAction,
    ComplianceReviewStatus,
    ContactVerificationStatus,
    CounterpartyVerificationStatus,
)
from app.domain.models import CompanySettings, Contact, Counterparty, CounterpartyCapability, User
from app.services.audit import log_audit
from app.services.domain_verification import verify_counterparty_domain


def ensure_company_settings(db: Session, user: User) -> CompanySettings:
    settings = db.scalar(select(CompanySettings).where(CompanySettings.user_id == user.id))
    if settings:
        return settings
    settings = CompanySettings(
        user_id=user.id,
        legal_name="Demo Trading Ltd",
        trade_name="Demo Trading",
        brand_name="Demo Trading",
        default_rfq_language="en",
        email_signature_text="Best regards,\nDemo Trading Ltd",
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def update_company_settings(db: Session, *, user: User, data: dict) -> CompanySettings:
    settings = ensure_company_settings(db, user)
    old = {
        "legal_name": settings.legal_name,
        "trade_name": settings.trade_name,
        "brand_name": settings.brand_name,
        "default_rfq_language": settings.default_rfq_language,
    }
    for key, value in data.items():
        if value is not None and hasattr(settings, key):
            setattr(settings, key, value)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="CompanySettings",
        entity_id=settings.id,
        old_value=old,
        new_value=data,
    )
    db.commit()
    db.refresh(settings)
    return settings


def create_counterparty(db: Session, *, user: User, data: dict) -> Counterparty:
    counterparty = Counterparty(
        owner_id=user.id,
        legal_name=data["legal_name"],
        trade_name=data.get("trade_name"),
        organization_type=data.get("organization_type", "OTHER"),
        incorporation_country=data.get("incorporation_country"),
        operating_countries=data.get("operating_countries"),
        registration_number=data.get("registration_number"),
        tax_id=data.get("tax_id"),
        website=data.get("website"),
        primary_domain=data.get("primary_domain"),
        address=data.get("address"),
        verification_status=CounterpartyVerificationStatus.DISCOVERED.value,
        compliance_review_status=ComplianceReviewStatus.NOT_REVIEWED.value,
        risk_flags=data.get("risk_flags"),
        source_ids=data.get("source_ids"),
    )
    db.add(counterparty)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="Counterparty",
        entity_id=counterparty.id,
        new_value={"legal_name": counterparty.legal_name},
    )
    db.commit()
    db.refresh(counterparty)
    return counterparty


def seed_demo_counterparties(db: Session, user: User) -> None:
    demos = [
        {
            "legal_name": "Gulf Base Oil Refinery LLC",
            "trade_name": "Gulf Base Oil",
            "organization_type": "PRODUCER",
            "incorporation_country": "UAE",
            "website": "https://gulfbasoil.example.com",
            "primary_domain": "gulfbasoil.example.com",
            "address": "Jebel Ali Free Zone, Dubai, UAE",
            "contact": {
                "full_name": "Ahmed Al-Rashid",
                "role_title": "Sales Manager",
                "email": "sales@gulfbasoil.example.com",
                "is_primary": True,
            },
        },
        {
            "legal_name": "Rotterdam Base Oils BV",
            "trade_name": "Rotterdam Base Oils",
            "organization_type": "TRADER",
            "incorporation_country": "Netherlands",
            "website": "https://rotterdambaseoils.example.com",
            "primary_domain": "rotterdambaseoils.example.com",
            "address": "Waalhaven Zuid 123, Rotterdam, Netherlands",
            "contact": {
                "full_name": "Jan de Vries",
                "role_title": "Procurement",
                "email": "procurement@rotterdambaseoils.example.com",
                "is_primary": True,
            },
        },
        {
            "legal_name": "Global Freight Partners Ltd",
            "trade_name": "GFP Logistics",
            "organization_type": "FORWARDER",
            "incorporation_country": "Singapore",
            "website": "https://gfplogistics.example.com",
            "primary_domain": "gfplogistics.example.com",
            "address": "1 Harbour Drive, Singapore",
            "contact": {
                "full_name": "Maria Chen",
                "role_title": "Freight Desk",
                "email": "freight@gfplogistics.example.com",
                "is_primary": True,
            },
        },
    ]

    for item in demos:
        counterparty = db.scalar(
            select(Counterparty).where(
                Counterparty.owner_id == user.id,
                Counterparty.legal_name == item["legal_name"],
            )
        )
        if counterparty is None:
            counterparty = create_counterparty(
                db,
                user=user,
                data={k: v for k, v in item.items() if k != "contact"},
            )
        contact_data = item["contact"]
        existing_contact = db.scalar(
            select(Contact).where(
                Contact.counterparty_id == counterparty.id,
                Contact.email == contact_data["email"],
            )
        )
        if existing_contact is None:
            create_contact(db, user=user, counterparty=counterparty, data=contact_data)


def update_counterparty(
    db: Session, *, user: User, counterparty: Counterparty, data: dict
) -> Counterparty:
    for key, value in data.items():
        if value is not None and hasattr(counterparty, key):
            setattr(counterparty, key, value)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="Counterparty",
        entity_id=counterparty.id,
        new_value=data,
    )
    db.commit()
    db.refresh(counterparty)
    return counterparty


def create_contact(db: Session, *, user: User, counterparty: Counterparty, data: dict) -> Contact:
    if counterparty.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counterparty not found")

    contact = Contact(
        counterparty_id=counterparty.id,
        full_name=data.get("full_name"),
        role_title=data.get("role_title"),
        department=data.get("department"),
        email=data.get("email"),
        phone=data.get("phone"),
        preferred_language=data.get("preferred_language", "en"),
        verification_status=ContactVerificationStatus.DISCOVERED.value,
        is_primary=data.get("is_primary", False),
    )
    db.add(contact)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="Contact",
        entity_id=contact.id,
        new_value={"counterparty_id": str(counterparty.id), "email": contact.email},
    )
    db.commit()
    db.refresh(contact)
    return contact


def run_domain_verification(db: Session, *, user: User, counterparty: Counterparty) -> dict:
    primary_contact = db.scalar(
        select(Contact)
        .where(Contact.counterparty_id == counterparty.id, Contact.is_primary.is_(True))
        .limit(1)
    )
    if primary_contact is None:
        primary_contact = db.scalar(
            select(Contact).where(Contact.counterparty_id == counterparty.id).limit(1)
        )

    report = verify_counterparty_domain(
        primary_domain=counterparty.primary_domain,
        website=counterparty.website,
        contact_email=primary_contact.email if primary_contact else None,
    )
    counterparty.domain_verification_report = report
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="Counterparty",
        entity_id=counterparty.id,
        new_value={"action": "verify_domain", "report": report},
    )
    db.commit()
    return report


def confirm_domain_verification(db: Session, *, user: User, counterparty: Counterparty) -> Counterparty:
    report = counterparty.domain_verification_report or {}
    if not report.get("ready_for_user_confirmation"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain verification checks are not ready for confirmation",
        )
    counterparty.verification_status = CounterpartyVerificationStatus.DOMAIN_VERIFIED.value
    db.flush()
    for contact in counterparty.contacts:
        if contact.email:
            contact.verification_status = ContactVerificationStatus.DOMAIN_VERIFIED.value
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="Counterparty",
        entity_id=counterparty.id,
        new_value={"verification_status": counterparty.verification_status},
    )
    db.commit()
    db.refresh(counterparty)
    return counterparty


def mark_compliance_reviewed(db: Session, *, user: User, counterparty: Counterparty) -> Counterparty:
    counterparty.compliance_review_status = ComplianceReviewStatus.MANUALLY_REVIEWED.value
    counterparty.compliance_reviewed_at = datetime.now(timezone.utc)
    counterparty.compliance_reviewed_by_id = user.id
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="Counterparty",
        entity_id=counterparty.id,
        new_value={"compliance_review_status": counterparty.compliance_review_status},
    )
    db.commit()
    db.refresh(counterparty)
    return counterparty


def list_counterparties_summary(db: Session, *, user: User) -> list[dict]:
    counterparties = list(
        db.scalars(
            select(Counterparty)
            .where(Counterparty.owner_id == user.id)
            .order_by(Counterparty.created_at.desc())
        )
    )
    if not counterparties:
        return []

    counterparty_ids = [item.id for item in counterparties]
    contact_counts = {
        row[0]: row[1]
        for row in db.execute(
            select(Contact.counterparty_id, func.count())
            .where(Contact.counterparty_id.in_(counterparty_ids))
            .group_by(Contact.counterparty_id)
        )
    }
    capability_rows = db.execute(
        select(
            CounterpartyCapability.counterparty_id,
            func.count(),
            func.sum(case((CounterpartyCapability.user_confirmed.is_(True), 1), else_=0)),
        )
        .where(CounterpartyCapability.counterparty_id.in_(counterparty_ids))
        .group_by(CounterpartyCapability.counterparty_id)
    ).all()
    capability_counts: dict[uuid.UUID, tuple[int, int]] = {
        row[0]: (int(row[1] or 0), int(row[2] or 0)) for row in capability_rows
    }

    items: list[dict] = []
    for counterparty in counterparties:
        caps_total, caps_confirmed = capability_counts.get(counterparty.id, (0, 0))
        items.append(
            {
                "counterparty": counterparty,
                "contacts_count": int(contact_counts.get(counterparty.id, 0)),
                "capabilities_count": caps_total,
                "confirmed_capabilities_count": caps_confirmed,
            }
        )
    return items


def get_counterparty(db: Session, *, user: User, counterparty_id: uuid.UUID) -> Counterparty:
    counterparty = db.scalar(
        select(Counterparty)
        .where(Counterparty.id == counterparty_id, Counterparty.owner_id == user.id)
        .options(joinedload(Counterparty.contacts))
    )
    if counterparty is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counterparty not found")
    return counterparty
