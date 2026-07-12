from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.api.schemas import OpportunityResponse, SourceResponse
from app.api.schemas_research import (
    CommercialFactResponse,
    CreateOpportunityFromCampaignRequest,
    OutreachDraftResponse,
    ResearchCampaignCreate,
    ResearchCampaignResponse,
    ResearchLeadResponse,
)
from app.db.session import get_db
from app.domain.models import OutreachDraft, ResearchCampaign, User
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.research import (
    create_opportunity_from_campaign,
    create_research_campaign,
    generate_outreach_drafts,
    import_campaign_response,
    mark_outreach_sent_externally,
    run_research,
)

router = APIRouter(prefix="/research-campaigns", tags=["research"])


def _get_campaign(db: Session, campaign_id: UUID, user: User) -> ResearchCampaign:
    campaign = db.scalar(
        select(ResearchCampaign)
        .where(ResearchCampaign.id == campaign_id, ResearchCampaign.owner_id == user.id)
        .options(
            joinedload(ResearchCampaign.leads),
            joinedload(ResearchCampaign.outreach_drafts),
            joinedload(ResearchCampaign.commercial_facts),
        )
    )
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Research campaign not found")
    return campaign


@router.get("", response_model=list[ResearchCampaignResponse])
def list_campaigns(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(ResearchCampaign)
        .where(ResearchCampaign.owner_id == current_user.id)
        .order_by(ResearchCampaign.created_at.desc())
    )
    return list(db.scalars(stmt))


@router.post("", response_model=ResearchCampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: ResearchCampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_research_campaign(
        db,
        user=current_user,
        name=payload.name,
        product_ids=payload.product_ids,
        target_buy_regions=payload.target_buy_regions,
        target_sell_regions=payload.target_sell_regions,
        quantity_range=payload.quantity_range,
        preferred_incoterms=payload.preferred_incoterms,
        excluded_regions=payload.excluded_regions,
        research_hypothesis=payload.research_hypothesis,
    )


@router.get("/{campaign_id}", response_model=ResearchCampaignResponse)
def get_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_campaign(db, campaign_id, current_user)


@router.post("/{campaign_id}/run", response_model=ResearchCampaignResponse)
def run_campaign_research(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = _get_campaign(db, campaign_id, current_user)
    return run_research(db, user=current_user, campaign=campaign)


@router.get("/{campaign_id}/leads", response_model=list[ResearchLeadResponse])
def list_campaign_leads(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = _get_campaign(db, campaign_id, current_user)
    return campaign.leads


@router.post("/{campaign_id}/outreach", response_model=list[OutreachDraftResponse])
def create_outreach_drafts(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = _get_campaign(db, campaign_id, current_user)
    return generate_outreach_drafts(db, user=current_user, campaign=campaign)


@router.get("/{campaign_id}/outreach", response_model=list[OutreachDraftResponse])
def list_outreach_drafts(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = _get_campaign(db, campaign_id, current_user)
    return campaign.outreach_drafts


@router.post("/outreach/{draft_id}/mark-sent", response_model=OutreachDraftResponse)
def mark_sent(
    draft_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    draft = db.scalar(
        select(OutreachDraft)
        .where(OutreachDraft.id == draft_id)
        .options(joinedload(OutreachDraft.campaign))
    )
    if draft is None or draft.campaign.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach draft not found")
    return mark_outreach_sent_externally(db, user=current_user, draft=draft)


@router.post("/{campaign_id}/import-response")
def import_response(
    campaign_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = _get_campaign(db, campaign_id, current_user)
    storage = LocalFilesystemStorage()
    source, facts = import_campaign_response(
        db, user=current_user, campaign=campaign, file=file, storage=storage
    )
    return {
        "source": SourceResponse.model_validate(source),
        "facts": [CommercialFactResponse.model_validate(f) for f in facts],
    }


@router.get("/{campaign_id}/facts", response_model=list[CommercialFactResponse])
def list_facts(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = _get_campaign(db, campaign_id, current_user)
    return campaign.commercial_facts


@router.get("/{campaign_id}/viability")
def get_viability(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = _get_campaign(db, campaign_id, current_user)
    return campaign.viability_report or {}


@router.post("/{campaign_id}/create-opportunity", response_model=OpportunityResponse)
def create_opportunity(
    campaign_id: UUID,
    payload: CreateOpportunityFromCampaignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = _get_campaign(db, campaign_id, current_user)
    return create_opportunity_from_campaign(
        db,
        user=current_user,
        campaign=campaign,
        lead_id=payload.lead_id,
        opportunity_type=payload.opportunity_type,
    )
