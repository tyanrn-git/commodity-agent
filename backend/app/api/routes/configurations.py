from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas_configuration import (
    ConfigurationCreate,
    ConfigurationResponse,
    ServiceQuoteCreate,
    ServiceQuoteResponse,
    TransportLegCreate,
    TransportLegResponse,
)
from app.db.session import get_db
from app.domain.models import Deal, User
from app.services.configuration import (
    add_service_quote,
    add_transport_leg,
    confirm_configuration_scenario,
    create_configuration_from_supply_offer,
    get_configuration,
    list_configurations,
    recalculate_configuration,
)

router = APIRouter(tags=["configurations"])


@router.get("/deals/{deal_id}/configurations", response_model=list[ConfigurationResponse])
def get_deal_configurations(
    deal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_configurations(db, user=current_user, deal_id=deal_id)


@router.post(
    "/deals/{deal_id}/configurations",
    response_model=ConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_deal_configuration(
    deal_id: UUID,
    payload: ConfigurationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deal = db.get(Deal, deal_id)
    if deal is None or deal.owner_id != current_user.id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Deal not found")
    return create_configuration_from_supply_offer(
        db,
        user=current_user,
        deal=deal,
        supply_offer_id=payload.supply_offer_id,
        name=payload.name,
        sales_price_per_unit=payload.sales_price_per_unit,
        sales_currency=payload.sales_currency,
    )


@router.get("/configurations/{configuration_id}", response_model=ConfigurationResponse)
def get_configuration_route(
    configuration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_configuration(db, user=current_user, configuration_id=configuration_id)


@router.post("/configurations/{configuration_id}/recalculate", response_model=ConfigurationResponse)
def recalculate_configuration_route(
    configuration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = get_configuration(db, user=current_user, configuration_id=configuration_id)
    return recalculate_configuration(db, user=current_user, configuration=config)


@router.post("/configurations/{configuration_id}/confirm", response_model=ConfigurationResponse)
def confirm_configuration_route(
    configuration_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = get_configuration(db, user=current_user, configuration_id=configuration_id)
    return confirm_configuration_scenario(db, user=current_user, configuration=config)


@router.post(
    "/configurations/{configuration_id}/transport-legs",
    response_model=TransportLegResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_transport_leg_route(
    configuration_id: UUID,
    payload: TransportLegCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = get_configuration(db, user=current_user, configuration_id=configuration_id)
    return add_transport_leg(db, user=current_user, configuration=config, data=payload.model_dump())


@router.post(
    "/configurations/{configuration_id}/service-quotes",
    response_model=ServiceQuoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_service_quote_route(
    configuration_id: UUID,
    payload: ServiceQuoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = get_configuration(db, user=current_user, configuration_id=configuration_id)
    return add_service_quote(db, user=current_user, configuration=config, data=payload.model_dump())
