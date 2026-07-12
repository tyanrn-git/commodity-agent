import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import (
    AuditAction,
    AutomatedActionStatus,
    AutomationActionCategory,
    AutomationActionType,
    AutomationRunStatus,
    BindingClass,
    DealRiskFlag,
    MessageDirection,
    MessageLinkStatus,
    RFQStatus,
    TaskStatus,
    TaskType,
)
from app.domain.models import (
    AutomatedActionLog,
    AutomationRun,
    AutomationSettings,
    CommunicationThread,
    Deal,
    Message,
    RFQ,
    Task,
    User,
)
from app.integrations.email.base import OutboundEmail
from app.integrations.email.mock_provider import get_email_provider
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.audit import log_audit
from app.services.rfq import build_approval_preview

ALLOWED_AUTO_ACTIONS: dict[str, str] = {
    AutomationActionType.RFQ_FOLLOW_UP.value: AutomationActionCategory.NON_BINDING.value,
}

AUTO_ALLOWED_BINDING_CLASSES = {
    BindingClass.INFORMATIONAL.value,
}

BLOCKED_BINDING_CLASSES = {
    BindingClass.COMMERCIAL_SENSITIVE.value,
    BindingClass.POTENTIALLY_BINDING.value,
    BindingClass.BINDING.value,
}

FOLLOW_UP_BODY_TEMPLATE = (
    "Dear {recipient_name},\n\n"
    "This is a gentle follow-up regarding our request below. "
    "Please let us know if you need any clarification or additional information.\n\n"
    "We would appreciate your response when convenient.\n\n"
    "Thank you.\n"
)


def ensure_automation_settings(db: Session, user: User) -> AutomationSettings:
    existing = db.scalar(select(AutomationSettings).where(AutomationSettings.user_id == user.id))
    if existing:
        return existing
    row = AutomationSettings(user_id=user.id, auto_follow_up_enabled=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_automation_settings(db: Session, *, user: User, data: dict) -> AutomationSettings:
    row = ensure_automation_settings(db, user)
    old_value = {
        "auto_follow_up_enabled": row.auto_follow_up_enabled,
        "follow_up_after_days": row.follow_up_after_days,
        "max_follow_ups_per_rfq": row.max_follow_ups_per_rfq,
        "min_days_between_follow_ups": row.min_days_between_follow_ups,
        "max_auto_actions_per_day": row.max_auto_actions_per_day,
    }
    for field, value in data.items():
        if hasattr(row, field) and value is not None:
            setattr(row, field, value)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="AutomationSettings",
        entity_id=row.id,
        old_value=old_value,
        new_value=data,
    )
    db.commit()
    db.refresh(row)
    return row


def can_automate_action(action_type: str, binding_class: str) -> tuple[bool, str | None]:
    category = ALLOWED_AUTO_ACTIONS.get(action_type)
    if category is None:
        return False, f"Action type {action_type} is not allowed for automation"
    if category != AutomationActionCategory.NON_BINDING.value:
        return False, "Only NON_BINDING actions can be automated"
    if binding_class in BLOCKED_BINDING_CLASSES:
        return False, f"Binding class {binding_class} requires manual approval"
    if binding_class not in AUTO_ALLOWED_BINDING_CLASSES:
        return False, f"Binding class {binding_class} cannot be auto-sent"
    return True, None


def schedule_follow_up_task(
    db: Session,
    *,
    user: User,
    rfq: RFQ,
    due_days: int,
) -> Task:
    existing = db.scalar(
        select(Task).where(
            Task.deal_id == rfq.deal_id,
            Task.related_entity_type == "RFQ",
            Task.related_entity_id == rfq.id,
            Task.task_type == TaskType.FOLLOW_UP.value,
            Task.status == TaskStatus.OPEN.value,
        )
    )
    if existing:
        return existing

    due_date = (rfq.sent_at or datetime.now(timezone.utc)) + timedelta(days=due_days)
    task = Task(
        deal_id=rfq.deal_id,
        task_type=TaskType.FOLLOW_UP.value,
        title=f"Follow up: {rfq.subject[:80]}",
        description="Automatic follow-up task after RFQ was sent.",
        status=TaskStatus.OPEN.value,
        related_entity_type="RFQ",
        related_entity_id=rfq.id,
        due_date=due_date,
    )
    db.add(task)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="Task",
        entity_id=task.id,
        new_value={"task_type": task.task_type, "rfq_id": str(rfq.id), "due_date": due_date.isoformat()},
    )
    return task


