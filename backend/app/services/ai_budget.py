from calendar import monthrange
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.enums import AuditAction
from app.domain.models import AIBudgetSettings, AIUsageLog, User
from app.services.audit import log_audit


class BudgetCheckResult:
    def __init__(
        self,
        *,
        allowed: bool,
        spent_usd: Decimal,
        budget_usd: Decimal,
        remaining_usd: Decimal,
        warning_level: str | None = None,
        reason: str | None = None,
    ) -> None:
        self.allowed = allowed
        self.spent_usd = spent_usd
        self.budget_usd = budget_usd
        self.remaining_usd = remaining_usd
        self.warning_level = warning_level
        self.reason = reason


def _month_window(now: datetime, reset_day: int) -> tuple[datetime, datetime]:
    year, month = now.year, now.month
    start = datetime(year, month, min(reset_day, monthrange(year, month)[1]), tzinfo=timezone.utc)
    if now < start:
        month -= 1
        if month == 0:
            month = 12
            year -= 1
        start = datetime(year, month, min(reset_day, monthrange(year, month)[1]), tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, min(reset_day, monthrange(year + 1, 1)[1]), tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, min(reset_day, monthrange(year, month + 1)[1]), tzinfo=timezone.utc)
    return start, end


def ensure_ai_budget_settings(db: Session, user: User) -> AIBudgetSettings:
    existing = db.scalar(select(AIBudgetSettings).where(AIBudgetSettings.user_id == user.id))
    if existing:
        return existing
    row = AIBudgetSettings(
        user_id=user.id,
        monthly_budget_usd=Decimal("100"),
        first_warning_percent=75,
        second_warning_percent=90,
        hard_limit_enabled=True,
        allow_manual_override=True,
        budget_reset_day=1,
        preferred_default_model=settings.openai_default_model,
        fallback_model=settings.openai_fallback_model,
        ai_enabled=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_monthly_spend(db: Session, user_id, reset_day: int) -> Decimal:
    now = datetime.now(timezone.utc)
    start, end = _month_window(now, reset_day)
    spent = db.scalar(
        select(func.coalesce(func.sum(AIUsageLog.cost_usd), 0)).where(
            AIUsageLog.user_id == user_id,
            AIUsageLog.created_at >= start,
            AIUsageLog.created_at < end,
        )
    )
    return Decimal(str(spent or 0))


def check_budget(
    db: Session,
    *,
    user: User,
    estimated_cost: Decimal = Decimal("0"),
    allow_override: bool = False,
) -> BudgetCheckResult:
    cfg = ensure_ai_budget_settings(db, user)
    if not cfg.ai_enabled:
        return BudgetCheckResult(
            allowed=False,
            spent_usd=Decimal("0"),
            budget_usd=Decimal(str(cfg.monthly_budget_usd)),
            remaining_usd=Decimal(str(cfg.monthly_budget_usd)),
            reason="AI is disabled",
        )

    spent = get_monthly_spend(db, user.id, cfg.budget_reset_day)
    budget = Decimal(str(cfg.monthly_budget_usd))
    remaining = budget - spent
    percent_used = (spent / budget * Decimal("100")) if budget > 0 else Decimal("100")

    warning = None
    if percent_used >= cfg.second_warning_percent:
        warning = "second"
    elif percent_used >= cfg.first_warning_percent:
        warning = "first"

    projected = spent + estimated_cost
    if cfg.hard_limit_enabled and projected > budget:
        if allow_override and cfg.allow_manual_override:
            return BudgetCheckResult(
                allowed=True,
                spent_usd=spent,
                budget_usd=budget,
                remaining_usd=remaining,
                warning_level=warning,
                reason="override",
            )
        return BudgetCheckResult(
            allowed=False,
            spent_usd=spent,
            budget_usd=budget,
            remaining_usd=remaining,
            warning_level=warning,
            reason="Monthly AI budget hard limit reached",
        )

    return BudgetCheckResult(
        allowed=True,
        spent_usd=spent,
        budget_usd=budget,
        remaining_usd=remaining,
        warning_level=warning,
    )


def log_ai_usage(
    db: Session,
    *,
    user: User,
    model: str,
    operation: str,
    cost_usd: Decimal,
    input_tokens: int,
    output_tokens: int,
    opportunity_id=None,
    deal_id=None,
    source_id=None,
    research_campaign_id=None,
) -> AIUsageLog:
    entry = AIUsageLog(
        user_id=user.id,
        model=model,
        operation=operation,
        opportunity_id=opportunity_id,
        deal_id=deal_id,
        source_id=source_id,
        research_campaign_id=research_campaign_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )
    db.add(entry)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.AI_CALL,
        entity_type="AIUsageLog",
        entity_id=entry.id,
        new_value={
            "model": model,
            "operation": operation,
            "cost_usd": str(cost_usd),
            "source_id": str(source_id) if source_id else None,
        },
    )
    return entry


