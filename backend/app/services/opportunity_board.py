import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.domain.enums import MonitoredPublicationStatus, OpportunityType
from app.domain.models import (
    Deal,
    FulfilmentConfiguration,
    InternetSource,
    InternetSourceSearchHit,
    MonitoredPublication,
    MonitoringRule,
    Opportunity,
    Product,
    Source,
    SupplierLeadContext,
    User,
)
from app.services.opportunity_commercial import build_commercial_row
from app.services.opportunity_status import resolve_display_status


def _format_quantity(min_qty, max_qty, unit: str | None) -> str | None:
    if min_qty is None and max_qty is None:
        return None
    if min_qty is not None and max_qty is not None and min_qty != max_qty:
        text = f"{int(min_qty)}–{int(max_qty)}"
    elif min_qty is not None:
        text = str(int(min_qty))
    else:
        text = str(int(max_qty))
    return f"{text} {unit}" if unit else text


def _commercial_summary(opp: Opportunity, product_name: str | None) -> str:
    parts: list[str] = []
    product = product_name or opp.raw_product_name
    if product:
        parts.append(product)
    qty = _format_quantity(opp.quantity_min, opp.quantity_max, opp.quantity_unit)
    if qty:
        parts.append(qty)
    if opp.destination_hint:
        parts.append(f"→ {opp.destination_hint}")
    if opp.buyer_or_supplier_hint:
        parts.append(f"· {opp.buyer_or_supplier_hint}")
    return " ".join(parts) if parts else "Коммерческие условия не заполнены"


def _type_label(opp_type: str) -> str:
    labels = {
        OpportunityType.BUYER_NEED.value: "Запрос покупателя",
        OpportunityType.AUTO_DISCOVERED.value: "Мониторинг",
        OpportunityType.SUPPLIER_OFFER.value: "Предложение поставщика",
        OpportunityType.TENDER.value: "Тендер",
    }
    return labels.get(opp_type, opp_type)


def _filter_match_text(item_text: str, keywords: list[str]) -> tuple[bool, list[str]]:
    haystack = item_text.lower()
    matched = [kw for kw in keywords if kw.lower() in haystack]
    return bool(matched), matched


def _publication_search_text(pub: MonitoredPublication) -> str:
    fields = pub.extracted_fields or {}
    return " ".join(
        filter(
            None,
            [
                pub.title,
                str(fields.get("product") or ""),
                str(fields.get("destination") or ""),
                str(fields.get("buyer") or ""),
            ],
        )
    )


def _build_origin_explanation(
    opp: Opportunity,
    *,
    publication: MonitoredPublication | None,
    rule: MonitoringRule | None,
) -> tuple[str, str, str | None]:
    if publication and rule:
        keywords = list((rule.filters or {}).get("product_keywords") or [])
        matched, hits = _filter_match_text(_publication_search_text(publication), keywords)
        keyword_text = ", ".join(keywords) if keywords else "не задан"
        if matched:
            explanation = (
                f"Правило «{rule.name}» нашло совпадение с фильтром ({keyword_text}): "
                f"{', '.join(hits)}."
            )
        else:
            explanation = f"Создано из мониторинга «{rule.name}»."
        return "MONITORING", f"Мониторинг · {rule.name}", explanation

    if opp.type == OpportunityType.AUTO_DISCOVERED.value:
        return "MONITORING", "Мониторинг", opp.notes or "Автоматически обнаруженная возможность"

    if opp.type == OpportunityType.BUYER_NEED.value:
        return "MANUAL", "Создано вручную", "Buyer-led возможность, созданная пользователем."

    if opp.type == OpportunityType.SUPPLIER_OFFER.value:
        return (
            "SUPPLIER_LED",
            "Предложение поставщика",
            opp.notes or "Supplier-led возможность: ищем покупателей под подтверждённое предложение.",
        )

    return "OTHER", _type_label(opp.type), opp.notes


