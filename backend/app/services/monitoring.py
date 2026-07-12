import hashlib
import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import (
    AuditAction,
    MonitoringHealthStatus,
    MonitoringRunStatus,
    MonitoredPublicationStatus,
    OpportunityStatus,
    OpportunityType,
)
from app.domain.models import (
    MonitoredPublication,
    MonitoringRule,
    MonitoringRun,
    Opportunity,
    Product,
    User,
)
from app.integrations.monitoring.base import MonitoringFeedItem
from app.integrations.monitoring.mock_connector import get_monitoring_connector
from app.integrations.storage.local import LocalFilesystemStorage
from app.services.audit import log_audit
from app.services.opportunity_status import initialize_opportunity_status
from app.services.tender_attachments import attach_tender_link


def _content_hash(item: MonitoringFeedItem) -> str:
    payload = {
        "source_item_id": item.source_item_id,
        "title": item.title,
        "product": item.product,
        "buyer": item.buyer,
        "destination": item.destination,
        "quantity": item.quantity,
        "quantity_unit": item.quantity_unit,
        "deadline": item.deadline.isoformat() if item.deadline else None,
        "body": item.body,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _matches_filters(item: MonitoringFeedItem, filters: dict) -> bool:
    keywords = [k.lower() for k in filters.get("product_keywords", []) if k]
    if not keywords:
        return True
    haystack = " ".join(
        filter(
            None,
            [item.title, item.product, item.body],
        )
    ).lower()
    return any(keyword in haystack for keyword in keywords)


def _resolve_product_id(db: Session, item: MonitoringFeedItem) -> uuid.UUID | None:
    if not item.product:
        return None
    products = db.scalars(select(Product)).all()
    product_lower = item.product.lower()
    for product in products:
        names = [product.normalized_name.lower(), *([a.lower() for a in product.aliases or []])]
        if any(name in product_lower or product_lower in name for name in names):
            return product.id
    return None


def get_monitoring_rule(db: Session, *, user: User, rule_id: uuid.UUID) -> MonitoringRule:
    rule = db.get(MonitoringRule, rule_id)
    if rule is None or rule.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitoring rule not found")
    return rule


def list_monitoring_rules(db: Session, *, user: User) -> list[MonitoringRule]:
    return list(
        db.scalars(
            select(MonitoringRule)
            .where(MonitoringRule.owner_id == user.id)
            .order_by(MonitoringRule.created_at.desc())
        )
    )


def create_monitoring_rule(
    db: Session,
    *,
    user: User,
    name: str,
    connector_type: str,
    source_url: str,
    poll_interval_hours: int = 24,
    filters: dict | None = None,
    access_mode: str = "PUBLIC",
    connector_config: dict | None = None,
) -> MonitoringRule:
    rule = MonitoringRule(
        owner_id=user.id,
        name=name,
        connector_type=connector_type,
        source_url=source_url,
        poll_interval_hours=poll_interval_hours,
        filters=filters or {},
        access_mode=access_mode,
        connector_config=connector_config or {},
        health_status=MonitoringHealthStatus.UNKNOWN.value,
    )
    db.add(rule)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="MonitoringRule",
        entity_id=rule.id,
        new_value={"name": name, "connector_type": connector_type, "source_url": source_url},
    )
    db.commit()
    db.refresh(rule)
    return rule


def check_monitoring_health(db: Session, *, user: User, rule: MonitoringRule) -> dict:
    connector = get_monitoring_connector(rule.connector_type, rule.source_url)
    health_status, message = connector.healthcheck()
    rule.health_status = health_status
    rule.health_message = message
    db.commit()
    return {"rule_id": str(rule.id), "health_status": health_status, "message": message}


def get_monitoring_run(db: Session, *, user: User, run_id: uuid.UUID) -> MonitoringRun:
    run = db.get(MonitoringRun, run_id)
    if run is None or run.rule.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitoring run not found")
    return run


def list_publications(db: Session, *, user: User, rule_id: uuid.UUID) -> list[MonitoredPublication]:
    rule = get_monitoring_rule(db, user=user, rule_id=rule_id)
    return list(
        db.scalars(
            select(MonitoredPublication)
            .where(MonitoredPublication.monitoring_rule_id == rule.id)
            .order_by(MonitoredPublication.first_seen_at.desc())
        )
    )


def _store_snapshot(storage: LocalFilesystemStorage, *, rule_id: uuid.UUID, item: MonitoringFeedItem) -> str:
    key = f"monitoring/{rule_id}/{item.source_item_id}.json"
    storage.save(key, json.dumps(item.raw, ensure_ascii=False, indent=2).encode("utf-8"))
    return key


