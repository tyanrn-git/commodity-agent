from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import get_ai_provider
from app.ai.schemas import SupplyDiscoveryOutput
from app.config import settings
from app.domain.enums import (
    AIUsageOperation,
    AgentResultType,
    AgentType,
    AuditAction,
)
from app.domain.models import InternetSourceSearchHit, Opportunity, Product, SupplierLeadContext, User
from app.services.agent_runtime import AgentExecutionContext, tracked_agent_run
from app.services.ai_budget import enforce_budget_or_raise, ensure_ai_budget_settings
from app.services.audit import log_audit

SUPPLY_DISCOVERY_SYSTEM_PROMPT = """You discover a plausible supply-side scenario for a commodity tender opportunity.
Rules:
- Propose one realistic supplier that could cover the tender product and route.
- Estimate buy side from supplier context, sell side from tender buyer context, freight and preliminary gross margin.
- All prices and margins are ESTIMATED — mark conservative assumptions.
- Do NOT decide whether the tender is qualified; focus only on supply feasibility.
- Explain risks briefly.
"""


def _build_supply_prompt(*, opportunity: Opportunity, product: Product | None, hit: InternetSourceSearchHit | None) -> str:
    fields = (hit.extracted_fields or {}) if hit else {}
    product_name = product.normalized_name if product else opportunity.raw_product_name
    return (
        f"Opportunity title: {opportunity.title}\n"
        f"Product: {product_name or 'unknown'}\n"
        f"Buyer hint: {opportunity.buyer_or_supplier_hint or fields.get('buyer') or 'unknown'}\n"
        f"Volume: {opportunity.quantity_min or fields.get('quantity') or 'unknown'} "
        f"{opportunity.quantity_unit or fields.get('quantity_unit') or ''}\n"
        f"Destination: {opportunity.destination_hint or fields.get('destination') or 'unknown'}\n"
        f"Submission deadline: {opportunity.deadline or fields.get('submission_deadline') or 'unknown'}\n"
        f"Source URL: {opportunity.source_url or hit.canonical_url if hit else 'n/a'}\n"
        f"Tender evidence: {hit.evidence_excerpt if hit else opportunity.notes or 'n/a'}\n"
    )


def _supply_output_to_economics(output: SupplyDiscoveryOutput) -> dict:
    return {
        "buyer_name": None,
        "seller_name": output.supplier_hint,
        "buy_price_per_unit": float(output.buy_price_per_unit) if output.buy_price_per_unit is not None else None,
        "buy_currency": output.buy_currency,
        "buy_incoterm": output.buy_incoterm,
        "buy_basis": output.buy_basis,
        "sell_price_per_unit": float(output.sell_price_per_unit) if output.sell_price_per_unit is not None else None,
        "sell_currency": output.sell_currency,
        "sell_incoterm": output.sell_incoterm,
        "sell_basis": output.sell_basis,
        "transport_cost": float(output.transport_cost) if output.transport_cost is not None else None,
        "gross_margin": float(output.gross_margin) if output.gross_margin is not None else None,
        "gross_margin_percent": output.gross_margin_percent,
        "margin_currency": output.margin_currency,
        "costs_currency": output.margin_currency,
        "data_completeness": "ESTIMATED",
        "source": "supply_discovery_ai",
        "feasibility_summary": output.summary,
        "supplier_reasoning": output.supplier_reasoning,
        "risks": output.risks,
        "confidence": output.confidence,
    }


def _economics_preview(economics: dict) -> str | None:
    margin = economics.get("gross_margin")
    if margin is None:
        return economics.get("feasibility_summary")
    currency = economics.get("margin_currency") or economics.get("costs_currency") or "USD"
    preview = f"Маржа {margin} {currency}"
    margin_pct = economics.get("gross_margin_percent")
    if margin_pct is not None:
        preview += f" ({margin_pct}%)"
    return preview


def _upsert_supplier_context(
    db: Session,
    *,
    opportunity: Opportunity,
    output: SupplyDiscoveryOutput,
) -> SupplierLeadContext:
    context = db.scalar(
        select(SupplierLeadContext).where(SupplierLeadContext.opportunity_id == opportunity.id)
    )
    if context is None:
        context = SupplierLeadContext(opportunity_id=opportunity.id)
        db.add(context)
    context.supplier_hint = output.supplier_hint
    if output.buy_price_per_unit is not None:
        context.unit_price = float(output.buy_price_per_unit)
    context.currency = output.buy_currency or context.currency
    context.incoterm = output.buy_incoterm or context.incoterm
    if output.buy_basis and not context.origin:
        context.origin = output.buy_basis
    db.flush()
    return context


def discover_supply_for_opportunity(
    db: Session,
    *,
    user: User,
    opportunity_id: uuid.UUID,
) -> tuple[Opportunity, SupplyDiscoveryOutput, dict]:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    hit = db.scalar(
        select(InternetSourceSearchHit).where(InternetSourceSearchHit.opportunity_id == opportunity.id)
    )
    product = db.get(Product, opportunity.normalized_product_id) if opportunity.normalized_product_id else None

    enforce_budget_or_raise(db, user=user)
    budget_settings = ensure_ai_budget_settings(db, user)
    provider = get_ai_provider()
    model = budget_settings.preferred_default_model or settings.openai_default_model

    with tracked_agent_run(
        db,
        user=user,
        context=AgentExecutionContext(
            agent_type=AgentType.SUPPLY_DISCOVERY.value,
            task_type="supplier_search",
            opportunity_id=opportunity.id,
            internet_source_search_hit_id=hit.id if hit else None,
            input_payload={"opportunity_id": str(opportunity.id), "title": opportunity.title},
        ),
    ) as agent:
        output, usage = provider.structured_completion(
            model=model,
            system_prompt=SUPPLY_DISCOVERY_SYSTEM_PROMPT,
            user_prompt=_build_supply_prompt(opportunity=opportunity, product=product, hit=hit),
            output_schema=SupplyDiscoveryOutput,
            temperature=0.0,
        )
        agent.attach_ai_usage(
            model=usage.model,
            operation=AIUsageOperation.RESEARCH.value,
            cost_usd=usage.cost_usd,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            opportunity_id=opportunity.id,
        )
        agent.record_result(
            result_type=AgentResultType.SUPPLY_DISCOVERY.value,
            structured_payload=output.model_dump(mode="json"),
            summary=output.summary,
            confidence=float(output.confidence),
            requires_review=True,
            applied=False,
        )

    economics = _supply_output_to_economics(output)
    opportunity.indicative_economics = economics
    supplier_note = output.supplier_hint or "не определён"
    opportunity.notes = (
        f"{opportunity.notes or ''}\n"
        f"Supply Discovery: {output.summary}\n"
        f"Поставщик (оценка): {supplier_note}"
    ).strip()
    _upsert_supplier_context(db, opportunity=opportunity, output=output)

    if hit:
        fields = dict(hit.extracted_fields or {})
        fields["supply_discovery"] = output.model_dump(mode="json")
        hit.extracted_fields = fields

    log_audit(
        db,
        actor=user,
        action=AuditAction.AI_CALL,
        entity_type="Opportunity",
        entity_id=opportunity.id,
        new_value={
            "operation": "supply_discovery",
            "supplier_hint": output.supplier_hint,
            "confidence": float(output.confidence),
        },
    )
    db.commit()
    db.refresh(opportunity)
    return opportunity, output, economics