def _utc_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start, end


def _count_sent_today(db: Session, *, user_id: uuid.UUID, now: datetime) -> int:
    day_start, day_end = _utc_day_bounds(now)
    return (
        db.scalar(
            select(func.count())
            .select_from(AutomatedActionLog)
            .where(
                AutomatedActionLog.owner_id == user_id,
                AutomatedActionLog.status == AutomatedActionStatus.SENT.value,
                AutomatedActionLog.created_at >= day_start,
                AutomatedActionLog.created_at < day_end,
            )
        )
        or 0
    )


def _count_follow_ups_for_rfq(db: Session, *, rfq_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(AutomatedActionLog)
            .where(
                AutomatedActionLog.entity_type == "RFQ",
                AutomatedActionLog.entity_id == rfq_id,
                AutomatedActionLog.action_type == AutomationActionType.RFQ_FOLLOW_UP.value,
                AutomatedActionLog.status == AutomatedActionStatus.SENT.value,
            )
        )
        or 0
    )


def _last_follow_up_at(db: Session, *, rfq_id: uuid.UUID) -> datetime | None:
    return db.scalar(
        select(func.max(AutomatedActionLog.created_at))
        .where(
            AutomatedActionLog.entity_type == "RFQ",
            AutomatedActionLog.entity_id == rfq_id,
            AutomatedActionLog.action_type == AutomationActionType.RFQ_FOLLOW_UP.value,
            AutomatedActionLog.status == AutomatedActionStatus.SENT.value,
        )
    )


def _build_follow_up_subject(original_subject: str) -> str:
    subject = original_subject.strip()
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"


def _build_follow_up_body(rfq: RFQ, preview: dict) -> str:
    recipient_name = "Sir/Madam"
    recipients = preview.get("recipients") or []
    if recipients and recipients[0].get("name"):
        recipient_name = recipients[0]["name"]
    return FOLLOW_UP_BODY_TEMPLATE.format(recipient_name=recipient_name)


def _validate_rfq_follow_up_candidate(
    db: Session,
    *,
    rfq: RFQ,
    deal: Deal,
    settings: AutomationSettings,
    now: datetime,
) -> tuple[bool, str, AutomatedActionStatus]:
    if not settings.auto_follow_up_enabled:
        return False, "Auto follow-up is disabled", AutomatedActionStatus.SKIPPED

    if rfq.status != RFQStatus.SENT.value:
        return False, f"RFQ status is {rfq.status}, expected SENT", AutomatedActionStatus.SKIPPED

    if not rfq.sent_at:
        return False, "RFQ has no sent_at timestamp", AutomatedActionStatus.SKIPPED

    if DealRiskFlag.BANK_DETAILS_CHANGED.value in (deal.risk_flags or []):
        return False, "BANK_DETAILS_CHANGED blocks outbound communication", AutomatedActionStatus.BLOCKED

    due_at = rfq.sent_at + timedelta(days=settings.follow_up_after_days)
    if now < due_at:
        return False, "Follow-up waiting period not elapsed", AutomatedActionStatus.SKIPPED

    sent_count = _count_follow_ups_for_rfq(db, rfq_id=rfq.id)
    if sent_count >= settings.max_follow_ups_per_rfq:
        return False, "Max follow-ups per RFQ reached", AutomatedActionStatus.SKIPPED

    last_follow_up = _last_follow_up_at(db, rfq_id=rfq.id)
    anchor = last_follow_up or rfq.sent_at
    next_allowed = anchor + timedelta(days=settings.min_days_between_follow_ups)
    if now < next_allowed:
        return False, "Minimum days between follow-ups not elapsed", AutomatedActionStatus.SKIPPED

    return True, "", AutomatedActionStatus.SENT


def _log_action(
    db: Session,
    *,
    user: User,
    run: AutomationRun,
    rfq: RFQ,
    status: str,
    reason: str | None,
    message_id: uuid.UUID | None = None,
    payload: dict | None = None,
) -> AutomatedActionLog:
    entry = AutomatedActionLog(
        owner_id=user.id,
        automation_run_id=run.id,
        action_type=AutomationActionType.RFQ_FOLLOW_UP.value,
        action_category=AutomationActionCategory.NON_BINDING.value,
        binding_class=BindingClass.INFORMATIONAL.value,
        entity_type="RFQ",
        entity_id=rfq.id,
        status=status,
        reason=reason,
        message_id=message_id,
        payload=payload,
    )
    db.add(entry)
    db.flush()
    return entry