def _create_opportunity_from_item(
    db: Session,
    *,
    user: User,
    item: MonitoringFeedItem,
    rule: MonitoringRule,
) -> Opportunity:
    product_id = _resolve_product_id(db, item)
    opportunity = Opportunity(
        owner_id=user.id,
        type=OpportunityType.AUTO_DISCOVERED.value,
        title=item.title,
        raw_product_name=item.product,
        normalized_product_id=product_id,
        buyer_or_supplier_hint=item.buyer,
        quantity_min=item.quantity,
        quantity_max=item.quantity,
        quantity_unit=item.quantity_unit,
        destination_hint=item.destination,
        deadline=item.deadline,
        quote_deadline=item.deadline,
        status=OpportunityStatus.NEW.value,
        notes=f"Auto-discovered from monitoring rule '{rule.name}'",
    )
    db.add(opportunity)
    db.flush()
    attach_tender_link(db, user=user, opportunity=opportunity, url=item.url)
    initialize_opportunity_status(db, opportunity=opportunity, actor=user, actor_type="SYSTEM")
    log_audit(
        db,
        actor=user,
        action=AuditAction.CREATE,
        entity_type="Opportunity",
        entity_id=opportunity.id,
        new_value={"source": "monitoring", "rule_id": str(rule.id), "source_item_id": item.source_item_id},
    )
    return opportunity


def run_monitoring_rule(
    db: Session,
    *,
    user: User,
    rule: MonitoringRule,
    storage: LocalFilesystemStorage | None = None,
) -> MonitoringRun:
    if rule.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitoring rule not found")

    storage = storage or LocalFilesystemStorage()
    connector = get_monitoring_connector(rule.connector_type, rule.source_url)
    started_at = datetime.now(timezone.utc)
    run = MonitoringRun(
        monitoring_rule_id=rule.id,
        status=MonitoringRunStatus.RUNNING.value,
        started_at=started_at,
        health_status=MonitoringHealthStatus.UNKNOWN.value,
    )
    db.add(run)
    db.flush()

    try:
        health_status, health_message = connector.healthcheck()
        rule.health_status = health_status
        rule.health_message = health_message
        run.health_status = health_status

        if health_status == MonitoringHealthStatus.UNHEALTHY.value:
            raise RuntimeError(health_message)

        items = connector.fetch_items()
        run.items_found = len(items)
        items_new = 0
        opportunities_created = 0
        now = datetime.now(timezone.utc)

        for item in items:
            content_hash = _content_hash(item)
            existing = db.scalar(
                select(MonitoredPublication).where(
                    MonitoredPublication.monitoring_rule_id == rule.id,
                    MonitoredPublication.source_item_id == item.source_item_id,
                )
            )
            if existing:
                existing.last_seen_at = now
                existing.content_hash = content_hash
                continue

            duplicate_hash = db.scalar(
                select(MonitoredPublication).where(
                    MonitoredPublication.monitoring_rule_id == rule.id,
                    MonitoredPublication.content_hash == content_hash,
                )
            )
            if duplicate_hash:
                continue

            items_new += 1
            snapshot_key = _store_snapshot(storage, rule_id=rule.id, item=item)
            matches = _matches_filters(item, rule.filters)
            publication = MonitoredPublication(
                monitoring_rule_id=rule.id,
                source_item_id=item.source_item_id,
                canonical_url=item.url,
                title=item.title,
                publication_date=item.publication_date,
                first_seen_at=now,
                last_seen_at=now,
                content_hash=content_hash,
                raw_snapshot_key=snapshot_key,
                status=MonitoredPublicationStatus.FILTERED_OUT.value
                if not matches
                else MonitoredPublicationStatus.SEEN.value,
                extracted_fields={
                    "product": item.product,
                    "quantity": item.quantity,
                    "quantity_unit": item.quantity_unit,
                    "destination": item.destination,
                    "buyer": item.buyer,
                    "deadline": item.deadline.isoformat() if item.deadline else None,
                },
            )
            db.add(publication)
            db.flush()

            if matches:
                opportunity = _create_opportunity_from_item(db, user=user, item=item, rule=rule)
                publication.status = MonitoredPublicationStatus.OPPORTUNITY_CREATED.value
                publication.opportunity_id = opportunity.id
                opportunities_created += 1

        run.items_new = items_new
        run.opportunities_created = opportunities_created
        run.status = MonitoringRunStatus.SUCCESS.value
        run.finished_at = datetime.now(timezone.utc)
        rule.last_run_at = run.finished_at
        log_audit(
            db,
            actor=user,
            action=AuditAction.UPDATE,
            entity_type="MonitoringRun",
            entity_id=run.id,
            new_value={
                "items_found": run.items_found,
                "items_new": run.items_new,
                "opportunities_created": run.opportunities_created,
            },
        )
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:
        run.status = MonitoringRunStatus.FAILED.value
        run.error_message = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        rule.health_status = MonitoringHealthStatus.UNHEALTHY.value
        rule.health_message = str(exc)
        db.commit()
        db.refresh(run)
        return run


def seed_demo_monitoring_rule(db: Session, user: User) -> MonitoringRule | None:
    existing = db.scalar(
        select(MonitoringRule).where(
            MonitoringRule.owner_id == user.id,
            MonitoringRule.name == "Demo SN500 tenders",
        )
    )
    if existing:
        return existing
    return create_monitoring_rule(
        db,
        user=user,
        name="Demo SN500 tenders",
        connector_type="MOCK",
        source_url="demo-feed.json",
        poll_interval_hours=24,
        filters={"product_keywords": ["SN500", "Base Oil"]},
    )
