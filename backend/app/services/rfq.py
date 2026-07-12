import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.ai.factory import get_ai_provider
from app.ai.schemas import RFQDraftOutput
from app.domain.enums import (
    ApprovalStatus,
    AuditAction,
    BindingClass,
    ComplianceReviewStatus,
    RFQStatus,
)
from app.domain.models import (
    ApprovalRequest,
    CompanySettings,
    Contact,
    Counterparty,
    Deal,
    DealParty,
    Requirement,
    RFQ,
    RFQTemplate,
    User,
)
from app.services.ai_budget import check_budget, ensure_ai_budget_settings, log_ai_usage
from app.services.audit import log_audit
from app.services.counterparty import ensure_company_settings


RFQ_TRANSITIONS: dict[str, set[str]] = {
    RFQStatus.DRAFT.value: {RFQStatus.PENDING_APPROVAL.value, RFQStatus.CANCELLED.value},
    RFQStatus.PENDING_APPROVAL.value: {
        RFQStatus.APPROVED.value,
        RFQStatus.DRAFT.value,
        RFQStatus.CANCELLED.value,
    },
    RFQStatus.APPROVED.value: {RFQStatus.DRAFT.value},
}


def seed_rfq_templates(db: Session) -> None:
    templates = [
        {
            "name": "Product RFQ - Supplier",
            "rfq_type": "PRODUCT",
            "language": "en",
            "subject_template": "RFQ: {product} supply for {destination}",
            "body_template": (
                "Dear {recipient_name},\n\n"
                "Please provide your best offer for {product} with the following details:\n"
                "- Available quantity\n"
                "- Loading point / origin\n"
                "- Incoterm\n"
                "- Price and currency\n"
                "- Validity\n"
                "- Payment terms\n"
                "- Product specification compliance\n\n"
                "Requested fields: {requested_fields}\n\n"
                "This message is a request for quotation only.\n\n"
                "{signature}"
            ),
            "default_requested_fields": [
                "quantity",
                "price",
                "currency",
                "incoterm",
                "origin",
                "validity",
                "payment_terms",
                "specification",
            ],
        },
        {
            "name": "Freight RFQ - Forwarder",
            "rfq_type": "FREIGHT",
            "language": "en",
            "subject_template": "Freight inquiry: {route}",
            "body_template": (
                "Dear {recipient_name},\n\n"
                "Please quote freight for {route} including:\n"
                "- Equipment type\n"
                "- Transit time\n"
                "- All-in freight cost and currency\n"
                "- Quote validity\n\n"
                "Requested fields: {requested_fields}\n\n"
                "{signature}"
            ),
            "default_requested_fields": [
                "freight_cost",
                "currency",
                "equipment_type",
                "transit_time",
                "validity",
            ],
        },
    ]
    for item in templates:
        existing = db.scalar(
            select(RFQTemplate).where(
                RFQTemplate.name == item["name"],
                RFQTemplate.rfq_type == item["rfq_type"],
            )
        )
        if existing:
            continue
        db.add(RFQTemplate(**item))
    db.commit()


def _snapshot_hash(subject: str, body: str, recipients: list) -> str:
    payload = json.dumps(
        {"subject": subject, "body": body, "recipients": recipients},
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _active_approval(db: Session, rfq: RFQ) -> ApprovalRequest | None:
    return db.scalar(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.rfq_id == rfq.id,
            ApprovalRequest.approval_status.in_(
                [ApprovalStatus.PENDING.value, ApprovalStatus.APPROVED.value]
            ),
        )
        .order_by(ApprovalRequest.created_at.desc())
    )


def _invalidate_approval(db: Session, *, rfq: RFQ) -> None:
    approval = _active_approval(db, rfq)
    if approval:
        approval.approval_status = ApprovalStatus.INVALIDATED.value
    if rfq.status in {RFQStatus.PENDING_APPROVAL.value, RFQStatus.APPROVED.value}:
        rfq.status = RFQStatus.DRAFT.value


def _build_recipients(rfq: RFQ) -> list[dict]:
    contact = rfq.contact
    if contact and contact.email:
        return [{"type": "to", "email": contact.email, "name": contact.full_name}]
    counterparty = rfq.target_deal_party.counterparty if rfq.target_deal_party else None
    if counterparty:
        for c in counterparty.contacts:
            if c.email:
                return [{"type": "to", "email": c.email, "name": c.full_name}]
    return []


def _compliance_warnings(rfq: RFQ) -> list[str]:
    warnings: list[str] = []
    counterparty = rfq.target_deal_party.counterparty if rfq.target_deal_party else None
    if counterparty is None:
        warnings.append("missing_counterparty")
        return warnings
    if counterparty.compliance_review_status == ComplianceReviewStatus.NOT_REVIEWED.value:
        warnings.append("counterparty_not_reviewed")
    if counterparty.compliance_review_status == ComplianceReviewStatus.REVIEW_REQUIRED.value:
        warnings.append("counterparty_review_required")
    recipients = _build_recipients(rfq)
    if not recipients:
        warnings.append("missing_recipient_email")
    return warnings


