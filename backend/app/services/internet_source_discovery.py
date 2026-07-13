from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import get_ai_provider
from app.ai.schemas import InternetSourceDiscoveryOutput
from app.config import settings
from app.domain.enums import AIUsageOperation, AuditAction, AgentResultType, AgentType, InternetSourceFetchStrategy, InternetSourceKind, MonitoringAccessMode
from app.domain.models import InternetSource, User
from app.services.ai_budget import enforce_budget_or_raise, ensure_ai_budget_settings
from app.services.agent_runtime import AgentExecutionContext, tracked_agent_run
from app.services.audit import log_audit
from app.integrations.ted import is_ted_api_url, is_ted_web_portal
from app.services.internet_source_catalog import create_internet_source, list_internet_sources, match_internet_sources
from app.services.product_keyword_localization import build_keyword_search_set, expand_product_keywords

DISCOVERY_SYSTEM_PROMPT = """You discover public procurement and tender platforms for commodity trading desks.
Rules:
- Return ONLY platforms that are NOT already listed in the known catalog.
- Prefer official government portals, state trading companies, commodity exchanges, and reputable aggregators.
- Each candidate must be a real, plausible public website for tenders or procurement notices.
- Do NOT suggest TED (ted.europa.eu) — it is already covered by the official TED Search API source.
- Use fetch_strategy=HTML unless the source is clearly a documented open API (then WORLD_BANK_API only if certain).
- product_tags must include the user's commodity terms and related trade names.
- search_hints: concise instructions where on the site to find tenders for this product.
- Do not duplicate URLs from the known catalog, even under a different name.
- Return an empty candidates list when the catalog already covers the product/region well.
"""

MIN_MATCHED_BEFORE_SKIP = 4
DISCOVERY_COOLDOWN_HOURS = 12


def normalize_source_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    if not cleaned:
        return ""
    parsed = urlparse(cleaned if "://" in cleaned else f"https://{cleaned}")
    host = (parsed.netloc or parsed.path).lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/").lower() if parsed.netloc else ""
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    if not host:
        return cleaned.lower()
    return f"{scheme}://{host}{path}"


def _known_source_index(sources: list[InternetSource]) -> dict[str, InternetSource]:
    index: dict[str, InternetSource] = {}
    for source in sources:
        key = normalize_source_url(source.base_url)
        if key:
            index[key] = source
    return index


def _build_known_catalog_summary(sources: list[InternetSource], *, limit: int = 80) -> str:
    lines: list[str] = []
    for source in sources[:limit]:
        tags = ", ".join(source.product_tags or []) or "—"
        lines.append(f"- {source.name} | {source.base_url} | tags: {tags}")
    if len(sources) > limit:
        lines.append(f"... and {len(sources) - limit} more")
    return "\n".join(lines) if lines else "(empty catalog)"


def _build_discovery_prompt(
    *,
    product_keywords: list[str],
    expanded_keywords: list[str],
    regions: list[str],
    access_mode: str | None,
    known_summary: str,
    region_focused: bool = False,
) -> str:
    if region_focused:
        return (
            f"Target regions: {', '.join(regions)}\n"
            f"Preferred access mode: {access_mode or 'PUBLIC'}\n\n"
            f"Known catalog (do NOT suggest these URLs again):\n{known_summary}\n\n"
            "Suggest up to 5 NEW public procurement and commodity tender platforms "
            "relevant to these regions (any commodity category)."
        )
    return (
        f"Commodity product keywords: {', '.join(product_keywords)}\n"
        f"Expanded trade terms: {', '.join(expanded_keywords)}\n"
        f"Target regions: {', '.join(regions) if regions else 'any'}\n"
        f"Preferred access mode: {access_mode or 'PUBLIC'}\n\n"
        f"Known catalog (do NOT suggest these URLs again):\n{known_summary}\n\n"
        "Suggest up to 5 NEW procurement platforms where this commodity is tendered or traded."
    )


