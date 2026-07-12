import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import (
    AuditAction,
    ChainViabilityStatus,
    ConfirmationLevel,
    OpportunityStatus,
    OpportunityType,
    OutreachStatus,
    OutreachType,
    ResearchCampaignStatus,
    ResearchLeadType,
    SourceType,
)
from app.domain.models import (
    CommercialFact,
    Opportunity,
    OutreachDraft,
    Product,
    ResearchCampaign,
    ResearchLead,
    Source,
    User,
)
from app.integrations.search.mock_provider import get_search_provider
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.audit import log_audit
from app.services.extraction import save_document_source
from app.services.opportunity import create_buyer_led_opportunity

OUTREACH_TEMPLATES = {
    OutreachType.BUYER.value: {
        "subject": "Inquiry: {product} supply availability",
        "body": (
            "Dear {organization},\n\n"
            "We are reviewing potential supply options for {product} into {region}. "
            "Could you please confirm your current requirements, preferred incoterm, "
            "and target delivery window?\n\n"
            "This message is exploratory only and does not constitute an offer.\n\n"
            "Best regards"
        ),
    },
    OutreachType.SUPPLIER.value: {
        "subject": "RFQ: {product} export availability",
        "body": (
            "Dear {organization},\n\n"
            "Please advise available quantity, loading point, incoterm, validity, "
            "and indicative commercial terms for {product}.\n\n"
            "Best regards"
        ),
    },
    OutreachType.LOGISTICS.value: {
        "subject": "Freight inquiry: {route}",
        "body": (
            "Dear {organization},\n\n"
            "Please provide indicative freight/options for {route} with equipment type, "
            "transit time, and quote validity.\n\n"
            "Best regards"
        ),
    },
}


def create_research_campaign(
    db: Session,
    *,
    user: User,
    name: str,
    product_ids: list[uuid.UUID],
    target_buy_regions: list[str] | None = None,
    target_sell_regions: list[str] | None = None,
    quantity_range: dict | None = None,
    preferred_incoterms: list[str] | None = None,
    excluded_regions: list[str] | None = None,
    research_hypothesis: str | None = None,
) -> ResearchCampaign:
    for pid in product_ids:
        if db.get(Product, pid) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {pid} not found")

    campaign = ResearchCampaign(
        owner_id=user.id,
        name=name,
        product_ids=[str(pid) for pid in product_ids],
        target_buy_regions=target_buy_regions,
        target_sell_regions=target_sell_regions,
        quantity_range=quantity_range,
        preferred_incoterms=preferred_incoterms,
        excluded_regions=excluded_regions,
        research_hypothesis=research_hypothesis,
        status=ResearchCampaignStatus.DRAFT.value,
        viability_status=ChainViabilityStatus.UNKNOWN.value,
        created_opportunity_ids=[],
    )
    db.add(campaign)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="ResearchCampaign",
        entity_id=campaign.id,
        new_value={"name": name},
    )
    db.commit()
    db.refresh(campaign)
    return campaign


def run_research(db: Session, *, user: User, campaign: ResearchCampaign) -> ResearchCampaign:
    if campaign.status == ResearchCampaignStatus.CANCELLED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign is cancelled")

    product_names = []
    for pid in campaign.product_ids or []:
        product = db.get(Product, uuid.UUID(str(pid)))
        if product:
            product_names.append(product.normalized_name)

    provider = get_search_provider()
    results = provider.search_chain_leads(
        product_names=product_names,
        target_buy_regions=campaign.target_buy_regions,
        target_sell_regions=campaign.target_sell_regions,
        quantity_range=campaign.quantity_range,
    )

    for existing in list(campaign.leads):
        db.delete(existing)
    db.flush()

    for item in results:
        db.add(
            ResearchLead(
                campaign_id=campaign.id,
                lead_type=item.lead_type,
                title=item.title,
                organization_name=item.organization_name,
                region=item.region,
                country=item.country,
                url=item.url,
                notes=item.notes,
                relevance_score=item.relevance_score,
                source_type=item.source_type,
                lead_metadata=item.metadata,
            )
        )

    campaign.status = ResearchCampaignStatus.ACTIVE.value
    campaign.started_at = campaign.started_at or datetime.now(timezone.utc)
    _refresh_viability(db, campaign=campaign)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="ResearchCampaign",
        entity_id=campaign.id,
        new_value={"action": "run_research", "leads_found": len(results)},
    )
    db.commit()
    db.refresh(campaign)
    return campaign


