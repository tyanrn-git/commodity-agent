from datetime import datetime, timezone
import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.enums import AuditAction, InternetSourceFetchStrategy, InternetSourceKind, MonitoringAccessMode
from app.domain.models import InternetSource, User
from app.integrations.ted import is_ted_source, is_ted_web_portal
from app.services.audit import log_audit
from app.services.product_keyword_localization import expand_product_keywords, source_keyword_matches


def _normalize_tags(values: list[str] | None) -> list[str]:
    if not values:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


REGION_ALIAS_GROUPS: list[frozenset[str]] = [
    frozenset({"russia", "россия", "ru", "rf", "cis", "eaeu", "eurasia"}),
    frozenset({"eu", "europe", "европа", "european union"}),
    frozenset({"india", "индия", "in"}),
    frozenset({"china", "китай", "cn"}),
    frozenset({"global", "world", "international", "глобальный"}),
    frozenset({"africa", "африка"}),
    frozenset({"asia", "азия"}),
    frozenset({"usa", "us", "united states", "сша"}),
]

_GLOBAL_REGION_TOKENS = frozenset({"global", "world", "international", "глобальный"})


def _expand_region_token(token: str) -> set[str]:
    lowered = token.strip().lower()
    if not lowered:
        return set()
    for group in REGION_ALIAS_GROUPS:
        if lowered in group:
            return set(group)
    return {lowered}


def expand_region_filters(region_filters: list[str]) -> set[str]:
    expanded: set[str] = set()
    for region in region_filters:
        expanded |= _expand_region_token(region)
    return expanded


def _source_region_matches(source: InternetSource, region_filters: list[str]) -> bool:
    if not region_filters:
        return True

    user_regions = expand_region_filters(region_filters)
    user_wants_global = bool(user_regions & _GLOBAL_REGION_TOKENS)
    source_regions = [str(region).lower() for region in (source.regions or [])]
    if not source_regions:
        return True

    for source_region in source_regions:
        expanded_source = _expand_region_token(source_region)
        if expanded_source & _GLOBAL_REGION_TOKENS:
            if user_wants_global:
                return True
            continue
        if user_regions & expanded_source:
            return True
    return False


def _source_visible_filter(user: User):
    return or_(InternetSource.owner_id.is_(None), InternetSource.owner_id == user.id)


def list_internet_sources(
    db: Session,
    *,
    user: User,
    product_tag: str | None = None,
    region: str | None = None,
    access_mode: str | None = None,
    source_kind: str | None = None,
    active_only: bool = True,
    include_inactive: bool = False,
) -> list[InternetSource]:
    if include_inactive:
        active_only = False
    stmt = (
        select(InternetSource)
        .where(_source_visible_filter(user))
        .order_by(InternetSource.priority.desc(), InternetSource.name.asc())
    )
    if active_only:
        stmt = stmt.where(InternetSource.is_active.is_(True))
    if access_mode:
        stmt = stmt.where(InternetSource.access_mode == access_mode)
    if source_kind:
        stmt = stmt.where(InternetSource.source_kind == source_kind)

    sources = list(db.scalars(stmt))
    expanded_product_tag = expand_product_keywords(db, [product_tag]) if product_tag else None
    if not expanded_product_tag and not region:
        return sources

    return match_internet_sources(
        sources,
        product_keywords=expanded_product_tag if expanded_product_tag else None,
        regions=[region] if region else None,
    )


