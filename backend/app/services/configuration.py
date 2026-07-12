from datetime import datetime, timezone
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import AllocationStatus, AuditAction, ConfigurationStatus
from app.domain.models import (
    Deal,
    FulfilmentConfiguration,
    Requirement,
    ServiceQuote,
    ShipmentLot,
    SupplyOffer,
    TransportLeg,
    User,
)
from app.services.audit import log_audit
from app.services.economics import calculate_configuration


def mark_configurations_stale(
    db: Session,
    *,
    deal_id: uuid.UUID,
    reason: str,
) -> int:
    configs = db.scalars(
        select(FulfilmentConfiguration).where(
            FulfilmentConfiguration.deal_id == deal_id,
            FulfilmentConfiguration.is_stale.is_(False),
        )
    ).all()
    now = datetime.now(timezone.utc)
    for config in configs:
        config.is_stale = True
        config.stale_since = now
        config.stale_reason = reason
    db.flush()
    return len(configs)


def mark_configurations_stale_for_supply_offer(
    db: Session,
    *,
    supply_offer_id: uuid.UUID,
    reason: str,
) -> int:
    lot_config_ids = db.scalars(
        select(ShipmentLot.configuration_id).where(ShipmentLot.supply_offer_id == supply_offer_id)
    ).all()
    if not lot_config_ids:
        return 0
    now = datetime.now(timezone.utc)
    configs = db.scalars(
        select(FulfilmentConfiguration).where(FulfilmentConfiguration.id.in_(lot_config_ids))
    ).all()
    for config in configs:
        config.is_stale = True
        config.stale_since = now
        config.stale_reason = reason
    db.flush()
    return len(configs)


def _load_configuration(db: Session, configuration_id: uuid.UUID) -> FulfilmentConfiguration | None:
    return db.scalar(
        select(FulfilmentConfiguration)
        .where(FulfilmentConfiguration.id == configuration_id)
        .options(
            joinedload(FulfilmentConfiguration.shipment_lots),
            joinedload(FulfilmentConfiguration.transport_legs),
            joinedload(FulfilmentConfiguration.service_quotes),
            joinedload(FulfilmentConfiguration.economics_snapshots),
        )
    )