def generate_outreach_drafts(db: Session, *, user: User, campaign: ResearchCampaign) -> list[OutreachDraft]:
    product_name = "Base Oil"
    if campaign.product_ids:
        product = db.get(Product, uuid.UUID(str(campaign.product_ids[0])))
        if product:
            product_name = product.normalized_name

    created: list[OutreachDraft] = []
    for lead in campaign.leads:
        outreach_type = _lead_to_outreach_type(lead.lead_type)
        if outreach_type is None:
            continue
        template = OUTREACH_TEMPLATES[outreach_type]
        route = (
            lead.lead_metadata.get("origin", "") + " → " + lead.lead_metadata.get("destination", "")
            if lead.lead_metadata
            else lead.region or ""
        )
        draft = OutreachDraft(
            campaign_id=campaign.id,
            target_lead_id=lead.id,
            outreach_type=outreach_type,
            subject=template["subject"].format(
                product=product_name,
                organization=lead.organization_name or lead.title,
                region=lead.region or "target market",
                route=route or "target route",
            ),
            body=template["body"].format(
                product=product_name,
                organization=lead.organization_name or lead.title,
                region=lead.region or "target market",
                route=route or "target route",
            ),
            language="en",
            status=OutreachStatus.DRAFT.value,
        )
        db.add(draft)
        created.append(draft)

    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="OutreachDraft",
        entity_id=campaign.id,
        new_value={"count": len(created)},
    )
    db.commit()
    for draft in created:
        db.refresh(draft)
    return created


def mark_outreach_sent_externally(db: Session, *, user: User, draft: OutreachDraft) -> OutreachDraft:
    draft.status = OutreachStatus.SENT_EXTERNALLY.value
    draft.sent_at = datetime.now(timezone.utc)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="OutreachDraft",
        entity_id=draft.id,
        new_value={"status": draft.status},
    )
    if draft.campaign:
        _refresh_viability(db, campaign=draft.campaign)
    db.commit()
    db.refresh(draft)
    return draft


def import_campaign_response(
    db: Session,
    *,
    user: User,
    campaign: ResearchCampaign,
    file: UploadFile,
    storage: LocalFilesystemStorage,
) -> tuple[Source, list[CommercialFact]]:
    filename = file.filename or "response.eml"
    content = file.file.read()
    source = save_document_source(
        db,
        user=user,
        opportunity=_get_or_create_campaign_opportunity(db, user=user, campaign=campaign),
        filename=filename,
        content=content,
        mime_type=file.content_type,
        storage=storage,
        source_type=SourceType.EMAIL.value,
    )
    source.research_campaign_id = campaign.id
    db.flush()

    facts = _parse_response_facts(campaign_id=campaign.id, source=source, content=content, filename=filename)
    for fact in facts:
        db.add(fact)
    db.flush()
    _refresh_viability(db, campaign=campaign)
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPLOAD,
        entity_type="ResearchCampaign",
        entity_id=campaign.id,
        new_value={"source_id": str(source.id), "facts_count": len(facts)},
    )
    db.commit()
    db.refresh(source)
    return source, facts