def match_internet_sources(
    sources: list[InternetSource],
    *,
    product_keywords: list[str] | None = None,
    regions: list[str] | None = None,
    access_mode: str | None = None,
    include_inactive: bool = False,
) -> list[InternetSource]:
    keywords = [k.lower() for k in _normalize_tags(product_keywords)]
    region_filters = [r.lower() for r in _normalize_tags(regions)]

    matched: list[tuple[int, InternetSource]] = []
    for source in sources:
        if not source.is_active and not include_inactive:
            continue
        if access_mode and source.access_mode != access_mode:
            continue

        score = source.priority
        if keywords:
            keyword_hits = sum(1 for keyword in keywords if source_keyword_matches(keyword, source))
            if keyword_hits == 0:
                continue
            score += keyword_hits * 10

        if region_filters:
            if not _source_region_matches(source, region_filters):
                continue
            score += 5

        matched.append((score, source))

    matched.sort(key=lambda item: (-item[0], item[1].name.lower()))
    result = [source for _, source in matched]

    if keywords:
        universal_feeds = _collect_universal_api_feeds(
            sources,
            region_filters=region_filters,
            access_mode=access_mode,
            include_inactive=include_inactive,
        )
        seen_ids = {source.id for source in result}
        prepended = [source for source in universal_feeds if source.id not in seen_ids]
        result = prepended + result

    return result


def _collect_universal_api_feeds(
    sources: list[InternetSource],
    *,
    region_filters: list[str],
    access_mode: str | None,
    include_inactive: bool,
) -> list[InternetSource]:
    universal_strategies = {
        InternetSourceFetchStrategy.TED_API.value,
        InternetSourceFetchStrategy.WORLD_BANK_API.value,
    }
    feeds: list[InternetSource] = []
    for source in sources:
        if not source.is_active and not include_inactive:
            continue
        if access_mode and source.access_mode != access_mode:
            continue
        if source.fetch_strategy not in universal_strategies:
            continue
        if region_filters and not _source_region_matches(source, region_filters):
            continue
        feeds.append(source)
    feeds.sort(key=lambda item: (-item.priority, item.name.lower()))
    return feeds


def get_internet_source(db: Session, *, user: User, source_id: uuid.UUID) -> InternetSource:
    source = db.scalar(
        select(InternetSource).where(
            InternetSource.id == source_id,
            _source_visible_filter(user),
        )
    )
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internet source not found")
    return source


def create_internet_source(
    db: Session,
    *,
    user: User,
    data: dict,
) -> InternetSource:
    source = InternetSource(
        owner_id=user.id,
        name=data["name"],
        base_url=data["base_url"],
        source_kind=data.get("source_kind", InternetSourceKind.TENDER_PORTAL.value),
        access_mode=data.get("access_mode", MonitoringAccessMode.PUBLIC.value),
        regions=_normalize_tags(data.get("regions")),
        product_tags=_normalize_tags(data.get("product_tags")),
        languages=_normalize_tags(data.get("languages")),
        description=data.get("description"),
        search_hints=data.get("search_hints"),
        is_active=data.get("is_active", True),
        is_test=data.get("is_test", False),
        priority=int(data.get("priority", 50)),
        fetch_strategy=data.get("fetch_strategy", InternetSourceFetchStrategy.HTML.value),
        fetch_config=data.get("fetch_config") or {},
        last_verified_at=data.get("last_verified_at"),
    )
    db.add(source)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="InternetSource",
        entity_id=source.id,
        new_value={"name": source.name, "base_url": source.base_url},
    )
    db.commit()
    db.refresh(source)
    return source


_SYSTEM_MUTABLE_FIELDS = frozenset({"is_active", "is_test"})


def update_internet_source(
    db: Session,
    *,
    user: User,
    source: InternetSource,
    data: dict,
) -> InternetSource:
    if source.owner_id is None:
        disallowed = {key for key in data if data[key] is not None and key not in _SYSTEM_MUTABLE_FIELDS}
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="System catalog entries can only toggle is_active and is_test",
            )
    elif source.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internet source not found")

    for field in (
        "name",
        "base_url",
        "source_kind",
        "access_mode",
        "description",
        "search_hints",
        "is_active",
        "is_test",
        "priority",
        "fetch_strategy",
        "fetch_config",
    ):
        if field in data and data[field] is not None:
            setattr(source, field, data[field])
    if "regions" in data and data["regions"] is not None:
        source.regions = _normalize_tags(data["regions"])
    if "product_tags" in data and data["product_tags"] is not None:
        source.product_tags = _normalize_tags(data["product_tags"])
    if "languages" in data and data["languages"] is not None:
        source.languages = _normalize_tags(data["languages"])
    if "last_verified_at" in data:
        source.last_verified_at = data["last_verified_at"]

    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="InternetSource",
        entity_id=source.id,
        new_value=data,
    )
    db.commit()
    db.refresh(source)
    return source


