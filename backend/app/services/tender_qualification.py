from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import get_ai_provider
from app.ai.schemas import TenderQualificationOutput, TenderSearchHitOutput
from app.config import settings
from app.domain.enums import (
    AIUsageOperation,
    AgentResultType,
    AgentType,
    QualifiedRequirementStatus,
    TenderPromotionMode,
)
from app.domain.models import InternetSourceSearchHit, QualifiedRequirement, User
from app.services.agent_runtime import AgentExecutionContext, tracked_agent_run
from app.services.ai_budget import enforce_budget_or_raise, ensure_ai_budget_settings
from app.services.tender_hit_evaluation import evaluate_tender_hit


def _parse_decimal(value):
    if value is None:
        return None
    try:
        from decimal import Decimal

        return Decimal(str(value))
    except Exception:
        return None


def get_search_hit(db: Session, *, user: User, hit_id: uuid.UUID) -> InternetSourceSearchHit:
    hit = db.get(InternetSourceSearchHit, hit_id)
    if hit is None or hit.search_run.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search hit not found")
    return hit

QUALIFICATION_SYSTEM_PROMPT = """You qualify public commodity procurement tenders for a trading desk.
Rules:
- Assess product fit, route/destination fit, and deadline feasibility only.
- Do NOT invent suppliers, prices, margins, or freight costs.
- qualified=true only when the tender clearly matches the search product and deadlines look workable.
- qualification_score 0.0-1.0 reflects overall fit for the desk.
- List missing_fields when critical data is absent (volume, destination, deadline, product spec).
- rejection_reason when qualified=false.
"""


def get_promotion_mode() -> TenderPromotionMode:
    raw = (settings.tender_promotion_mode or TenderPromotionMode.LEGACY.value).strip().lower()
    try:
        return TenderPromotionMode(raw)
    except ValueError:
        return TenderPromotionMode.LEGACY


def _build_qualification_prompt(*, hit: InternetSourceSearchHit, run) -> str:
    fields = hit.extracted_fields or {}
    return (
        f"Tender title: {hit.title}\n"
        f"Source: {hit.source.name if hit.source else 'unknown'}\n"
        f"URL: {hit.canonical_url or 'n/a'}\n"
        f"Product keywords: {', '.join(run.product_keywords or [])}\n"
        f"Regions: {', '.join(run.regions or [])}\n"
        f"Buyer: {fields.get('buyer') or 'unknown'}\n"
        f"Product: {fields.get('product') or 'unknown'}\n"
        f"Volume: {fields.get('volume') or 'unknown'}\n"
        f"Destination: {fields.get('destination') or 'unknown'}\n"
        f"Submission deadline: {fields.get('submission_deadline') or 'unknown'}\n"
        f"Delivery deadline: {fields.get('delivery_deadline') or 'unknown'}\n"
        f"Evidence: {hit.evidence_excerpt or fields.get('body') or 'n/a'}\n"
    )


def _status_from_output(output: TenderQualificationOutput) -> str:
    if output.qualified:
        return QualifiedRequirementStatus.QUALIFIED.value
    if output.missing_fields:
        return QualifiedRequirementStatus.NEEDS_REVIEW.value
    return QualifiedRequirementStatus.REJECTED.value


def _upsert_qualification(
    db: Session,
    *,
    user: User,
    hit: InternetSourceSearchHit,
    output: TenderQualificationOutput,
) -> QualifiedRequirement:
    record = db.scalar(
        select(QualifiedRequirement).where(
            QualifiedRequirement.internet_source_search_hit_id == hit.id,
            QualifiedRequirement.owner_id == user.id,
        )
    )
    now = datetime.now(timezone.utc)
    payload = output.model_dump(mode="json")
    if record is None:
        record = QualifiedRequirement(
            internet_source_search_hit_id=hit.id,
            owner_id=user.id,
        )
        db.add(record)

    record.status = _status_from_output(output)
    record.qualified = output.qualified
    record.qualification_score = float(output.qualification_score)
    record.confidence = float(output.confidence)
    record.summary = output.summary
    record.rejection_reason = output.rejection_reason
    record.structured_payload = payload
    record.missing_fields = output.missing_fields
    record.qualified_at = now if output.qualified else None

    fields = dict(hit.extracted_fields or {})
    fields["qualification"] = payload
    hit.extracted_fields = fields
    db.flush()
    return record