def create_rfq(
    db: Session,
    *,
    user: User,
    deal: Deal,
    target_deal_party_id: uuid.UUID,
    rfq_type: str,
    contact_id: uuid.UUID | None = None,
    template_id: uuid.UUID | None = None,
    requested_fields: list[str] | None = None,
    language: str | None = None,
) -> RFQ:
    if deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    party = db.scalar(
        select(DealParty)
        .where(DealParty.id == target_deal_party_id, DealParty.deal_id == deal.id)
        .options(joinedload(DealParty.counterparty).joinedload(Counterparty.contacts))
    )
    if party is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal party not found")

    template = None
    if template_id:
        template = db.get(RFQTemplate, template_id)
    else:
        template = db.scalar(
            select(RFQTemplate).where(RFQTemplate.rfq_type == rfq_type, RFQTemplate.is_active.is_(True))
        )

    company = ensure_company_settings(db, user)
    lang = language or company.default_rfq_language or "en"
    fields = requested_fields or (template.default_requested_fields if template else [])

    subject = ""
    body = ""
    if template:
        context = _template_context(db, deal=deal, party=party, company=company, fields=fields)
        subject = template.subject_template.format(**context)
        body = template.body_template.format(**context)

    rfq = RFQ(
        deal_id=deal.id,
        target_deal_party_id=party.id,
        contact_id=contact_id,
        template_id=template.id if template else None,
        rfq_type=rfq_type,
        requested_fields=fields,
        language=lang,
        subject=subject,
        body=body,
        status=RFQStatus.DRAFT.value,
    )
    db.add(rfq)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="RFQ",
        entity_id=rfq.id,
        new_value={"deal_id": str(deal.id), "rfq_type": rfq_type},
    )
    db.commit()
    db.refresh(rfq)
    return rfq


def _template_context(
    db: Session,
    *,
    deal: Deal,
    party: DealParty,
    company: CompanySettings,
    fields: list[str],
) -> dict:
    req = db.scalar(
        select(Requirement)
        .where(Requirement.deal_id == deal.id)
        .options(joinedload(Requirement.product))
        .limit(1)
    )
    product = req.product.normalized_name if req and req.product else "product"
    destination = req.destination if req else "destination"
    route = f"{party.counterparty.incorporation_country or 'origin'} → {destination}"
    recipient = party.counterparty.trade_name or party.counterparty.legal_name
    return {
        "product": product,
        "destination": destination or "destination",
        "route": route,
        "recipient_name": recipient,
        "requested_fields": ", ".join(fields),
        "signature": company.email_signature_text or "Best regards",
    }


def update_rfq(db: Session, *, user: User, rfq: RFQ, data: dict) -> RFQ:
    deal = db.get(Deal, rfq.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found")

    content_changed = any(
        key in data and data[key] is not None for key in ("subject", "body", "contact_id", "requested_fields")
    )
    if content_changed:
        _invalidate_approval(db, rfq=rfq)

    for key, value in data.items():
        if value is not None and hasattr(rfq, key):
            setattr(rfq, key, value)

    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="RFQ",
        entity_id=rfq.id,
        new_value=data,
    )
    db.commit()
    db.refresh(rfq)
    return rfq


def draft_rfq_with_ai(db: Session, *, user: User, rfq: RFQ) -> RFQ:
    deal = db.get(Deal, rfq.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found")

    budget = check_budget(db, user=user)
    if not budget.allowed:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=budget.reason)

    _invalidate_approval(db, rfq=rfq)
    company = ensure_company_settings(db, user)
    party = rfq.target_deal_party
    context = _template_context(
        db,
        deal=deal,
        party=party,
        company=company,
        fields=list(rfq.requested_fields or []),
    )

    provider = get_ai_provider()
    prompt = (
        f"Adapt this RFQ draft for {party.counterparty.legal_name}.\n"
        f"RFQ type: {rfq.rfq_type}\n"
        f"Language: {rfq.language}\n"
        f"Requested fields: {', '.join(rfq.requested_fields or [])}\n"
        f"Current subject: {rfq.subject}\n"
        f"Current body:\n{rfq.body}\n"
        f"Context: {json.dumps(context)}"
    )
    cfg = ensure_ai_budget_settings(db, user)
    output, usage = provider.structured_completion(
        model=cfg.preferred_default_model,
        system_prompt="Adapt RFQ templates. Return subject and body only. Do not invent binding commitments.",
        user_prompt=prompt,
        output_schema=RFQDraftOutput,
    )

    log_ai_usage(
        db,
        user=user,
        model=usage.model,
        operation="drafting",
        cost_usd=usage.cost_usd,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        deal_id=deal.id,
    )

    rfq.subject = output.subject
    rfq.body = output.body
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.AI_CALL,
        entity_type="RFQ",
        entity_id=rfq.id,
        new_value={"action": "draft_with_ai", "model": usage.model},
    )
    db.commit()
    db.refresh(rfq)
    return rfq


