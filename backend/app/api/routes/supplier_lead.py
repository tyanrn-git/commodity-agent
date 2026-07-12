from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import (
    SupplierLeadDetailResponse,
    SupplierLeadMatchResponse,
    SupplierLedFromSupplyOfferCreate,
    SupplierLedOpportunityCreate,
    OpportunityResponse,
)
from app.db.session import get_db
from app.domain.models import Opportunity, SupplierLeadMatch, User
from app.services.supplier_lead import (
    build_route_for_match,
    create_supplier_led_from_supply_offer,
    create_supplier_led_opportunity,
    draft_buyer_outreach,
    get_supplier_lead_detail,
    match_buyer_needs,
)

router = APIRouter(tags=["supplier-lead"])


def _get_owned_opportunity(db: Session, user: User, opportunity_id: UUID) -> Opportunity:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return opportunity


def _get_owned_match(db: Session, user: User, match_id: UUID) -> SupplierLeadMatch:
    match = db.get(SupplierLeadMatch, match_id)
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    opportunity = db.get(Opportunity, match.supplier_opportunity_id)
    if opportunity is None or opportunity.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    return match


@router.post(
    "/opportunities/supplier-led",
    response_model=OpportunityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier_led(
    payload: SupplierLedOpportunityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Opportunity:
    return create_supplier_led_opportunity(
        db,
        user=current_user,
        title=payload.title,
        raw_product_name=payload.raw_product_name,
        normalized_product_id=payload.normalized_product_id,
        buyer_or_supplier_hint=payload.buyer_or_supplier_hint,
        quantity_min=payload.quantity_min,
        quantity_max=payload.quantity_max,
        quantity_unit=payload.quantity_unit,
        origin_hint=payload.origin_hint,
        destination_hint=payload.destination_hint,
        deadline=payload.deadline,
        notes=payload.notes,
        unit_price=payload.unit_price,
        currency=payload.currency,
        incoterm=payload.incoterm,
        origin=payload.origin,
    )


@router.post(
    "/supply-offers/{supply_offer_id}/supplier-led",
    response_model=OpportunityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier_led_from_offer(
    supply_offer_id: UUID,
    payload: SupplierLedFromSupplyOfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Opportunity:
    return create_supplier_led_from_supply_offer(
        db,
        user=current_user,
        supply_offer_id=supply_offer_id,
        title=payload.title,
    )


@router.get(
    "/opportunities/{opportunity_id}/supplier-lead",
    response_model=SupplierLeadDetailResponse,
)
def get_supplier_lead(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = _get_owned_opportunity(db, current_user, opportunity_id)
    detail = get_supplier_lead_detail(db, user=current_user, opportunity=opportunity)
    return SupplierLeadDetailResponse(
        context=detail["context"],
        matches=detail["matches"],
        market_comparison=detail["market_comparison"],
    )


@router.post(
    "/opportunities/{opportunity_id}/match-buyer-needs",
    response_model=list[SupplierLeadMatchResponse],
)
def run_match_buyer_needs(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = _get_owned_opportunity(db, current_user, opportunity_id)
    return match_buyer_needs(db, user=current_user, opportunity=opportunity)


@router.post(
    "/supplier-lead-matches/{match_id}/build-route",
    response_model=SupplierLeadMatchResponse,
)
def run_build_route(
    match_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SupplierLeadMatch:
    match = _get_owned_match(db, current_user, match_id)
    return build_route_for_match(db, user=current_user, match=match)


@router.post(
    "/supplier-lead-matches/{match_id}/draft-outreach",
    response_model=SupplierLeadMatchResponse,
)
def run_draft_outreach(
    match_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SupplierLeadMatch:
    match = _get_owned_match(db, current_user, match_id)
    return draft_buyer_outreach(db, user=current_user, match=match)
