import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import (
    AuditAction,
    DealDirection,
    OpportunityStatus,
    OpportunityType,
    SupplierLeadMatchStatus,
    SupplierLeadMatchType,
)
from app.domain.models import (
    Deal,
    Opportunity,
    Product,
    Requirement,
    SupplierLeadContext,
    SupplierLeadMatch,
    SupplyOffer,
    User,
)
from app.services.audit import log_audit
from app.services.opportunity_status import initialize_opportunity_status
from app.services.opportunity_commercial import build_indicative_economics_from_supplier_context
from app.services.formatting import format_amount, format_percent, format_quantity
from app.services.opportunity import opportunity_to_dict

MIN_MATCH_SCORE = Decimal("30")
DEFAULT_MARKUP_PERCENT = Decimal("8")
FREIGHT_PER_MT_USD = Decimal("40")
ACTIVE_BUYER_TYPES = {
    OpportunityType.BUYER_NEED.value,
    OpportunityType.AUTO_DISCOVERED.value,
    OpportunityType.TENDER.value,
}
INACTIVE_STATUSES = {
    OpportunityStatus.CONVERTED.value,
    OpportunityStatus.REJECTED.value,
    OpportunityStatus.ARCHIVED.value,
}


def _decimal(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _product_tokens(opp: Opportunity, product: Product | None) -> set[str]:
    tokens: set[str] = set()
    if product and product.normalized_name:
        tokens.add(product.normalized_name.lower())
        for alias in product.aliases or []:
            tokens.add(str(alias).lower())
    if opp.raw_product_name:
        tokens.add(opp.raw_product_name.lower())
    return tokens


def _names_overlap(left: set[str], right: set[str]) -> bool:
    if not left or not right:
        return False
    for a in left:
        for b in right:
            if a in b or b in a:
                return True
    return False


def _quantity_overlap(
    supplier_min, supplier_max, buyer_min, buyer_max
) -> tuple[bool, str | None]:
    s_min = _decimal(supplier_min)
    s_max = _decimal(supplier_max) or s_min
    b_min = _decimal(buyer_min)
    b_max = _decimal(buyer_max) or b_min
    if s_min is None and s_max is None:
        return False, None
    if b_min is None and b_max is None:
        return False, None
    s_lo = s_min if s_min is not None else s_max
    s_hi = s_max if s_max is not None else s_min
    b_lo = b_min if b_min is not None else b_max
    b_hi = b_max if b_max is not None else b_min
    if s_lo is None or s_hi is None or b_lo is None or b_hi is None:
        return False, None
    overlaps = s_lo <= b_hi and b_lo <= s_hi
    if not overlaps:
        return False, None
    overlap_lo = max(s_lo, b_lo)
    overlap_hi = min(s_hi, b_hi)
    return True, f"Пересечение объёма {int(overlap_lo)}–{int(overlap_hi)}"


def _score_buyer_need(
    supplier: Opportunity,
    supplier_product: Product | None,
    buyer: Opportunity,
    buyer_product: Product | None,
    *,
    destination: str | None,
    quantity_min,
    quantity_max,
    quantity_unit: str | None,
) -> tuple[Decimal, list[str], str]:
    reasons: list[str] = []
    score = Decimal("0")

    supplier_tokens = _product_tokens(supplier, supplier_product)
    buyer_tokens = _product_tokens(buyer, buyer_product)
    if supplier.normalized_product_id and buyer.normalized_product_id:
        if supplier.normalized_product_id == buyer.normalized_product_id:
            score += Decimal("40")
            reasons.append("Совпадение нормализованного товара")
    elif _names_overlap(supplier_tokens, buyer_tokens):
        score += Decimal("25")
        reasons.append("Совпадение названия товара")

    qty_ok, qty_reason = _quantity_overlap(
        supplier.quantity_min,
        supplier.quantity_max,
        quantity_min,
        quantity_max,
    )
    if qty_ok:
        score += Decimal("20")
        if qty_reason:
            reasons.append(qty_reason)

    dest = destination or buyer.destination_hint
    if dest and supplier.origin_hint:
        score += Decimal("15")
        reasons.append(f"Маршрут {supplier.origin_hint} → {dest}")
    elif dest:
        score += Decimal("10")
        reasons.append(f"Спрос в {dest}")

    if supplier.quantity_unit and quantity_unit and supplier.quantity_unit == quantity_unit:
        score += Decimal("5")
        reasons.append(f"Единица {quantity_unit}")

    buyer_label = buyer.buyer_or_supplier_hint or buyer.title
    summary_parts = [buyer_label]
    if buyer_product:
        summary_parts.insert(0, buyer_product.normalized_name)
    elif buyer.raw_product_name:
        summary_parts.insert(0, buyer.raw_product_name)
    if dest:
        summary_parts.append(f"→ {dest}")
    return score, reasons, " · ".join(summary_parts)


def _ensure_supplier_opportunity(opportunity: Opportunity) -> None:
    if opportunity.type != OpportunityType.SUPPLIER_OFFER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only SUPPLIER_OFFER opportunities support supplier-led flow",
        )


