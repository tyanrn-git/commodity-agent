from dataclasses import dataclass
from datetime import datetime, timezone

from app.ai.schemas import TenderSearchHitOutput
from app.services.internet_source_catalog import expand_region_filters
from app.services.product_keyword_localization import hit_matches_assignment


def _region_match_in_text(text: str, region_filters: list[str] | None) -> tuple[bool, str]:
    if not region_filters:
        return True, ""
    haystack = text.lower()
    for token in sorted(expand_region_filters(region_filters), key=len, reverse=True):
        if len(token) >= 2 and token in haystack:
            return True, f"Регион в тексте: {token}"
    return False, "Регион вне фильтра"


def _append_region_hint(label: str, region_match: bool, region_reason: str) -> str:
    if region_match or not region_reason:
        return label
    return f"{label} · {region_reason}"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            parsed = datetime.strptime(cleaned[:10], fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        try:
            from datetime import date

            parsed = datetime.combine(date.fromisoformat(cleaned[:10]), datetime.min.time())
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _format_volume(quantity, quantity_unit: str | None) -> str | None:
    if quantity is None:
        return None
    text = str(quantity)
    if quantity_unit:
        return f"{text} {quantity_unit}".strip()
    return text


def _format_estimated_value(value, currency: str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if currency:
        return f"{text} {currency}".strip()
    return text


@dataclass(frozen=True)
class TenderHitEvaluation:
    product_match: bool
    product_match_reason: str
    submission_deadline: datetime | None
    delivery_deadline: datetime | None
    submission_expired: bool
    deadline_known: bool
    region_match: bool
    region_match_reason: str
    display_status: str
    display_status_label: str
    volume: str | None
    estimated_value: str | None


def evaluate_tender_hit(
    hit: TenderSearchHitOutput,
    *,
    user_keywords: list[str],
    reference_date: datetime,
    region_filters: list[str] | None = None,
) -> TenderHitEvaluation:
    haystack = " ".join(
        filter(
            None,
            [hit.title, hit.product, hit.body, hit.buyer, hit.destination],
        )
    )
    product_match, product_match_reason = hit_matches_assignment(haystack, user_keywords)
    region_match, region_match_reason = _region_match_in_text(haystack, region_filters)

    submission_deadline = _parse_datetime(hit.submission_deadline or hit.deadline)
    delivery_deadline = _parse_datetime(hit.delivery_deadline)
    reference = reference_date if reference_date.tzinfo else reference_date.replace(tzinfo=timezone.utc)
    deadline_known = submission_deadline is not None
    submission_expired = bool(submission_deadline and submission_deadline < reference)

    if not product_match:
        display_status = "MISMATCH"
        display_status_label = "Не соответствует заданию"
    elif submission_expired:
        display_status = "EXPIRED"
        display_status_label = "Срок подачи истёк"
    elif not deadline_known:
        display_status = "ACTIVE"
        display_status_label = _append_region_hint("Актуальный · срок не указан", region_match, region_match_reason)
    else:
        display_status = "ACTIVE"
        display_status_label = _append_region_hint("Актуальный", region_match, region_match_reason)

    return TenderHitEvaluation(
        product_match=product_match,
        product_match_reason=product_match_reason,
        submission_deadline=submission_deadline,
        delivery_deadline=delivery_deadline,
        submission_expired=submission_expired,
        deadline_known=deadline_known,
        region_match=region_match,
        region_match_reason=region_match_reason,
        display_status=display_status,
        display_status_label=display_status_label,
        volume=_format_volume(hit.quantity, hit.quantity_unit),
        estimated_value=_format_estimated_value(hit.estimated_value, hit.estimated_value_currency),
    )