def _should_skip_region_discovery(
    db: Session,
    *,
    user: User,
    regions: list[str],
    access_mode: str | None,
) -> bool:
    if not regions:
        return True
    sources = list_internet_sources(db, user=user, active_only=True, include_inactive=False)
    matched = match_internet_sources(
        sources,
        product_keywords=None,
        regions=regions,
        access_mode=access_mode,
    )
    return len(matched) >= MIN_MATCHED_BEFORE_SKIP


def _should_skip_discovery(
    db: Session,
    *,
    user: User,
    product_keywords: list[str],
    regions: list[str],
    access_mode: str | None,
) -> bool:
    sources = list_internet_sources(db, user=user, active_only=True, include_inactive=False)
    expanded = expand_product_keywords(db, product_keywords)
    matched = match_internet_sources(
        sources,
        product_keywords=expanded,
        regions=regions or None,
        access_mode=access_mode,
    )
    if len(matched) >= MIN_MATCHED_BEFORE_SKIP:
        return True

    cutoff = datetime.now(timezone.utc) - timedelta(hours=DISCOVERY_COOLDOWN_HOURS)
    keyword_lowers = {keyword.lower() for keyword in product_keywords if keyword.strip()}
    for source in sources:
        if source.owner_id != user.id:
            continue
        if source.created_at and source.created_at.replace(tzinfo=timezone.utc) < cutoff:
            continue
        source_tags = {str(tag).lower() for tag in (source.product_tags or [])}
        if keyword_lowers & source_tags:
            return True
    return False


def _merge_product_tags(existing: list[str], new_tags: list[str], user_keywords: list[str]) -> list[str]:
    merged = list(existing or [])
    for value in [*new_tags, *user_keywords]:
        if value and value not in merged:
            merged.append(value)
    return merged


def _find_system_ted_source(sources: list[InternetSource]) -> InternetSource | None:
    for source in sources:
        if source.owner_id is not None:
            continue
        if source.fetch_strategy == InternetSourceFetchStrategy.TED_API.value:
            return source
    for source in sources:
        if source.owner_id is not None:
            continue
        if is_ted_api_url(source.base_url) or is_ted_web_portal(source.base_url):
            return source
    return None


def _is_ted_discovery_candidate(url: str) -> bool:
    return is_ted_api_url(url) or is_ted_web_portal(url)


@dataclass(frozen=True)
class SourceDiscoveryResult:
    added_sources: list[InternetSource]
    skipped_existing: int
    ai_notes: str | None
    skipped_discovery: bool