def _get_context(db: Session, opportunity: Opportunity) -> SupplierLeadContext:
    context = db.scalar(
        select(SupplierLeadContext).where(SupplierLeadContext.opportunity_id == opportunity.id)
    )
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supplier lead context is missing for this opportunity",
        )
    return context


def create_supplier_led_opportunity(
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
    notes: str | None = None,
    unit_price: Decimal | None = None,
    currency: str = "USD",
    incoterm: str | None = None,
    origin: str | None = None,
) -> Opportunity:
    if normalized_product_id:
        product = db.get(Product, normalized_product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    opportunity = Opportunity(
        owner_id=user.id,
        type=OpportunityType.SUPPLIER_OFFER.value,
        title=title,
        raw_product_name=raw_product_name,
        normalized_product_id=normalized_product_id,
        buyer_or_supplier_hint=buyer_or_supplier_hint,
        quantity_min=quantity_min,
        quantity_max=quantity_max,
        quantity_unit=quantity_unit,
        origin_hint=origin_hint or origin,
        destination_hint=destination_hint,
        deadline=deadline,
        status=OpportunityStatus.NEW.value,
        notes=notes,
    )
    db.add(opportunity)
    db.flush()
    initialize_opportunity_status(db, opportunity=opportunity, actor=user, actor_type="USER")

    context = SupplierLeadContext(
        opportunity_id=opportunity.id,
        unit_price=unit_price,
        currency=currency,
        incoterm=incoterm,
        origin=origin or origin_hint,
        supplier_hint=buyer_or_supplier_hint,
    )
    db.add(context)
    db.flush()
    opportunity.indicative_economics = build_indicative_economics_from_supplier_context(context)

    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="Opportunity",
        entity_id=opportunity.id,
        new_value={
            **opportunity_to_dict(opportunity),
            "supplier_led": True,
            "unit_price": str(unit_price) if unit_price is not None else None,
        },
    )
    db.commit()
    db.refresh(opportunity)
    return opportunity


def create_supplier_led_from_supply_offer(
    db: Session,
    *,
    user: User,
    supply_offer_id: uuid.UUID,
    title: str | None = None,
) -> Opportunity:
    offer = db.scalar(
        select(SupplyOffer)
        .where(SupplyOffer.id == supply_offer_id)
        .options(joinedload(SupplyOffer.deal), joinedload(SupplyOffer.supplier))
    )
    if offer is None or offer.deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supply offer not found")

    product = None
    if offer.product_name:
        product = db.scalar(
            select(Product).where(Product.normalized_name.ilike(offer.product_name.strip()))
        )

    supplier_name = (offer.supplier.trade_name or offer.supplier.legal_name) if offer.supplier else None
    opportunity = Opportunity(
        owner_id=user.id,
        type=OpportunityType.SUPPLIER_OFFER.value,
        title=title or f"Предложение: {offer.product_name or 'товар'}",
        raw_product_name=offer.product_name,
        normalized_product_id=product.id if product else None,
        buyer_or_supplier_hint=supplier_name,
        quantity_min=offer.available_quantity,
        quantity_max=offer.available_quantity,
        quantity_unit=offer.quantity_unit,
        origin_hint=offer.origin or offer.loading_point,
        status=OpportunityStatus.NEW.value,
        notes=f"Создано из SupplyOffer {offer.id}",
    )
    db.add(opportunity)
    db.flush()

    context = SupplierLeadContext(
        opportunity_id=opportunity.id,
        supply_offer_id=offer.id,
        unit_price=offer.price,
        currency=offer.currency or "USD",
        incoterm=offer.incoterm,
        origin=offer.origin or offer.loading_point,
        supplier_hint=supplier_name,
    )
    db.add(context)
    db.flush()

    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="Opportunity",
        entity_id=opportunity.id,
        new_value={
            **opportunity_to_dict(opportunity),
            "supply_offer_id": str(offer.id),
        },
    )
    db.commit()
    db.refresh(opportunity)
    return opportunity