def _send_rfq_follow_up(
    db: Session,
    *,
    user: User,
    rfq: RFQ,
    storage: LocalFilesystemStorage,
) -> Message:
    from app.services.email_loop import _save_message_source, ensure_mailbox_connection

    deal = db.get(Deal, rfq.deal_id)
    if deal is None:
        raise ValueError("Deal not found")

    preview = build_approval_preview(db, rfq=rfq)
    recipients = preview["recipients"]
    to_addresses = [r["email"] for r in recipients if r.get("email")]
    if not to_addresses:
        raise ValueError("No recipients for follow-up")

    subject = _build_follow_up_subject(rfq.subject)
    body = _build_follow_up_body(rfq, preview)

    allowed, block_reason = can_automate_action(
        AutomationActionType.RFQ_FOLLOW_UP.value,
        BindingClass.INFORMATIONAL.value,
    )
    if not allowed:
        raise ValueError(block_reason or "Automation not allowed")

    mailbox = ensure_mailbox_connection(db, user)
    provider = get_email_provider(mailbox.provider)

    thread = db.scalar(
        select(CommunicationThread)
        .where(CommunicationThread.rfq_id == rfq.id)
        .order_by(CommunicationThread.created_at.desc())
    )
    if thread is None:
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

    original_message = db.scalar(
        select(Message)
        .where(Message.rfq_id == rfq.id, Message.direction == MessageDirection.OUTBOUND.value)
        .order_by(Message.sent_at.asc())
    )
    in_reply_to = original_message.mailbox_message_id if original_message else None

    mailbox_message_id = provider.send_message(
        message=OutboundEmail(subject=subject, body=body, to_addresses=to_addresses)
    )

    eml_content = (
        f"Subject: {subject}\r\n"
        f"From: {mailbox.email_address}\r\n"
        f"To: {', '.join(to_addresses)}\r\n"
        f"Message-ID: {mailbox_message_id}\r\n"
        + (f"In-Reply-To: {in_reply_to}\r\n" if in_reply_to else "")
        + "Content-Type: text/plain; charset=utf-8\r\n\r\n"
        + body
    ).encode()
    source = _save_message_source(
        db,
        user=user,
        filename=f"follow-up-{rfq.id}.eml",
        content=eml_content,
        mime_type="message/rfc822",
        storage=storage,
        deal_id=deal.id,
    )

    now = datetime.now(timezone.utc)
    message = Message(
        thread_id=thread.id,
        rfq_id=rfq.id,
        source_id=source.id,
        direction=MessageDirection.OUTBOUND.value,
        link_status=MessageLinkStatus.LINKED.value,
        subject=subject,
        body_text=body,
        from_address=mailbox.email_address,
        to_addresses=to_addresses,
        binding_class=BindingClass.INFORMATIONAL.value,
        mailbox_message_id=mailbox_message_id,
        in_reply_to=in_reply_to,
        sent_at=now,
    )
    db.add(message)
    thread.last_message_at = now
    db.flush()

    log_audit(
        db,
        actor=user,
        action=AuditAction.AUTO_EXECUTE,
        entity_type="Message",
        entity_id=message.id,
        new_value={
            "action_type": AutomationActionType.RFQ_FOLLOW_UP.value,
            "rfq_id": str(rfq.id),
            "binding_class": BindingClass.INFORMATIONAL.value,
            "automated": True,
        },
    )
    return message


def find_rfq_follow_up_candidates(db: Session, *, user: User) -> list[RFQ]:
    settings = ensure_automation_settings(db, user)
    now = datetime.now(timezone.utc)
    stmt = (
        select(RFQ)
        .join(Deal)
        .where(
            Deal.owner_id == user.id,
            RFQ.status == RFQStatus.SENT.value,
            RFQ.sent_at.is_not(None),
        )
        .options(joinedload(RFQ.deal))
        .order_by(RFQ.sent_at.asc())
    )
    rfqs = list(db.scalars(stmt).unique())
    eligible: list[RFQ] = []
    for rfq in rfqs:
        ok, _, _ = _validate_rfq_follow_up_candidate(
            db, rfq=rfq, deal=rfq.deal, settings=settings, now=now
        )
        if ok:
            eligible.append(rfq)
    return eligible


