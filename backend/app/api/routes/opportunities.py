from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.api.schemas import (
    DealResponse,
    OpportunityBoardResponse,
    OpportunityCreate,
    OpportunityDisplayStatus,
    OpportunityResponse,
    OpportunityStatusEventResponse,
    OpportunityStatusTransition,
    OpportunityUpdate,
    RequirementCreate,
    RequirementResponse,
    RequirementUpdate,
    SourceResponse,
)
from app.db.session import get_db
from app.domain.enums import AuditAction
from app.domain.models import Deal, FulfilmentConfiguration, Opportunity, Product, Requirement, User
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.audit import log_audit
from app.services.extraction import upload_document_source
from app.services.opportunity import (
    convert_opportunity_to_deal,
    create_buyer_led_opportunity,
    create_requirement,
    update_opportunity,
)
from app.services.opportunity_board import list_opportunity_board
from app.services.opportunity_status import (
    list_status_history,
    resolve_display_status,
    transition_opportunity_status,
)

router = APIRouter(tags=["opportunities"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}



@router.get("/opportunities", response_model=list[OpportunityResponse])
def list_opportunities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Opportunity]:
    stmt = (
        select(Opportunity)
        .where(Opportunity.owner_id == current_user.id)
        .order_by(Opportunity.created_at.desc())
    )
    return list(db.scalars(stmt))


@router.get("/opportunities/board", response_model=OpportunityBoardResponse)
def get_opportunities_board(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_opportunity_board(db, user=current_user)


@router.post("/opportunities", response_model=OpportunityResponse, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    payload: OpportunityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Opportunity:
    return create_buyer_led_opportunity(
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
        quote_deadline=payload.quote_deadline,
        delivery_deadline=payload.delivery_deadline,
        notes=payload.notes,
    )


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityResponse)
def get_opportunity(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Opportunity:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return opportunity


@router.patch("/opportunities/{opportunity_id}", response_model=OpportunityResponse)
def patch_opportunity(
    opportunity_id: UUID,
    payload: OpportunityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Opportunity:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    data = payload.model_dump(exclude_unset=True)
    return update_opportunity(db, user=current_user, opportunity=opportunity, data=data)


@router.post("/opportunities/{opportunity_id}/status", response_model=OpportunityResponse)
def change_opportunity_status(
    opportunity_id: UUID,
    payload: OpportunityStatusTransition,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Opportunity:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    transition_opportunity_status(
        db,
        opportunity=opportunity,
        new_status=payload.status,
        actor=current_user,
        note=payload.note,
    )
    db.commit()
    db.refresh(opportunity)
    return opportunity


@router.get(
    "/opportunities/{opportunity_id}/status-history",
    response_model=list[OpportunityStatusEventResponse],
)
def get_opportunity_status_history(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return list_status_history(db, opportunity_id=opportunity_id)


@router.get("/opportunities/{opportunity_id}/display-status", response_model=OpportunityDisplayStatus)
def get_opportunity_display_status(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    deal = db.scalar(select(Deal).where(Deal.origin_opportunity_id == opportunity.id))
    config = None
    if deal:
        config = db.scalar(
            select(FulfilmentConfiguration)
            .where(
                FulfilmentConfiguration.deal_id == deal.id,
                FulfilmentConfiguration.status.in_(("SELECTED", "FEASIBLE")),
            )
            .order_by(FulfilmentConfiguration.updated_at.desc())
        )
    return resolve_display_status(opportunity, deal=deal, config=config)


@router.post(
    "/opportunities/{opportunity_id}/sources",
    response_model=SourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_source(
    opportunity_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SourceResponse:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    storage = LocalFilesystemStorage()
    return upload_document_source(db, user=current_user, opportunity=opportunity, file=file, storage=storage)


@router.get("/opportunities/{opportunity_id}/sources", response_model=list[SourceResponse])
def list_sources(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return opportunity.sources


@router.post("/opportunities/{opportunity_id}/convert", response_model=DealResponse)
def convert_opportunity(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Deal:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return convert_opportunity_to_deal(db, user=current_user, opportunity=opportunity)


@router.get("/deals", response_model=list[DealResponse])
def list_deals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Deal]:
    stmt = select(Deal).where(Deal.owner_id == current_user.id).order_by(Deal.created_at.desc())
    return list(db.scalars(stmt))


@router.get("/deals/{deal_id}", response_model=DealResponse)
def get_deal(
    deal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Deal:
    deal = db.get(Deal, deal_id)
    if deal is None or deal.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    return deal


@router.post("/deals/{deal_id}/requirements", response_model=RequirementResponse, status_code=status.HTTP_201_CREATED)
def create_deal_requirement(
    deal_id: UUID,
    payload: RequirementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Requirement:
    deal = db.get(Deal, deal_id)
    if deal is None or deal.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    evidence = [item.model_dump() for item in payload.evidence]
    return create_requirement(
        db,
        user=current_user,
        deal=deal,
        product_id=payload.product_id,
        quantity_min=payload.quantity_min,
        quantity_max=payload.quantity_max,
        quantity_unit=payload.quantity_unit,
        destination=payload.destination,
        requested_incoterm=payload.requested_incoterm,
        packaging=payload.packaging,
        commercial_deadline=payload.commercial_deadline,
        user_confirmed=payload.user_confirmed,
        evidence=evidence,
    )


@router.get("/deals/{deal_id}/requirements", response_model=list[RequirementResponse])
def list_requirements(
    deal_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Requirement]:
    deal = db.get(Deal, deal_id)
    if deal is None or deal.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
    stmt = (
        select(Requirement)
        .where(Requirement.deal_id == deal_id)
        .options(joinedload(Requirement.evidence_items))
        .order_by(Requirement.created_at.desc())
    )
    return list(db.scalars(stmt).unique())


@router.patch("/requirements/{requirement_id}", response_model=RequirementResponse)
def patch_requirement(
    requirement_id: UUID,
    payload: RequirementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Requirement:
    requirement = db.scalar(
        select(Requirement)
        .where(Requirement.id == requirement_id)
        .options(joinedload(Requirement.evidence_items), joinedload(Requirement.deal))
    )
    if requirement is None or requirement.deal.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    old_value = {
        "quantity_min": str(requirement.quantity_min) if requirement.quantity_min else None,
        "user_confirmed": requirement.user_confirmed,
    }
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(requirement, field, value)
    log_audit(
        db,
        actor=current_user,
        action=AuditAction.UPDATE,
        entity_type="Requirement",
        entity_id=requirement.id,
        old_value=old_value,
        new_value=data,
    )
    db.commit()
    db.refresh(requirement)
    return requirement