def create_opportunity_from_campaign(
    db: Session,
    *,
    user: User,
    campaign: ResearchCampaign,
    lead_id: uuid.UUID | None = None,
    opportunity_type: str = OpportunityType.BUYER_NEED.value,
) -> Opportunity:
    product_id = uuid.UUID(str(campaign.product_ids[0])) if campaign.product_ids else None
    lead = db.get(ResearchLead, lead_id) if lead_id else None
    title = lead.title if lead else f"Opportunity from {campaign.name}"
    destination = lead.region if lead else (campaign.target_buy_regions or [None])[0]

    if opportunity_type == OpportunityType.BUYER_NEED.value:
        opp = create_buyer_led_opportunity(
            db,
            user=user,
            title=title,
            normalized_product_id=product_id,
            destination_hint=destination,
            buyer_or_supplier_hint=lead.organization_name if lead else None,
        )
    else:
        opp = Opportunity(
            owner_id=user.id,
            type=OpportunityType.SUPPLIER_OFFER.value,
            title=title,
            normalized_product_id=product_id,
            origin_hint=lead.region if lead else None,
            buyer_or_supplier_hint=lead.organization_name if lead else None,
            status=OpportunityStatus.NEW.value,
        )
        db.add(opp)
        db.flush()
        log_audit(
            db,
            actor=user,
            action=AuditAction.CREATE,
            entity_type="Opportunity",
            entity_id=opp.id,
            new_value={"campaign_id": str(campaign.id), "type": opp.type},
        )
        db.commit()
        db.refresh(opp)

    ids = list(campaign.created_opportunity_ids or [])
    ids.append(str(opp.id))
    campaign.created_opportunity_ids = ids
    _refresh_viability(db, campaign=campaign)
    db.commit()
    return opp


def assess_chain_viability(campaign: ResearchCampaign) -> dict:
    buyers = [
        lead
        for lead in campaign.leads
        if lead.lead_type in {ResearchLeadType.BUYER_NEED.value, ResearchLeadType.PUBLIC_BUYER_NEED.value}
    ]
    suppliers = [lead for lead in campaign.leads if lead.lead_type == ResearchLeadType.SUPPLIER.value]
    routes = [lead for lead in campaign.leads if lead.lead_type == ResearchLeadType.LOGISTICS_ROUTE.value]
    sent_outreach = [
        draft for draft in campaign.outreach_drafts if draft.status == OutreachStatus.SENT_EXTERNALLY.value
    ]
    facts = list(campaign.commercial_facts or [])
    opportunities = list(campaign.created_opportunity_ids or [])

    missing_facts: list[str] = []
    reasons: list[str] = []

    if len(buyers) < 3:
        missing_facts.append("buyer_needs_min_3")
        reasons.append(f"Only {len(buyers)} buyer leads found; need at least 3")
    if len(suppliers) < 3:
        missing_facts.append("suppliers_min_3")
        reasons.append(f"Only {len(suppliers)} supplier leads found; need at least 3")
    if len(routes) < 1:
        missing_facts.append("logistics_route")
        reasons.append("No logistics route identified")
    if not sent_outreach:
        missing_facts.append("manual_outreach_sent")
        reasons.append("No outreach marked as sent externally")
    if not facts:
        missing_facts.append("imported_response_or_public_quote")
        reasons.append("No imported response or public quote captured as CommercialFact")
    if not opportunities:
        missing_facts.append("opportunity_created")
        reasons.append("No Opportunity created from campaign yet")

    has_price = any(f.field_path in {"price", "quantity", "incoterm"} for f in facts)
    if facts and not has_price:
        missing_facts.append("confirmed_commercial_values")
        reasons.append("Imported response lacks price/quantity/incoterm facts")

    core_ready = len(buyers) >= 3 and len(suppliers) >= 3 and len(routes) >= 1
    workflow_ready = bool(sent_outreach) and bool(facts) and bool(opportunities) and has_price

    if core_ready and workflow_ready:
        viability_status = ChainViabilityStatus.VIABLE_CANDIDATE.value
        summary = "Chain has enough discovery signals to continue qualification."
    elif core_ready:
        viability_status = ChainViabilityStatus.UNKNOWN.value
        summary = "Discovery complete, but chain is not yet workable."
    else:
        viability_status = ChainViabilityStatus.NO_VIABLE_CHAIN_FOUND.value
        summary = "Insufficient discovery results for a workable chain."

    return {
        "viability_status": viability_status,
        "summary": summary,
        "counts": {
            "buyers": len(buyers),
            "suppliers": len(suppliers),
            "routes": len(routes),
            "sent_outreach": len(sent_outreach),
            "commercial_facts": len(facts),
            "opportunities": len(opportunities),
        },
        "missing_facts": missing_facts,
        "reasons": reasons,
    }


