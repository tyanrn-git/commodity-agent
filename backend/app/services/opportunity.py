import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import AuditAction, DealDirection, DealOutcome, DealStage, OpportunityStatus, OpportunityType, SourceType
from app.domain.models import Deal, Evidence, Opportunity, Product, Requirement, Source, User
from app.integrations.storage.local import LocalFilesystemStorage
from app.security.auth import generate_deal_number
from app.services.audit import log_audit
from app.services.opportunity_status import initialize_opportunity_status, transition_opportunity_status

ALLOWED_PDF_MIME = {"application/pdf"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}


def _decimal_to_str(value: Decimal | float | None) -> str | None:
    if value is None:
        return None
    return str(value)


def opportunity_to_dict(opp: Opportunity) -> dict:
    return {
        "id": str(opp.id),
        "type": opp.type,
        "title": opp.title,
        "status": opp.status,
        "raw_product_name": opp.raw_product_name,
        "normalized_product_id": str(opp.normalized_product_id) if opp.normalized_product_id else None,
        "quantity_min": _decimal_to_str(opp.quantity_min),
        "quantity_max": _decimal_to_str(opp.quantity_max),
        "quantity_unit": opp.quantity_unit,
        "origin_hint": opp.origin_hint,
        "destination_hint": opp.destination_hint,
        "deadline": opp.deadline.isoformat() if opp.deadline else None,
        "quote_deadline": opp.quote_deadline.isoformat() if opp.quote_deadline else None,
        "delivery_deadline": opp.delivery_deadline.isoformat() if opp.delivery_deadline else None,
        "status_changed_at": opp.status_changed_at.isoformat() if opp.status_changed_at else None,
    }


def create_buyer_led_opportunity(
    db: Session,
    *,
    user: User,
    title: str,
    raw_product_name: str | None = None,
    normalized_product_id: uuid.UUID | None = None,
    buyer_or_supplier_hint: str | None = None,
    quantity_min: Decimal | None = None,
    quantity_max: Decimal | None = None,
    quantity_unit: str | None = None,
    origin_hint: str | None = None,
    destination_hint: str | None = None,
    deadline: datetime | None = None,
    quote_deadline: datetime | None = None,
    delivery_deadline: datetime | None = None,
    notes: str | None = None,
) -> Opportunity:
    if normalized_product_id:
        product = db.get(Product, normalized_product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    opportunity = Opportunity(
        owner_id=user.id,
        type=OpportunityType.BUYER_NEED.value,
        title=title,
        raw_product_name=raw_product_name,
        normalized_product_id=normalized_product_id,
        buyer_or_supplier_hint=buyer_or_supplier_hint,
        quantity_min=quantity_min,
        quantity_max=quantity_max,
        quantity_unit=quantity_unit,
        origin_hint=origin_hint,
        destination_hint=destination_hint,
        deadline=deadline or quote_deadline,
        quote_deadline=quote_deadline or deadline,
        delivery_deadline=delivery_deadline,
        status=OpportunityStatus.NEW.value,
        notes=notes,
    )
    db.add(opportunity)
    db.flush()
    initialize_opportunity_status(db, opportunity=opportunity, actor=user, actor_type="USER")
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="Opportunity",
        entity_id=opportunity.id,
        new_value=opportunity_to_dict(opportunity),
    )
    db.commit()
    db.refresh(opportunity)
    return opportunity


def update_opportunity(db: Session, *, user: User, opportunity: Opportunity, data: dict) -> Opportunity:
    if opportunity.status == OpportunityStatus.CONVERTED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Converted opportunity cannot be edited")

    old_value = opportunity_to_dict(opportunity)
    status_update = data.pop("status", None)
    status_note = data.pop("status_note", None)
    for field, value in data.items():
        if value is not None and hasattr(opportunity, field):
            setattr(opportunity, field, value)
    if status_update is not None:
        transition_opportunity_status(
            db,
            opportunity=opportunity,
            new_status=status_update,
            actor=user,
            note=status_note,
        )
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="Opportunity",
        entity_id=opportunity.id,
        old_value=old_value,
        new_value=opportunity_to_dict(opportunity),
    )
    db.commit()
    db.refresh(opportunity)
    return opportunity


