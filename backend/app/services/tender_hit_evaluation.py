from dataclasses import dataclass
from datetime import datetime, timezone

from app.ai.schemas import TenderSearchHitOutput
from app.services.product_keyword_localization import hit_matches_assignment


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            from datetime import date

            parsed = datetime.combine(date.fromisoformat(value[:10]), datetime.min.time())
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


@dataclass(frozen=True)
class TenderHitEvaluation:
    product_match: bool
    product_match_reason: str
    submission_deadline: datetime | None
    delivery_deadline: datetime | None
    submission_expired: bool
    display_status: str
    display_status_label: str
    volume: str | None


def evaluate_tender_hit(
    hit: TenderSearchHitOutput,
    *,
    user_keywords: list[str],
    reference_date: datetime,
) -> TenderHitEvaluation:
    haystack = " ".join(
        filter(
            None,
            [hit.title, hit.product, hit.body, hit.buyer, hit.destination],
        )
    )
    product_match, product_match_reason = hit_matches_assignment(haystack, user_keywords)

    submission_deadline = _parse_datetime(hit.submission_deadline or hit.deadline)
    delivery_deadline = _parse_datetime(hit.delivery_deadline)
    reference = reference_date if reference_date.tzinfo else reference_date.replace(tzinfo=timezone.utc)
    submission_expired = bool(submission_deadline and submission_deadline < reference)

    if not product_match:
        display_status = "MISMATCH"
        display_status_label = "Не соответствует заданию"
    elif submission_expired:
        display_status = "EXPIRED"
        display_status_label = "Срок подачи истёк"
    else:
        display_status = "ACTIVE"
        display_status_label = "Актуальный"

    return TenderHitEvaluation(
        product_match=product_match,
        product_match_reason=product_match_reason,
        submission_deadline=submission_deadline,
        delivery_deadline=delivery_deadline,
        submission_expired=submission_expired,
        display_status=display_status,
        display_status_label=display_status_label,
        volume=_format_volume(hit.quantity, hit.quantity_unit),
    )