def match_buyer_needs(db: Session, *, user: User, opportunity: Opportunity) -> list[SupplierLeadMatch]:
    _ensure_supplier_opportunity(opportunity)
    if opportunity.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    _get_context(db, opportunity)
    supplier_product = (
        db.get(Product, opportunity.normalized_product_id)
        if opportunity.normalized_product_id
        else None
    )

    db.execute(
        delete(SupplierLeadMatch).where(
            SupplierLeadMatch.supplier_opportunity_id == opportunity.id
        )
    )

    candidates: list[SupplierLeadMatch] = []

    buyer_opps = db.scalars(
        select(Opportunity)
        .where(
            Opportunity.owner_id == user.id,
            Opportunity.id != opportunity.id,
            Opportunity.type.in_(ACTIVE_BUYER_TYPES),
            Opportunity.status.not_in(INACTIVE_STATUSES),
        )
        .options(joinedload(Opportunity.product))
    ).unique()
    for buyer in buyer_opps:
        score, reasons, summary = _score_buyer_need(
            opportunity,
            supplier_product,
            buyer,
            buyer.product,
            destination=buyer.destination_hint,
            quantity_min=buyer.quantity_min,
            quantity_max=buyer.quantity_max,
            quantity_unit=buyer.quantity_unit,
        )
        if score < MIN_MATCH_SCORE:
            continue
        candidates.append(
            SupplierLeadMatch(
                supplier_opportunity_id=opportunity.id,
                match_type=SupplierLeadMatchType.BUYER_OPPORTUNITY.value,
                matched_opportunity_id=buyer.id,
                score=score,
                match_summary=summary,
                match_reasons=reasons,
                status=SupplierLeadMatchStatus.SUGGESTED.value,
            )
        )

    requirements = db.scalars(
        select(Requirement)
        .join(Deal)
        .where(
            Deal.owner_id == user.id,
            Deal.direction == DealDirection.BUYER_LED.value,
        )
        .options(joinedload(Requirement.product), joinedload(Requirement.deal))
    ).unique()
    for requirement in requirements:
        buyer_product = requirement.product
        pseudo_buyer = Opportunity(
            raw_product_name=requirement.product.normalized_name if requirement.product else None,
            normalized_product_id=requirement.product_id,
            destination_hint=requirement.destination,
            buyer_or_supplier_hint=requirement.deal.title,
        )
        score, reasons, summary = _score_buyer_need(
            opportunity,
            supplier_product,
            pseudo_buyer,
            buyer_product,
            destination=requirement.destination,
            quantity_min=requirement.quantity_min,
            quantity_max=requirement.quantity_max,
            quantity_unit=requirement.quantity_unit,
        )
        if score < MIN_MATCH_SCORE:
            continue
        summary = f"{requirement.deal.deal_number}: {summary}"
        candidates.append(
            SupplierLeadMatch(
                supplier_opportunity_id=opportunity.id,
                match_type=SupplierLeadMatchType.BUYER_REQUIREMENT.value,
                matched_deal_id=requirement.deal_id,
                matched_requirement_id=requirement.id,
                score=score,
                match_summary=summary,
                match_reasons=reasons,
                status=SupplierLeadMatchStatus.SUGGESTED.value,
            )
        )

    candidates.sort(key=lambda item: Decimal(str(item.score)), reverse=True)
    for match in candidates:
        db.add(match)
    db.flush()

    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="Opportunity",
        entity_id=opportunity.id,
        new_value={"action": "match_buyer_needs", "matches_found": len(candidates)},
    )
    db.commit()
    for match in candidates:
        db.refresh(match)
    return candidates


def _resolve_destination(match: SupplierLeadMatch, db: Session) -> str:
    if match.matched_opportunity_id:
        opp = db.get(Opportunity, match.matched_opportunity_id)
        if opp and opp.destination_hint:
            return opp.destination_hint
    if match.matched_requirement_id:
        req = db.get(Requirement, match.matched_requirement_id)
        if req and req.destination:
            return req.destination
    return "destination TBD"


