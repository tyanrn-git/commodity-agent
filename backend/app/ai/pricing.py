from decimal import Decimal

# USD per 1M tokens (approximate, configurable without migration)
MODEL_PRICING: dict[str, dict[str, Decimal]] = {
    "gpt-4o-mini": {"input": Decimal("0.15"), "output": Decimal("0.60")},
    "gpt-4o": {"input": Decimal("2.50"), "output": Decimal("10.00")},
    "mock-model": {"input": Decimal("0.01"), "output": Decimal("0.01")},
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4o-mini"])
    input_cost = Decimal(input_tokens) / Decimal(1_000_000) * pricing["input"]
    output_cost = Decimal(output_tokens) / Decimal(1_000_000) * pricing["output"]
    return (input_cost + output_cost).quantize(Decimal("0.000001"))
