from app.domain.enums import OpportunityType
from app.domain.models import (
    Deal,
    FulfilmentConfiguration,
    MonitoredPublication,
    Opportunity,
    SupplierLeadContext,
)


def _format_quantity(min_qty, max_qty, unit: str | None) -> str | None:
    if min_qty is None and max_qty is None:
        return None
    if min_qty is not None and max_qty is not None and min_qty != max_qty:
        text = f"{int(min_qty)}–{int(max_qty)}"
    elif min_qty is not None:
        text = str(int(min_qty))
    else:
        text = str(int(max_qty))
    return f"{text} {unit}".strip() if unit else text


def _format_basis(incoterm: str | None, location: str | None) -> str | None:
    if incoterm and location:
        return f"{incoterm} {location}"
    return location or incoterm


def _as_float(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _other_costs_from_breakdown(breakdown: dict | None) -> float | None:
    if not breakdown:
        return None
    keys = (
        "inland_transport",
        "terminal",
        "storage",
        "insurance",
        "inspection",
        "customs",
        "financing",
        "other",
    )
    total = sum(_as_float(breakdown.get(key)) or 0 for key in keys)
    return total if total > 0 else None


def build_indicative_economics_from_supplier_context(context: SupplierLeadContext) -> dict:
    return {
        "seller_name": context.supplier_hint,
        "buy_price_per_unit": _as_float(context.unit_price),
        "buy_currency": context.currency,
        "buy_incoterm": context.incoterm,
        "buy_basis": _format_basis(context.incoterm, context.origin),
        "data_completeness": "PARTIAL",
        "source": "supplier_intake",
    }


def build_commercial_row(
    opp: Opportunity,
    *,
    product_name: str | None,
    publication: MonitoredPublication | None = None,
    supplier_context: SupplierLeadContext | None = None,
    deal: Deal | None = None,
    config: FulfilmentConfiguration | None = None,
) -> dict:
    stored = dict(opp.indicative_economics or {})
    pub_fields = (publication.extracted_fields or {}) if publication else {}

    row: dict = {
        "buyer_name": stored.get("buyer_name"),
        "seller_name": stored.get("seller_name"),
        "product_name": product_name or opp.raw_product_name,
        "volume": _format_quantity(opp.quantity_min, opp.quantity_max, opp.quantity_unit),
        "buy_price_per_unit": stored.get("buy_price_per_unit"),
        "buy_currency": stored.get("buy_currency"),
        "buy_incoterm": stored.get("buy_incoterm"),
        "buy_basis": stored.get("buy_basis"),
        "sell_price_per_unit": stored.get("sell_price_per_unit"),
        "sell_currency": stored.get("sell_currency"),
        "sell_incoterm": stored.get("sell_incoterm"),
        "sell_basis": stored.get("sell_basis"),
        "transport_cost": stored.get("transport_cost"),
        "other_costs": stored.get("other_costs"),
        "costs_currency": stored.get("costs_currency"),
        "gross_margin": stored.get("gross_margin"),
        "gross_margin_percent": stored.get("gross_margin_percent"),
        "margin_currency": stored.get("margin_currency"),
        "data_completeness": stored.get("data_completeness") or "EMPTY",
        "source": stored.get("source"),
    }

    if opp.type == OpportunityType.BUYER_NEED.value:
        row["buyer_name"] = row["buyer_name"] or opp.buyer_or_supplier_hint or pub_fields.get("buyer")
    elif opp.type == OpportunityType.SUPPLIER_OFFER.value:
        if supplier_context:
            row["seller_name"] = row["seller_name"] or supplier_context.supplier_hint
            row["buy_price_per_unit"] = row["buy_price_per_unit"] or _as_float(supplier_context.unit_price)
            row["buy_currency"] = row["buy_currency"] or supplier_context.currency
            row["buy_incoterm"] = row["buy_incoterm"] or supplier_context.incoterm
            row["buy_basis"] = row["buy_basis"] or _format_basis(supplier_context.incoterm, supplier_context.origin)
        else:
            row["seller_name"] = row["seller_name"] or opp.buyer_or_supplier_hint
    elif opp.type == OpportunityType.AUTO_DISCOVERED.value:
        row["buyer_name"] = row["buyer_name"] or opp.buyer_or_supplier_hint or pub_fields.get("buyer")
        row["product_name"] = row["product_name"] or opp.raw_product_name or pub_fields.get("product")
        row["volume"] = row["volume"] or _format_quantity(opp.quantity_min, opp.quantity_max, opp.quantity_unit)
        row["sell_basis"] = row["sell_basis"] or opp.destination_hint or pub_fields.get("destination")
        if row["data_completeness"] == "EMPTY" and any(
            row.get(key) for key in ("buyer_name", "product_name", "volume", "sell_basis")
        ):
            row["data_completeness"] = "PARTIAL"

    if supplier_context and opp.type == OpportunityType.SUPPLIER_OFFER.value:
        if row["data_completeness"] == "EMPTY":
            row["data_completeness"] = "PARTIAL"

    if config and deal:
        currency = deal.base_currency
        row["costs_currency"] = row["costs_currency"] or currency
        row["margin_currency"] = row["margin_currency"] or currency

        if config.sales_price_per_unit is not None:
            row["sell_price_per_unit"] = _as_float(config.sales_price_per_unit)
            row["sell_currency"] = config.sales_currency or currency
        if config.destination:
            row["sell_basis"] = row["sell_basis"] or config.destination

        if config.shipment_lots:
            lot = config.shipment_lots[0]
            if lot.purchase_price_per_unit is not None:
                row["buy_price_per_unit"] = _as_float(lot.purchase_price_per_unit)
            row["buy_currency"] = row["buy_currency"] or lot.currency or currency
            row["buy_incoterm"] = row["buy_incoterm"] or lot.incoterm
            row["buy_basis"] = row["buy_basis"] or _format_basis(lot.incoterm, lot.origin)

        breakdown = config.cost_breakdown or {}
        freight = _as_float(breakdown.get("freight"))
        if freight is not None:
            row["transport_cost"] = freight
        other = _other_costs_from_breakdown(breakdown)
        if other is not None:
            row["other_costs"] = other

        if config.gross_margin is not None:
            row["gross_margin"] = _as_float(config.gross_margin)
        if config.gross_margin_percent is not None:
            row["gross_margin_percent"] = _as_float(config.gross_margin_percent)

        row["data_completeness"] = "CONFIRMED"
        row["source"] = row["source"] or "deal_configuration"

    if row["data_completeness"] == "EMPTY" and any(
        row.get(key) for key in ("buyer_name", "seller_name", "buy_price_per_unit", "sell_price_per_unit")
    ):
        row["data_completeness"] = "PARTIAL"

    return row
