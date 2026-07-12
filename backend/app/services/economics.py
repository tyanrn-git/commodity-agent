from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.enums import ConfigurationStatus, EconomicsScenario, ServiceQuoteType
from app.domain.models import (
    Deal,
    EconomicsSnapshot,
    FulfilmentConfiguration,
    Requirement,
    ShipmentLot,
)
from app.services.fx import convert_amount
from app.services.spec_matcher import build_spec_summary


def _d(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def calculate_configuration(
    db: Session,
    *,
    configuration: FulfilmentConfiguration,
    deal: Deal,
    requirement: Requirement | None = None,
) -> FulfilmentConfiguration:
    base_currency = deal.base_currency.upper()
    overrides = configuration.fx_rates_used or {}

    quantity = _d(configuration.target_quantity)
    if quantity <= 0 and configuration.shipment_lots:
        quantity = sum(_d(lot.quantity) for lot in configuration.shipment_lots)

    sales_price = _d(configuration.sales_price_per_unit)
    sales_currency = (configuration.sales_currency or base_currency).upper()
    revenue_base, rates = convert_amount(
        sales_price * quantity, sales_currency, base_currency, overrides
    )

    product_cost = Decimal("0")
    for lot in configuration.shipment_lots:
        lot_cost, rates = convert_amount(
            _d(lot.purchase_price_per_unit) * _d(lot.quantity),
            (lot.currency or base_currency).upper(),
            base_currency,
            rates,
        )
        product_cost += lot_cost

    freight_cost = Decimal("0")
    for leg in configuration.transport_legs:
        leg_cost, rates = convert_amount(
            _d(leg.cost),
            (leg.currency or base_currency).upper(),
            base_currency,
            rates,
        )
        freight_cost += leg_cost

    service_costs: dict[str, Decimal] = {}
    for quote in configuration.service_quotes:
        quote_cost, rates = convert_amount(
            _d(quote.amount),
            (quote.currency or base_currency).upper(),
            base_currency,
            rates,
        )
        service_costs[quote.quote_type] = service_costs.get(quote.quote_type, Decimal("0")) + quote_cost
        if quote.quote_type == ServiceQuoteType.FREIGHT.value:
            freight_cost += quote_cost

    inland_transport = service_costs.get(ServiceQuoteType.OTHER.value, Decimal("0"))
    terminal = service_costs.get(ServiceQuoteType.TERMINAL.value, Decimal("0"))
    storage = service_costs.get(ServiceQuoteType.STORAGE.value, Decimal("0"))
    insurance = service_costs.get(ServiceQuoteType.INSURANCE.value, Decimal("0"))
    inspection = service_costs.get(ServiceQuoteType.INSPECTION.value, Decimal("0"))
    customs = service_costs.get(ServiceQuoteType.CUSTOMS.value, Decimal("0"))
    financing = service_costs.get(ServiceQuoteType.FINANCING.value, Decimal("0"))

    total_cost = (
        product_cost
        + inland_transport
        + freight_cost
        + terminal
        + storage
        + insurance
        + inspection
        + customs
        + financing
    )
    gross_margin = revenue_base - total_cost
    gross_margin_percent = (
        (gross_margin / revenue_base * Decimal("100")).quantize(Decimal("0.0001"))
        if revenue_base > 0
        else Decimal("0")
    )

    req_product = None
    if requirement and requirement.product:
        req_product = requirement.product.normalized_name
    offer_product = configuration.shipment_lots[0].product_name if configuration.shipment_lots else None
    spec_summary = build_spec_summary(req_product, offer_product)

    missing: list[str] = []
    if quantity <= 0:
        missing.append("quantity")
    if sales_price <= 0:
        missing.append("sales_price")
    if product_cost <= 0:
        missing.append("product_cost")
    completeness = Decimal("100") - Decimal(len(missing) * 20)
    if completeness < 0:
        completeness = Decimal("0")

    status = ConfigurationStatus.FEASIBLE.value
    if missing:
        status = ConfigurationStatus.INCOMPLETE.value
    if spec_summary["health_status"] == "MISMATCH":
        status = ConfigurationStatus.REJECTED.value

    configuration.revenue = float(revenue_base)
    configuration.total_cost = float(total_cost)
    configuration.gross_margin = float(gross_margin)
    configuration.gross_margin_percent = float(gross_margin_percent)
    configuration.cost_breakdown = {
        "product_purchase_cost": str(product_cost),
        "inland_transport": str(inland_transport),
        "main_freight": str(freight_cost),
        "port_terminal_handling": str(terminal),
        "storage": str(storage),
        "insurance": str(insurance),
        "inspection": str(inspection),
        "customs_and_duties": str(customs),
        "financing_cost": str(financing),
        "base_currency": base_currency,
    }
    configuration.fx_rates_used = rates
    configuration.spec_match_summary = spec_summary
    configuration.completeness_score = float(completeness)
    configuration.status = status
    configuration.last_calculated_at = datetime.now(timezone.utc)

    snapshot = EconomicsSnapshot(
        configuration_id=configuration.id,
        scenario=EconomicsScenario.CURRENT.value,
        snapshot_data={
            "revenue": str(revenue_base),
            "total_cost": str(total_cost),
            "gross_margin": str(gross_margin),
            "gross_margin_percent": str(gross_margin_percent),
            "cost_breakdown": configuration.cost_breakdown,
            "fx_rates_used": rates,
            "spec_match_summary": spec_summary,
            "status": status,
        },
    )
    db.add(snapshot)
    db.flush()
    return configuration
