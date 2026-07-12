from decimal import Decimal

# MVP reference rates vs USD (manual/ECB-style placeholder)
REFERENCE_RATES_USD: dict[str, Decimal] = {
    "USD": Decimal("1"),
    "EUR": Decimal("0.92"),
    "GBP": Decimal("0.79"),
    "AED": Decimal("3.6725"),
    "SGD": Decimal("1.35"),
}


def convert_amount(
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    overrides: dict[str, str] | None = None,
) -> tuple[Decimal, dict[str, str]]:
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    rates = {k: str(v) for k, v in REFERENCE_RATES_USD.items()}
    if overrides:
        rates.update({k.upper(): v for k, v in overrides.items()})

    if from_currency == to_currency:
        return amount, rates

    from_rate = Decimal(rates.get(from_currency, "1"))
    to_rate = Decimal(rates.get(to_currency, "1"))
    usd_amount = amount / from_rate
    converted = usd_amount * to_rate
    return converted.quantize(Decimal("0.000001")), rates
