import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import (
    ConfigurationStatus,
    DealOutcome,
    DealStage,
    OpportunityPipelineStatus,
    OpportunityStatus,
    StatusActorType,
    StatusEventKind,
)
from app.domain.models import Deal, FulfilmentConfiguration, Opportunity, OpportunityStatusEvent, User

OPPORTUNITY_STATUS_LABELS: dict[str, str] = {
    OpportunityStatus.NEW.value: "Новая",
    OpportunityStatus.IN_ANALYSIS.value: "В анализе",
    OpportunityStatus.ANALYSIS_DONE.value: "Анализ закончен",
    OpportunityStatus.NEEDS_INPUT.value: "Требует данных",
    OpportunityStatus.ACCEPTED.value: "Принята",
    OpportunityStatus.REJECTED.value: "Отклонена",
    OpportunityStatus.CONVERTED.value: "Конвертирована в сделку",
    OpportunityStatus.ARCHIVED.value: "В архиве",
    OpportunityStatus.OTHER.value: "Другое",
}

PIPELINE_STATUS_LABELS: dict[str, str] = {
    OpportunityPipelineStatus.DEAL_DRAFT.value: "Сделка в проработке",
    OpportunityPipelineStatus.DEAL_AGREED.value: "Согласована сделка",
    OpportunityPipelineStatus.IN_EXECUTION.value: "В исполнении",
    OpportunityPipelineStatus.COMPLETED.value: "Исполнена",
    OpportunityPipelineStatus.CANCELLED.value: "Сорвана",
}

EXECUTION_STAGES = {
    DealStage.OFFER.value,
    DealStage.NEGOTIATION.value,
    DealStage.DUE_DILIGENCE.value,
}


def opportunity_status_label(code: str) -> str:
    return OPPORTUNITY_STATUS_LABELS.get(code, code)


def pipeline_status_label(code: str) -> str:
    return PIPELINE_STATUS_LABELS.get(code, code)


def resolve_pipeline_status(
    deal: Deal | None,
    config: FulfilmentConfiguration | None,
) -> str | None:
    if deal is None:
        return None

    if deal.outcome in {DealOutcome.LOST.value, DealOutcome.CANCELLED.value}:
        return OpportunityPipelineStatus.CANCELLED.value

    if deal.stage == DealStage.CLOSED.value or deal.outcome == DealOutcome.WON.value:
        return OpportunityPipelineStatus.COMPLETED.value

    has_selected = config is not None and config.status == ConfigurationStatus.SELECTED.value
    if has_selected and deal.stage in EXECUTION_STAGES:
        return OpportunityPipelineStatus.IN_EXECUTION.value

    if has_selected:
        return OpportunityPipelineStatus.DEAL_AGREED.value

    return OpportunityPipelineStatus.DEAL_DRAFT.value


def resolve_display_status(
    opportunity: Opportunity,
    *,
    deal: Deal | None = None,
    config: FulfilmentConfiguration | None = None,
) -> dict:
    if opportunity.status == OpportunityStatus.CONVERTED.value and deal is not None:
        pipeline_code = resolve_pipeline_status(deal, config)
        assert pipeline_code is not None
        changed_at = deal.updated_at or opportunity.status_changed_at
        return {
            "code": pipeline_code,
            "label": pipeline_status_label(pipeline_code),
            "kind": StatusEventKind.PIPELINE.value,
            "changed_at": changed_at,
        }

    return {
        "code": opportunity.status,
        "label": opportunity_status_label(opportunity.status),
        "kind": StatusEventKind.OPPORTUNITY.value,
        "changed_at": opportunity.status_changed_at,
    }


def record_status_event(
    db: Session,
    *,
    opportunity: Opportunity,
    status_code: str,
    status_kind: str = StatusEventKind.OPPORTUNITY.value,
    actor: User | None = None,
    actor_type: str = StatusActorType.USER.value,
    note: str | None = None,
    changed_at: datetime | None = None,
) -> OpportunityStatusEvent:
    event = OpportunityStatusEvent(
        opportunity_id=opportunity.id,
        status_code=status_code,
        status_kind=status_kind,
        changed_at=changed_at or datetime.now(timezone.utc),
        changed_by_id=actor.id if actor else None,
        actor_type=actor_type,
        note=note,
    )
    db.add(event)
    return event


def initialize_opportunity_status(
    db: Session,
    *,
    opportunity: Opportunity,
    actor: User | None = None,
    actor_type: str = StatusActorType.SYSTEM.value,
) -> None:
    now = datetime.now(timezone.utc)
    opportunity.status_changed_at = now
    opportunity.status_changed_by_id = actor.id if actor else None
    record_status_event(
        db,
        opportunity=opportunity,
        status_code=opportunity.status,
        actor=actor,
        actor_type=actor_type,
        note="Создание возможности",
        changed_at=now,
    )


def transition_opportunity_status(
    db: Session,
    *,
    opportunity: Opportunity,
    new_status: str,
    actor: User | None = None,
    actor_type: str = StatusActorType.USER.value,
    note: str | None = None,
) -> Opportunity:
    allowed = {item.value for item in OpportunityStatus}
    if new_status not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid opportunity status")

    if opportunity.status == OpportunityStatus.CONVERTED.value and new_status != OpportunityStatus.CONVERTED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Converted opportunity status is managed via deal pipeline",
        )

    if new_status == opportunity.status and not note:
        return opportunity

    now = datetime.now(timezone.utc)
    opportunity.status = new_status
    opportunity.status_changed_at = now
    opportunity.status_changed_by_id = actor.id if actor else None
    if new_status == OpportunityStatus.OTHER.value:
        opportunity.status_note = note
    elif note:
        opportunity.status_note = note

    record_status_event(
        db,
        opportunity=opportunity,
        status_code=new_status,
        actor=actor,
        actor_type=actor_type,
        note=note,
        changed_at=now,
    )
    return opportunity


def list_status_history(db: Session, *, opportunity_id: uuid.UUID) -> list[OpportunityStatusEvent]:
    return list(
        db.scalars(
            select(OpportunityStatusEvent)
            .where(OpportunityStatusEvent.opportunity_id == opportunity_id)
            .order_by(OpportunityStatusEvent.changed_at.desc())
        )
    )