def run_automation(
    db: Session,
    *,
    user: User,
    storage: LocalFilesystemStorage | None = None,
) -> AutomationRun:
    settings = ensure_automation_settings(db, user)
    now = datetime.now(timezone.utc)
    storage = storage or LocalFilesystemStorage()

    run = AutomationRun(
        owner_id=user.id,
        status=AutomationRunStatus.RUNNING.value,
        started_at=now,
    )
    db.add(run)
    db.flush()

    try:
        if not settings.auto_follow_up_enabled:
            run.status = AutomationRunStatus.SKIPPED.value
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(run)
            return run

        rfqs = list(
            db.scalars(
                select(RFQ)
                .join(Deal)
                .where(
                    Deal.owner_id == user.id,
                    RFQ.status == RFQStatus.SENT.value,
                    RFQ.sent_at.is_not(None),
                )
                .options(joinedload(RFQ.deal))
                .order_by(RFQ.sent_at.asc())
            ).unique()
        )

        sent_today = _count_sent_today(db, user_id=user.id, now=now)

        for rfq in rfqs:
            run.actions_evaluated += 1
            deal = rfq.deal

            ok, reason, expected_status = _validate_rfq_follow_up_candidate(
                db, rfq=rfq, deal=deal, settings=settings, now=now
            )
            if not ok:
                status = expected_status.value
                if status == AutomatedActionStatus.SENT.value:
                    status = AutomatedActionStatus.SKIPPED.value
                _log_action(db, user=user, run=run, rfq=rfq, status=status, reason=reason)
                if status == AutomatedActionStatus.BLOCKED.value:
                    run.actions_blocked += 1
                else:
                    run.actions_skipped += 1
                continue

            if sent_today >= settings.max_auto_actions_per_day:
                _log_action(
                    db,
                    user=user,
                    run=run,
                    rfq=rfq,
                    status=AutomatedActionStatus.RATE_LIMITED.value,
                    reason="Daily auto-action limit reached",
                )
                run.actions_rate_limited += 1
                continue

            allowed, block_reason = can_automate_action(
                AutomationActionType.RFQ_FOLLOW_UP.value,
                BindingClass.INFORMATIONAL.value,
            )
            if not allowed:
                _log_action(
                    db,
                    user=user,
                    run=run,
                    rfq=rfq,
                    status=AutomatedActionStatus.BLOCKED.value,
                    reason=block_reason,
                )
                run.actions_blocked += 1
                continue

            message = _send_rfq_follow_up(db, user=user, rfq=rfq, storage=storage)
            preview = build_approval_preview(db, rfq=rfq)
            _log_action(
                db,
                user=user,
                run=run,
                rfq=rfq,
                status=AutomatedActionStatus.SENT.value,
                reason=None,
                message_id=message.id,
                payload={
                    "subject": message.subject,
                    "to": message.to_addresses,
                    "binding_class": BindingClass.INFORMATIONAL.value,
                    "recipients": preview.get("recipients"),
                },
            )
            run.actions_sent += 1
            sent_today += 1

        if run.actions_sent and (run.actions_blocked or run.actions_skipped or run.actions_rate_limited):
            run.status = AutomationRunStatus.PARTIAL.value
        elif run.actions_sent:
            run.status = AutomationRunStatus.SUCCESS.value
        elif run.actions_blocked or run.actions_rate_limited:
            run.status = AutomationRunStatus.PARTIAL.value
        else:
            run.status = AutomationRunStatus.SUCCESS.value

        run.finished_at = datetime.now(timezone.utc)
        log_audit(
            db,
            actor=user,
            action=AuditAction.AUTO_EXECUTE,
            entity_type="AutomationRun",
            entity_id=run.id,
            new_value={
                "actions_evaluated": run.actions_evaluated,
                "actions_sent": run.actions_sent,
                "actions_blocked": run.actions_blocked,
                "actions_skipped": run.actions_skipped,
                "actions_rate_limited": run.actions_rate_limited,
            },
        )
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        run.status = AutomationRunStatus.FAILED.value
        run.error_message = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        raise