def get_configuration(
    db: Session, *, user: User, configuration_id: uuid.UUID
) -> FulfilmentConfiguration:
    config = _load_configuration(db, configuration_id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
    deal = db.get(Deal, config.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")
    return config


def list_configurations(db: Session, *, user: User, deal_id: uuid.UUID) -> list[FulfilmentConfiguration]:
    deal = db.scalar(select(Deal).where(Deal.id == deal_id, Deal.owner_id == user.id))
    if deal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return list(
        db.scalars(
            select(FulfilmentConfiguration)
            .where(FulfilmentConfiguration.deal_id == deal_id)
            .options(
                joinedload(FulfilmentConfiguration.shipment_lots),
                joinedload(FulfilmentConfiguration.transport_legs),
                joinedload(FulfilmentConfiguration.service_quotes),
            )
            .order_by(FulfilmentConfiguration.created_at.desc())
        ).unique()
    )


def create_configuration_from_supply_offer(
    db: Session,
    *,
    user: User,
    deal: Deal,
    supply_offer_id: uuid.UUID,
    name: str,
    sales_price_per_unit: float,
    sales_currency: str | None = None,
) -> FulfilmentConfiguration:
    if deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    offer = db.scalar(
        select(SupplyOffer).where(
            SupplyOffer.id == supply_offer_id,
            SupplyOffer.deal_id == deal.id,
        )
    )
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supply offer not found")

    requirement = db.scalar(
        select(Requirement)
        .where(Requirement.deal_id == deal.id)
        .options(joinedload(Requirement.product))
        .order_by(Requirement.created_at.asc())
        .limit(1)
    )

    config = FulfilmentConfiguration(
        deal_id=deal.id,
        name=name,
        target_quantity=offer.available_quantity,
        target_quantity_unit=offer.quantity_unit,
        destination=requirement.destination if requirement else None,
        sales_price_per_unit=sales_price_per_unit,
        sales_currency=sales_currency or deal.base_currency,
        status=ConfigurationStatus.DRAFT.value,
    )
    db.add(config)
    db.flush()

    lot = ShipmentLot(
        configuration_id=config.id,
        supply_offer_id=offer.id,
        supplier_counterparty_id=offer.supplier_counterparty_id,
        product_name=offer.product_name,
        quantity=offer.available_quantity,
        quantity_unit=offer.quantity_unit,
        purchase_price_per_unit=offer.price,
        currency=offer.currency,
        incoterm=offer.incoterm,
        origin=offer.origin,
        allocation_status=AllocationStatus.PLANNED.value,
    )
    db.add(lot)
    db.flush()

    calculate_configuration(db, configuration=config, deal=deal, requirement=requirement)
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="FulfilmentConfiguration",
        entity_id=config.id,
        new_value={"deal_id": str(deal.id), "supply_offer_id": str(offer.id), "name": name},
    )
    db.commit()
    config = get_configuration(db, user=user, configuration_id=config.id)
    return config


def upsert_transport_leg(
    db: Session,
    *,
    user: User,
    configuration: FulfilmentConfiguration,
    data: dict,
) -> TransportLeg:
    deal = db.get(Deal, configuration.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")

    mode = data.get("mode", "SEA")
    same_mode_legs = [leg for leg in configuration.transport_legs if leg.mode == mode]
    existing = same_mode_legs[0] if same_mode_legs else None
    for duplicate in same_mode_legs[1:]:
        db.delete(duplicate)
    if existing:
        existing.origin = data.get("origin", existing.origin)
        existing.destination = data.get("destination", existing.destination)
        existing.carrier_name = data.get("carrier_name", existing.carrier_name)
        existing.equipment = data.get("equipment", existing.equipment)
        existing.quantity = data.get("quantity", existing.quantity)
        existing.quantity_unit = data.get("quantity_unit", existing.quantity_unit)
        existing.cost = data.get("cost", existing.cost)
        existing.currency = data.get("currency", existing.currency or deal.base_currency)
        existing.risk_transfer_point = data.get("risk_transfer_point", existing.risk_transfer_point)
        existing.leg_incoterm = data.get("leg_incoterm", existing.leg_incoterm)
        leg = existing
    else:
        leg = TransportLeg(
            configuration_id=configuration.id,
            sequence=data.get("sequence", len(configuration.transport_legs) + 1),
            mode=mode,
            origin=data.get("origin"),
            destination=data.get("destination"),
            carrier_name=data.get("carrier_name"),
            equipment=data.get("equipment"),
            quantity=data.get("quantity"),
            quantity_unit=data.get("quantity_unit"),
            cost=data.get("cost"),
            currency=data.get("currency", deal.base_currency),
            risk_transfer_point=data.get("risk_transfer_point"),
            leg_incoterm=data.get("leg_incoterm"),
        )
        db.add(leg)

    configuration.is_stale = False
    configuration.stale_since = None
    configuration.stale_reason = None
    db.flush()

    requirement = db.scalar(
        select(Requirement)
        .where(Requirement.deal_id == deal.id)
        .options(joinedload(Requirement.product))
        .limit(1)
    )
    calculate_configuration(db, configuration=configuration, deal=deal, requirement=requirement)
    db.commit()
    db.refresh(leg)
    return leg


def add_transport_leg(
    db: Session,
    *,
    user: User,
    configuration: FulfilmentConfiguration,
    data: dict,
) -> TransportLeg:
    return upsert_transport_leg(db, user=user, configuration=configuration, data=data)


def add_service_quote(
    db: Session,
    *,
    user: User,
    configuration: FulfilmentConfiguration,
    data: dict,
) -> ServiceQuote:
    return upsert_service_quote(db, user=user, configuration=configuration, data=data)


def upsert_service_quote(
    db: Session,
    *,
    user: User,
    configuration: FulfilmentConfiguration,
    data: dict,
) -> ServiceQuote:
    deal = db.get(Deal, configuration.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")

    quote_type = data["quote_type"]
    same_type = [q for q in configuration.service_quotes if q.quote_type == quote_type]
    existing = same_type[0] if same_type else None
    for duplicate in same_type[1:]:
        db.delete(duplicate)

    if existing:
        existing.provider_name = data.get("provider_name", existing.provider_name)
        existing.description = data.get("description", existing.description)
        existing.amount = data.get("amount", existing.amount)
        existing.currency = data.get("currency", existing.currency or deal.base_currency)
        existing.user_confirmed = data.get("user_confirmed", existing.user_confirmed)
        quote = existing
    else:
        quote = ServiceQuote(
            deal_id=deal.id,
            configuration_id=configuration.id,
            quote_type=quote_type,
            provider_name=data.get("provider_name"),
            description=data.get("description"),
            amount=data.get("amount"),
            currency=data.get("currency", deal.base_currency),
            user_confirmed=data.get("user_confirmed", False),
        )
        db.add(quote)

    configuration.is_stale = False
    configuration.stale_since = None
    configuration.stale_reason = None
    db.flush()

    requirement = db.scalar(
        select(Requirement)
        .where(Requirement.deal_id == deal.id)
        .options(joinedload(Requirement.product))
        .limit(1)
    )
    calculate_configuration(db, configuration=configuration, deal=deal, requirement=requirement)
    db.commit()
    db.refresh(quote)
    return quote


def recalculate_configuration(
    db: Session, *, user: User, configuration: FulfilmentConfiguration
) -> FulfilmentConfiguration:
    deal = db.get(Deal, configuration.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")

    requirement = db.scalar(
        select(Requirement)
        .where(Requirement.deal_id == deal.id)
        .options(joinedload(Requirement.product))
        .limit(1)
    )
    calculate_configuration(db, configuration=configuration, deal=deal, requirement=requirement)
    configuration.is_stale = False
    configuration.stale_since = None
    configuration.stale_reason = None
    db.commit()
    return get_configuration(db, user=user, configuration_id=configuration.id)


def confirm_configuration_scenario(
    db: Session, *, user: User, configuration: FulfilmentConfiguration
) -> FulfilmentConfiguration:
    from app.domain.enums import EconomicsScenario
    from app.domain.models import EconomicsSnapshot

    deal = db.get(Deal, configuration.deal_id)
    if deal is None or deal.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configuration not found")

    if configuration.is_stale:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot confirm stale configuration; recalculate first",
        )

    snapshot = EconomicsSnapshot(
        configuration_id=configuration.id,
        scenario=EconomicsScenario.CONFIRMED.value,
        snapshot_data={
            "revenue": str(configuration.revenue),
            "total_cost": str(configuration.total_cost),
            "gross_margin": str(configuration.gross_margin),
            "gross_margin_percent": str(configuration.gross_margin_percent),
            "cost_breakdown": configuration.cost_breakdown,
            "fx_rates_used": configuration.fx_rates_used,
            "spec_match_summary": configuration.spec_match_summary,
            "status": configuration.status,
        },
    )
    db.add(snapshot)
    configuration.status = ConfigurationStatus.SELECTED.value
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="FulfilmentConfiguration",
        entity_id=configuration.id,
        new_value={"action": "confirm_scenario", "scenario": EconomicsScenario.CONFIRMED.value},
    )
    db.commit()
    return get_configuration(db, user=user, configuration_id=configuration.id)