def update_ai_budget_settings(
    db: Session,
    *,
    user: User,
    data: dict,
) -> AIBudgetSettings:
    cfg = ensure_ai_budget_settings(db, user)
    old_value = {
        "monthly_budget_usd": str(cfg.monthly_budget_usd),
        "ai_enabled": cfg.ai_enabled,
        "hard_limit_enabled": cfg.hard_limit_enabled,
        "preferred_default_model": cfg.preferred_default_model,
    }
    serializable_data = {
        key: str(value) if isinstance(value, Decimal) else value for key, value in data.items()
    }
    for field, value in data.items():
        if value is not None and hasattr(cfg, field):
            setattr(cfg, field, value)
    cfg.effective_from = datetime.now(timezone.utc)
    db.flush()
    log_audit(
        db,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="AIBudgetSettings",
        entity_id=cfg.id,
        old_value=old_value,
        new_value=serializable_data,
    )
    db.commit()
    db.refresh(cfg)
    return cfg


def get_usage_summary(db: Session, user: User) -> dict:
    cfg = ensure_ai_budget_settings(db, user)
    spent = get_monthly_spend(db, user.id, cfg.budget_reset_day)
    budget = Decimal(str(cfg.monthly_budget_usd))
    remaining = budget - spent

    now = datetime.now(timezone.utc)
    start, end = _month_window(now, cfg.budget_reset_day)
    days_elapsed = max((now - start).days, 1)
    days_total = max((end - start).days, 1)
    daily_avg = spent / Decimal(days_elapsed)
    forecast = daily_avg * Decimal(days_total)

    by_model = db.execute(
        select(AIUsageLog.model, func.sum(AIUsageLog.cost_usd), func.count())
        .where(
            AIUsageLog.user_id == user.id,
            AIUsageLog.created_at >= start,
            AIUsageLog.created_at < end,
        )
        .group_by(AIUsageLog.model)
    ).all()
    by_operation = db.execute(
        select(AIUsageLog.operation, func.sum(AIUsageLog.cost_usd), func.count())
        .where(
            AIUsageLog.user_id == user.id,
            AIUsageLog.created_at >= start,
            AIUsageLog.created_at < end,
        )
        .group_by(AIUsageLog.operation)
    ).all()

    percent_used = float(spent / budget * 100) if budget > 0 else 100.0
    warning_level = None
    if percent_used >= cfg.second_warning_percent:
        warning_level = "second"
    elif percent_used >= cfg.first_warning_percent:
        warning_level = "first"

    return {
        "monthly_budget_usd": str(budget),
        "spent_usd": str(spent),
        "remaining_usd": str(remaining),
        "percent_used": round(percent_used, 2),
        "forecast_usd": str(forecast.quantize(Decimal("0.01"))),
        "warning_level": warning_level,
        "ai_enabled": cfg.ai_enabled,
        "by_model": [
            {"model": row[0], "cost_usd": str(row[1]), "count": row[2]} for row in by_model
        ],
        "by_operation": [
            {"operation": row[0], "cost_usd": str(row[1]), "count": row[2]} for row in by_operation
        ],
    }


def enforce_budget_or_raise(db: Session, user: User, *, allow_override: bool = False) -> BudgetCheckResult:
    result = check_budget(db, user=user, allow_override=allow_override)
    if not result.allowed:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=result.reason)
    return result