def _resolve_quantity(opportunity: Opportunity, match: SupplierLeadMatch, db: Session) -> Decimal:
    if match.matched_requirement_id:
        req = db.get(Requirement, match.matched_requirement_id)
        if req and req.quantity_max:
            return Decimal(str(req.quantity_max))
        if req and req.quantity_min:
            return Decimal(str(req.quantity_min))
    if match.matched_opportunity_id:
        opp = db.get(Opportunity, match.matched_opportunity_id)
        if opp and opp.quantity_max:
            return Decimal(str(opp.quantity_max))
        if opp and opp.quantity_min:
            return Decimal(str(opp.quantity_min))
    if opportunity.quantity_max:
        return Decimal(str(opportunity.quantity_max))
    if opportunity.quantity_min:
        return Decimal(str(opportunity.quantity_min))
    return Decimal("100")


def build_market_comparison(
    db: Session,
    *,
    opportunity: Opportunity,
    context: SupplierLeadContext,
) -> dict:
    product_name = opportunity.raw_product_name
    if opportunity.normalized_product_id:
        product = db.get(Product, opportunity.normalized_product_id)
        if product:
            product_name = product.normalized_name

    comparable: list[dict] = []
    if product_name:
        offers = db.scalars(
            select(SupplyOffer)
            .join(Deal)
            .where(
                Deal.owner_id == opportunity.owner_id,
                SupplyOffer.price.is_not(None),
                SupplyOffer.product_name.ilike(f"%{product_name}%"),
            )
            .limit(10)
        )
        for offer in offers:
            comparable.append(
                {
                    "source": "supply_offer",
                    "reference_id": str(offer.id),
                    "product": offer.product_name,
                    "unit_price": str(offer.price),
                    "currency": offer.currency or "USD",
                    "incoterm": offer.incoterm,
                    "origin": offer.origin,
                }
            )

    contexts = db.scalars(
        select(SupplierLeadContext)
        .join(Opportunity)
        .where(
            Opportunity.owner_id == opportunity.owner_id,
            Opportunity.type == OpportunityType.SUPPLIER_OFFER.value,
            Opportunity.id != opportunity.id,
            SupplierLeadContext.unit_price.is_not(None),
        )
        .limit(10)
    )
    for other in contexts:
        comparable.append(
            {
                "source": "supplier_lead_context",
                "reference_id": str(other.opportunity_id),
                "unit_price": str(other.unit_price),
                "currency": other.currency or "USD",
                "incoterm": other.incoterm,
                "origin": other.origin,
            }
        )

    prices = [Decimal(item["unit_price"]) for item in comparable if item.get("unit_price")]
    our_price = _decimal(context.unit_price)
    summary = {
        "product": product_name,
        "our_unit_price": str(our_price) if our_price is not None else None,
        "currency": context.currency or "USD",
        "comparable_count": len(comparable),
        "comparables": comparable,
        "confirmation_level": "ESTIMATE",
        "assumptions": [
            "Сравнение основано только на подтверждённых SupplyOffer и supplier-led контекстах в системе",
            "Внешние рыночные индексы не подключены на этапе 7",
        ],
    }
    if prices:
        summary["market_min"] = str(min(prices))
        summary["market_max"] = str(max(prices))
        summary["market_avg"] = str(sum(prices) / Decimal(len(prices)))
        if our_price is not None:
            if our_price <= min(prices):
                summary["position"] = "below_market"
            elif our_price >= max(prices):
                summary["position"] = "above_market"
            else:
                summary["position"] = "within_market"
    return summary


