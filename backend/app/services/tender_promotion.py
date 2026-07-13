import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai.factory import get_ai_provider
from app.ai.schemas import TenderFeasibilityOutput
from app.config import settings
from app.domain.enums import (
    AIUsageOperation,
    AuditAction,
    InternetSourceSearchHitStatus,
    OpportunityStatus,
    OpportunityType,
    AgentResultType,
    AgentType,
)
from app.domain.models import InternetSourceSearchHit, Opportunity, User
from app.services.ai_budget import enforce_budget_or_raise, ensure_ai_budget_settings
from app.services.agent_runtime import AgentExecutionContext, tracked_agent_run
from app.services.audit import log_audit
from app.services.opportunity_status import initialize_opportunity_status
from app.services.tender_attachments import attach_tender_link
from app.services.tender_hit_evaluation import evaluate_tender_hit
from app.ai.schemas import TenderSearchHitOutput

FEASIBILITY_SYSTEM_PROMPT = """You assess whether a public tender can be executed profitably by a commodity trading desk.
Rules:
- Propose one realistic supplier that could cover the tender product and route.
- Estimate buy side from supplier, sell side from tender buyer context, freight and preliminary gross margin.
- Mark feasible=false when product/route is unclear, deadline is impossible, or margin is likely negative.
- Use conservative assumptions and explain risks briefly.
- Return feasible=true only when a credible supplier-backed scenario exists.
"""


def _parse_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def get_search_hit(db: Session, *, user: User, hit_id: uuid.UUID) -> InternetSourceSearchHit:
    hit = db.get(InternetSourceSearchHit, hit_id)
    if hit is None or hit.search_run.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search hit not found")
    return hit


def _build_feasibility_prompt(*, hit: InternetSourceSearchHit, run) -> str:
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


def _feasibility_to_economics(result: TenderFeasibilityOutput) -> dict:
    completeness = "CONFIRMED" if result.feasible and result.gross_margin is not None else "PARTIAL"
    return {
        "buyer_name": None,
        "seller_name": result.supplier_hint,
        "buy_price_per_unit": float(result.buy_price_per_unit) if result.buy_price_per_unit is not None else None,
        "buy_currency": result.buy_currency,
        "buy_incoterm": result.buy_incoterm,
        "buy_basis": result.buy_basis,
        "sell_price_per_unit": float(result.sell_price_per_unit) if result.sell_price_per_unit is not None else None,
        "sell_currency": result.sell_currency,
        "sell_incoterm": result.sell_incoterm,
        "sell_basis": result.sell_basis,
        "transport_cost": float(result.transport_cost) if result.transport_cost is not None else None,
        "gross_margin": float(result.gross_margin) if result.gross_margin is not None else None,
        "gross_margin_percent": result.gross_margin_percent,
        "margin_currency": result.margin_currency,
        "costs_currency": result.margin_currency,
        "data_completeness": completeness,
        "source": "tender_feasibility_ai",
        "feasibility_summary": result.summary,
        "supplier_reasoning": result.supplier_reasoning,
        "risks": result.risks,
        "confidence": result.confidence,
    }


def promote_search_hit_to_opportunity(db: Session, *, user: User, hit_id: uuid.UUID) -> tuple[InternetSourceSearchHit, Opportunity]:
    hit = get_search_hit(db, user=user, hit_id=hit_id)
    run = hit.search_run
    fields = dict(hit.extracted_fields or {})

    if hit.opportunity_id:
        opportunity = db.get(Opportunity, hit.opportunity_id)
        if opportunity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked opportunity not found")
        return hit, opportunity

    if hit.status in {InternetSourceSearchHitStatus.SKIPPED.value, InternetSourceSearchHitStatus.FILTERED_OUT.value}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Тендер отфильтрован и не может быть перенесён")
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
            agent_type=AgentType.LEGACY_TENDER_PROMOTION.value,
            task_type="feasibility_assessment",
            internet_source_search_run_id=run.id,
            internet_source_search_hit_id=hit.id,
            input_payload={
                "hit_id": str(hit.id),
                "title": hit.title,
                "product_keywords": list(run.product_keywords or []),
            },
        ),
    ) as agent:
        feasibility, usage = provider.structured_completion(
            model=model,
            system_prompt=FEASIBILITY_SYSTEM_PROMPT,
            user_prompt=_build_feasibility_prompt(hit=hit, run=run),
            output_schema=TenderFeasibilityOutput,
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
            result_type=AgentResultType.TENDER_FEASIBILITY.value,
            structured_payload=feasibility.model_dump(mode="json"),
            summary=feasibility.summary,
            confidence=float(feasibility.confidence),
            requires_review=True,
            applied=False,
        )

    fields["feasibility"] = feasibility.model_dump(mode="json")
    hit.extracted_fields = fields
    db.flush()

    if not feasibility.feasible:
        db.commit()
        db.refresh(hit)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=feasibility.summary,
        )

    economics = _feasibility_to_economics(feasibility)
    opportunity = Opportunity(
        owner_id=user.id,
        type=OpportunityType.AUTO_DISCOVERED.value,
        title=hit.title,
        raw_product_name=fields.get("product"),
        buyer_or_supplier_hint=fields.get("buyer"),
        quantity_min=_parse_decimal(fields.get("quantity")),
        quantity_max=_parse_decimal(fields.get("quantity")),
        quantity_unit=fields.get("quantity_unit"),
        destination_hint=fields.get("destination"),
        deadline=_parse_datetime(fields.get("submission_deadline")),
        quote_deadline=_parse_datetime(fields.get("submission_deadline")),
        delivery_deadline=_parse_datetime(fields.get("delivery_deadline")),
        source_url=hit.canonical_url,
        status=OpportunityStatus.NEW.value,
        indicative_economics=economics,
        notes=(
            f"Перенесено из мониторинга после AI-оценки реализуемости.\n"
            f"Поставщик: {feasibility.supplier_hint or 'не определён'}\n"
            f"{feasibility.summary}"
        ),
    )
    db.add(opportunity)
    db.flush()
    attach_tender_link(db, user=user, opportunity=opportunity, url=hit.canonical_url)
    initialize_opportunity_status(db, opportunity=opportunity, actor=user, actor_type="AI")

    hit.opportunity_id = opportunity.id
    hit.status = InternetSourceSearchHitStatus.OPPORTUNITY_CREATED.value
    run.opportunities_created = int(run.opportunities_created or 0) + 1

    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="Opportunity",
        entity_id=opportunity.id,
        new_value={
            "source": "monitoring_promote",
            "search_hit_id": str(hit.id),
            "search_run_id": str(run.id),
            "supplier_hint": feasibility.supplier_hint,
            "feasible": feasibility.feasible,
        },
    )
    db.commit()
    db.refresh(hit)
    db.refresh(opportunity)
    return hit, opportunity