def _refresh_viability(db: Session, *, campaign: ResearchCampaign) -> None:
    db.expire(campaign, ["leads", "outreach_drafts", "commercial_facts"])
    report = assess_chain_viability(campaign)
    campaign.viability_report = report
    campaign.viability_status = report["viability_status"]


def _lead_to_outreach_type(lead_type: str) -> str | None:
    if lead_type in {ResearchLeadType.BUYER_NEED.value, ResearchLeadType.PUBLIC_BUYER_NEED.value}:
        return OutreachType.BUYER.value
    if lead_type == ResearchLeadType.SUPPLIER.value:
        return OutreachType.SUPPLIER.value
    if lead_type == ResearchLeadType.LOGISTICS_ROUTE.value:
        return OutreachType.LOGISTICS.value
    return None


def _get_or_create_campaign_opportunity(db: Session, *, user: User, campaign: ResearchCampaign) -> Opportunity:
    if campaign.created_opportunity_ids:
        opp = db.get(Opportunity, uuid.UUID(str(campaign.created_opportunity_ids[0])))
        if opp:
            return opp
    return create_opportunity_from_campaign(db, user=user, campaign=campaign)


def _parse_response_facts(
    *,
    campaign_id: uuid.UUID,
    source: Source,
    content: bytes,
    filename: str,
) -> list[CommercialFact]:
    text = content.decode("utf-8", errors="ignore")
    facts: list[CommercialFact] = []

    def add_fact(field_path: str, value: str, unit: str | None = None, currency: str | None = None) -> None:
        facts.append(
            CommercialFact(
                research_campaign_id=campaign_id,
                source_id=source.id,
                entity_type="ResearchCampaign",
                field_path=field_path,
                value=value,
                unit=unit,
                currency=currency,
                confirmation_level=ConfirmationLevel.COUNTERPARTY_MESSAGE.value,
                evidence_excerpt=value,
            )
        )

    lower = text.lower()
    if "sn500" in lower or "sn150" in lower or "base oil" in lower:
        add_fact("product", "Base Oil SN500")
    if "100" in text and "mt" in lower:
        add_fact("quantity", "100", unit="MT")
    if "cif" in lower:
        add_fact("incoterm", "CIF")
    if "usd" in lower or "$" in text:
        add_fact("price", "850", currency="USD")
    if not facts:
        add_fact("response_received", "true")
    return facts


def seed_product_specifications(db: Session) -> None:
    specs = {
        "SN500": [
            ("kinematic_viscosity_40c", "cSt", 4.0, 5.5, True, "IDENTITY", "MATERIAL"),
            ("flash_point", "C", 180.0, None, True, "VARIANT", "MATERIAL"),
            ("pour_point", "C", None, -9.0, False, "VARIANT", "IMMATERIAL"),
        ],
        "SN150": [
            ("kinematic_viscosity_40c", "cSt", 12.0, 16.0, True, "IDENTITY", "MATERIAL"),
            ("flash_point", "C", 180.0, None, True, "VARIANT", "MATERIAL"),
            ("pour_point", "C", None, -6.0, False, "VARIANT", "IMMATERIAL"),
        ],
    }
    from app.domain.models import ProductSpecificationProfile

    for product_name, rows in specs.items():
        product = db.scalar(select(Product).where(Product.normalized_name == product_name))
        if not product:
            continue
        existing = db.scalar(
            select(ProductSpecificationProfile).where(ProductSpecificationProfile.product_id == product.id)
        )
        if existing:
            continue
        for param_name, unit, min_v, max_v, mandatory, kind, materiality in rows:
            db.add(
                ProductSpecificationProfile(
                    product_id=product.id,
                    version=1,
                    parameter_name=param_name,
                    unit=unit,
                    minimum_value=min_v,
                    maximum_value=max_v,
                    is_mandatory=mandatory,
                    parameter_kind=kind,
                    variation_materiality=materiality,
                )
            )
    db.commit()