def build_route_for_match(
    db: Session,
    *,
    user: User,
    match: SupplierLeadMatch,
) -> SupplierLeadMatch:
    opportunity = db.get(Opportunity, match.supplier_opportunity_id)
    if opportunity is None or opportunity.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    context = _get_context(db, opportunity)
    destination = _resolve_destination(match, db)
    origin = context.origin or opportunity.origin_hint or "origin TBD"
    quantity = _resolve_quantity(opportunity, match, db)
    purchase_price = _decimal(context.unit_price) or Decimal("0")
    freight_total = (quantity * FREIGHT_PER_MT_USD).quantize(Decimal("0.01"))
    freight_per_mt = FREIGHT_PER_MT_USD
    landed_cost = purchase_price + freight_per_mt
    markup_multiplier = Decimal("1") + (DEFAULT_MARKUP_PERCENT / Decimal("100"))
    suggested_sell = (landed_cost * markup_multiplier).quantize(Decimal("0.01"))
    currency = context.currency or "USD"
    incoterm = context.incoterm or "CIF"

    route = {
        "origin": origin,
        "destination": destination,
        "quantity_mt": str(quantity),
        "purchase_incoterm": incoterm,
        "purchase_unit_price": str(purchase_price),
        "currency": currency,
        "freight_estimate_total": str(freight_total),
        "freight_per_mt": str(freight_per_mt),
        "landed_cost_per_mt": str(landed_cost),
        "markup_percent": str(DEFAULT_MARKUP_PERCENT),
        "suggested_sell_price_per_mt": str(suggested_sell),
        "confirmation_level": "ESTIMATE",
        "assumptions": [
            f"Фрахт оценён как {format_amount(freight_per_mt)} {currency}/MT (заглушка этапа 7)",
            f"Наценка {format_percent(DEFAULT_MARKUP_PERCENT)}% для индикативного предложения покупателю",
        ],
        "executable": purchase_price > 0 and destination != "destination TBD" and origin != "origin TBD",
    }
    match.route_proposal = route
    match.market_comparison = build_market_comparison(db, opportunity=opportunity, context=context)
    match.status = SupplierLeadMatchStatus.ROUTE_BUILT.value
    db.flush()

    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="SupplierLeadMatch",
        entity_id=match.id,
        new_value={"status": match.status, "route": route},
    )
    db.commit()
    db.refresh(match)
    return match


def draft_buyer_outreach(
    db: Session,
    *,
    user: User,
    match: SupplierLeadMatch,
) -> SupplierLeadMatch:
    opportunity = db.get(Opportunity, match.supplier_opportunity_id)
    if opportunity is None or opportunity.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    if not match.route_proposal:
        match = build_route_for_match(db, user=user, match=match)

    route = match.route_proposal or {}
    product = opportunity.raw_product_name or "product"
    if opportunity.normalized_product_id:
        prod = db.get(Product, opportunity.normalized_product_id)
        if prod:
            product = prod.normalized_name

    destination = route.get("destination", "your destination")
    qty = route.get("quantity_mt", "—")
    unit = opportunity.quantity_unit or "MT"
    sell_price = route.get("suggested_sell_price_per_mt")
    currency = route.get("currency", "USD")
    incoterm = route.get("purchase_incoterm", "CIF")

    buyer_name = "Customer"
    if match.matched_opportunity_id:
        buyer_opp = db.get(Opportunity, match.matched_opportunity_id)
        if buyer_opp and buyer_opp.buyer_or_supplier_hint:
            buyer_name = buyer_opp.buyer_or_supplier_hint
    if match.matched_deal_id:
        deal = db.get(Deal, match.matched_deal_id)
        if deal:
            buyer_name = deal.title

    subject = f"Indicative offer: {product} — {destination}"
    body_lines = [
        f"Dear {buyer_name},",
        "",
        "We can offer the following indicative terms based on confirmed supplier availability:",
        "",
        f"Product: {product}",
        f"Quantity: {format_quantity(qty, unit)}",
        f"Destination: {destination}",
        f"Incoterm: {incoterm} {destination}",
    ]
    if sell_price:
        body_lines.append(
            f"Indicative price: {currency} {format_amount(sell_price)} per {unit}"
        )
    body_lines.extend(
        [
            "",
            "This is a non-binding indicative offer subject to final confirmation, "
            "specification review, and internal approval.",
            "",
            "Please let us know if you would like us to proceed with a formal quote.",
            "",
            "Best regards,",
        ]
    )
    match.outreach_subject = subject
    match.outreach_body = "\n".join(body_lines)
    match.status = SupplierLeadMatchStatus.OUTREACH_DRAFTED.value
    db.flush()

    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="SupplierLeadMatch",
        entity_id=match.id,
        new_value={"status": match.status, "outreach_subject": subject},
    )
    db.commit()
    db.refresh(match)
    return match


def get_supplier_lead_detail(db: Session, *, user: User, opportunity: Opportunity) -> dict:
    _ensure_supplier_opportunity(opportunity)
    context = db.scalar(
        select(SupplierLeadContext).where(SupplierLeadContext.opportunity_id == opportunity.id)
    )
    matches = list(
        db.scalars(
            select(SupplierLeadMatch)
            .where(SupplierLeadMatch.supplier_opportunity_id == opportunity.id)
            .order_by(SupplierLeadMatch.score.desc())
        )
    )
    market = None
    if context:
        market = build_market_comparison(db, opportunity=opportunity, context=context)
    return {
        "context": context,
        "matches": matches,
        "market_comparison": market,
    }