def discover_and_register_sources(
    db: Session,
    *,
    user: User,
    product_keywords: list[str],
    regions: list[str] | None = None,
    access_mode: str | None = MonitoringAccessMode.PUBLIC.value,
    force: bool = False,
) -> SourceDiscoveryResult:
    keywords = [keyword.strip() for keyword in product_keywords if keyword and keyword.strip()]
    region_list = [region.strip() for region in (regions or []) if region and region.strip()]
    region_focused = not keywords and bool(region_list)

    if not keywords and not region_list:
        return SourceDiscoveryResult([], 0, None, True)

    discovery_keywords = keywords or ["commodity procurement", "public tenders"]

    if region_focused:
        if not force and _should_skip_region_discovery(
            db,
            user=user,
            regions=region_list,
            access_mode=access_mode,
        ):
            return SourceDiscoveryResult(
                [],
                0,
                "Каталог уже покрывает выбранные регионы — поиск новых площадок пропущен",
                True,
            )
    elif not force and _should_skip_discovery(
        db,
        user=user,
        product_keywords=keywords,
        regions=region_list,
        access_mode=access_mode,
    ):
        return SourceDiscoveryResult([], 0, "Каталог уже покрывает товар — поиск новых площадок пропущен", True)

    all_sources = list_internet_sources(db, user=user, active_only=False, include_inactive=True)
    known_index = _known_source_index(all_sources)
    search_set = build_keyword_search_set(db, discovery_keywords)
    expanded_keywords = search_set.expanded

    enforce_budget_or_raise(db, user=user)
    budget_settings = ensure_ai_budget_settings(db, user)
    provider = get_ai_provider()
    model = budget_settings.preferred_default_model or settings.openai_default_model

    with tracked_agent_run(
        db,
        user=user,
        context=AgentExecutionContext(
            agent_type=AgentType.TENDER_DISCOVERY.value,
            task_type="source_discovery",
            input_payload={
                "product_keywords": keywords,
                "regions": region_list,
                "region_focused": region_focused,
            },
        ),
    ) as agent:
        discovery, usage = provider.structured_completion(
            model=model,
            system_prompt=DISCOVERY_SYSTEM_PROMPT,
            user_prompt=_build_discovery_prompt(
                product_keywords=discovery_keywords,
                expanded_keywords=expanded_keywords,
                regions=region_list,
                access_mode=access_mode,
                known_summary=_build_known_catalog_summary(all_sources),
                region_focused=region_focused,
            ),
            output_schema=InternetSourceDiscoveryOutput,
            temperature=0.0,
        )
        agent.attach_ai_usage(
            model=usage.model,
            operation=AIUsageOperation.CATALOG.value,
            cost_usd=usage.cost_usd,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        agent.record_result(
            result_type=AgentResultType.SOURCE_DISCOVERY.value,
            structured_payload=discovery.model_dump(mode="json"),
            summary=discovery.notes,
            applied=False,
        )

    added: list[InternetSource] = []
    skipped = 0
    for candidate in discovery.candidates:
        normalized = normalize_source_url(candidate.base_url)
        if not normalized:
            skipped += 1
            continue

        if _is_ted_discovery_candidate(candidate.base_url):
            ted_system = _find_system_ted_source(all_sources)
            if ted_system is not None:
                merged_tags = _merge_product_tags(ted_system.product_tags or [], candidate.product_tags, discovery_keywords)
                if merged_tags != (ted_system.product_tags or []):
                    ted_system.product_tags = merged_tags
                    ted_system.search_hints = ted_system.search_hints or candidate.search_hints
                skipped += 1
                continue

        if normalized in known_index:
            existing = known_index[normalized]
            merged_tags = _merge_product_tags(existing.product_tags or [], candidate.product_tags, discovery_keywords)
            if merged_tags != (existing.product_tags or []):
                existing.product_tags = merged_tags
                existing.search_hints = existing.search_hints or candidate.search_hints
            skipped += 1
            continue

        fetch_strategy = candidate.fetch_strategy or InternetSourceFetchStrategy.HTML.value
        if fetch_strategy not in {
            InternetSourceFetchStrategy.HTML.value,
            InternetSourceFetchStrategy.TED_API.value,
            InternetSourceFetchStrategy.WORLD_BANK_API.value,
        }:
            fetch_strategy = InternetSourceFetchStrategy.HTML.value

        source_kind = candidate.source_kind or InternetSourceKind.TENDER_PORTAL.value
        if source_kind not in {item.value for item in InternetSourceKind}:
            source_kind = InternetSourceKind.TENDER_PORTAL.value

        source = create_internet_source(
            db,
            user=user,
            data={
                "name": candidate.name.strip(),
                "base_url": candidate.base_url.strip(),
                "source_kind": source_kind,
                "access_mode": candidate.access_mode or MonitoringAccessMode.PUBLIC.value,
                "fetch_strategy": fetch_strategy,
                "regions": candidate.regions or region_list,
                "product_tags": _merge_product_tags(candidate.product_tags, discovery_keywords, discovery_keywords),
                "languages": candidate.languages or ["en"],
                "description": candidate.description or candidate.evidence,
                "search_hints": candidate.search_hints,
                "is_active": True,
                "is_test": False,
                "priority": min(95, 50 + int(candidate.confidence * 40)),
            },
        )
        known_index[normalized] = source
        added.append(source)

    if added:
        log_audit(
            db,
            actor=user,
            action=AuditAction.CREATE,
            entity_type="InternetSourceDiscovery",
            entity_id=uuid.uuid4(),
            new_value={
                "product_keywords": discovery_keywords,
                "user_keywords": keywords,
                "regions": region_list,
                "region_focused": region_focused,
                "added_count": len(added),
                "skipped_existing": skipped,
                "source_names": [source.name for source in added],
            },
        )

    return SourceDiscoveryResult(
        added_sources=added,
        skipped_existing=skipped,
        ai_notes=discovery.notes,
        skipped_discovery=False,
    )
