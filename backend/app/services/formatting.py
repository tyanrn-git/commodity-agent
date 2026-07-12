from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


def _to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def format_amount(value) -> str:
    amount = _to_decimal(value)
    if amount is None:
        return "—"
    rounded = amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    sign = "-" if rounded < 0 else ""
    digits = str(abs(int(rounded)))
    groups = []
    while digits:
        groups.append(digits[-3:])
        digits = digits[:-3]
    return sign + " ".join(reversed(groups))


def format_percent(value) -> str:
    amount = _to_decimal(value)
    if amount is None:
        return "—"
    rounded = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(rounded).replace(".", ",")


def format_quantity(value, unit: str | None = None) -> str:
    amount = _to_decimal(value)
    if amount is None:
        return unit or "—"
    text = format_amount(amount)
    return f"{text} {unit}" if unit else text