def qualify_search_hit(
    db: Session,
    *,
    user: User,
    hit_id: uuid.UUID,
    force: bool = False,
) -> QualifiedRequirement:
    hit = get_search_hit(db, user=user, hit_id=hit_id)
    run = hit.search_run
    fields = dict(hit.extracted_fields or {})

    if not force:
        existing = db.scalar(
            select(QualifiedRequirement).where(
                QualifiedRequirement.internet_source_search_hit_id == hit.id,
                QualifiedRequirement.owner_id == user.id,
            )
        )
        if existing and existing.status != QualifiedRequirementStatus.PENDING.value:
            return existing

    if fields.get("submission_expired"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Срок подачи заявки истёк")
    if not fields.get("product_match", True):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Предмет тендера не соответствует заданию")

    tender_item = TenderSearchHitOutput(
        title=hit.title,
        url=hit.canonical_url,
        product=fields.get("product"),
        buyer=fields.get("buyer"),
        destination=fields.get("destination"),
        deadline=fields.get("submission_deadline"),
        submission_deadline=fields.get("submission_deadline"),
        delivery_deadline=fields.get("delivery_deadline"),
        body=fields.get("body"),
        confidence=float(hit.confidence or 0.5),
        evidence_excerpt=hit.evidence_excerpt,
        quantity=_parse_decimal(fields.get("quantity")),
        quantity_unit=fields.get("quantity_unit"),
    )
    evaluation = evaluate_tender_hit(
        tender_item,
        user_keywords=list(run.product_keywords or []),
        reference_date=datetime.now(timezone.utc),
    )
    if evaluation.display_status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=evaluation.product_match_reason)

    enforce_budget_or_raise(db, user=user)
    budget_settings = ensure_ai_budget_settings(db, user)
    provider = get_ai_provider()
    model = budget_settings.preferred_default_model or settings.openai_default_model

    with tracked_agent_run(
        db,
        user=user,
        context=AgentExecutionContext(
            agent_type=AgentType.TENDER_QUALIFICATION.value,
            task_type="qualification",
            internet_source_search_run_id=run.id,
            internet_source_search_hit_id=hit.id,
            input_payload={"hit_id": str(hit.id), "title": hit.title},
        ),
    ) as agent:
        output, usage = provider.structured_completion(
            model=model,
            system_prompt=QUALIFICATION_SYSTEM_PROMPT,
            user_prompt=_build_qualification_prompt(hit=hit, run=run),
            output_schema=TenderQualificationOutput,
            temperature=0.0,
        )
        agent.attach_ai_usage(
            model=usage.model,
            operation=AIUsageOperation.MONITORING.value,
            cost_usd=usage.cost_usd,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        agent.record_result(
            result_type=AgentResultType.TENDER_QUALIFICATION.value,
            structured_payload=output.model_dump(mode="json"),
            summary=output.summary,
            confidence=float(output.confidence),
            requires_review=not output.qualified,
            applied=False,
        )

    record = _upsert_qualification(db, user=user, hit=hit, output=output)
    db.commit()
    db.refresh(record)
    return record


def passes_auto_gates(record: QualifiedRequirement) -> bool:
    if not record.qualified:
        return False
    score = float(record.qualification_score or 0.0)
    return score >= settings.auto_qualify_score_threshold


def auto_qualify_search_hits(
    db: Session,
    *,
    user: User,
    hits: list[InternetSourceSearchHit],
) -> list[QualifiedRequirement]:
    results: list[QualifiedRequirement] = []
    for hit in hits:
        if hit.status != "FOUND" or hit.opportunity_id:
            continue
        fields = hit.extracted_fields or {}
        if not fields.get("product_match", True) or fields.get("submission_expired"):
            continue
        try:
            record = qualify_search_hit(db, user=user, hit_id=hit.id)
            results.append(record)
        except HTTPException:
            continue
    return results
