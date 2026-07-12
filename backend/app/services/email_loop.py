import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.domain.enums import (
    ApprovalStatus,
    AuditAction,
    BindingClass,
    DealRiskFlag,
    MessageDirection,
    MessageLinkStatus,
    RFQStatus,
    SourceType,
    SupplyOfferStatus,
)
from app.domain.models import (
    ApprovalRequest,
    CommunicationThread,
    Deal,
    MailboxConnection,
    Message,
    Offer,
    RFQ,
    Source,
    SupplyOffer,
    User,
)
from app.domain.enums import OfferStatus
from app.integrations.email.base import InboundEmail, OutboundEmail
from app.integrations.email.mock_provider import MockEmailProvider, get_email_provider
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.audit import log_audit
from app.services.document_parser import compute_content_hash
from app.services.quote_extraction import (
    answered_requested_fields,
    detect_bank_details_changed,
    extract_supply_offer_fields,
    parse_eml_headers_and_body,
)
from app.services.rfq import _active_approval, _snapshot_hash, build_approval_preview
from app.services.offer import _active_offer_approval, build_offer_approval_preview, _snapshot_hash as _offer_snapshot_hash


def ensure_mailbox_connection(db: Session, user: User) -> MailboxConnection:
    conn = db.scalar(select(MailboxConnection).where(MailboxConnection.user_id == user.id))
    if conn:
        return conn
    conn = MailboxConnection(
        user_id=user.id,
        provider=settings.email_provider.upper(),
        email_address=user.email,
        is_active=True,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


def _save_message_source(
    db: Session,
    *,
    user: User,
    filename: str,
    content: bytes,
    mime_type: str | None,
    storage: LocalFilesystemStorage,
    deal_id: uuid.UUID | None = None,
) -> Source:
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".eml"
    prefix = f"deals/{deal_id}" if deal_id else "inbox/unlinked"
    storage_key = f"{prefix}/{uuid.uuid4()}{extension}"
    storage.save(storage_key, content)
    source = Source(
        opportunity_id=None,
        source_type=SourceType.EMAIL.value,
        content_hash=compute_content_hash(content),
        original_filename=filename,
        mime_type=mime_type or "message/rfc822",
        storage_key=storage_key,
        file_size_bytes=len(content),
        is_immutable=True,
        uploaded_by_id=user.id,
    )
    db.add(source)
    db.flush()
    return source


def _add_deal_risk_flag(deal: Deal, flag: str) -> None:
    flags = list(deal.risk_flags or [])
    if flag not in flags:
        flags.append(flag)
    deal.risk_flags = flags


def send_approved_rfq(
    db: Session,
    *,
    user: User,
    rfq: RFQ,
    storage: LocalFilesystemStorage,
) -> tuple[RFQ, Message]:
    deal = db.get(Deal, rfq.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found")
    if rfq.status != RFQStatus.APPROVED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="RFQ must be APPROVED to send")

    approval = _active_approval(db, rfq)
    if approval is None or approval.approval_status != ApprovalStatus.APPROVED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valid approval required")

    preview = build_approval_preview(db, rfq=rfq)
    recipients = preview["recipients"]
    snapshot_hash = _snapshot_hash(rfq.subject, rfq.body, recipients)
    if approval.approved_snapshot_hash != snapshot_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval snapshot is stale; edit invalidated approval",
        )

    if DealRiskFlag.BANK_DETAILS_CHANGED.value in (deal.risk_flags or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BANK_DETAILS_CHANGED flag blocks outbound communication",
        )

    mailbox = ensure_mailbox_connection(db, user)
    provider = get_email_provider(mailbox.provider)

    thread = CommunicationThread(
        owner_id=user.id,
        deal_id=deal.id,
        deal_party_id=rfq.target_deal_party_id,
        rfq_id=rfq.id,
        subject=rfq.subject,
        mailbox_thread_id=f"thread-{rfq.id}",
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(thread)
    db.flush()

    to_addresses = [r["email"] for r in recipients if r.get("email")]
    mailbox_message_id = provider.send_message(
        message=OutboundEmail(subject=rfq.subject, body=rfq.body, to_addresses=to_addresses)
    )

    eml_content = (
        f"Subject: {rfq.subject}\r\n"
        f"From: {mailbox.email_address}\r\n"
        f"To: {', '.join(to_addresses)}\r\n"
        f"Message-ID: {mailbox_message_id}\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        f"{rfq.body}"
    ).encode()
    source = _save_message_source(
        db,
        user=user,
        filename=f"rfq-{rfq.id}.eml",
        content=eml_content,
        mime_type="message/rfc822",
        storage=storage,
        deal_id=deal.id,
    )

    message = Message(
        thread_id=thread.id,
        rfq_id=rfq.id,
        source_id=source.id,
        direction=MessageDirection.OUTBOUND.value,
        link_status=MessageLinkStatus.LINKED.value,
        subject=rfq.subject,
        body_text=rfq.body,
        from_address=mailbox.email_address,
        to_addresses=to_addresses,
        binding_class=BindingClass.REQUEST.value,
        mailbox_message_id=mailbox_message_id,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(message)
    db.flush()

    rfq.status = RFQStatus.SENT.value
    rfq.sent_at = datetime.now(timezone.utc)
    rfq.source_message_id = message.id

    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="RFQ",
        entity_id=rfq.id,
        new_value={"status": rfq.status, "message_id": str(message.id)},
    )
    from app.services.automation import ensure_automation_settings, schedule_follow_up_task

    automation_settings = ensure_automation_settings(db, user)
    schedule_follow_up_task(
        db,
        user=user,
        rfq=rfq,
        due_days=automation_settings.follow_up_after_days,
    )
    db.commit()
    db.refresh(rfq)
    db.refresh(message)
    return rfq, message


def send_approved_offer(
    db: Session,
    *,
    user: User,
    offer: Offer,
    storage: LocalFilesystemStorage,
) -> tuple[Offer, Message]:
    deal = db.get(Deal, offer.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    if offer.status != OfferStatus.APPROVED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Offer must be APPROVED to send")

    approval = _active_offer_approval(db, offer)
    if approval is None or approval.approval_status != ApprovalStatus.APPROVED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valid approval required")

    preview = build_offer_approval_preview(db, offer=offer)
    if preview["configuration_is_stale"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Configuration is stale")

    snapshot_hash = _offer_snapshot_hash(approval.exact_payload)
    if approval.approved_snapshot_hash != snapshot_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval snapshot is stale; edit invalidated approval",
        )

    if DealRiskFlag.BANK_DETAILS_CHANGED.value in (deal.risk_flags or []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BANK_DETAILS_CHANGED flag blocks outbound communication",
        )

    mailbox = ensure_mailbox_connection(db, user)
    provider = get_email_provider(mailbox.provider)
    recipients = preview["recipients"]
    to_addresses = [r["email"] for r in recipients if r.get("email")]

    thread = CommunicationThread(
        owner_id=user.id,
        deal_id=deal.id,
        deal_party_id=offer.target_deal_party_id,
        subject=offer.subject,
        mailbox_thread_id=f"offer-thread-{offer.id}",
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(thread)
    db.flush()

    mailbox_message_id = provider.send_message(
        message=OutboundEmail(subject=offer.subject, body=offer.body, to_addresses=to_addresses)
    )

    eml_content = (
        f"Subject: {offer.subject}\r\n"
        f"From: {mailbox.email_address}\r\n"
        f"To: {', '.join(to_addresses)}\r\n"
        f"Message-ID: {mailbox_message_id}\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        f"{offer.body}"
    ).encode()
    source = _save_message_source(
        db,
        user=user,
        filename=f"offer-{offer.id}.eml",
        content=eml_content,
        mime_type="message/rfc822",
        storage=storage,
        deal_id=deal.id,
    )

    message = Message(
        thread_id=thread.id,
        direction=MessageDirection.OUTBOUND.value,
        link_status=MessageLinkStatus.LINKED.value,
        subject=offer.subject,
        body_text=offer.body,
        from_address=mailbox.email_address,
        to_addresses=to_addresses,
        binding_class=BindingClass.COMMERCIAL_SENSITIVE.value,
        mailbox_message_id=mailbox_message_id,
        sent_at=datetime.now(timezone.utc),
        source_id=source.id,
    )
    db.add(message)
    db.flush()

    offer.status = OfferStatus.SENT.value
    offer.sent_at = datetime.now(timezone.utc)
    offer.source_message_id = message.id

    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="Offer",
        entity_id=offer.id,
        new_value={"status": offer.status, "message_id": str(message.id)},
    )
    db.commit()
    db.refresh(offer)
    db.refresh(message)
    return offer, message


def import_inbound_eml(
    db: Session,
    *,
    user: User,
    file: UploadFile,
    storage: LocalFilesystemStorage,
    deal_id: uuid.UUID | None = None,
    rfq_id: uuid.UUID | None = None,
) -> tuple[Message, SupplyOffer | None]:
    content = file.file.read()
    parsed = parse_eml_headers_and_body(content)
    return _process_inbound(
        db,
        user=user,
        content=content,
        filename=file.filename or "inbound.eml",
        parsed=parsed,
        storage=storage,
        deal_id=deal_id,
        rfq_id=rfq_id,
    )


def _process_inbound(
    db: Session,
    *,
    user: User,
    content: bytes,
    filename: str,
    parsed: dict,
    storage: LocalFilesystemStorage,
    deal_id: uuid.UUID | None,
    rfq_id: uuid.UUID | None,
    mailbox_message_id: str | None = None,
    in_reply_to: str | None = None,
) -> tuple[Message, SupplyOffer | None]:
    rfq: RFQ | None = None
    deal: Deal | None = None
    thread: CommunicationThread | None = None

    if rfq_id:
        rfq = db.scalar(
            select(RFQ).where(RFQ.id == rfq_id).options(joinedload(RFQ.deal))
        )
        if rfq is None or rfq.deal.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found")
        deal = rfq.deal
        deal_id = deal.id
        thread = db.scalar(
            select(CommunicationThread).where(
                CommunicationThread.rfq_id == rfq.id,
                CommunicationThread.deal_id == deal.id,
            )
        )
    elif deal_id:
        deal = db.scalar(select(Deal).where(Deal.id == deal_id, Deal.owner_id == user.id))
        if deal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    if thread is None:
        linked = bool(deal_id)
        thread = CommunicationThread(
            owner_id=user.id,
            deal_id=deal_id,
            rfq_id=rfq.id if rfq else None,
            subject=parsed.get("subject") or "(no subject)",
            mailbox_thread_id=mailbox_message_id or f"import-{uuid.uuid4()}",
            last_message_at=datetime.now(timezone.utc),
        )
        db.add(thread)
        db.flush()
    else:
        thread.last_message_at = datetime.now(timezone.utc)

    if not rfq and in_reply_to:
        outbound = db.scalar(
            select(Message).where(Message.mailbox_message_id == in_reply_to)
        )
        if outbound and outbound.rfq_id:
            rfq = db.get(RFQ, outbound.rfq_id)
            deal = db.get(Deal, rfq.deal_id) if rfq else deal
            thread.deal_id = deal.id if deal else thread.deal_id
            thread.rfq_id = rfq.id if rfq else thread.rfq_id

    source = _save_message_source(
        db,
        user=user,
        filename=filename,
        content=content,
        mime_type="message/rfc822",
        storage=storage,
        deal_id=deal_id,
    )

    body = parsed.get("body") or ""
    link_status = MessageLinkStatus.LINKED.value if (deal_id and rfq) else MessageLinkStatus.UNLINKED.value

    message = Message(
        thread_id=thread.id,
        rfq_id=rfq.id if rfq else None,
        source_id=source.id,
        direction=MessageDirection.INBOUND.value,
        link_status=link_status,
        subject=parsed.get("subject") or "(no subject)",
        body_text=body,
        from_address=parsed.get("from"),
        to_addresses=[parsed.get("to")] if parsed.get("to") else [],
        binding_class=BindingClass.COMMERCIAL_SENSITIVE.value,
        mailbox_message_id=mailbox_message_id or f"inbound-{uuid.uuid4()}",
        in_reply_to=in_reply_to or parsed.get("in-reply-to") or None,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(message)
    db.flush()

    supply_offer: SupplyOffer | None = None
    if deal and rfq and link_status == MessageLinkStatus.LINKED.value:
        supply_offer = _create_supply_offer_from_reply(
            db, user=user, deal=deal, rfq=rfq, message=message, body=body
        )

    if deal and detect_bank_details_changed(body):
        _add_deal_risk_flag(deal, DealRiskFlag.BANK_DETAILS_CHANGED.value)

    log_audit(
        db,
        actor=user,
        action=AuditAction.UPLOAD,
        entity_type="Message",
        entity_id=message.id,
        new_value={"link_status": link_status, "rfq_id": str(rfq.id) if rfq else None},
    )
    db.commit()
    db.refresh(message)
    if supply_offer:
        db.refresh(supply_offer)
    return message, supply_offer


def _create_supply_offer_from_reply(
    db: Session,
    *,
    user: User,
    deal: Deal,
    rfq: RFQ,
    message: Message,
    body: str,
) -> SupplyOffer:
    extraction = extract_supply_offer_fields(body, list(rfq.requested_fields or []))
    extracted = extraction["extracted"]
    answered, missing = answered_requested_fields(list(rfq.requested_fields or []), extracted)

    if missing:
        rfq.status = RFQStatus.PARTIALLY_ANSWERED.value
    else:
        rfq.status = RFQStatus.ANSWERED.value

    party = rfq.target_deal_party
    supplier_id = party.counterparty_id if party else None

    offer = SupplyOffer(
        deal_id=deal.id,
        rfq_id=rfq.id,
        supplier_counterparty_id=supplier_id,
        source_message_id=message.id,
        product_name=extracted.get("product_name"),
        available_quantity=extracted.get("available_quantity"),
        quantity_unit=extracted.get("quantity_unit"),
        price=extracted.get("price"),
        currency=extracted.get("currency"),
        incoterm=extracted.get("incoterm"),
        origin=extracted.get("origin"),
        payment_terms=extracted.get("payment_terms"),
        extracted_fields=extracted,
        missing_fields=missing,
        status=SupplyOfferStatus.NEEDS_REVIEW.value if missing else SupplyOfferStatus.EXTRACTED.value,
    )
    db.add(offer)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="SupplyOffer",
        entity_id=offer.id,
        new_value={"rfq_id": str(rfq.id), "missing_fields": missing},
    )
    return offer


def link_message_to_rfq(
    db: Session,
    *,
    user: User,
    message: Message,
    rfq_id: uuid.UUID,
) -> tuple[Message, SupplyOffer]:
    rfq = db.scalar(
        select(RFQ)
        .where(RFQ.id == rfq_id)
        .options(joinedload(RFQ.deal), joinedload(RFQ.target_deal_party))
    )
    if rfq is None or rfq.deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RFQ not found")

    thread = db.get(CommunicationThread, message.thread_id)
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    thread.deal_id = rfq.deal_id
    thread.rfq_id = rfq.id
    message.rfq_id = rfq.id
    message.link_status = MessageLinkStatus.LINKED.value

    offer = _create_supply_offer_from_reply(
        db,
        user=user,
        deal=rfq.deal,
        rfq=rfq,
        message=message,
        body=message.body_text,
    )
    if detect_bank_details_changed(message.body_text):
        _add_deal_risk_flag(rfq.deal, DealRiskFlag.BANK_DETAILS_CHANGED.value)

    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="Message",
        entity_id=message.id,
        new_value={"link_status": "LINKED", "rfq_id": str(rfq.id)},
    )
    db.commit()
    db.refresh(message)
    db.refresh(offer)
    return message, offer


def sync_mailbox(db: Session, *, user: User, storage: LocalFilesystemStorage) -> list[Message]:
    mailbox = ensure_mailbox_connection(db, user)
    provider = get_email_provider(mailbox.provider)
    inbound_items, cursor = provider.fetch_new_messages(since_cursor=mailbox.sync_cursor)
    created: list[Message] = []
    for item in inbound_items:
        content = (
            f"Subject: {item.subject}\r\n"
            f"From: {item.from_address}\r\n"
            f"To: {', '.join(item.to_addresses)}\r\n"
            f"Message-ID: {item.mailbox_message_id}\r\n"
            f"In-Reply-To: {item.in_reply_to or ''}\r\n\r\n"
            f"{item.body}"
        ).encode()
        parsed = parse_eml_headers_and_body(content)
        message, _ = _process_inbound(
            db,
            user=user,
            content=content,
            filename="sync.eml",
            parsed=parsed,
            storage=storage,
            deal_id=None,
            rfq_id=None,
            mailbox_message_id=item.mailbox_message_id,
            in_reply_to=item.in_reply_to,
        )
        created.append(message)
    mailbox.last_sync_at = datetime.now(timezone.utc)
    mailbox.sync_cursor = cursor
    db.commit()
    return created


def list_inbox(db: Session, *, user: User, linked_only: bool = True) -> list[Message]:
    stmt = (
        select(Message)
        .join(CommunicationThread)
        .where(CommunicationThread.owner_id == user.id)
        .order_by(Message.sent_at.desc())
    )
    if linked_only:
        stmt = stmt.where(Message.link_status == MessageLinkStatus.LINKED.value)
    else:
        stmt = stmt.where(Message.link_status == MessageLinkStatus.UNLINKED.value)
    return list(db.scalars(stmt))


def list_supply_offers(db: Session, *, user: User, deal_id: uuid.UUID) -> list[SupplyOffer]:
    deal = db.scalar(select(Deal).where(Deal.id == deal_id, Deal.owner_id == user.id))
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return list(
        db.scalars(
            select(SupplyOffer)
            .where(SupplyOffer.deal_id == deal_id)
            .order_by(SupplyOffer.created_at.desc())
        )
    )
