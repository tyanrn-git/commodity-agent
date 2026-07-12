from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas_intelligence import (
    CounterpartyCapabilityResponse,
    CounterpartyEnrichmentRequest,
    CounterpartyEnrichmentResponse,
    ContactHintResponse,
    OpportunitySpecValueResponse,
    ProposedProductResponse,
    ProductResolutionRequest,
    ProductResolutionResponse,
)
from app.api.schemas_products import SpecParameterCreate
from app.db.session import get_db
from app.domain.models import Opportunity, OpportunitySpecValue, User
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.counterparty import get_counterparty
from app.services.counterparty_enrichment import (
    confirm_capability,
    enrich_counterparty_profile,
    list_counterparty_capabilities,
)
from app.services.product_resolution import (
    confirm_spec_value,
    list_opportunity_spec_values,
    resolve_opportunity_product,
)

router = APIRouter(tags=["intelligence"])


@router.post(
    "/opportunities/{opportunity_id}/resolve-product",
    response_model=ProductResolutionResponse,
)
def resolve_product(
    opportunity_id: UUID,
    payload: ProductResolutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    storage = LocalFilesystemStorage()
    result = resolve_opportunity_product(
        db,
        user=current_user,
        opportunity=opportunity,
        rough_product_name=payload.rough_product_name,
        source_text=payload.source_text,
        source_id=payload.source_id,
        storage=storage,
        create_if_missing=payload.create_if_missing,
    )
    output = result["resolution"]
    usage = result["ai_usage"]
    matched = result["matched"]
    product_created = result["product_created"]
    product_name = None
    if matched and opportunity.normalized_product_id:
        product_name = opportunity.product.normalized_name if opportunity.product else None
        if product_name is None:
            from app.domain.models import Product

            product = db.get(Product, opportunity.normalized_product_id)
            product_name = product.normalized_name if product else None

    proposed = None
    if output.proposed_new_product and not product_created:
        proposal = output.proposed_new_product
        proposed = ProposedProductResponse(
            normalized_name=proposal.normalized_name,
            category=proposal.category,
            aliases=proposal.aliases,
            typical_units=proposal.typical_units,
            parameters=[
                SpecParameterCreate(
                    parameter_name=item.parameter_name,
                    unit=item.unit,
                    is_mandatory=item.is_mandatory,
                    minimum_value=item.value_min,
                    maximum_value=item.value_max,
                )
                for item in proposal.parameters
            ],
            reasoning=proposal.reasoning,
        )

    return ProductResolutionResponse(
        opportunity_id=opportunity.id,
        normalized_product_id=opportunity.normalized_product_id if matched else None,
        normalized_product_name=product_name,
        rough_product_name=opportunity.raw_product_name or payload.rough_product_name,
        matched=matched,
        product_created=product_created,
        proposed_new_product=proposed,
        catalog_products=result["catalog_products"],
        confidence=float(output.confidence),
        reasoning=output.reasoning,
        missing_mandatory=output.missing_mandatory,
        spec_values=result["spec_values"],
        ai_model=usage.model,
        ai_cost_usd=str(usage.cost_usd),
    )


@router.get(
    "/opportunities/{opportunity_id}/spec-values",
    response_model=list[OpportunitySpecValueResponse],
)
def get_spec_values(
    opportunity_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None or opportunity.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return list_opportunity_spec_values(db, opportunity=opportunity)


@router.post(
    "/opportunity-spec-values/{spec_value_id}/confirm",
    response_model=OpportunitySpecValueResponse,
)
def confirm_spec_value_route(
    spec_value_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    spec_value = db.get(OpportunitySpecValue, spec_value_id)
    if spec_value is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spec value not found")
    opportunity = db.get(Opportunity, spec_value.opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spec value not found")
    return confirm_spec_value(db, user=current_user, spec_value=spec_value, opportunity=opportunity)


@router.get(
    "/counterparties/{counterparty_id}/capabilities",
    response_model=list[CounterpartyCapabilityResponse],
)
def get_capabilities(
    counterparty_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_counterparty(db, user=current_user, counterparty_id=counterparty_id)
    return list_counterparty_capabilities(db, counterparty_id=counterparty_id)


@router.post(
    "/counterparties/{counterparty_id}/enrich",
    response_model=CounterpartyEnrichmentResponse,
)
def enrich_counterparty(
    counterparty_id: UUID,
    payload: CounterpartyEnrichmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    counterparty = get_counterparty(db, user=current_user, counterparty_id=counterparty_id)
    result = enrich_counterparty_profile(
        db,
        user=current_user,
        counterparty=counterparty,
        source_text=payload.source_text,
    )
    output = result["enrichment"]
    usage = result["ai_usage"]
    return CounterpartyEnrichmentResponse(
        summary=output.summary,
        capabilities=result["capabilities"],
        contact_hints=[ContactHintResponse.model_validate(h.model_dump()) for h in output.contact_hints],
        missing_fields=output.missing_fields,
        ai_model=usage.model,
        ai_cost_usd=str(usage.cost_usd),
    )


@router.post(
    "/counterparty-capabilities/{capability_id}/confirm",
    response_model=CounterpartyCapabilityResponse,
)
def confirm_capability_route(
    capability_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return confirm_capability(db, user=current_user, capability_id=capability_id)
