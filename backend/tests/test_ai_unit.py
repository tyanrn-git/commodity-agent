from decimal import Decimal

from app.ai.mock_provider import MockAIProvider
from app.ai.pricing import estimate_cost_usd
from app.ai.schemas import OpportunityExtractionOutput


def test_mock_provider_extraction():
    provider = MockAIProvider()
    parsed, usage = provider.structured_completion(
        model="mock-model",
        system_prompt="extract",
        user_prompt="SN500 100 MT Rotterdam",
        output_schema=OpportunityExtractionOutput,
    )
    assert parsed.raw_product_name == "Base Oil SN500"
    assert usage.cost_usd > 0


def test_estimate_cost():
    cost = estimate_cost_usd("gpt-4o-mini", 1000, 500)
    assert cost > Decimal("0")
