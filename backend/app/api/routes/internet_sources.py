from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas_internet_sources import (
    InternetSourceCreate,
    InternetSourceDiscoverRequest,
    InternetSourceDiscoverResponse,
    InternetSourceMatchResponse,
    InternetSourceResponse,
    InternetSourceSearchHitResponse,
    InternetSourceSearchRequest,
    InternetSourceSearchRunResponse,
    InternetSourceUpdate,
    TenderHitPromoteResponse,
)
from app.db.session import get_db
from app.domain.models import User
from app.services.internet_source_catalog import (
    create_internet_source,
    get_internet_source,
    list_internet_sources,
    match_internet_sources,
    update_internet_source,
)
from app.services.product_keyword_localization import expand_product_keywords
from app.services.internet_source_discovery import discover_and_register_sources
from app.services.internet_source_search import (
    get_search_run,
    list_search_hits,
    list_search_runs,
    run_internet_source_search,
)
from app.services.tender_promotion import promote_search_hit_to_opportunity

router = APIRouter(prefix="/internet-sources", tags=["internet-sources"])


def _parse_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [part.strip() for part in value.split(",") if part.strip()]
    return items or None


@router.get("", response_model=list[InternetSourceResponse])
def get_internet_sources(
    product_tag: str | None = Query(default=None),
    region: str | None = Query(default=None),
    access_mode: str | None = Query(default=None),
    source_kind: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sources = list_internet_sources(
        db,
        user=current_user,
        product_tag=product_tag,
        region=region,
        access_mode=access_mode,
        source_kind=source_kind,
        active_only=active_only,
        include_inactive=include_inactive,
    )
    return [InternetSourceResponse.from_model(source) for source in sources]


@router.get("/match", response_model=InternetSourceMatchResponse)
def match_internet_sources_route(
    product_keywords: str | None = Query(default=None, description="Comma-separated product keywords"),
    regions: str | None = Query(default=None, description="Comma-separated regions"),
    access_mode: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    auto_discover: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    keywords = _parse_csv(product_keywords) or []
    region_list = _parse_csv(regions) or []
    sources_discovered = 0
    discovery_notes: str | None = None
    if keywords and auto_discover:
        discovery = discover_and_register_sources(
            db,
            user=current_user,
            product_keywords=keywords,
            regions=region_list,
            access_mode=access_mode,
        )
        sources_discovered = len(discovery.added_sources)
        discovery_notes = discovery.ai_notes

    expanded_keywords = expand_product_keywords(db, keywords) if keywords else []
    sources = list_internet_sources(
        db,
        user=current_user,
        active_only=not include_inactive,
        include_inactive=include_inactive,
    )
    matched = match_internet_sources(
        sources,
        product_keywords=expanded_keywords or None,
        regions=region_list or None,
        access_mode=access_mode,
        include_inactive=include_inactive,
    )
    return InternetSourceMatchResponse(
        sources=[InternetSourceResponse.from_model(source) for source in matched],
        matched_count=len(matched),
        product_keywords=keywords,
        regions=region_list,
        sources_discovered=sources_discovered,
        discovery_notes=discovery_notes,
    )


@router.post("/discover", response_model=InternetSourceDiscoverResponse)
def discover_internet_sources(
    payload: InternetSourceDiscoverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    discovery = discover_and_register_sources(
        db,
        user=current_user,
        product_keywords=payload.product_keywords,
        regions=payload.regions,
        access_mode=payload.access_mode,
        force=payload.force,
    )
    return InternetSourceDiscoverResponse(
        added_sources=[InternetSourceResponse.from_model(source) for source in discovery.added_sources],
        added_count=len(discovery.added_sources),
        skipped_existing=discovery.skipped_existing,
        skipped_discovery=discovery.skipped_discovery,
        discovery_notes=discovery.ai_notes,
        product_keywords=payload.product_keywords,
        regions=payload.regions,
    )


@router.post("/search", response_model=InternetSourceSearchRunResponse)
def post_internet_source_search(
    payload: InternetSourceSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run, sources_discovered = run_internet_source_search(
        db,
        user=current_user,
        product_keywords=payload.product_keywords,
        regions=payload.regions,
        search_date=payload.search_date,
        access_mode=payload.access_mode,
        max_sources=payload.max_sources,
        verify_real=payload.verify_real,
        auto_discover_sources=payload.auto_discover_sources,
    )
    response = InternetSourceSearchRunResponse.model_validate(run)
    return response.model_copy(update={"sources_discovered": sources_discovered})


@router.get("/search/runs", response_model=list[InternetSourceSearchRunResponse])
def get_internet_source_search_runs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_search_runs(db, user=current_user)


@router.get("/search/runs/{run_id}", response_model=InternetSourceSearchRunResponse)
def get_internet_source_search_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_search_run(db, user=current_user, run_id=run_id)


@router.get("/search/runs/{run_id}/hits", response_model=list[InternetSourceSearchHitResponse])
def get_internet_source_search_hits(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    hits = list_search_hits(db, user=current_user, run_id=run_id)
    id_to_name: dict[UUID, str] = {}
    for hit in hits:
        if hit.internet_source_id not in id_to_name:
            source = get_internet_source(db, user=current_user, source_id=hit.internet_source_id)
            id_to_name[hit.internet_source_id] = source.name
    return [
        InternetSourceSearchHitResponse.from_model(hit, source_name=id_to_name.get(hit.internet_source_id))
        for hit in hits
    ]


@router.post("/search/hits/{hit_id}/promote", response_model=TenderHitPromoteResponse)
def promote_search_hit(
    hit_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    hit, opportunity = promote_search_hit_to_opportunity(db, user=current_user, hit_id=hit_id)
    source = get_internet_source(db, user=current_user, source_id=hit.internet_source_id)
    feasibility = (hit.extracted_fields or {}).get("feasibility") or {}
    economics = opportunity.indicative_economics or {}
    margin = economics.get("gross_margin")
    margin_pct = economics.get("gross_margin_percent")
    currency = economics.get("margin_currency") or economics.get("costs_currency")
    economics_preview = None
    if margin is not None:
        economics_preview = f"Маржа {margin} {currency or ''}"
        if margin_pct is not None:
            economics_preview += f" ({margin_pct}%)"
    return TenderHitPromoteResponse(
        hit=InternetSourceSearchHitResponse.from_model(hit, source_name=source.name),
        opportunity_id=opportunity.id,
        opportunity_title=opportunity.title,
        feasibility_summary=str(feasibility.get("summary") or opportunity.notes or ""),
        supplier_hint=feasibility.get("supplier_hint"),
        economics_preview=economics_preview,
    )


@router.post("", response_model=InternetSourceResponse, status_code=status.HTTP_201_CREATED)
def post_internet_source(
    payload: InternetSourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = create_internet_source(db, user=current_user, data=payload.model_dump())
    return InternetSourceResponse.from_model(source)


@router.get("/{source_id}", response_model=InternetSourceResponse)
def get_internet_source_route(
    source_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = get_internet_source(db, user=current_user, source_id=source_id)
    return InternetSourceResponse.from_model(source)


@router.patch("/{source_id}", response_model=InternetSourceResponse)
def patch_internet_source(
    source_id: UUID,
    payload: InternetSourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = get_internet_source(db, user=current_user, source_id=source_id)
    updated = update_internet_source(
        db,
        user=current_user,
        source=source,
        data=payload.model_dump(exclude_unset=True),
    )
    return InternetSourceResponse.from_model(updated)