def _build_skipped_explanation(pub: MonitoredPublication, rule: MonitoringRule) -> str:
    keywords = list((rule.filters or {}).get("product_keywords") or [])
    keyword_text = ", ".join(keywords) if keywords else "не заданы"
    search_text = _publication_search_text(pub)
    product = (pub.extracted_fields or {}).get("product") or pub.title
    return (
        f"Правило «{rule.name}» отслеживает только: {keyword_text}. "
        f"В объявлении «{product}» совпадений нет."
    )


def _document_label(source: Source) -> str:
    if source.source_type == "URL" and source.source_url:
        return source.source_url
    return source.original_filename or source.source_type


def _build_documents(sources: list[Source]) -> list[dict]:
    return [
        {
            "id": source.id,
            "source_type": source.source_type,
            "label": _document_label(source),
            "source_url": source.source_url,
        }
        for source in sources
    ]


def list_opportunity_board(db: Session, *, user: User) -> dict:
    opportunities = list(
        db.scalars(
            select(Opportunity)
            .where(Opportunity.owner_id == user.id)
            .options(joinedload(Opportunity.product))
            .order_by(Opportunity.created_at.desc())
        )
    )

    publications = list(
        db.scalars(
            select(MonitoredPublication)
            .join(MonitoringRule, MonitoringRule.id == MonitoredPublication.monitoring_rule_id)
            .where(MonitoringRule.owner_id == user.id)
            .options(joinedload(MonitoredPublication.rule))
        )
    )
    pub_by_opp = {
        pub.opportunity_id: pub for pub in publications if pub.opportunity_id is not None
    }

    opp_ids = [o.id for o in opportunities]
    if opp_ids:
        deal_by_opp = {
            deal.origin_opportunity_id: deal
            for deal in db.scalars(
                select(Deal).where(
                    Deal.owner_id == user.id,
                    Deal.origin_opportunity_id.in_(opp_ids),
                )
            )
        }
    else:
        deal_by_opp = {}

    deal_ids = [d.id for d in deal_by_opp.values()]
    config_by_deal: dict[uuid.UUID, FulfilmentConfiguration] = {}
    if deal_ids:
        configs = list(
            db.scalars(
                select(FulfilmentConfiguration)
                .where(
                    FulfilmentConfiguration.deal_id.in_(deal_ids),
                    FulfilmentConfiguration.status.in_(("SELECTED", "FEASIBLE")),
                )
                .options(joinedload(FulfilmentConfiguration.shipment_lots))
                .order_by(FulfilmentConfiguration.updated_at.desc())
            ).unique()
        )
        for config in configs:
            if config.deal_id not in config_by_deal:
                config_by_deal[config.deal_id] = config

    supplier_contexts = {}
    if opp_ids:
        for ctx in db.scalars(
            select(SupplierLeadContext).where(SupplierLeadContext.opportunity_id.in_(opp_ids))
        ):
            supplier_contexts[ctx.opportunity_id] = ctx

    sources_by_opp: dict[uuid.UUID, list[Source]] = {opp_id: [] for opp_id in opp_ids}
    if opp_ids:
        for source in db.scalars(select(Source).where(Source.opportunity_id.in_(opp_ids))):
            if source.opportunity_id is not None:
                sources_by_opp[source.opportunity_id].append(source)

    search_hit_by_opp: dict[uuid.UUID, InternetSourceSearchHit] = {}
    internet_source_names: dict[uuid.UUID, str] = {}
    if opp_ids:
        for hit in db.scalars(
            select(InternetSourceSearchHit).where(InternetSourceSearchHit.opportunity_id.in_(opp_ids))
        ):
            if hit.opportunity_id is not None and hit.opportunity_id not in search_hit_by_opp:
                search_hit_by_opp[hit.opportunity_id] = hit
        source_ids = {hit.internet_source_id for hit in search_hit_by_opp.values()}
        if source_ids:
            for source in db.scalars(select(InternetSource).where(InternetSource.id.in_(source_ids))):
                internet_source_names[source.id] = source.name

    items = []
    for opp in opportunities:
        publication = pub_by_opp.get(opp.id)
        rule = publication.rule if publication else None
        product_name = opp.product.normalized_name if opp.product else None
        origin_kind, origin_label, origin_explanation = _build_origin_explanation(
            opp, publication=publication, rule=rule
        )
        deal = deal_by_opp.get(opp.id)
        config = config_by_deal.get(deal.id) if deal else None
        supplier_context = supplier_contexts.get(opp.id)
        opportunity_sources = sources_by_opp.get(opp.id, [])
        search_hit = search_hit_by_opp.get(opp.id)
        source_url = (
            opp.source_url
            or (publication.canonical_url if publication else None)
            or (search_hit.canonical_url if search_hit else None)
        )
        internet_source_name = None
        if search_hit:
            internet_source_name = internet_source_names.get(search_hit.internet_source_id)
        commercial_row = build_commercial_row(
            opp,
            product_name=product_name,
            publication=publication,
            supplier_context=supplier_context,
            deal=deal,
            config=config,
        )
        display_status = resolve_display_status(opp, deal=deal, config=config)
        economics_preview = None
        if config and config.gross_margin is not None:
            margin = int(round(config.gross_margin))
            percent = float(config.gross_margin_percent or 0)
            economics_preview = (
                f"Сценарий «{config.name}»: маржа {margin:,} {deal.base_currency} "
                f"({percent:.2f}%)".replace(",", " ")
            )
        items.append(
            {
                "id": opp.id,
                "type": opp.type,
                "type_label": _type_label(opp.type),
                "title": opp.title,
                "status": opp.status,
                "raw_product_name": opp.raw_product_name,
                "normalized_product_id": opp.normalized_product_id,
                "normalized_product_name": product_name,
                "buyer_or_supplier_hint": opp.buyer_or_supplier_hint,
                "quantity_min": opp.quantity_min,
                "quantity_max": opp.quantity_max,
                "quantity_unit": opp.quantity_unit,
                "origin_hint": opp.origin_hint,
                "destination_hint": opp.destination_hint,
                "deadline": opp.deadline,
                "notes": opp.notes,
                "created_at": opp.created_at,
                "updated_at": opp.updated_at,
                "commercial_summary": _commercial_summary(opp, product_name),
                "description": opp.notes,
                "origin_kind": origin_kind,
                "origin_label": origin_label,
                "origin_explanation": origin_explanation,
                "deal_id": deal.id if deal else None,
                "deal_number": deal.deal_number if deal else None,
                "economics_preview": economics_preview,
                "commercial_row": commercial_row,
                "display_status": display_status,
                "quote_deadline": opp.quote_deadline,
                "delivery_deadline": opp.delivery_deadline,
                "status_changed_at": opp.status_changed_at,
                "status_note": opp.status_note,
                "source_url": source_url,
                "monitoring_rule_name": rule.name if rule else None,
                "monitoring_publication_id": publication.id if publication else None,
                "sources_count": len(opportunity_sources),
                "documents": _build_documents(opportunity_sources),
                "internet_source_name": internet_source_name,
            }
        )

    skipped = []
    for pub in publications:
        if pub.status != MonitoredPublicationStatus.FILTERED_OUT.value:
            continue
        rule = pub.rule
        skipped.append(
            {
                "id": pub.id,
                "monitoring_rule_id": pub.monitoring_rule_id,
                "monitoring_rule_name": rule.name if rule else None,
                "title": pub.title,
                "product": (pub.extracted_fields or {}).get("product"),
                "destination": (pub.extracted_fields or {}).get("destination"),
                "buyer": (pub.extracted_fields or {}).get("buyer"),
                "quantity": (pub.extracted_fields or {}).get("quantity"),
                "quantity_unit": (pub.extracted_fields or {}).get("quantity_unit"),
                "first_seen_at": pub.first_seen_at,
                "filter_explanation": _build_skipped_explanation(pub, rule) if rule else None,
            }
        )

    return {"opportunities": items, "skipped_monitoring": skipped}