SYSTEM_INTERNET_SOURCES: list[dict] = [
    {
        "name": "TED — EU Notices API",
        "base_url": "https://api.ted.europa.eu/v3/notices/search",
        "source_kind": InternetSourceKind.PROCUREMENT_FEED.value,
        "access_mode": MonitoringAccessMode.PUBLIC.value,
        "fetch_strategy": InternetSourceFetchStrategy.TED_API.value,
        "regions": ["EU", "Europe"],
        "product_tags": [
            "urea", "carbamide", "fertilizer", "chemicals", "карбамид",
            "commodities", "polymers", "gum", "guar gum", "procurement",
            "transformer oil", "insulating oil", "трансформаторное масло", "base oil", "oil",
        ],
        "languages": ["en"],
        "description": "Official EU TED Search API — real published procurement notices.",
        "search_hints": "Full-text search with publication date filter.",
        "priority": 95,
        "is_active": True,
    },
    {
        "name": "World Bank Procurement",
        "base_url": "https://search.worldbank.org/api/v2/procnotices",
        "source_kind": InternetSourceKind.AGGREGATOR.value,
        "access_mode": MonitoringAccessMode.PUBLIC.value,
        "fetch_strategy": InternetSourceFetchStrategy.WORLD_BANK_API.value,
        "regions": ["Global", "Africa", "Asia"],
        "product_tags": [
            "urea", "fertilizer", "carbamide", "карбамид",
            "commodities", "chemicals", "polymers", "gum", "guar gum", "procurement",
        ],
        "languages": ["en"],
        "description": "World Bank open procurement notices API (fertilizer/urea-related bids).",
        "search_hints": "Search by qterm and filter by notice date.",
        "priority": 90,
        "is_active": True,
    },
    {
        "name": "ЕИС Закупки (zakupki.gov.ru)",
        "base_url": "https://zakupki.gov.ru/epz/order/extendedsearch/search.html",
        "source_kind": InternetSourceKind.GOV_REGISTRY.value,
        "access_mode": MonitoringAccessMode.PUBLIC.value,
        "fetch_strategy": InternetSourceFetchStrategy.HTML.value,
        "regions": ["Russia", "CIS"],
        "product_tags": [
            "urea", "carbamide", "fertilizer", "карбамид", "chemicals", "commodities",
            "transformer oil", "insulating oil", "трансформаторное масло", "oil", "procurement",
        ],
        "languages": ["ru", "en"],
        "description": "Единая информационная система закупок РФ — поиск извещений по 44-ФЗ и 223-ФЗ.",
        "search_hints": "https://zakupki.gov.ru/epz/order/extendedsearch/search.html — фильтр по наименованию объекта закупки.",
        "priority": 92,
        "is_active": True,
    },
    {
        "name": "eProcure Government of India",
        "base_url": "https://eprocure.gov.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page",
        "source_kind": InternetSourceKind.GOV_REGISTRY.value,
        "access_mode": MonitoringAccessMode.PUBLIC.value,
        "fetch_strategy": InternetSourceFetchStrategy.HTML.value,
        "regions": ["India"],
        "product_tags": [
            "urea", "carbamide", "fertilizer", "карбамид",
            "commodities", "chemicals", "polymers", "gum", "guar gum",
        ],
        "languages": ["en"],
        "description": "Indian government eProcurement active tenders page.",
        "search_hints": "Parse active tenders list for fertilizer/urea keywords.",
        "priority": 85,
        "is_active": True,
    },
    {
        "name": "MMTC Limited",
        "base_url": "https://www.mmtc-limited.com/",
        "source_kind": InternetSourceKind.TENDER_PORTAL.value,
        "access_mode": MonitoringAccessMode.PUBLIC.value,
        "fetch_strategy": InternetSourceFetchStrategy.HTML.value,
        "regions": ["India", "Asia"],
        "product_tags": ["urea", "carbamide", "fertilizer", "карбамид"],
        "languages": ["en"],
        "description": "Indian state trading company — HTML fetch may fail from some networks.",
        "search_hints": "Tender/notice pages about urea imports.",
        "priority": 40,
        "is_active": False,
        "is_test": True,
    },
    {
        "name": "Government e-Marketplace (GeM)",
        "base_url": "https://gem.gov.in/",
        "source_kind": InternetSourceKind.GOV_REGISTRY.value,
        "access_mode": MonitoringAccessMode.PUBLIC.value,
        "fetch_strategy": InternetSourceFetchStrategy.HTML.value,
        "regions": ["India"],
        "product_tags": ["urea", "carbamide", "fertilizer", "chemicals"],
        "languages": ["en", "hi"],
        "description": "GeM portal — often slow/blocked for automated fetch; kept for manual extension.",
        "search_hints": "Search bids by urea / carbamide.",
        "priority": 35,
        "is_active": False,
        "is_test": True,
    },
    {
        "name": "UN Global Marketplace",
        "base_url": "https://www.ungm.org/Public/Notice",
        "source_kind": InternetSourceKind.AGGREGATOR.value,
        "access_mode": MonitoringAccessMode.PUBLIC.value,
        "fetch_strategy": InternetSourceFetchStrategy.HTML.value,
        "regions": ["Global"],
        "product_tags": ["urea", "fertilizer", "chemicals", "commodities", "polymers", "gum", "procurement"],
        "languages": ["en"],
        "description": "UNGM public notices — HTML keyword extraction.",
        "search_hints": "Open procurement notices for chemicals/fertilizers.",
        "priority": 70,
        "is_active": True,
    },
]