def build_approval_preview(db: Session, *, rfq: RFQ) -> dict:
    db.refresh(rfq, attribute_names=["target_deal_party", "contact", "deal"])
    recipients = _build_recipients(rfq)
    warnings = _compliance_warnings(rfq)
    counterparty = rfq.target_deal_party.counterparty if rfq.target_deal_party else None
    return {
        "rfq_id": str(rfq.id),
        "status": rfq.status,
        "subject": rfq.subject,
        "body": rfq.body,
        "recipients": recipients,
        "binding_class": BindingClass.REQUEST.value,
        "compliance_warnings": warnings,
        "counterparty": {
            "id": str(counterparty.id) if counterparty else None,
            "legal_name": counterparty.legal_name if counterparty else None,
            "compliance_review_status": counterparty.compliance_review_status if counterparty else None,
            "verification_status": counterparty.verification_status if counterparty else None,
        },
        "disclosed_information": {
            "disclosure_status": rfq.target_deal_party.disclosure_status if rfq.target_deal_party else None,
        },
        "deal": {
            "id": str(rfq.deal_id),
            "deal_number": rfq.deal.deal_number if rfq.deal else None,
            "title": rfq.deal.title if rfq.deal else None,
        },
        "can_submit": bool(recipients) and rfq.subject and rfq.body,
    }


def submit_rfq_for_approval(db: Session, *, user: User, rfq: RFQ) -> RFQ:
    deal = db.get(Deal, rfq.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found")
    if rfq.status != RFQStatus.DRAFT.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="RFQ is not in DRAFT status")

    preview = build_approval_preview(db, rfq=rfq)
    if not preview["can_submit"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="RFQ is incomplete")

    recipients = preview["recipients"]
    approval = ApprovalRequest(
        rfq_id=rfq.id,
        proposed_action="SEND_RFQ",
        exact_payload={"subject": rfq.subject, "body": rfq.body},
        recipients=recipients,
        disclosed_information=preview["disclosed_information"],
        binding_class=BindingClass.REQUEST.value,
        risk_flags=preview["compliance_warnings"],
        compliance_warnings=preview["compliance_warnings"],
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        approval_status=ApprovalStatus.PENDING.value,
    )
    db.add(approval)
    db.flush()
    rfq.status = RFQStatus.PENDING_APPROVAL.value
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="RFQ",
        entity_id=rfq.id,
        new_value={"status": rfq.status, "approval_id": str(approval.id)},
    )
    db.commit()
    db.refresh(rfq)
    return rfq


def approve_rfq(db: Session, *, user: User, rfq: RFQ, acknowledge_warnings: bool = False) -> RFQ:
    deal = db.get(Deal, rfq.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found")
    if rfq.status != RFQStatus.PENDING_APPROVAL.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="RFQ is not pending approval")

    approval = _active_approval(db, rfq)
    if approval is None or approval.approval_status != ApprovalStatus.PENDING.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approval request missing")

    preview = build_approval_preview(db, rfq=rfq)
    warnings = preview["compliance_warnings"]
    if warnings and not acknowledge_warnings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Compliance warnings require acknowledgement", "warnings": warnings},
        )

    recipients = _build_recipients(rfq)
    snapshot_hash = _snapshot_hash(rfq.subject, rfq.body, recipients)
    approval.approval_status = ApprovalStatus.APPROVED.value
    approval.approved_snapshot_hash = snapshot_hash
    approval.approved_at = datetime.now(timezone.utc)
    approval.approved_by_id = user.id
    approval.exact_payload = {"subject": rfq.subject, "body": rfq.body}
    approval.recipients = recipients
    rfq.status = RFQStatus.APPROVED.value

    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="ApprovalRequest",
        entity_id=approval.id,
        new_value={"approval_status": approval.approval_status, "snapshot_hash": snapshot_hash},
    )
    db.commit()
    db.refresh(rfq)
    return rfq


def get_rfq(db: Session, *, user: User, rfq_id: uuid.UUID) -> RFQ:
    rfq = db.scalar(
        select(RFQ)
        .where(RFQ.id == rfq_id)
        .options(
            joinedload(RFQ.deal),
            joinedload(RFQ.target_deal_party).joinedload(DealParty.counterparty).joinedload(Counterparty.contacts),
            joinedload(RFQ.contact),
        )
    )
    if rfq is None or rfq.deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found")
    return rfq


_RFQ_PROTECTED_STATUSES = {
    RFQStatus.SENT.value,
    RFQStatus.PARTIALLY_ANSWERED.value,
    RFQStatus.ANSWERED.value,
}


def delete_rfq(db: Session, *, user: User, rfq: RFQ) -> None:
    if rfq.deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found")
    if rfq.status in _RFQ_PROTECTED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RFQ with sent messages or replies cannot be deleted",
        )

    rfq_id = rfq.id
    deal_id = str(rfq.deal_id)
    status_value = rfq.status
    db.delete(rfq)
    log_audit(
        db,
        actor=user,
        action=AuditAction.DELETE,
        entity_type="RFQ",
        entity_id=rfq_id,
        old_value={"deal_id": deal_id, "status": status_value},
    )
    db.commit()