def upload_pdf_source(
    db: Session,
    *,
    user: User,
    opportunity: Opportunity,
    file: UploadFile,
    storage: LocalFilesystemStorage,
) -> Source:
    filename = file.filename or "document.pdf"
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_PDF_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are allowed")
    if file.content_type and file.content_type not in ALLOWED_PDF_MIME:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PDF content type")

    content = file.file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    storage_key = f"opportunities/{opportunity.id}/{uuid.uuid4()}{extension}"
    storage.save(storage_key, content)

    source = Source(
        opportunity_id=opportunity.id,
        source_type=SourceType.DOCUMENT.value,
        original_filename=filename,
        mime_type=file.content_type or "application/pdf",
        storage_key=storage_key,
        file_size_bytes=len(content),
        is_immutable=True,
        uploaded_by_id=user.id,
    )
    db.add(source)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPLOAD,
        entity_type="Source",
        entity_id=source.id,
        new_value={
            "opportunity_id": str(opportunity.id),
            "storage_key": storage_key,
            "original_filename": filename,
        },
    )
    db.commit()
    db.refresh(source)
    return source


def convert_opportunity_to_deal(db: Session, *, user: User, opportunity: Opportunity) -> Deal:
    if opportunity.status == OpportunityStatus.CONVERTED.value:
        existing = db.scalar(select(Deal).where(Deal.origin_opportunity_id == opportunity.id))
        if existing:
            return existing
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Opportunity already converted")

    deal = Deal(
        deal_number=generate_deal_number(),
        title=opportunity.title,
        origin_opportunity_id=opportunity.id,
        direction=(
            DealDirection.SUPPLIER_LED.value
            if opportunity.type == OpportunityType.SUPPLIER_OFFER.value
            else DealDirection.BUYER_LED.value
        ),
        base_currency="USD",
        owner_id=user.id,
        stage=DealStage.QUALIFICATION.value,
        outcome=DealOutcome.OPEN.value,
        deadline=opportunity.quote_deadline or opportunity.deadline,
    )
    transition_opportunity_status(
        db,
        opportunity=opportunity,
        new_status=OpportunityStatus.CONVERTED.value,
        actor=user,
        note="Конвертация в сделку",
    )
    db.add(deal)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.CONVERT,
        entity_type="Deal",
        entity_id=deal.id,
        new_value={"deal_number": deal.deal_number, "opportunity_id": str(opportunity.id)},
    )
    db.commit()
    db.refresh(deal)
    return deal


def create_requirement(
    db: Session,
    *,
    user: User,
    deal: Deal,
    product_id: uuid.UUID | None = None,
    quantity_min: Decimal | None = None,
    quantity_max: Decimal | None = None,
    quantity_unit: str | None = None,
    destination: str | None = None,
    requested_incoterm: str | None = None,
    packaging: str | None = None,
    commercial_deadline: datetime | None = None,
    user_confirmed: bool = False,
    evidence: list[dict] | None = None,
) -> Requirement:
    requirement = Requirement(
        deal_id=deal.id,
        product_id=product_id,
        quantity_min=quantity_min,
        quantity_max=quantity_max,
        quantity_unit=quantity_unit,
        destination=destination,
        requested_incoterm=requested_incoterm,
        packaging=packaging,
        commercial_deadline=commercial_deadline,
        user_confirmed=user_confirmed,
    )
    db.add(requirement)
    db.flush()

    if evidence:
        for item in evidence:
            ev = Evidence(
                requirement_id=requirement.id,
                source_id=item.get("source_id"),
                field_path=item["field_path"],
                excerpt=item.get("excerpt"),
                page_number=item.get("page_number"),
                user_confirmed=item.get("user_confirmed", False),
            )
            db.add(ev)

    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="Requirement",
        entity_id=requirement.id,
        new_value={"deal_id": str(deal.id), "user_confirmed": user_confirmed},
    )
    db.commit()
    db.refresh(requirement)
    return requirement


def seed_products(db: Session) -> None:
    products = [
        ("SN500", "base_oil", ["Base Oil SN500"], ["MT", "kg"]),
        ("SN150", "base_oil", ["Base Oil SN150"], ["MT", "kg"]),
        ("Guar Gum", "polymer", ["guar gum", "гуар", "гуаровая камедь", "камедь"], ["MT", "kg"]),
        ("Gum Arabic", "polymer", ["gum arabic", "acacia gum", "арабская камедь", "гуммиарабик", "камедь"], ["MT", "kg"]),
    ]
    for name, category, aliases, units in products:
        existing = db.scalar(select(Product).where(Product.normalized_name == name))
        if existing:
            continue
        db.add(
            Product(
                normalized_name=name,
                category=category,
                aliases=aliases,
                typical_units=units,
            )
        )
    db.commit()