LEGACY_TEST_SOURCE_NAMES = (
    "RCF Limited",
    "NFL India",
    "EU Lubricants Buyer Portal",
    "TED Europa",
    "TED — Tenders Electronic Daily",
    "Demo EU lubricants feed",
)


def sync_system_internet_sources(db: Session) -> int:
    now = datetime.now(timezone.utc)
    changed = 0
    for item in SYSTEM_INTERNET_SOURCES:
        existing = db.scalar(
            select(InternetSource).where(
                InternetSource.owner_id.is_(None),
                InternetSource.name == item["name"],
            )
        )
        payload = {
            **item,
            "languages": item.get("languages", []),
            "fetch_config": item.get("fetch_config", {}),
            "last_verified_at": now,
        }
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
            changed += 1
        else:
            db.add(InternetSource(owner_id=None, **payload))
            changed += 1

    for legacy_name in LEGACY_TEST_SOURCE_NAMES:
        legacy = db.scalar(
            select(InternetSource).where(
                InternetSource.owner_id.is_(None),
                InternetSource.name == legacy_name,
            )
        )
        if legacy is None:
            continue
        legacy.is_active = False
        legacy.is_test = True
        changed += 1

    for legacy in db.scalars(select(InternetSource).where(InternetSource.owner_id.is_(None))):
        if legacy.fetch_strategy == InternetSourceFetchStrategy.TED_API.value:
            continue
        if is_ted_web_portal(legacy.base_url) or (
            is_ted_source(legacy) and legacy.fetch_strategy == InternetSourceFetchStrategy.HTML.value
        ):
            legacy.is_active = False
            legacy.is_test = True
            changed += 1

    if changed:
        db.commit()
    return changed


def seed_internet_sources(db: Session) -> int:
    return sync_system_internet_sources(db)
